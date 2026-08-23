#!/usr/bin/env python3
"""Opt-in validation against checksum-pinned public operando data.

The script never writes downloaded or derived data into the source repository.
It verifies the public archives, extracts only named members to a temporary
directory, converts their documented local clocks to an elapsed coordinate, and
then exercises the public API, CLI, GUI controller, QC, and export call paths.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.request
import zipfile
from collections.abc import Iterable
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from matplotlib import pyplot as plt

from operandomerge.config import load_config, save_config
from operandomerge.controller import GuiController
from operandomerge.export import export_excel, plot_alignment
from operandomerge.models import (
    AlignmentConfig,
    AlignmentMethod,
    ChannelConfig,
    DatasetConfig,
    DataType,
    MergeConfig,
    TimeRepresentation,
)
from operandomerge.service import MergeService

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = Path(__file__).with_name("public-data-manifest.json")
GC_TIMESTAMP_FORMATS = ("%d/%m/%Y %H:%M", "%d/%b/%Y %H:%M")
MS_TIMESTAMP_FORMAT = "%Y-%m-%d %H:%M:%S"
GC_INJECTION_PATTERN = re.compile(r"^(\d+)\t(\d{2}/(?:\d{2}|[A-Za-z]{3})/\d{4} \d{2}:\d{2})\t")
GC_TIMESTAMP_PATTERN = re.compile(r"^(\d{2})/(\d{2}|[A-Za-z]{3})/(\d{4}) (\d{2}):(\d{2})$")
GC_ENGLISH_MONTHS = {
    month: index
    for index, month in enumerate(
        ("JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"),
        start=1,
    )
}
COMPONENT_SLUGS = {
    "MeOH": "methanol",
    "Carbon Dioxide": "carbon_dioxide",
    "N2": "n2",
    "H2": "h2",
    "CO": "co",
    "nC5/DME": "nc5_dme",
    "Methane": "methane",
}


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _verify_file(path: Path, specification: dict[str, Any]) -> dict[str, Any]:
    _require(path.is_file(), f"Required public archive is missing: {path}")
    size = path.stat().st_size
    digest = _sha256(path)
    _require(
        size == int(specification["size_bytes"]),
        f"Size mismatch for {path.name}: expected {specification['size_bytes']}, got {size}",
    )
    _require(
        digest == specification["sha256"],
        f"SHA-256 mismatch for {path.name}: expected {specification['sha256']}, got {digest}",
    )
    return {"name": path.name, "size_bytes": size, "sha256": digest}


def _download(specification: dict[str, Any], destination: Path) -> Path:
    request = urllib.request.Request(
        specification["download_url"],
        headers={
            "User-Agent": (
                "OperandoMerge-public-validation/0.1 (+https://github.com/hdkim99/OperandoMerge)"
            )
        },
    )
    with (
        urllib.request.urlopen(request, timeout=120) as response,
        destination.open("wb") as output,
    ):
        shutil.copyfileobj(response, output)
    return destination


def _extract_member(archive: Path, member: str, destination: Path, size_bytes: int) -> Path:
    with zipfile.ZipFile(archive) as bundle:
        try:
            information = bundle.getinfo(member)
        except KeyError as error:
            raise ValueError(f"Archive {archive.name} does not contain {member!r}") from error
        _require(
            information.file_size == size_bytes,
            f"Member size mismatch for {member}: expected {size_bytes}, "
            f"got {information.file_size}",
        )
        destination.parent.mkdir(parents=True, exist_ok=True)
        with bundle.open(information) as source, destination.open("wb") as output:
            shutil.copyfileobj(source, output)
    return destination


def _numeric_or_nan(value: str) -> float:
    text = value.strip()
    return float("nan") if text in {"", "n.a.", "n.a"} else float(text)


def _parse_gc_timestamp(value: str) -> datetime:
    matched = GC_TIMESTAMP_PATTERN.fullmatch(value)
    try:
        if matched is None:
            raise ValueError
        day, month_token, year, hour, minute = matched.groups()
        month = (
            int(month_token) if month_token.isdigit() else GC_ENGLISH_MONTHS[month_token.upper()]
        )
        return datetime(int(year), month, int(day), int(hour), int(minute))
    except (KeyError, ValueError) as error:
        raise ValueError(
            f"GC timestamp {value!r} does not match an explicit published format: "
            f"{', '.join(GC_TIMESTAMP_FORMATS)}"
        ) from error


def _cadence(values: Iterable[float], *, positive_only: bool = False) -> list[float]:
    array = np.asarray(list(values), dtype=float)
    differences = np.diff(array)
    if positive_only:
        differences = differences[differences > 1e-6]
    _require(len(differences) > 0, "At least two distinct time values are required")
    return [
        float(np.min(differences)),
        float(np.median(differences)),
        float(np.max(differences)),
    ]


def _require_close(actual: Iterable[float], expected: Iterable[float], label: str) -> None:
    np.testing.assert_allclose(
        np.asarray(list(actual), dtype=float),
        np.asarray(list(expected), dtype=float),
        rtol=0,
        atol=5e-6,
        err_msg=label,
    )


def _component_name(line: str) -> str | None:
    cells = [cell.strip() for cell in line.split("\t") if cell.strip()]
    if len(cells) < 2 or cells[0] != "By Component":
        return None
    return cells[1]


def _preprocess_gc(
    source: Path,
    output: Path,
    *,
    archive_name: str,
    member_name: str,
    run_specification: dict[str, Any],
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Convert repeated Chromeleon component tables using an explicit DD/MM format."""

    origin = datetime.strptime(run_specification["rx_origin_local"], MS_TIMESTAMP_FORMAT)
    records: dict[int, dict[str, Any]] = {}
    active_component: str | None = None
    text = source.read_text(encoding="utf-8-sig", errors="strict")
    for source_line, line in enumerate(text.splitlines(), start=1):
        component = _component_name(line)
        if component is not None:
            _require(component in COMPONENT_SLUGS, f"Unknown GC component {component!r}")
            active_component = component
            continue
        match = GC_INJECTION_PATTERN.match(line)
        if match is None:
            continue
        _require(
            active_component is not None,
            f"Injection before component header at line {source_line}",
        )
        cells = line.split("\t")
        _require(len(cells) >= 6, f"Incomplete GC injection row at source line {source_line}")
        injection_id = int(match.group(1))
        local_time = _parse_gc_timestamp(match.group(2))
        record = records.setdefault(
            injection_id,
            {
                "injection_id": injection_id,
                "source_local_timestamp": local_time.isoformat(sep=" "),
                "source_archive": archive_name,
                "source_member": member_name,
                "source_line": source_line,
            },
        )
        _require(
            record["source_local_timestamp"] == local_time.isoformat(sep=" "),
            f"Injection {injection_id} has inconsistent timestamps across component tables",
        )
        slug = COMPONENT_SLUGS[active_component]
        amount_key = f"{slug}_amount"
        _require(
            amount_key not in record,
            f"Duplicate {active_component} row for injection {injection_id}",
        )
        record[amount_key] = _numeric_or_nan(cells[5])
        record[f"{slug}_source_line"] = source_line

    expected_count = int(run_specification["gc_injections"])
    _require(
        len(records) == expected_count,
        f"Expected {expected_count} GC injections, got {len(records)}",
    )
    _require(
        sorted(records) == list(range(1, expected_count + 1)),
        "GC injection IDs are not contiguous",
    )
    rows = [records[index] for index in sorted(records)]
    expected_columns = [f"{slug}_amount" for slug in COMPONENT_SLUGS.values()]
    for record in rows:
        _require(
            all(column in record for column in expected_columns),
            f"Injection {record['injection_id']} is missing a component table",
        )
        local_time = datetime.strptime(record["source_local_timestamp"], MS_TIMESTAMP_FORMAT)
        record["elapsed_seconds"] = (local_time - origin).total_seconds()
    ordered = [
        "elapsed_seconds",
        "injection_id",
        "source_local_timestamp",
        "source_archive",
        "source_member",
        "source_line",
    ]
    for slug in COMPONENT_SLUGS.values():
        ordered.extend([f"{slug}_amount", f"{slug}_source_line"])
    frame = pd.DataFrame(rows)[ordered]
    frame.to_csv(output, index=False, lineterminator="\n", float_format="%.10g")

    local_times = [
        datetime.strptime(value, MS_TIMESTAMP_FORMAT) for value in frame["source_local_timestamp"]
    ]
    cadence = _cadence((value - local_times[0]).total_seconds() for value in local_times)
    _require(
        frame["source_local_timestamp"].iloc[0] == run_specification["gc_start_local"],
        "GC start mismatch",
    )
    _require(
        frame["source_local_timestamp"].iloc[-1] == run_specification["gc_end_local"],
        "GC end mismatch",
    )
    _require_close(cadence, run_specification["gc_cadence_s_min_median_max"], "GC cadence")
    return frame, {
        "rows": len(frame),
        "start_local": frame["source_local_timestamp"].iloc[0],
        "end_local": frame["source_local_timestamp"].iloc[-1],
        "cadence_s_min_median_max": cadence,
        "explicit_source_formats": list(GC_TIMESTAMP_FORMATS),
    }


def _clean_ms_row(row: dict[str | None, str | None]) -> dict[str, str]:
    return {
        str(key).strip(): "" if value is None else value.strip()
        for key, value in row.items()
        if key is not None
    }


def _preprocess_ms(
    source: Path,
    output: Path,
    *,
    archive_name: str,
    member_name: str,
    run_specification: dict[str, Any],
) -> tuple[pd.DataFrame, list[str], dict[str, Any]]:
    """Use the published elapsed hours, cross-checked against its naive local wall clock."""

    origin = datetime.strptime(run_specification["rx_origin_local"], MS_TIMESTAMP_FORMAT)
    output_rows: list[dict[str, Any]] = []
    ion_columns: list[str] = []
    with source.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        for source_line, raw_row in enumerate(reader, start=2):
            row = _clean_ms_row(raw_row)
            if not ion_columns:
                ion_columns = [
                    key.replace(" ", "_")
                    for key in row
                    if re.fullmatch(r"ion \d+ norm current", key)
                ]
                _require(len(ion_columns) >= 5, "Expected at least five normalized MS ion channels")
            source_time = datetime.strptime(row["timestamp"], MS_TIMESTAMP_FORMAT)
            elapsed_from_clock = (source_time - origin).total_seconds()
            elapsed_hours = float(row["hours since RX start"])
            elapsed_from_column = elapsed_hours * 3600.0
            _require(
                abs(elapsed_from_clock - elapsed_from_column) <= 5e-6,
                f"MS elapsed/wall-clock mismatch at source line {source_line}",
            )
            output_row: dict[str, Any] = {
                "elapsed_seconds": elapsed_from_clock,
                "elapsed_hours_from_rx": elapsed_hours,
                "source_local_timestamp": source_time.isoformat(sep=" "),
                "source_archive": archive_name,
                "source_member": member_name,
                "source_line": source_line,
                "source_index": int(row.get("[index]", row.get("", ""))),
            }
            for raw_name in [key for key in row if re.fullmatch(r"ion \d+ norm current", key)]:
                output_row[raw_name.replace(" ", "_")] = _numeric_or_nan(row[raw_name])
            output_rows.append(output_row)

    frame = pd.DataFrame(output_rows)
    frame.to_csv(output, index=False, lineterminator="\n", float_format="%.10g")
    expected_rows = int(run_specification["ms_rows"])
    _require(len(frame) == expected_rows, f"Expected {expected_rows} MS rows, got {len(frame)}")
    _require(
        frame["source_local_timestamp"].iloc[0] == run_specification["ms_start_local"],
        "MS start mismatch",
    )
    _require(
        frame["source_local_timestamp"].iloc[-1] == run_specification["ms_end_local"],
        "MS end mismatch",
    )
    cadence = _cadence(frame["elapsed_seconds"])
    _require_close(cadence, run_specification["ms_cadence_s_min_median_max"], "MS cadence")
    elapsed_bounds = [
        float(frame["elapsed_hours_from_rx"].iloc[0]),
        float(frame["elapsed_hours_from_rx"].iloc[-1]),
    ]
    _require_close(
        elapsed_bounds,
        run_specification["ms_elapsed_hours_start_end"],
        "MS elapsed bounds",
    )
    return (
        frame,
        ion_columns,
        {
            "rows": len(frame),
            "start_local": frame["source_local_timestamp"].iloc[0],
            "end_local": frame["source_local_timestamp"].iloc[-1],
            "elapsed_hours_start_end": elapsed_bounds,
            "cadence_s_min_median_max": cadence,
            "derived_rx_origin_local": origin.isoformat(sep=" "),
            "source_timezone": "unspecified; not interpreted as UTC",
        },
    )


def _append_source_sheets(path: Path, gc_frame: pd.DataFrame, ms_frame: pd.DataFrame) -> None:
    with pd.ExcelWriter(path, engine="openpyxl", mode="a", if_sheet_exists="replace") as writer:
        gc_frame.to_excel(writer, sheet_name="source_gc", index=False)
        ms_frame.to_excel(writer, sheet_name="source_ms", index=False)


def _lineage_for_gc(result: Any, gc_frame: pd.DataFrame) -> pd.DataFrame:
    provenance = result.provenance.loc[
        result.provenance["output_column"] == "gc__injection_id"
    ].copy()
    source = gc_frame.reset_index(names="processed_source_row")
    lineage = provenance.merge(
        source,
        left_on="source_row",
        right_on="processed_source_row",
        how="left",
        validate="one_to_one",
    )
    _require(lineage["source_archive"].notna().all(), "GC source archive lineage was lost")
    _require(lineage["source_member"].notna().all(), "GC source member lineage was lost")
    _require(lineage["source_line"].notna().all(), "GC source line lineage was lost")
    return lineage


def _exercise_run(
    run_name: str,
    run_output: Path,
    gc_frame: pd.DataFrame,
    ms_frame: pd.DataFrame,
    ion_columns: list[str],
    expected_injections: int,
) -> dict[str, Any]:
    gc_path = run_output / "processed_gc.csv"
    ms_path = run_output / "processed_ms.csv"
    gc_channels = [ChannelConfig("injection_id", DataType.DISCRETE_SAMPLE, "gc__injection_id")] + [
        ChannelConfig(column, DataType.DISCRETE_SAMPLE, f"gc__{column}")
        for column in gc_frame.columns
        if column.endswith("_amount")
    ]
    ms_channels = [
        ChannelConfig(column, DataType.CONTINUOUS, f"ms__{column}") for column in ion_columns
    ]
    datasets = [
        DatasetConfig(
            path=ms_path,
            name="ms",
            time_column="elapsed_seconds",
            time_representation=TimeRepresentation.ELAPSED_SECONDS,
            channels=tuple(ms_channels),
            alignment=AlignmentConfig(method=AlignmentMethod.ELAPSED),
        ),
        DatasetConfig(
            path=gc_path,
            name="gc",
            time_column="elapsed_seconds",
            time_representation=TimeRepresentation.ELAPSED_SECONDS,
            channels=tuple(gc_channels),
            alignment=AlignmentConfig(method=AlignmentMethod.ELAPSED),
        ),
    ]
    merge = MergeConfig(timeline="union", continuous_method="linear", exact_tolerance_s=1e-6)
    config_path = run_output / "config.json"
    save_config(datasets, merge, config_path)
    loaded_datasets, loaded_merge = load_config(config_path)

    api_result = MergeService().run(loaded_datasets, loaded_merge)
    gc_output = api_result.merged["gc__injection_id"]
    populated = api_result.merged.loc[gc_output.notna(), "experiment_time_s"].to_numpy(float)
    expected_times = gc_frame["elapsed_seconds"].to_numpy(float)
    _require(len(populated) == expected_injections, "GC injection count changed during merge")
    np.testing.assert_allclose(populated, expected_times, rtol=0, atol=1e-9)
    non_injection = ~api_result.merged["experiment_time_s"].isin(expected_times)
    _require(gc_output[non_injection].isna().all(), "GC was populated between injections")
    provenance = api_result.provenance.loc[
        api_result.provenance["output_column"] == "gc__injection_id"
    ]
    _require(len(provenance) == expected_injections, "GC provenance count mismatch")
    _require(
        provenance["interpolation_method"].eq("original").all(),
        "GC provenance contains an interpolated value",
    )
    _require(
        provenance["data_type"].eq("discrete_sample").all(),
        "GC provenance lost discrete-sample semantics",
    )
    lineage = _lineage_for_gc(api_result, gc_frame)
    lineage.to_csv(run_output / "gc_provenance_with_source.csv", index=False)

    api_excel = run_output / "api_report.xlsx"
    api_plot = run_output / "api_alignment.png"
    export_excel(api_result, api_excel)
    figure = plot_alignment(api_result, api_plot)
    plt.close(figure)
    _append_source_sheets(api_excel, gc_frame, ms_frame)
    api_sheets = pd.ExcelFile(api_excel).sheet_names
    _require(
        {"merged", "metadata", "provenance", "qc", "configuration", "source_gc", "source_ms"}
        <= set(api_sheets),
        "API Excel export is missing a required sheet",
    )

    cli_output = run_output / "cli_csv"
    cli_plot = run_output / "cli_alignment.png"
    command = [
        sys.executable,
        "-m",
        "operandomerge.cli",
        "merge",
        str(config_path),
        "--csv-dir",
        str(cli_output),
        "--plot",
        str(cli_plot),
    ]
    environment = os.environ.copy()
    source_path = str(REPOSITORY_ROOT / "src")
    environment["PYTHONPATH"] = os.pathsep.join(
        [source_path, environment.get("PYTHONPATH", "")]
    ).rstrip(os.pathsep)
    completed = subprocess.run(
        command,
        check=True,
        capture_output=True,
        text=True,
        cwd=REPOSITORY_ROOT,
        env=environment,
    )
    cli_merged = pd.read_csv(cli_output / "merged.csv")
    pd.testing.assert_frame_equal(
        cli_merged,
        api_result.merged,
        check_exact=False,
        rtol=1e-12,
        atol=1e-12,
    )
    gc_frame.to_csv(cli_output / "source_gc.csv", index=False)
    ms_frame.to_csv(cli_output / "source_ms.csv", index=False)

    controller = GuiController()
    controller.load(config_path)
    gui_result = controller.run_merge()
    pd.testing.assert_frame_equal(gui_result.merged, api_result.merged)
    gui_excel = run_output / "gui_controller_report.xlsx"
    controller.export(gui_excel)
    _append_source_sheets(gui_excel, gc_frame, ms_frame)
    gui_gc = pd.read_excel(gui_excel, sheet_name="source_gc")
    _require(len(gui_gc) == expected_injections, "GUI-controller export lost GC rows")
    _require(gui_gc["source_archive"].notna().all(), "GUI-controller export lost archive IDs")
    _require(gui_gc["source_member"].notna().all(), "GUI-controller export lost member IDs")
    _require(gui_gc["source_line"].notna().all(), "GUI-controller export lost source lines")

    qc_counts: dict[str, int] = {}
    for issue in api_result.qc:
        qc_counts[issue.code] = qc_counts.get(issue.code, 0) + 1
    return {
        "run": run_name,
        "timeline_rows": len(api_result.merged),
        "gc_discrete_populated_rows": len(populated),
        "gc_non_injection_rows_are_nan": True,
        "gc_provenance_rows": len(provenance),
        "gc_provenance_methods": sorted(provenance["interpolation_method"].unique()),
        "source_lineage_rows": len(lineage),
        "api_export_sheets": api_sheets,
        "cli_command": command,
        "cli_stdout": completed.stdout.strip(),
        "cli_export_roundtrip": True,
        "gui_controller_matches_api": True,
        "gui_controller_export_roundtrip": True,
        "qc_counts": qc_counts,
    }


def _validate_tpr_qc(
    source: Path,
    output: Path,
    *,
    archive_name: str,
    member_name: str,
    specification: dict[str, Any],
) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    table_rows = 0
    with source.open(encoding="utf-8-sig", newline="") as stream:
        for source_line, row in enumerate(csv.DictReader(stream), start=2):
            table_rows += 1
            elapsed = row["timedelta MS (min)"].strip()
            if not elapsed:
                continue
            rows.append(
                {
                    "elapsed_seconds": float(elapsed) * 60.0,
                    "scan": float(row["Scan"]),
                    "mass_2": float(row["Mass 2"]),
                    "source_archive": archive_name,
                    "source_member": member_name,
                    "source_line": source_line,
                }
            )
    frame = pd.DataFrame(rows)
    frame.to_csv(output / "processed_tpr_ms.csv", index=False, lineterminator="\n")
    times = frame["elapsed_seconds"].to_numpy(float)
    differences = np.diff(times)
    unique_times = len(np.unique(times))
    zero_transitions = int(np.count_nonzero(np.abs(differences) <= 1e-9))
    negative_transitions = int(np.count_nonzero(differences < -1e-9))
    positive_cadence = _cadence(times, positive_only=True)
    _require(table_rows == specification["table_rows"], "TPR table row count mismatch")
    _require(len(frame) == specification["ms_populated_rows"], "TPR populated MS count mismatch")
    _require(
        unique_times == specification["unique_ms_timestamps"],
        "TPR unique time count mismatch",
    )
    _require(
        zero_transitions == specification["zero_time_transitions"],
        "TPR zero-transition count mismatch",
    )
    _require(
        negative_transitions == specification["negative_time_transitions"],
        "TPR negative-transition count mismatch",
    )
    _require_close(
        positive_cadence,
        specification["positive_ms_cadence_s_min_median_max"],
        "TPR positive MS cadence",
    )

    config = DatasetConfig(
        path=output / "processed_tpr_ms.csv",
        name="tpr_ms",
        time_column="elapsed_seconds",
        time_representation=TimeRepresentation.ELAPSED_SECONDS,
        channels=(ChannelConfig("mass_2", DataType.CONTINUOUS, "tpr_ms__mass_2"),),
    )
    result = MergeService().run([config], MergeConfig(continuous_method="none"))
    duplicate_issues = [issue for issue in result.qc if issue.code == "duplicate_timestamp"]
    non_monotonic = [issue for issue in result.qc if issue.code == "non_monotonic_time"]
    _require(
        len(duplicate_issues) == specification["duplicate_qc_rows"],
        "Existing QC did not report every duplicate TPR MS source row",
    )
    _require(
        len(non_monotonic) == 0,
        "Equal adjacent timestamps are duplicates, not decreasing timestamps",
    )
    report_path = output / "tpr_qc_report.xlsx"
    export_excel(result, report_path)
    with pd.ExcelWriter(
        report_path, engine="openpyxl", mode="a", if_sheet_exists="replace"
    ) as writer:
        frame.to_excel(writer, sheet_name="source_tpr_ms", index=False)
    exported_qc = pd.read_excel(report_path, sheet_name="qc")
    _require(
        int(exported_qc["code"].eq("duplicate_timestamp").sum()) == len(duplicate_issues),
        "TPR duplicate QC was lost during Excel export",
    )
    return {
        "validation_level": "combined-table sparse/duplicate QC; not multi-file alignment evidence",
        "table_rows": table_rows,
        "ms_populated_rows": len(frame),
        "unique_ms_timestamps": unique_times,
        "zero_time_transitions": zero_transitions,
        "negative_time_transitions": negative_transitions,
        "positive_ms_cadence_s_min_median_max": positive_cadence,
        "duplicate_qc_rows": len(duplicate_issues),
        "non_monotonic_qc_issues": len(non_monotonic),
        "export_roundtrip": True,
    }


def _external_empty_directory(path: Path) -> Path:
    resolved = path.expanduser().resolve()
    _require(
        resolved != REPOSITORY_ROOT and REPOSITORY_ROOT not in resolved.parents,
        "Public-data validation output must be outside the OperandoMerge repository",
    )
    if resolved.exists():
        _require(resolved.is_dir(), f"Output path is not a directory: {resolved}")
        _require(not any(resolved.iterdir()), f"Output directory must be empty: {resolved}")
    else:
        resolved.mkdir(parents=True)
    return resolved


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument(
        "--source-dir",
        type=Path,
        help="Directory containing the two checksum-pinned Zenodo ZIP files",
    )
    source.add_argument(
        "--download",
        action="store_true",
        help="Explicitly download the two CC-BY-4.0 Zenodo ZIP files into temporary storage",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        required=True,
        help="New or empty directory outside the repository",
    )
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--runs", nargs="+", choices=["5Sn", "5Zr"], default=["5Sn", "5Zr"])
    return parser


def run(arguments: argparse.Namespace) -> dict[str, Any]:
    manifest = json.loads(arguments.manifest.read_text(encoding="utf-8"))
    _require(manifest["schema_version"] == 1, "Unsupported public-data manifest schema")
    output_root = _external_empty_directory(arguments.output_dir)
    source_spec = manifest["sources"]["OM-PUB-001"]
    figure_4_spec = source_spec["files"]["figure_4_gc_ms"]
    tpr_spec = source_spec["files"]["figure_5_tpr"]
    archive_reports: list[dict[str, Any]] = []
    run_reports: list[dict[str, Any]] = []

    with tempfile.TemporaryDirectory(prefix="operandomerge-public-validation-") as temporary:
        temporary_root = Path(temporary)
        if arguments.source_dir is not None:
            source_root = arguments.source_dir.expanduser().resolve()
            _require(source_root.is_dir(), f"Source directory does not exist: {source_root}")
        else:
            source_root = temporary_root / "downloads"
            source_root.mkdir()
            _download(figure_4_spec, source_root / figure_4_spec["name"])
            _download(tpr_spec, source_root / tpr_spec["name"])

        figure_4_archive = source_root / figure_4_spec["name"]
        tpr_archive = source_root / tpr_spec["name"]
        archive_reports.append(_verify_file(figure_4_archive, figure_4_spec))
        archive_reports.append(_verify_file(tpr_archive, tpr_spec))

        for run_name in arguments.runs:
            run_spec = figure_4_spec["runs"][run_name]
            run_output = output_root / run_name
            run_output.mkdir()
            gc_spec = figure_4_spec["members"][run_spec["gc_member"]]
            ms_spec = figure_4_spec["members"][run_spec["ms_member"]]
            extraction = temporary_root / "extracted" / run_name
            gc_source = _extract_member(
                figure_4_archive,
                gc_spec["path"],
                extraction / "gc.txt",
                gc_spec["size_bytes"],
            )
            ms_source = _extract_member(
                figure_4_archive,
                ms_spec["path"],
                extraction / "ms.csv",
                ms_spec["size_bytes"],
            )
            gc_frame, gc_stats = _preprocess_gc(
                gc_source,
                run_output / "processed_gc.csv",
                archive_name=figure_4_spec["name"],
                member_name=gc_spec["path"],
                run_specification=run_spec,
            )
            ms_frame, ion_columns, ms_stats = _preprocess_ms(
                ms_source,
                run_output / "processed_ms.csv",
                archive_name=figure_4_spec["name"],
                member_name=ms_spec["path"],
                run_specification=run_spec,
            )
            interfaces = _exercise_run(
                run_name,
                run_output,
                gc_frame,
                ms_frame,
                ion_columns,
                int(run_spec["gc_injections"]),
            )
            run_reports.append(
                {
                    "run": run_name,
                    "gc_observed": gc_stats,
                    "ms_observed": ms_stats,
                    "interfaces": interfaces,
                }
            )

        tpr_member = tpr_spec["representative_member"]
        tpr_source = _extract_member(
            tpr_archive,
            tpr_member["path"],
            temporary_root / "extracted" / "tpr.csv",
            tpr_member["size_bytes"],
        )
        tpr_output = output_root / "tpr_qc"
        tpr_output.mkdir()
        tpr_report = _validate_tpr_qc(
            tpr_source,
            tpr_output,
            archive_name=tpr_spec["name"],
            member_name=tpr_member["path"],
            specification=tpr_member,
        )

    report = {
        "manifest_schema_version": manifest["schema_version"],
        "source_id": "OM-PUB-001",
        "dataset_doi": source_spec["dataset_doi"],
        "dataset_license": source_spec["dataset_license"],
        "manifest_accessed_on": manifest["accessed_on"],
        "validated_on": datetime.now().astimezone().isoformat(),
        "archives": archive_reports,
        "runs": run_reports,
        "tpr_qc": tpr_report,
        "unsupported": [
            "vendor QMP ingestion",
            "ZIP ingestion by the OperandoMerge core",
            "scan-level XANES/XRD alignment without source timestamps",
            "automatic inference of a timezone for naive local wall clocks",
        ],
    }
    report_path = output_root / "validation-report.json"
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


def main(argv: list[str] | None = None) -> int:
    arguments = _parser().parse_args(argv)
    try:
        report = run(arguments)
    except (AssertionError, KeyError, OSError, subprocess.CalledProcessError, ValueError) as error:
        print(f"public-data validation failed: {error}", file=sys.stderr)
        return 2
    print(
        f"Validated {len(report['runs'])} GC/MS run(s) and the combined-table TPR QC case; "
        f"report: {arguments.output_dir.expanduser().resolve() / 'validation-report.json'}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
