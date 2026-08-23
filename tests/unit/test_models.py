from __future__ import annotations

from pathlib import Path

import pytest

from operandomerge.models import (
    AlignmentConfig,
    AlignmentMethod,
    ChannelConfig,
    DatasetConfig,
    DelayConfig,
    MergeConfig,
    TimeRepresentation,
)


def test_delay_total_has_all_physical_components() -> None:
    delay = DelayConfig(manual_s=1, sampling_s=2, transport_s=3, dead_volume_s=4, analysis_s=5)
    assert delay.total_s == 15


@pytest.mark.parametrize(
    "field", ["manual_s", "sampling_s", "transport_s", "dead_volume_s", "analysis_s"]
)
def test_negative_delay_is_rejected(field: str) -> None:
    delay = DelayConfig(**{field: -0.1})
    with pytest.raises(ValueError, match="non-negative"):
        delay.validate()


def test_reference_event_offset_recovers_known_shift() -> None:
    alignment = AlignmentConfig(
        method=AlignmentMethod.REFERENCE_EVENT,
        source_event_time_s=17.5,
        target_event_time_s=2.5,
        manual_offset_s=1.0,
    )
    assert alignment.effective_offset_s() == -14.0


def test_reference_event_requires_both_events() -> None:
    with pytest.raises(ValueError, match="requires source and target"):
        AlignmentConfig(method=AlignmentMethod.REFERENCE_EVENT).effective_offset_s()


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"timeline": "grid"}, "timeline"),
        ({"timeline": "reference"}, "reference_dataset"),
        ({"continuous_method": "cubic"}, "continuous_method"),
        ({"stepwise_method": "future"}, "stepwise_method"),
        ({"exact_tolerance_s": -1}, "cannot be negative"),
        ({"experiment_origin": "not-a-timestamp"}, "experiment_origin"),
    ],
)
def test_invalid_merge_config_is_rejected(kwargs: dict[str, object], message: str) -> None:
    with pytest.raises(ValueError, match=message):
        MergeConfig(**kwargs).validate()


def test_duplicate_dataset_channel_mapping_is_rejected() -> None:
    config = DatasetConfig(
        path=Path("sample.csv"),
        time_column="time",
        time_representation=TimeRepresentation.ELAPSED_SECONDS,
        channels=(ChannelConfig("signal"), ChannelConfig("signal")),
    )
    with pytest.raises(ValueError, match="duplicate"):
        config.validate()


def test_absolute_alignment_rejects_elapsed_clock() -> None:
    config = DatasetConfig(
        path=Path("sample.csv"),
        time_column="time",
        time_representation=TimeRepresentation.ELAPSED_SECONDS,
        channels=(ChannelConfig("signal"),),
        alignment=AlignmentConfig(method=AlignmentMethod.ABSOLUTE),
    )
    with pytest.raises(ValueError, match="Absolute alignment requires"):
        config.validate()


def test_elapsed_alignment_rejects_absolute_clock() -> None:
    config = DatasetConfig(
        path=Path("sample.csv"),
        time_column="time",
        time_representation=TimeRepresentation.ABSOLUTE,
        channels=(ChannelConfig("signal"),),
    )
    with pytest.raises(ValueError, match="require absolute"):
        config.validate()


@pytest.mark.parametrize("value", [float("nan"), float("inf")])
def test_non_finite_delay_is_rejected(value: float) -> None:
    with pytest.raises(ValueError, match="non-negative"):
        DelayConfig(sampling_s=value).validate()
