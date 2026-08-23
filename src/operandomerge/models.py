"""Validated configuration and result models used by API, CLI, and GUI."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

import pandas as pd


class TimeRepresentation(str, Enum):
    """Supported source-clock representations."""

    ABSOLUTE = "absolute"
    ELAPSED_SECONDS = "elapsed_seconds"
    ELAPSED_MINUTES = "elapsed_minutes"
    INSTRUMENT_LOCAL_TIME = "instrument_local_time"
    INJECTION_TIMESTAMP = "injection_timestamp"


class AlignmentMethod(str, Enum):
    """How a source clock is placed on the experiment clock."""

    ABSOLUTE = "absolute"
    ELAPSED = "elapsed"
    MANUAL_OFFSET = "manual_offset"
    REFERENCE_EVENT = "reference_event"


class DataType(str, Enum):
    """Sampling semantics used by the resampler."""

    CONTINUOUS = "continuous"
    STEPWISE = "stepwise"
    EVENT = "event"
    DISCRETE_SAMPLE = "discrete_sample"


@dataclass(frozen=True)
class DelayConfig:
    """Instrument delay components in seconds.

    Positive values mean that an instrument reports a phenomenon after it occurred.
    They are therefore subtracted from the reported time during correction.
    """

    manual_s: float = 0.0
    sampling_s: float = 0.0
    transport_s: float = 0.0
    dead_volume_s: float = 0.0
    analysis_s: float = 0.0

    @property
    def total_s(self) -> float:
        return (
            self.manual_s
            + self.sampling_s
            + self.transport_s
            + self.dead_volume_s
            + self.analysis_s
        )

    def validate(self) -> None:
        for name, value in asdict(self).items():
            if value < 0:
                raise ValueError(f"Delay {name} must be non-negative, got {value}")


@dataclass(frozen=True)
class AlignmentConfig:
    method: AlignmentMethod = AlignmentMethod.ELAPSED
    manual_offset_s: float = 0.0
    source_event_time_s: float | None = None
    target_event_time_s: float | None = None

    def effective_offset_s(self) -> float:
        if self.method is AlignmentMethod.REFERENCE_EVENT:
            if self.source_event_time_s is None or self.target_event_time_s is None:
                raise ValueError("Reference-event alignment requires source and target event times")
            return self.target_event_time_s - self.source_event_time_s + self.manual_offset_s
        return self.manual_offset_s


@dataclass(frozen=True)
class ChannelConfig:
    source_column: str
    data_type: DataType = DataType.CONTINUOUS
    output_name: str | None = None


@dataclass(frozen=True)
class DatasetConfig:
    path: Path
    time_column: str
    time_representation: TimeRepresentation
    channels: tuple[ChannelConfig, ...]
    name: str | None = None
    sheet_name: str | int | None = 0
    alignment: AlignmentConfig = field(default_factory=AlignmentConfig)
    delay: DelayConfig = field(default_factory=DelayConfig)

    @property
    def dataset_name(self) -> str:
        return self.name or self.path.stem

    def validate(self) -> None:
        if not self.channels:
            raise ValueError(f"Dataset {self.dataset_name!r} has no channels")
        source_columns = [channel.source_column for channel in self.channels]
        if len(source_columns) != len(set(source_columns)):
            raise ValueError(f"Dataset {self.dataset_name!r} has duplicate channel mappings")
        self.delay.validate()
        self.alignment.effective_offset_s()


@dataclass(frozen=True)
class MergeConfig:
    timeline: str = "union"
    reference_dataset: str | None = None
    experiment_origin: str | None = None
    continuous_method: str = "linear"
    stepwise_method: str = "previous"
    exact_tolerance_s: float = 1e-9

    def validate(self) -> None:
        if self.timeline not in {"union", "reference"}:
            raise ValueError("timeline must be 'union' or 'reference'")
        if self.timeline == "reference" and not self.reference_dataset:
            raise ValueError("reference_dataset is required for a reference timeline")
        if self.experiment_origin is not None:
            try:
                pd.to_datetime(self.experiment_origin, utc=True)
            except (TypeError, ValueError) as error:
                raise ValueError("experiment_origin must be an ISO-8601 timestamp") from error
        if self.continuous_method not in {"linear", "nearest", "none"}:
            raise ValueError("continuous_method must be linear, nearest, or none")
        if self.stepwise_method not in {"previous", "none"}:
            raise ValueError("stepwise_method must be previous or none")
        if self.exact_tolerance_s < 0:
            raise ValueError("exact_tolerance_s cannot be negative")


@dataclass
class NormalizedDataset:
    name: str
    source_file: Path
    frame: pd.DataFrame
    channels: tuple[ChannelConfig, ...]
    time_column: str
    time_representation: TimeRepresentation
    alignment: AlignmentConfig
    delay: DelayConfig
    applied_offset_s: float
    total_delay_s: float
    absolute_origin: pd.Timestamp | None


@dataclass
class QCIssue:
    severity: str
    code: str
    dataset: str
    channel: str | None
    message: str
    row: int | None = None

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class MergeResult:
    merged: pd.DataFrame
    provenance: pd.DataFrame
    metadata: pd.DataFrame
    qc: list[QCIssue]
    configuration: dict[str, Any]
