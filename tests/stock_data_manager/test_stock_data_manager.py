from datetime import datetime

import pandas as pd
from pandas.testing import assert_frame_equal

from stock_data_manager.managers.stock_data_manager import StockDataManager
from stock_data_manager.strategies.append_merge import AppendMergeStrategy


class FakeReader:
    def __init__(self, data=None):
        self.data = data
        self.paths = []

    def read(self, filepath):
        self.paths.append(filepath)
        return self.data


class FakeWriter:
    def __init__(self):
        self.calls = []

    def write(self, data, filepath):
        self.calls.append((data.copy(), filepath))


class FakeDownloader:
    def __init__(self, data):
        self.data = data
        self.configs = []

    def download(self, config):
        self.configs.append(config)
        return self.data


class FailingDownloader:
    def download(self, config):
        raise RuntimeError(f"download failed for {config.symbol}")


def test_download_and_save_downloads_incremental_data_merges_and_writes(tmp_path):
    existing = pd.DataFrame(
        {"Close": [10.0]},
        index=pd.to_datetime(["2024-01-01"]),
    )
    new = pd.DataFrame(
        {"Close": [11.0]},
        index=pd.to_datetime(["2024-01-02"]),
    )
    reader = FakeReader(existing)
    writer = FakeWriter()
    downloader = FakeDownloader(new)
    manager = StockDataManager(
        reader=reader,
        writer=writer,
        downloader=downloader,
        merge_strategy=AppendMergeStrategy(),
        data_dir=str(tmp_path),
    )

    result = manager.download_and_save("AAPL", interval="1d")

    expected = pd.DataFrame(
        {"Close": [10.0, 11.0]},
        index=pd.to_datetime(["2024-01-01", "2024-01-02"]),
    )
    assert_frame_equal(result, expected)
    assert downloader.configs[0].symbol == "AAPL"
    assert downloader.configs[0].start_date == "2024-01-02"
    assert downloader.configs[0].interval == "1d"
    assert writer.calls[0][1] == tmp_path / "AAPL.csv"
    assert_frame_equal(writer.calls[0][0], expected)


def test_download_and_save_returns_existing_data_when_already_current(tmp_path):
    today = datetime.now().strftime("%Y-%m-%d")
    existing = pd.DataFrame(
        {"Close": [10.0]},
        index=pd.to_datetime([today]),
    )
    reader = FakeReader(existing)
    writer = FakeWriter()
    downloader = FailingDownloader()
    manager = StockDataManager(
        reader=reader,
        writer=writer,
        downloader=downloader,
        merge_strategy=AppendMergeStrategy(),
        data_dir=str(tmp_path),
    )

    result = manager.download_and_save("AAPL")

    assert_frame_equal(result, existing)
    assert writer.calls == []


def test_download_multiple_returns_none_for_failed_symbol(tmp_path):
    manager = StockDataManager(
        reader=FakeReader(None),
        writer=FakeWriter(),
        downloader=FailingDownloader(),
        merge_strategy=AppendMergeStrategy(),
        data_dir=str(tmp_path),
    )

    result = manager.download_multiple(["AAPL"])

    assert result == {"AAPL": None}
