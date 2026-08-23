from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from operandomerge.models import (
    AlignmentConfig,
    AlignmentMethod,
    ChannelConfig,
    DatasetConfig,
    DelayConfig,
    TimeRepresentation,
)
from operandomerge.timeline import discover_absolute_origin, normalize_dataset, parse_local_clock


def _config(path: Path, representation: TimeRepresentation, **kwargs: object) -> DatasetConfig:
    if "alignment" not in kwargs and representation in {
        TimeRepresentation.ABSOLUTE,
        TimeRepresentation.INJECTION_TIMESTAMP,
    }:
        kwargs["alignment"] = AlignmentConfig(method=AlignmentMethod.ABSOLUTE)
    return DatasetConfig(
        path=path,
        time_column="time",
        time_representation=representation,
        channels=(ChannelConfig("signal"),),
        **kwargs,
    )


def test_elapsed_minutes_convert_to_seconds_and_apply_offset_delay(table_writer) -> None:
    path = table_writer("minutes", {"time": [0, 1.5], "signal": [1, 2]})
    config = _config(
        path,
        TimeRepresentation.ELAPSED_MINUTES,
        alignment=AlignmentConfig(method=AlignmentMethod.MANUAL_OFFSET, manual_offset_s=10),
        delay=DelayConfig(sampling_s=2, transport_s=3),
    )
    result = normalize_dataset(config, None)
    np.testing.assert_allclose(result.frame["experiment_time_s"], [5, 95])
    assert result.frame["original_timestamp"].tolist() == [0.0, 1.5]


def test_local_clock_unwraps_midnight() -> None:
    clock = pd.Series(["23:59:58.5", "23:59:59.5", "00:00:01.0"])
    np.testing.assert_allclose(parse_local_clock(clock), [0, 1, 2.5])


def test_invalid_local_clock_is_rejected() -> None:
    with pytest.raises(ValueError, match="Invalid local"):
        parse_local_clock(pd.Series(["25:00:00"]))


def test_absolute_origin_is_earliest_across_files(table_writer) -> None:
    late = table_writer("late", {"time": ["2026-01-01T00:00:10Z"], "signal": [2]})
    early = table_writer("early", {"time": ["2026-01-01T00:00:05Z"], "signal": [1]})
    configs = [
        _config(late, TimeRepresentation.ABSOLUTE),
        _config(early, TimeRepresentation.INJECTION_TIMESTAMP),
    ]
    origin = discover_absolute_origin(configs)
    assert origin == pd.Timestamp("2026-01-01T00:00:05Z")
    normalized = normalize_dataset(configs[0], origin)
    assert normalized.frame["experiment_time_s"].iloc[0] == 5


def test_unparseable_absolute_timestamp_fails_before_merge(table_writer) -> None:
    path = table_writer("bad", {"time": ["not-a-time"], "signal": [1]})
    with pytest.raises(ValueError, match="Unparseable"):
        discover_absolute_origin([_config(path, TimeRepresentation.ABSOLUTE)])


def test_reference_event_alignment_changes_real_canonical_time(table_writer) -> None:
    path = table_writer("event", {"time": [7, 17], "signal": [1, 2]})
    config = _config(
        path,
        TimeRepresentation.ELAPSED_SECONDS,
        alignment=AlignmentConfig(
            method=AlignmentMethod.REFERENCE_EVENT,
            source_event_time_s=7,
            target_event_time_s=0,
        ),
    )
    np.testing.assert_allclose(normalize_dataset(config, None).frame["experiment_time_s"], [0, 10])
