import pandas as pd

from stock_data_manager.cli import CLI, PROJECT_ROOT, SymbolsLoader
from stock_data_manager.factories import StockDataManagerFactory


class FakeManager:
    def __init__(self):
        self.calls = []

    def download_multiple(self, symbols, force_full=False, interval="1d"):
        self.calls.append(
            {
                "symbols": symbols,
                "force_full": force_full,
                "interval": interval,
            }
        )
        return {
            symbol: pd.DataFrame(
                {"Close": [10.0]},
                index=pd.to_datetime(["2024-01-01"]),
            )
            for symbol in symbols
        }


def test_factory_is_exported_from_factories_package():
    assert StockDataManagerFactory.__name__ == "StockDataManagerFactory"


def test_cli_uses_custom_data_dir_for_default_strategy(monkeypatch, tmp_path):
    manager = FakeManager()
    factory_calls = []

    def create_default(data_dir, storage="csv", db_path="data/financial.db"):
        factory_calls.append(
            {"data_dir": data_dir, "storage": storage, "db_path": db_path}
        )
        return manager

    monkeypatch.setattr(
        "stock_data_manager.cli.StockDataManagerFactory.create_default",
        create_default,
    )

    exit_code = CLI().run(["-s", "AAPL", "-d", str(tmp_path), "-i", "1d"])

    assert exit_code == 0
    assert factory_calls == [
        {"data_dir": str(tmp_path), "storage": "csv", "db_path": "data/financial.db"}
    ]
    assert manager.calls == [
        {"symbols": ["AAPL"], "force_full": False, "interval": "1d"}
    ]


def test_cli_uses_interval_based_default_data_dir(monkeypatch):
    manager = FakeManager()
    factory_calls = []

    def create_default(data_dir, storage="csv", db_path="data/financial.db"):
        factory_calls.append(
            {"data_dir": data_dir, "storage": storage, "db_path": db_path}
        )
        return manager

    monkeypatch.setattr(
        "stock_data_manager.cli.StockDataManagerFactory.create_default",
        create_default,
    )

    exit_code = CLI().run(["-s", "AAPL", "-i", "1w"])

    assert exit_code == 0
    assert factory_calls == [
        {
            "data_dir": f"{PROJECT_ROOT}/data/stocks/1W",
            "storage": "csv",
            "db_path": "data/financial.db",
        }
    ]
    assert manager.calls == [
        {"symbols": ["AAPL"], "force_full": False, "interval": "1w"}
    ]


def test_cli_uses_custom_data_dir_for_update_strategy(monkeypatch, tmp_path):
    manager = FakeManager()
    factory_calls = []

    def create_with_update_strategy(
        data_dir, storage="csv", db_path="data/financial.db"
    ):
        factory_calls.append(
            {"data_dir": data_dir, "storage": storage, "db_path": db_path}
        )
        return manager

    monkeypatch.setattr(
        "stock_data_manager.cli.StockDataManagerFactory.create_with_update_strategy",
        create_with_update_strategy,
    )

    exit_code = CLI().run(
        ["-s", "AAPL", "-d", str(tmp_path), "-i", "1w", "--strategy", "update"]
    )

    assert exit_code == 0
    assert factory_calls == [
        {"data_dir": str(tmp_path), "storage": "csv", "db_path": "data/financial.db"}
    ]
    assert manager.calls == [
        {"symbols": ["AAPL"], "force_full": False, "interval": "1w"}
    ]


def test_cli_rejects_unsupported_interval():
    try:
        CLI().parse_args(["-s", "AAPL", "-i", "1h"])
    except SystemExit as exc:
        assert exc.code == 2
    else:
        raise AssertionError("Expected unsupported interval to exit with code 2")


def test_cli_passes_sqlite_storage_options(monkeypatch, tmp_path):
    manager = FakeManager()
    factory_calls = []
    db_path = tmp_path / "financial.db"

    def create_default(data_dir, storage="csv", db_path="data/financial.db"):
        factory_calls.append(
            {"data_dir": data_dir, "storage": storage, "db_path": db_path}
        )
        return manager

    monkeypatch.setattr(
        "stock_data_manager.cli.StockDataManagerFactory.create_default",
        create_default,
    )

    exit_code = CLI().run(
        [
            "-s",
            "AAPL",
            "-d",
            str(tmp_path),
            "--storage",
            "sqlite",
            "--db-path",
            str(db_path),
        ]
    )

    assert exit_code == 0
    assert factory_calls == [
        {
            "data_dir": str(tmp_path),
            "storage": "sqlite",
            "db_path": str(db_path),
        }
    ]


def test_symbols_loader_reads_text_file(tmp_path):
    symbols_file = tmp_path / "symbols.txt"
    symbols_file.write_text("# comment\nAAPL\n\nMSFT\n", encoding="utf-8")

    symbols = SymbolsLoader.from_file(str(symbols_file))

    assert symbols == ["AAPL", "MSFT"]


def test_symbols_loader_reads_csv_symbol_column(tmp_path):
    symbols_file = tmp_path / "symbols.csv"
    symbols_file.write_text(
        "symbol,name\nAAPL,Apple\nMSFT,Microsoft\n", encoding="utf-8"
    )

    symbols = SymbolsLoader.from_file(str(symbols_file))

    assert symbols == ["AAPL", "MSFT"]
