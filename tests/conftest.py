from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest


@pytest.fixture
def table_writer(tmp_path: Path):
    def write(name: str, data: dict[str, list[object]], *, excel: bool = False) -> Path:
        suffix = ".xlsx" if excel else ".csv"
        path = tmp_path / f"{name}{suffix}"
        frame = pd.DataFrame(data)
        if excel:
            frame.to_excel(path, index=False)
        else:
            frame.to_csv(path, index=False)
        return path

    return write
