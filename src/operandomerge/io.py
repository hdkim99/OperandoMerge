"""Tabular input with lossless source-column preservation."""

from __future__ import annotations

from pathlib import Path

import pandas as pd


def read_table(path: Path, sheet_name: str | int | None = 0) -> pd.DataFrame:
    """Read CSV or XLSX without altering source values."""

    if not path.exists():
        raise FileNotFoundError(path)
    suffix = path.suffix.lower()
    if suffix == ".csv":
        return pd.read_csv(path)
    if suffix in {".xlsx", ".xlsm"}:
        frame = pd.read_excel(path, sheet_name=sheet_name)
        if not isinstance(frame, pd.DataFrame):
            raise ValueError("A single Excel sheet must be selected")
        return frame
    raise ValueError(f"Unsupported input format {suffix!r}; use CSV or XLSX")


def inspect_columns(path: Path, sheet_name: str | int | None = 0) -> list[str]:
    return list(read_table(path, sheet_name).columns.astype(str))

