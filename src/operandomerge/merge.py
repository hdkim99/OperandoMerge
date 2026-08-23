"""Data-type-aware merge algorithms.

Continuous channels may be interpolated within their measured domain. Stepwise
channels use a causal previous-value hold. Event and discrete-sample channels are
never interpolated: a value appears only at a matching measured timestamp.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from operandomerge.models import DataType, MergeConfig, MergeResult, NormalizedDataset
from operandomerge.qc import inspect_dataset


def _deduplicated_numeric(dataset: NormalizedDataset, column: str) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    work = dataset.frame[["experiment_time_s", "source_row", column]].copy()
    work[column] = pd.to_numeric(work[column], errors="coerce")
    work = work.dropna(subset=[column]).sort_values(["experiment_time_s", "source_row"])
    work = work.drop_duplicates(subset="experiment_time_s", keep="last")
    return (
        work["experiment_time_s"].to_numpy(dtype=float),
        work[column].to_numpy(dtype=float),
        work["source_row"].to_numpy(dtype=int),
    )


def _exact_indices(source_t: np.ndarray, target_t: np.ndarray, tolerance: float) -> np.ndarray:
    indices = np.searchsorted(source_t, target_t, side="left")
    result = np.full(len(target_t), -1, dtype=int)
    for target_index, candidate in enumerate(indices):
        choices = [index for index in (candidate - 1, candidate) if 0 <= index < len(source_t)]
        if choices:
            nearest = min(choices, key=lambda index: abs(source_t[index] - target_t[target_index]))
            if abs(source_t[nearest] - target_t[target_index]) <= tolerance:
                result[target_index] = nearest
    return result


def _resample(
    source_t: np.ndarray,
    source_y: np.ndarray,
    target_t: np.ndarray,
    data_type: DataType,
    config: MergeConfig,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    values = np.full(len(target_t), np.nan, dtype=float)
    methods = np.full(len(target_t), "missing", dtype=object)
    source_indices = np.full(len(target_t), -1, dtype=int)
    if len(source_t) == 0:
        return values, methods, source_indices
    exact = _exact_indices(source_t, target_t, config.exact_tolerance_s)
    exact_mask = exact >= 0
    values[exact_mask] = source_y[exact[exact_mask]]
    methods[exact_mask] = "original"
    source_indices[exact_mask] = exact[exact_mask]

    remaining = ~exact_mask
    if data_type in {DataType.EVENT, DataType.DISCRETE_SAMPLE} or not remaining.any():
        return values, methods, source_indices
    in_domain = remaining & (target_t >= source_t[0]) & (target_t <= source_t[-1])
    if data_type is DataType.CONTINUOUS and config.continuous_method == "linear":
        values[in_domain] = np.interp(target_t[in_domain], source_t, source_y)
        methods[in_domain] = "linear"
        right = np.searchsorted(source_t, target_t[in_domain], side="left")
        source_indices[in_domain] = np.clip(right, 0, len(source_t) - 1)
    elif data_type is DataType.CONTINUOUS and config.continuous_method == "nearest":
        targets = target_t[in_domain]
        right = np.searchsorted(source_t, targets, side="left")
        left = np.clip(right - 1, 0, len(source_t) - 1)
        right = np.clip(right, 0, len(source_t) - 1)
        choose_right = np.abs(source_t[right] - targets) < np.abs(source_t[left] - targets)
        chosen = np.where(choose_right, right, left)
        values[in_domain] = source_y[chosen]
        methods[in_domain] = "nearest"
        source_indices[in_domain] = chosen
    elif data_type is DataType.STEPWISE and config.stepwise_method == "previous":
        chosen = np.searchsorted(source_t, target_t[in_domain], side="right") - 1
        values[in_domain] = source_y[chosen]
        methods[in_domain] = "previous"
        source_indices[in_domain] = chosen
    return values, methods, source_indices


def _target_timeline(datasets: list[NormalizedDataset], config: MergeConfig) -> np.ndarray:
    if config.timeline == "reference":
        matches = [dataset for dataset in datasets if dataset.name == config.reference_dataset]
        if len(matches) != 1:
            raise ValueError(f"Reference dataset {config.reference_dataset!r} was not found uniquely")
        values = matches[0].frame["experiment_time_s"].to_numpy(dtype=float)
    else:
        values = np.concatenate(
            [dataset.frame["experiment_time_s"].to_numpy(dtype=float) for dataset in datasets]
        )
    return np.unique(values[np.isfinite(values)])


def merge_datasets(datasets: list[NormalizedDataset], config: MergeConfig) -> MergeResult:
    config.validate()
    if not datasets:
        raise ValueError("At least one dataset is required")
    names = [dataset.name for dataset in datasets]
    if len(names) != len(set(names)):
        raise ValueError("Dataset names must be unique")
    target = _target_timeline(datasets, config)
    merged = pd.DataFrame({"experiment_time_s": target})
    provenance_rows: list[dict[str, Any]] = []
    metadata_rows: list[dict[str, Any]] = []
    issues = []

    for dataset in datasets:
        issues.extend(inspect_dataset(dataset))
        metadata_rows.append(
            {
                "dataset": dataset.name,
                "source_file": str(dataset.source_file),
                "time_column": dataset.time_column,
                "time_representation": dataset.time_representation.value,
                "applied_offset_s": dataset.applied_offset_s,
                "total_delay_s": dataset.total_delay_s,
                "absolute_origin": dataset.absolute_origin.isoformat() if dataset.absolute_origin is not None else None,
            }
        )
        for channel in dataset.channels:
            source_t, source_y, source_rows = _deduplicated_numeric(dataset, channel.source_column)
            values, methods, source_index = _resample(source_t, source_y, target, channel.data_type, config)
            output = channel.output_name or f"{dataset.name}__{channel.source_column}"
            if output in merged:
                raise ValueError(f"Duplicate output channel name {output!r}")
            merged[output] = values
            for target_index in np.flatnonzero(~pd.isna(values)):
                dedup_index = int(source_index[target_index])
                source_row = int(source_rows[dedup_index])
                raw_row = dataset.frame.loc[dataset.frame["source_row"] == source_row].iloc[-1]
                provenance_rows.append(
                    {
                        "output_column": output,
                        "experiment_time_s": float(target[target_index]),
                        "value": float(values[target_index]),
                        "source_file": str(dataset.source_file),
                        "source_column": channel.source_column,
                        "source_row": source_row,
                        "original_timestamp": raw_row["original_timestamp"],
                        "applied_offset_s": dataset.applied_offset_s,
                        "total_delay_s": dataset.total_delay_s,
                        "interpolation_method": methods[target_index],
                        "data_type": channel.data_type.value,
                    }
                )

    provenance_columns = [
        "output_column",
        "experiment_time_s",
        "value",
        "source_file",
        "source_column",
        "source_row",
        "original_timestamp",
        "applied_offset_s",
        "total_delay_s",
        "interpolation_method",
        "data_type",
    ]
    provenance = pd.DataFrame(provenance_rows, columns=provenance_columns)
    configuration = {
        "timeline": config.timeline,
        "reference_dataset": config.reference_dataset,
        "continuous_method": config.continuous_method,
        "stepwise_method": config.stepwise_method,
        "exact_tolerance_s": config.exact_tolerance_s,
    }
    return MergeResult(
        merged=merged,
        provenance=provenance,
        metadata=pd.DataFrame(metadata_rows),
        qc=issues,
        configuration=configuration,
    )
