"""Quality-control checks kept separate from numeric merge results."""

from __future__ import annotations

import numpy as np
import pandas as pd

from operandomerge.models import NormalizedDataset, QCIssue


def inspect_dataset(dataset: NormalizedDataset) -> list[QCIssue]:
    frame = dataset.frame
    issues: list[QCIssue] = []
    time = frame["experiment_time_s"]
    duplicate = time.duplicated(keep=False)
    for row in frame.index[duplicate].tolist():
        issues.append(
            QCIssue(
                "warning",
                "duplicate_timestamp",
                dataset.name,
                None,
                "Duplicate canonical timestamp",
                int(row),
            )
        )
    if not time.is_monotonic_increasing:
        issues.append(
            QCIssue("warning", "non_monotonic_time", dataset.name, None, "Time is not monotonic")
        )
    for channel in dataset.channels:
        values = frame[channel.source_column]
        missing_count = int(values.isna().sum())
        if missing_count:
            issues.append(
                QCIssue(
                    "warning",
                    "missing_data",
                    dataset.name,
                    channel.source_column,
                    f"{missing_count} missing value(s)",
                )
            )
        numeric = pd.to_numeric(values, errors="coerce")
        non_numeric = int((numeric.isna() & values.notna()).sum())
        if non_numeric:
            issues.append(
                QCIssue(
                    "error",
                    "non_numeric_channel",
                    dataset.name,
                    channel.source_column,
                    f"{non_numeric} non-numeric value(s)",
                )
            )
        finite = numeric.dropna().to_numpy(dtype=float)
        if len(finite) >= 4:
            median = float(np.median(finite))
            mad = float(np.median(np.abs(finite - median)))
            if mad > 0:
                robust_z = np.abs(finite - median) / (1.4826 * mad)
                count = int(np.count_nonzero(robust_z > 5.0))
                if count:
                    issues.append(
                        QCIssue(
                            "info",
                            "possible_outlier",
                            dataset.name,
                            channel.source_column,
                            f"{count} value(s) exceed robust z-score 5",
                        )
                    )
    return issues
