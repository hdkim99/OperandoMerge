"""Time normalization and physical delay correction.

The canonical coordinate is ``experiment_time_s``. Source timestamp values remain
in ``original_timestamp``. Positive instrument delays are subtracted because an
analysis reported at t corresponds to a sample/phenomenon occurring earlier.
"""

from __future__ import annotations

from datetime import datetime

import numpy as np
import pandas as pd

from operandomerge.models import DatasetConfig, NormalizedDataset, TimeRepresentation


def parse_absolute(series: pd.Series) -> pd.Series:
    parsed = pd.to_datetime(series, errors="coerce", utc=True)
    if parsed.isna().any():
        rows = parsed.index[parsed.isna()].tolist()[:5]
        raise ValueError(f"Unparseable absolute timestamp at row(s) {rows}")
    return parsed


def _local_clock_seconds(value: object) -> float:
    if isinstance(value, pd.Timedelta):
        return value.total_seconds()
    if isinstance(value, datetime):
        return value.hour * 3600.0 + value.minute * 60.0 + value.second + value.microsecond / 1e6
    text = str(value).strip()
    parts = text.split(":")
    if len(parts) != 3:
        raise ValueError(f"Local instrument time must be HH:MM:SS[.sss], got {text!r}")
    hour, minute, second = int(parts[0]), int(parts[1]), float(parts[2])
    if hour not in range(24) or minute not in range(60) or not (0 <= second < 60):
        raise ValueError(f"Invalid local instrument time {text!r}")
    return hour * 3600.0 + minute * 60.0 + second


def parse_local_clock(series: pd.Series) -> np.ndarray:
    values = np.asarray([_local_clock_seconds(value) for value in series], dtype=float)
    if not np.isfinite(values).all():
        raise ValueError("Local instrument time contains non-finite values")
    unwrapped = values.copy()
    day_shift = 0.0
    for index in range(1, len(unwrapped)):
        if values[index] + day_shift < unwrapped[index - 1] - 43200.0:
            day_shift += 86400.0
        unwrapped[index] = values[index] + day_shift
    return unwrapped - unwrapped[0]


def discover_absolute_origin(configs: list[DatasetConfig]) -> pd.Timestamp | None:
    starts: list[pd.Timestamp] = []
    for config in configs:
        if config.time_representation not in {
            TimeRepresentation.ABSOLUTE,
            TimeRepresentation.INJECTION_TIMESTAMP,
        }:
            continue
        from operandomerge.io import read_table

        frame = read_table(config.path, config.sheet_name)
        if config.time_column not in frame:
            raise ValueError(f"Time column {config.time_column!r} missing from {config.path}")
        starts.append(parse_absolute(frame[config.time_column]).min())
    return min(starts) if starts else None


def normalize_dataset(config: DatasetConfig, absolute_origin: pd.Timestamp | None) -> NormalizedDataset:
    """Normalize one dataset without discarding the original timestamp or any input row."""

    from operandomerge.io import read_table

    config.validate()
    source = read_table(config.path, config.sheet_name)
    required = {config.time_column, *(channel.source_column for channel in config.channels)}
    missing = sorted(required.difference(source.columns))
    if missing:
        raise ValueError(f"Missing column(s) in {config.path}: {', '.join(missing)}")

    original = source[config.time_column].copy()
    representation = config.time_representation
    local_origin: pd.Timestamp | None = None
    if representation in {TimeRepresentation.ABSOLUTE, TimeRepresentation.INJECTION_TIMESTAMP}:
        absolute = parse_absolute(original)
        if absolute_origin is None:
            absolute_origin = absolute.min()
        base_seconds = (absolute - absolute_origin).dt.total_seconds().to_numpy(dtype=float)
        local_origin = absolute_origin
    elif representation is TimeRepresentation.ELAPSED_SECONDS:
        base_seconds = pd.to_numeric(original, errors="coerce").to_numpy(dtype=float)
    elif representation is TimeRepresentation.ELAPSED_MINUTES:
        base_seconds = pd.to_numeric(original, errors="coerce").to_numpy(dtype=float) * 60.0
    elif representation is TimeRepresentation.INSTRUMENT_LOCAL_TIME:
        base_seconds = parse_local_clock(original)
    else:  # pragma: no cover - enum exhaustiveness guard
        raise ValueError(f"Unsupported time representation {representation}")

    if not np.isfinite(base_seconds).all():
        bad = np.flatnonzero(~np.isfinite(base_seconds)).tolist()[:5]
        raise ValueError(f"Non-numeric elapsed time at row(s) {bad}")

    offset_s = config.alignment.effective_offset_s()
    delay_s = config.delay.total_s
    canonical = base_seconds + offset_s - delay_s
    normalized = pd.DataFrame(
        {
            "experiment_time_s": canonical,
            "original_timestamp": original.to_numpy(copy=True),
            "source_row": np.arange(len(source), dtype=int),
        }
    )
    for channel in config.channels:
        normalized[channel.source_column] = source[channel.source_column].to_numpy(copy=True)
    return NormalizedDataset(
        name=config.dataset_name,
        source_file=config.path.resolve(),
        frame=normalized,
        channels=config.channels,
        time_column=config.time_column,
        time_representation=representation,
        applied_offset_s=offset_s,
        total_delay_s=delay_s,
        absolute_origin=local_origin,
    )

