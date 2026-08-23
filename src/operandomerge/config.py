"""JSON configuration parsing and serialization."""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

from operandomerge.models import (
    AlignmentConfig,
    AlignmentMethod,
    ChannelConfig,
    DataType,
    DatasetConfig,
    DelayConfig,
    MergeConfig,
)


def _dataset_from_dict(raw: dict[str, Any], base: Path) -> DatasetConfig:
    source_path = Path(str(raw["path"])).expanduser()
    if not source_path.is_absolute():
        source_path = (base / source_path).resolve()
    alignment_raw = raw.get("alignment", {})
    delay_raw = raw.get("delay", {})
    return DatasetConfig(
        path=source_path,
        name=raw.get("name"),
        sheet_name=raw.get("sheet_name", 0),
        time_column=str(raw["time_column"]),
        time_representation=TimeRepresentation(raw["time_representation"]),
        channels=tuple(
            ChannelConfig(
                source_column=str(channel["source_column"]),
                data_type=DataType(channel.get("data_type", "continuous")),
                output_name=channel.get("output_name"),
            )
            for channel in raw["channels"]
        ),
        alignment=AlignmentConfig(
            method=AlignmentMethod(alignment_raw.get("method", "elapsed")),
            manual_offset_s=float(alignment_raw.get("manual_offset_s", 0.0)),
            source_event_time_s=_optional_float(alignment_raw.get("source_event_time_s")),
            target_event_time_s=_optional_float(alignment_raw.get("target_event_time_s")),
        ),
        delay=DelayConfig(
            manual_s=float(delay_raw.get("manual_s", 0.0)),
            sampling_s=float(delay_raw.get("sampling_s", 0.0)),
            transport_s=float(delay_raw.get("transport_s", 0.0)),
            dead_volume_s=float(delay_raw.get("dead_volume_s", 0.0)),
            analysis_s=float(delay_raw.get("analysis_s", 0.0)),
        ),
    )


def _optional_float(value: Any) -> float | None:
    return None if value in {None, ""} else float(value)


def load_config(path: Path) -> tuple[list[DatasetConfig], MergeConfig]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict) or not isinstance(raw.get("datasets"), list):
        raise ValueError("Configuration must contain a 'datasets' list")
    datasets = [_dataset_from_dict(item, path.parent) for item in raw["datasets"]]
    merge_raw = raw.get("merge", {})
    merge = MergeConfig(
        timeline=merge_raw.get("timeline", "union"),
        reference_dataset=merge_raw.get("reference_dataset"),
        continuous_method=merge_raw.get("continuous_method", "linear"),
        stepwise_method=merge_raw.get("stepwise_method", "previous"),
        exact_tolerance_s=float(merge_raw.get("exact_tolerance_s", 1e-9)),
    )
    return datasets, merge


def config_as_dict(datasets: list[DatasetConfig], merge: MergeConfig) -> dict[str, Any]:
    dataset_items: list[dict[str, Any]] = []
    for dataset in datasets:
        item = asdict(dataset)
        item["path"] = str(dataset.path)
        item["time_representation"] = dataset.time_representation.value
        item["alignment"]["method"] = dataset.alignment.method.value
        for channel_item, channel in zip(item["channels"], dataset.channels, strict=True):
            channel_item["data_type"] = channel.data_type.value
        dataset_items.append(item)
    return {"datasets": dataset_items, "merge": asdict(merge)}


def save_config(datasets: list[DatasetConfig], merge: MergeConfig, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(config_as_dict(datasets, merge), indent=2), encoding="utf-8")

