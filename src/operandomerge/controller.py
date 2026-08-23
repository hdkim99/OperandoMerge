"""GUI application state without a desktop-toolkit dependency."""

from __future__ import annotations

from pathlib import Path

from operandomerge.config import load_config, save_config
from operandomerge.export import export_excel
from operandomerge.models import DatasetConfig, MergeConfig, MergeResult
from operandomerge.service import MergeService


class GuiController:
    """Testable GUI application layer; scientific work remains in MergeService."""

    def __init__(self, service: MergeService | None = None) -> None:
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
