"""Generate the license-free OperandoMerge showcase and its real result figures."""

from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.figure import Figure

from operandomerge.config import load_config
from operandomerge.export import export_excel, plot_alignment
from operandomerge.models import MergeResult
from operandomerge.service import MergeService

SHOWCASE_DIR = Path(__file__).resolve().parent
REPOSITORY_ROOT = SHOWCASE_DIR.parents[1]
EXPERIMENT_ORIGIN = pd.Timestamp("2026-01-01T12:00:00Z")


def generate_source_files(directory: Path = SHOWCASE_DIR) -> None:
    """Write deterministic synthetic files with deliberately different clocks."""

    reactor_time = np.arange(0.0, 601.0, 10.0)
    temperature = (
        25.0 + 0.45 * reactor_time + 14.0 * np.exp(-(((reactor_time - 360.0) / 65.0) ** 2))
    )
    pressure = 1.05 + 0.018 * np.sin(reactor_time / 70.0)
    pd.DataFrame(
        {
            "timestamp_utc": [
                (EXPERIMENT_ORIGIN + pd.to_timedelta(float(value), unit="s")).isoformat()
                for value in reactor_time
            ],
            "temperature_C": np.round(temperature, 4),
            "pressure_bar": np.round(pressure, 6),
        }
    ).to_csv(directory / "reactor_logger.csv", index=False)

    # The MFC logger starts 20 s after the experiment. Its 100 s local event is
    # the same physical setpoint transition as experiment time 120 s.
    mfc_local_elapsed = np.arange(0.0, 581.0, 20.0)
    mfc_experiment_time = mfc_local_elapsed + 20.0
    h2_flow = np.select(
        [mfc_experiment_time < 120, mfc_experiment_time < 300, mfc_experiment_time < 480],
        [20.0, 30.0, 45.0],
        default=25.0,
    )
    ar_flow = 80.0 - h2_flow
    local_clock_origin = pd.Timestamp("2026-01-01T12:00:20")
    pd.DataFrame(
        {
            "instrument_local_time": [
                (local_clock_origin + pd.to_timedelta(float(value), unit="s")).strftime("%H:%M:%S")
                for value in mfc_local_elapsed
            ],
            "h2_flow_sccm": h2_flow,
            "ar_flow_sccm": ar_flow,
        }
    ).to_csv(directory / "mfc_controller.csv", index=False)

    # MS reports eight seconds after the gas composition existed at the reactor.
    ms_actual_time = np.arange(0.0, 601.0, 2.0)
    composition_transition = 1.0 / (1.0 + np.exp(-(ms_actual_time - 330.0) / 62.0))
    mz_44 = 0.06 + 0.86 * composition_transition + 0.012 * np.sin(ms_actual_time / 13.0)
    mz_28 = 0.94 - 0.63 * composition_transition + 0.009 * np.cos(ms_actual_time / 17.0)
    pd.DataFrame(
        {
            "reported_elapsed_s": ms_actual_time + 8.0,
            "mz_44_au": np.round(mz_44, 7),
            "mz_28_au": np.round(mz_28, 7),
        }
    ).to_csv(directory / "mass_spectrometer.csv", index=False)

    # A GC record appears 30 s after physical sampling: 12 s sampling/transport
    # plus 18 s instrument analysis scheduling. Values sum to 100 mol% per row.
    gc_sample_time = np.asarray([120.0, 300.0, 480.0])
    pd.DataFrame(
        {
            "reported_injection_timestamp": [
                (EXPERIMENT_ORIGIN + pd.to_timedelta(float(value + 30.0), unit="s")).isoformat()
                for value in gc_sample_time
            ],
            "co2_mol_pct": [5.0, 18.0, 42.0],
            "co_mol_pct": [80.0, 55.0, 20.0],
            "ch4_mol_pct": [15.0, 27.0, 38.0],
        }
    ).to_csv(directory / "gas_chromatograph.csv", index=False)

    # Each XRD result is reported 20 s late. A -5 s clock correction and 15 s
    # analysis delay place scans at 0, 60, ..., 600 s on the experiment clock.
    xrd_actual_time = np.arange(0.0, 601.0, 60.0)
    phase_fraction = 1.0 / (1.0 + np.exp(-(xrd_actual_time - 350.0) / 65.0))
    lattice_parameter = 3.615 - 0.018 * phase_fraction
    pd.DataFrame(
        {
            "reported_elapsed_s": xrd_actual_time + 20.0,
            "reduced_phase_fraction": np.round(phase_fraction, 7),
            "lattice_parameter_A": np.round(lattice_parameter, 7),
        }
    ).to_csv(directory / "xrd_scans.csv", index=False)


def _normalized_track(series: pd.Series) -> np.ndarray:
    numeric = pd.to_numeric(series, errors="coerce").to_numpy(dtype=float)
    finite = np.isfinite(numeric)
    result = np.full(len(numeric), np.nan, dtype=float)
    if not finite.any():
        return result
    low = float(np.nanmin(numeric))
    high = float(np.nanmax(numeric))
    result[finite] = 0.5 if high == low else (numeric[finite] - low) / (high - low)
    return result


def _reported_clock_positions(directory: Path) -> list[tuple[str, np.ndarray, str]]:
    reactor = pd.read_csv(directory / "reactor_logger.csv")
    reactor_seconds = (
        (pd.to_datetime(reactor["timestamp_utc"], utc=True) - EXPERIMENT_ORIGIN)
        .dt.total_seconds()
        .to_numpy(dtype=float)
    )
    mfc = pd.read_csv(directory / "mfc_controller.csv")
    mfc_seconds = np.arange(len(mfc), dtype=float) * 20.0
    ms = pd.read_csv(directory / "mass_spectrometer.csv")
    gc = pd.read_csv(directory / "gas_chromatograph.csv")
    gc_seconds = (
        (pd.to_datetime(gc["reported_injection_timestamp"], utc=True) - EXPERIMENT_ORIGIN)
        .dt.total_seconds()
        .to_numpy(dtype=float)
    )
    xrd = pd.read_csv(directory / "xrd_scans.csv")
    return [
        ("Reactor UTC (10 s)", reactor_seconds, "#e76f51"),
        ("MFC local (20 s; starts late)", mfc_seconds, "#f4a261"),
        ("MS reported (+8 s)", ms["reported_elapsed_s"].to_numpy(dtype=float), "#2a9d8f"),
        ("GC reported (+30 s)", gc_seconds, "#9b5de5"),
        (
            "XRD reported (+20 s)",
            xrd["reported_elapsed_s"].to_numpy(dtype=float),
            "#457b9d",
        ),
    ]


def plot_before_after(result: MergeResult, source_directory: Path = SHOWCASE_DIR) -> Figure:
    """Plot raw reported clocks beside values on the canonical timeline."""

    figure, (raw_axis, aligned_axis) = plt.subplots(
        1, 2, figsize=(14, 7.5), gridspec_kw={"width_ratios": [0.9, 1.45]}, constrained_layout=True
    )
    raw_axis.set_title("Before: instrument-reported clocks", loc="left", fontweight="bold")
    clock_rows = _reported_clock_positions(source_directory)
    for row, (_label, positions, color) in enumerate(clock_rows):
        display_positions = positions[:: max(1, len(positions) // 80)]
        raw_axis.scatter(
            display_positions, np.full(len(display_positions), row), marker="|", s=95, color=color
        )
    raw_axis.set_yticks(range(len(clock_rows)), [item[0] for item in clock_rows])
    raw_axis.set_xlabel("Reported clock / s relative to own or reactor origin")
    raw_axis.set_xlim(-12, 632)
    raw_axis.set_ylim(-0.7, len(clock_rows) - 0.3)
    raw_axis.grid(axis="x", color="#dddddd", linewidth=0.7)
    raw_axis.text(
        0.02,
        0.98,
        "Offsets are visible before correction.\nTicks show actual source records.",
        transform=raw_axis.transAxes,
        va="top",
        fontsize=9,
        color="#555555",
    )

    aligned_axis.set_title("After: one experiment_time_s", loc="left", fontweight="bold")
    timeline = result.merged["experiment_time_s"].to_numpy(dtype=float)
    tracks = [
        ("Temperature", "reactor_temperature_C", "#e76f51", "continuous"),
        ("Pressure", "reactor_pressure_bar", "#f4a261", "continuous"),
        ("H₂ flow", "mfc_h2_flow_sccm", "#e9c46a", "stepwise"),
        ("MS m/z 44", "ms_mz_44_au", "#2a9d8f", "continuous"),
        ("XRD phase", "xrd_reduced_phase_fraction", "#457b9d", "stepwise"),
    ]
    offsets = np.arange(len(tracks), 0, -1, dtype=float)
    for offset, (label, column, color, semantics) in zip(offsets, tracks, strict=True):
        values = _normalized_track(result.merged[column])
        draw_style = "steps-post" if semantics == "stepwise" else "default"
        aligned_axis.plot(
            timeline, offset + 0.72 * values, color=color, linewidth=1.8, drawstyle=draw_style
        )
        aligned_axis.text(
            -12, offset + 0.35, label, ha="right", va="center", color=color, fontweight="bold"
        )

    gc_column = "gc_co2_mol_pct"
    gc_mask = result.merged[gc_column].notna().to_numpy()
    gc_values = _normalized_track(result.merged[gc_column])
    aligned_axis.scatter(
        timeline[gc_mask],
        0.72 * gc_values[gc_mask],
        color="#9b5de5",
        edgecolor="white",
        linewidth=0.8,
        s=70,
        zorder=5,
        label="GC CO₂ — measured samples only",
    )
    for sample_time in timeline[gc_mask]:
        aligned_axis.axvline(sample_time, color="#9b5de5", alpha=0.12, linewidth=1)
    aligned_axis.text(
        -12, 0.35, "GC CO₂", ha="right", va="center", color="#9b5de5", fontweight="bold"
    )
    aligned_axis.text(
        0.99,
        0.02,
        (
            f"GC: {int(gc_mask.sum())} measured points, "
            f"{int((~gc_mask).sum())} NaNs — never interpolated"
        ),
        transform=aligned_axis.transAxes,
        ha="right",
        fontsize=9,
        color="#6a3d9a",
    )
    aligned_axis.set_xlim(-20, 620)
    aligned_axis.set_ylim(-0.25, len(tracks) + 1.1)
    aligned_axis.set_xlabel("Canonical experiment_time_s")
    aligned_axis.set_yticks([])
    aligned_axis.grid(axis="x", color="#dddddd", linewidth=0.7)
    aligned_axis.legend(loc="lower left", frameon=False, fontsize=9)
    figure.suptitle(
        "OperandoMerge synthetic operando showcase",
        x=0.02,
        ha="left",
        fontsize=17,
        fontweight="bold",
    )
    return figure


def plot_social_preview(result: MergeResult) -> Figure:
    """Create a social-preview candidate using the real aligned result."""

    figure, axis = plt.subplots(figsize=(12.8, 6.4), constrained_layout=True)
    figure.patch.set_facecolor("#102a43")
    axis.set_facecolor("#102a43")
    timeline = result.merged["experiment_time_s"].to_numpy(dtype=float)
    tracks = [
        ("Temperature", "reactor_temperature_C", "#ff8a65", 3.3),
        ("MS m/z 44", "ms_mz_44_au", "#58d6c7", 2.15),
        ("XRD phase", "xrd_reduced_phase_fraction", "#71b7e6", 1.0),
    ]
    for label, column, color, offset in tracks:
        values = _normalized_track(result.merged[column])
        axis.plot(timeline, offset + 0.7 * values, color=color, linewidth=2.6)
        axis.text(-18, offset + 0.34, label, ha="right", va="center", color=color, fontsize=11)
    gc_mask = result.merged["gc_co2_mol_pct"].notna().to_numpy()
    gc_values = _normalized_track(result.merged["gc_co2_mol_pct"])
    axis.scatter(timeline[gc_mask], 0.72 * gc_values[gc_mask], color="#d99cff", s=95, zorder=5)
    axis.text(-18, 0.34, "GC samples", ha="right", va="center", color="#d99cff", fontsize=11)
    axis.set_xlim(-25, 615)
    axis.set_ylim(-0.25, 4.35)
    axis.set_xticks([0, 120, 240, 360, 480, 600])
    axis.tick_params(colors="#b8c9d9")
    axis.set_yticks([])
    axis.set_xlabel("experiment_time_s", color="#d9e6f2", fontsize=12)
    for spine in axis.spines.values():
        spine.set_visible(False)
    axis.grid(axis="x", color="white", alpha=0.09)
    figure.text(0.055, 0.92, "OperandoMerge", color="white", fontsize=30, fontweight="bold")
    figure.text(
        0.055,
        0.86,
        "Heterogeneous instruments. One reproducible timeline.",
        color="#c8d8e8",
        fontsize=15,
    )
    figure.text(
        0.75,
        0.9,
        "GC stays discrete",
        color="#d99cff",
        fontsize=13,
        fontweight="bold",
    )
    return figure


def build_showcase(output_directory: Path, write_doc_images: bool = False) -> MergeResult:
    generate_source_files()
    datasets, merge_config = load_config(SHOWCASE_DIR / "config.json")
    result = MergeService().run(datasets, merge_config)
    output_directory.mkdir(parents=True, exist_ok=True)
    export_excel(result, output_directory / "operandomerge-showcase.xlsx")
    alignment = plot_alignment(result, output_directory / "alignment-cli.png")
    plt.close(alignment)
    before_after = plot_before_after(result)
    before_after.savefig(output_directory / "before-after.png", dpi=150)
    if write_doc_images:
        docs_directory = REPOSITORY_ROOT / "docs" / "images"
        docs_directory.mkdir(parents=True, exist_ok=True)
        before_after.savefig(docs_directory / "showcase-before-after.png", dpi=150)
    plt.close(before_after)
    social = plot_social_preview(result)
    social.savefig(output_directory / "social-preview.png", dpi=100)
    if write_doc_images:
        social.savefig(REPOSITORY_ROOT / "docs" / "images" / "social-preview.png", dpi=100)
    plt.close(social)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=SHOWCASE_DIR / "output",
        help="Directory for Excel and PNG outputs",
    )
    parser.add_argument(
        "--write-doc-images",
        action="store_true",
        help="Also refresh the tracked README images under docs/images",
    )
    args = parser.parse_args()
    result = build_showcase(args.output_dir, args.write_doc_images)
    gc_measured = int(result.merged["gc_co2_mol_pct"].notna().sum())
    print(
        f"Showcase complete: {len(result.merged)} canonical rows, "
        f"{gc_measured} discrete GC samples, {len(result.qc)} QC issue(s); "
        f"output: {args.output_dir}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
