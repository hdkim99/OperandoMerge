"""Application service shared by API, CLI, and GUI."""

from __future__ import annotations

from operandomerge.merge import merge_datasets
from operandomerge.models import DatasetConfig, MergeConfig, MergeResult
from operandomerge.timeline import discover_absolute_origin, normalize_dataset


class MergeService:
    """Orchestrate IO, normalization, QC, and merging without a UI dependency."""

    def run(self, datasets: list[DatasetConfig], merge: MergeConfig | None = None) -> MergeResult:
        if not datasets:
            raise ValueError("At least one dataset configuration is required")
        merge_config = merge or MergeConfig()
        merge_config.validate()
        absolute_origin = discover_absolute_origin(datasets, merge_config.experiment_origin)
        normalized = [normalize_dataset(config, absolute_origin) for config in datasets]
        return merge_datasets(normalized, merge_config)
