from __future__ import annotations

from operandomerge.models import ChannelConfig, DatasetConfig, TimeRepresentation
from operandomerge.service import MergeService


def test_qc_reports_duplicate_missing_and_non_numeric_values(table_writer) -> None:
    path = table_writer("quality", {"time": [0, 0, 2, 3], "signal": [1, None, "bad", 100]})
    config = DatasetConfig(
        path=path,
        name="quality",
        time_column="time",
        time_representation=TimeRepresentation.ELAPSED_SECONDS,
        channels=(ChannelConfig("signal"),),
    )
    result = MergeService().run([config])
    codes = [issue.code for issue in result.qc]
    assert codes.count("duplicate_timestamp") == 2
    assert "missing_data" in codes
    assert "non_numeric_channel" in codes
