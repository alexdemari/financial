from types import SimpleNamespace

import pandas as pd

from options_tech_scanner.scan import scan_universe


def make_csv(path, rows: int = 220, volume: int = 2_000_000):
    pd.DataFrame(
        {
            "Date": pd.date_range("2026-01-01", periods=rows, freq="D"),
            "Open": [10.0] * rows,
            "High": [11.0] * rows,
            "Low": [9.0] * rows,
            "Close": [10.5] * rows,
            "Volume": [volume] * rows,
        }
    ).to_csv(path, index=False)


def test_scan_universe_generates_csv_and_sorts_top_results(
    tmp_path, monkeypatch, capsys
):
    universe_file = tmp_path / "universe.csv"
    pd.DataFrame(
        {
            "symbol": ["AAPL", "MSFT", "MISSING"],
            "market_cap": [2_000_000_000, 3_000_000_000, 4_000_000_000],
        }
    ).to_csv(universe_file, index=False)

    data_dir = tmp_path / "data"
    data_dir.mkdir()
    make_csv(data_dir / "AAPL.csv")
    make_csv(data_dir / "MSFT.csv")

    class FakeAnalyzer:
        def __init__(self, config=None, signal_model="rsi-sma"):
            self.signal_model = signal_model

        def generate_signal(self, symbol, df):
            if self.signal_model == "lux":
                if symbol == "AAPL":
                    return SimpleNamespace(
                        close_price=10.5,
                        combined_signal=1,
                        options_hint="CALL",
                        trend="BULLISH",
                        strength="STRONG",
                        adx=28.0,
                        confirmation_signal=1,
                        contrarian_signal=0,
                    )
                return SimpleNamespace(
                    close_price=10.5,
                    combined_signal=-1,
                    options_hint="PUT",
                    trend="BEARISH",
                    strength="NORMAL",
                    adx=18.0,
                    confirmation_signal=-1,
                    contrarian_signal=0,
                )

            if symbol == "AAPL":
                return SimpleNamespace(
                    close_price=10.5,
                    combined_signal=1,
                    options_hint="CALL",
                    long_signal=True,
                    short_signal=False,
                    swing_low_marker=False,
                    swing_high_marker=False,
                    in_discount=True,
                    in_premium=False,
                    bullish_rejection=False,
                    bearish_rejection=False,
                    bias="BULLISH",
                    range_position_pct=22.0,
                    rsi=45.0,
                )
            return SimpleNamespace(
                close_price=10.5,
                combined_signal=0,
                options_hint="NO_TRADE",
                long_signal=False,
                short_signal=False,
                swing_low_marker=False,
                swing_high_marker=False,
                in_discount=False,
                in_premium=False,
                bullish_rejection=False,
                bearish_rejection=False,
                bias="NEUTRAL",
                range_position_pct=50.0,
                rsi=50.0,
            )

    monkeypatch.setattr("options_tech_scanner.scan.StockDataAnalyzer", FakeAnalyzer)

    output_file = tmp_path / "scan.csv"
    result_df, written_path = scan_universe(
        universe_file=universe_file,
        data_dir=data_dir,
        min_market_cap=1_000_000_000,
        min_avg_volume_20=1_000_000,
        top=10,
        output=output_file,
    )

    eligible = result_df[result_df["eligible"]]
    assert written_path == output_file
    assert output_file.exists()
    assert eligible.iloc[0]["symbol"] == "AAPL"
    assert eligible.iloc[0]["consistency_score"] == 4
    assert eligible.iloc[0]["alignment"] == "bullish_aligned"
    assert (
        result_df.loc[result_df["symbol"] == "MISSING", "excluded_reason"].item()
        == "missing_csv"
    )

    stdout = capsys.readouterr().out
    assert "AAPL" in stdout
    assert "MSFT" in stdout
    assert "Exported:" in stdout
