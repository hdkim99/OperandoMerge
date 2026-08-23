from __future__ import annotations

from pathlib import Path

import numpy as np

from operandomerge.config import load_config
from operandomerge.service import MergeService


def test_example_recovers_known_ms_and_gc_delays() -> None:
    datasets, merge = load_config(Path(__file__).parents[2] / "examples" / "example-config.json")
    result = MergeService().run(datasets, merge)
    np.testing.assert_allclose(result.merged["experiment_time_s"], [0, 10, 20, 30])
    np.testing.assert_allclose(result.merged["ms__mz_44"], [0.1, 0.5, 1.0, 0.3])
    gc = result.merged.set_index("experiment_time_s")["gc__co2_area"]
    assert gc.loc[0] == 10
    assert gc.loc[20] == 60
    assert np.isnan(gc.loc[10]) and np.isnan(gc.loc[30])
    metadata = result.metadata.set_index("dataset")
    assert metadata.loc["ms", "total_delay_s"] == 2
    assert metadata.loc["gc", "total_delay_s"] == 5
