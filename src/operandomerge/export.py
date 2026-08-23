"""Reproducible CSV/Excel and figure exports."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import pandas as pd
from matplotlib.figure import Figure

from operandomerge.models import MergeResult


def qc_frame(result: MergeResult) -> pd.DataFrame:
    return pd.DataFrame(
        [issue.as_dict() for issue in result.qc],
        columns=["severity", "code", "dataset", "channel", "message", "row"],
    )


def configuration_frame(configuration: dict[str, Any]) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {"setting": key, "value": json.dumps(value) if value is not None else ""}
            for key, value in configuration.items()
        ]
    )


def export_excel(result: MergeResult, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with pd.ExcelWriter(path, engine="openpyxl") as writer:
        result.merged.to_excel(writer, sheet_name="merged", index=False)
        result.metadata.to_excel(writer, sheet_name="metadata", index=False)
        result.provenance.to_excel(writer, sheet_name="provenance", index=False)
        qc_frame(result).to_excel(writer, sheet_name="qc", index=False)
        configuration_frame(result.configuration).to_excel(
            writer, sheet_name="configuration", index=False
        )


def export_csv_bundle(result: MergeResult, directory: Path) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    result.merged.to_csv(directory / "merged.csv", index=False)
    result.metadata.to_csv(directory / "metadata.csv", index=False)
    result.provenance.to_csv(directory / "provenance.csv", index=False)
    qc_frame(result).to_csv(directory / "qc.csv", index=False)
    configuration_frame(result.configuration).to_csv(directory / "configuration.csv", index=False)


def plot_alignment(result: MergeResult, path: Path | None = None) -> Figure:
    figure, axis = plt.subplots(figsize=(9, 5), constrained_layout=True)
    time = result.merged["experiment_time_s"]
    for column in result.merged.columns[1:]:
        axis.plot(time, result.merged[column], marker=".", linewidth=1, label=column)
    axis.set_xlabel("Experiment time / s")
    axis.set_ylabel("Signal (source units)")
    axis.set_title("OperandoMerge alignment preview")
    if len(result.merged.columns) > 1:
        axis.legend(loc="best", fontsize="small")
    if path is not None:
        path.parent.mkdir(parents=True, exist_ok=True)
        figure.savefig(path, dpi=160)
    return figure
