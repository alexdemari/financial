import json

import pandas as pd

from options_tech_scanner.universe_loader import load_universe


def test_load_universe_from_tradingview_json_extracts_market_cap(tmp_path):
    universe_file = tmp_path / "universe.json"
    payload = {
        "data": [
            {"s": "NASDAQ:AAPL", "d": ["AAPL"] * 15 + [3_000_000_000_000]},
            {"s": "NYSE:IBM", "d": ["IBM"] * 15 + [200_000_000_000]},
        ]
    }
    universe_file.write_text(json.dumps(payload), encoding="utf-8")

    result = load_universe(universe_file)

    assert result.to_dict("records") == [
        {"symbol": "AAPL", "market_cap": 3_000_000_000_000},
        {"symbol": "IBM", "market_cap": 200_000_000_000},
    ]


def test_load_universe_from_csv_normalizes_market_cap_column(tmp_path):
    universe_file = tmp_path / "universe.csv"
    pd.DataFrame(
        {
            "symbol": ["aapl", "msft"],
            "market_cap_basic": [1_000_000_000, 2_000_000_000],
        }
    ).to_csv(universe_file, index=False)

    result = load_universe(universe_file)

    assert result.to_dict("records") == [
        {"symbol": "AAPL", "market_cap": 1_000_000_000},
        {"symbol": "MSFT", "market_cap": 2_000_000_000},
    ]
