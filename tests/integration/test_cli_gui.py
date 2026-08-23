from __future__ import annotations

from pathlib import Path

from operandomerge.cli import main
from operandomerge.controller import GuiController, merge_config_from_fields
from operandomerge.models import (
    AlignmentConfig,
    AlignmentMethod,
    ChannelConfig,
    DatasetConfig,
    DataType,
    DelayConfig,
    MergeConfig,
    MergeResult,
    TimeRepresentation,
)


def test_cli_inspect_and_merge_example(tmp_path: Path, capsys) -> None:
    root = Path(__file__).parents[2]
    assert main(["inspect", str(root / "examples" / "reactor_logger.csv")]) == 0
    assert "temperature_C" in capsys.readouterr().out
    report = tmp_path / "report.xlsx"
    plot = tmp_path / "plot.png"
    assert (
        main(
            [
                "merge",
                str(root / "examples" / "example-config.json"),
                "--excel",
                str(report),
                "--plot",
                str(plot),
            ]
        )
        == 0
    )
    assert report.stat().st_size > 0
    assert plot.stat().st_size > 0


def test_cli_returns_nonzero_for_invalid_input(tmp_path: Path, capsys) -> None:
    code = main(["inspect", str(tmp_path / "missing.csv")])
    assert code == 2
    assert "error" in capsys.readouterr().err


class CapturingService:
    def __init__(self) -> None:
        self.datasets = None
        self.merge = None

    def run(self, datasets, merge):
        self.datasets = datasets
        self.merge = merge
        return MergeResult.__new__(MergeResult)


def test_gui_controller_passes_alignment_delay_channel_and_merge_settings(table_writer) -> None:
    path = table_writer("gui", {"time": [0], "signal": [1]})
    dataset = DatasetConfig(
        path=path,
        name="gui-source",
        time_column="time",
        time_representation=TimeRepresentation.ELAPSED_MINUTES,
        channels=(ChannelConfig("signal", DataType.DISCRETE_SAMPLE, "gc_signal"),),
        alignment=AlignmentConfig(
            method=AlignmentMethod.REFERENCE_EVENT,
            manual_offset_s=3,
            source_event_time_s=10,
            target_event_time_s=20,
        ),
        delay=DelayConfig(manual_s=1, sampling_s=2, transport_s=3, dead_volume_s=4, analysis_s=5),
    )
    merge = MergeConfig(
        timeline="reference",
        reference_dataset="gui-source",
        continuous_method="nearest",
        stepwise_method="none",
        exact_tolerance_s=0.02,
    )
    service = CapturingService()
    controller = GuiController(service=service)
    controller.datasets = [dataset]
    controller.merge_config = merge
    controller.run_merge()
    assert service.datasets == [dataset]
    assert service.merge == merge
    assert service.datasets[0].channels[0].data_type is DataType.DISCRETE_SAMPLE
    assert service.datasets[0].alignment.effective_offset_s() == 13
    assert service.datasets[0].delay.total_s == 15


def test_gui_text_controls_preserve_all_merge_settings() -> None:
    config = merge_config_from_fields(
        "reference",
        "gc",
        "2026-01-01T00:00:00Z",
        "nearest",
        "none",
        "0.025",
    )
    assert config == MergeConfig(
        timeline="reference",
        reference_dataset="gc",
        experiment_origin="2026-01-01T00:00:00Z",
        continuous_method="nearest",
        stepwise_method="none",
        exact_tolerance_s=0.025,
    )
