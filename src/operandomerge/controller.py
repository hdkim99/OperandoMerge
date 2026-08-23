"""GUI application state without a desktop-toolkit dependency."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol

from operandomerge.config import load_config, save_config
from operandomerge.export import export_excel
from operandomerge.models import DatasetConfig, MergeConfig, MergeResult
from operandomerge.service import MergeService


class MergeRunner(Protocol):
    def run(self, datasets: list[DatasetConfig], merge: MergeConfig) -> MergeResult: ...


def merge_config_from_fields(
    timeline: str,
    reference_dataset: str,
    experiment_origin: str,
    continuous_method: str,
    stepwise_method: str,
    exact_tolerance_s: str,
) -> MergeConfig:
    """Convert GUI text controls into the same validated core model used by JSON."""

    config = MergeConfig(
        timeline=timeline,
        reference_dataset=reference_dataset or None,
        experiment_origin=experiment_origin or None,
        continuous_method=continuous_method,
        stepwise_method=stepwise_method,
        exact_tolerance_s=float(exact_tolerance_s),
    )
    config.validate()
    return config


class GuiController:
    """Testable GUI application layer; scientific work remains in MergeService."""

    def __init__(self, service: MergeRunner | None = None) -> None:
        self.service = service or MergeService()
        self.datasets: list[DatasetConfig] = []
        self.merge_config = MergeConfig()
        self.result: MergeResult | None = None

    def run_merge(self) -> MergeResult:
        self.result = self.service.run(self.datasets, self.merge_config)
        return self.result

    def export(self, path: Path) -> None:
        if self.result is None:
            raise ValueError("Run a merge before exporting")
        export_excel(self.result, path)

    def load(self, path: Path) -> None:
        self.datasets, self.merge_config = load_config(path)
        self.result = None

    def save(self, path: Path) -> None:
        save_config(self.datasets, self.merge_config, path)
