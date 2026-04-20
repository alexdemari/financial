import pandas as pd
from pandas.testing import assert_frame_equal

from stock_data_manager.strategies.append_merge import AppendMergeStrategy
from stock_data_manager.strategies.update_merge import UpdateMergeStrategy


def test_append_merge_keeps_new_rows_for_duplicate_dates_and_sorts_index():
    existing = pd.DataFrame(
        {"Close": [10.0, 11.0]},
        index=pd.to_datetime(["2024-01-01", "2024-01-02"]),
    )
    new = pd.DataFrame(
        {"Close": [12.0, 13.0]},
        index=pd.to_datetime(["2024-01-02", "2024-01-03"]),
    )

    result = AppendMergeStrategy().merge(existing, new)

    expected = pd.DataFrame(
        {"Close": [10.0, 12.0, 13.0]},
        index=pd.to_datetime(["2024-01-01", "2024-01-02", "2024-01-03"]),
    )
    assert_frame_equal(result, expected)


def test_update_merge_updates_existing_rows_and_appends_missing_rows():
    existing = pd.DataFrame(
        {"Close": [10.0, 11.0], "Volume": [100, 200]},
        index=pd.to_datetime(["2024-01-01", "2024-01-02"]),
    )
    new = pd.DataFrame(
        {"Close": [12.0, 13.0], "Volume": [250, 300]},
        index=pd.to_datetime(["2024-01-02", "2024-01-03"]),
    )

    result = UpdateMergeStrategy().merge(existing.copy(), new)

    expected = pd.DataFrame(
        {"Close": [10.0, 12.0, 13.0], "Volume": [100, 250, 300]},
        index=pd.to_datetime(["2024-01-01", "2024-01-02", "2024-01-03"]),
    )
    assert_frame_equal(result, expected)
