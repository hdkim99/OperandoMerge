from __future__ import annotations

import numpy as np

from operandomerge.models import (
    ChannelConfig,
    DatasetConfig,
    DataType,
    MergeConfig,
    TimeRepresentation,
)
from operandomerge.service import MergeService


def _dataset(path, name: str, data_type: DataType, column: str = "signal") -> DatasetConfig:
    return DatasetConfig(
        path=path,
        name=name,
        time_column="time",
        time_representation=TimeRepresentation.ELAPSED_SECONDS,
        channels=(ChannelConfig(column, data_type),),
    )


def test_continuous_linear_interpolation_recovers_hand_calculation(table_writer) -> None:
    continuous = table_writer("continuous", {"time": [0, 10], "signal": [0, 100]})
    clock = table_writer("clock", {"time": [5], "event": [1]})
    result = MergeService().run(
        [
            _dataset(continuous, "continuous", DataType.CONTINUOUS),
            _dataset(clock, "clock", DataType.EVENT, "event"),
        ]
    )
    row = result.merged.loc[result.merged["experiment_time_s"] == 5].iloc[0]
    assert row["continuous__signal"] == 50
    provenance = result.provenance.query(
        "output_column == 'continuous__signal' and experiment_time_s == 5"
    ).iloc[0]
    assert provenance["interpolation_method"] == "linear"
    assert provenance["source_row_left"] == 0
    assert provenance["source_row_right"] == 1
    assert provenance["original_timestamp_left"] == 0
    assert provenance["original_timestamp_right"] == 10


def test_continuous_interpolation_scales_linearly(table_writer) -> None:
    first = table_writer("first", {"time": [0, 10], "signal": [2, 6]})
    second = table_writer("second", {"time": [0, 10], "signal": [4, 12]})
    clock = table_writer("clock", {"time": [5], "event": [1]})
    result = MergeService().run(
        [
            _dataset(first, "first", DataType.CONTINUOUS),
            _dataset(second, "second", DataType.CONTINUOUS),
            _dataset(clock, "clock", DataType.EVENT, "event"),
        ]
    )
    row = result.merged.loc[result.merged["experiment_time_s"] == 5].iloc[0]
    assert row["second__signal"] == 2 * row["first__signal"]


def test_common_interpolated_value_is_invariant_to_target_sampling_density(table_writer) -> None:
    source = table_writer("source", {"time": [0, 10], "signal": [0, 100]})
    sparse = table_writer("sparse", {"time": [5], "event": [1]})
    dense = table_writer("dense", {"time": [2.5, 5, 7.5], "event": [1, 1, 1]})
    sparse_result = MergeService().run(
        [
            _dataset(source, "source", DataType.CONTINUOUS),
            _dataset(sparse, "clock", DataType.EVENT, "event"),
        ]
    )
    dense_result = MergeService().run(
        [
            _dataset(source, "source", DataType.CONTINUOUS),
            _dataset(dense, "clock", DataType.EVENT, "event"),
        ]
    )
    sparse_value = sparse_result.merged.loc[
        sparse_result.merged["experiment_time_s"] == 5, "source__signal"
    ].iloc[0]
    dense_value = dense_result.merged.loc[
        dense_result.merged["experiment_time_s"] == 5, "source__signal"
    ].iloc[0]
    assert sparse_value == dense_value == 50


def test_nearest_continuous_policy_uses_closest_measurement(table_writer) -> None:
    source = table_writer("source", {"time": [0, 10], "signal": [1, 9]})
    clock = table_writer("clock", {"time": [6], "event": [1]})
    result = MergeService().run(
        [
            _dataset(source, "source", DataType.CONTINUOUS),
            _dataset(clock, "clock", DataType.EVENT, "event"),
        ],
        MergeConfig(continuous_method="nearest"),
    )
    assert result.merged.loc[result.merged["experiment_time_s"] == 6, "source__signal"].iloc[0] == 9


def test_disabled_interpolation_leaves_nonmeasured_times_missing(table_writer) -> None:
    source = table_writer("source", {"time": [0, 10], "signal": [1, 9]})
    clock = table_writer("clock", {"time": [5], "event": [1]})
    result = MergeService().run(
        [
            _dataset(source, "source", DataType.CONTINUOUS),
            _dataset(clock, "clock", DataType.EVENT, "event"),
        ],
        MergeConfig(continuous_method="none"),
    )
    assert result.merged.loc[result.merged["experiment_time_s"] == 5, "source__signal"].isna().all()


def test_stepwise_uses_causal_previous_value(table_writer) -> None:
    step = table_writer("step", {"time": [0, 10], "signal": [2, 9]})
    clock = table_writer("clock", {"time": [5], "event": [1]})
    result = MergeService().run(
        [
            _dataset(step, "step", DataType.STEPWISE),
            _dataset(clock, "clock", DataType.EVENT, "event"),
        ]
    )
    row = result.merged.loc[result.merged["experiment_time_s"] == 5].iloc[0]
    assert row["step__signal"] == 2
    provenance = result.provenance.query(
        "output_column == 'step__signal' and experiment_time_s == 5"
    ).iloc[0]
    assert provenance["interpolation_method"] == "previous"
    assert provenance["source_row_left"] == provenance["source_row_right"] == 0


def test_discrete_samples_are_never_interpolated(table_writer) -> None:
    gc = table_writer("gc", {"time": [0, 10], "signal": [10, 30]})
    clock = table_writer("clock", {"time": [5], "event": [1]})
    result = MergeService().run(
        [
            _dataset(gc, "gc", DataType.DISCRETE_SAMPLE),
            _dataset(clock, "clock", DataType.EVENT, "event"),
        ]
    )
    middle = result.merged.loc[result.merged["experiment_time_s"] == 5, "gc__signal"]
    assert middle.isna().all()
    assert set(
        result.provenance.query("output_column == 'gc__signal'")["interpolation_method"]
    ) == {"original"}


def test_events_are_never_interpolated_even_with_nearest_policy(table_writer) -> None:
    event = table_writer("event", {"time": [0, 10], "signal": [1, 1]})
    clock = table_writer("clock", {"time": [5], "marker": [1]})
    result = MergeService().run(
        [
            _dataset(event, "event", DataType.EVENT),
            _dataset(clock, "clock", DataType.EVENT, "marker"),
        ],
        MergeConfig(continuous_method="nearest"),
    )
    assert np.isnan(
        result.merged.loc[result.merged["experiment_time_s"] == 5, "event__signal"].iloc[0]
    )


def test_continuous_channels_are_not_extrapolated(table_writer) -> None:
    source = table_writer("source", {"time": [0, 10], "signal": [0, 10]})
    clock = table_writer("clock", {"time": [-5, 15], "event": [1, 1]})
    result = MergeService().run(
        [
            _dataset(source, "source", DataType.CONTINUOUS),
            _dataset(clock, "clock", DataType.EVENT, "event"),
        ]
    )
    outside = result.merged.loc[result.merged["experiment_time_s"].isin([-5, 15]), "source__signal"]
    assert outside.isna().all()


def test_reference_timeline_is_exactly_selected_dataset_clock(table_writer) -> None:
    reference = table_writer("reference", {"time": [0, 10], "signal": [1, 2]})
    other = table_writer("other", {"time": [5], "signal": [3]})
    result = MergeService().run(
        [
            _dataset(reference, "ref", DataType.CONTINUOUS),
            _dataset(other, "other", DataType.DISCRETE_SAMPLE),
        ],
        MergeConfig(timeline="reference", reference_dataset="ref"),
    )
    assert result.merged["experiment_time_s"].tolist() == [0, 10]
    assert result.merged["other__signal"].isna().all()
