"""Tests for main.py CLI helpers."""

from pathlib import Path

import pandas as pd

from ibkr_trades.main import _tag_history


def test_tag_history_normalizes_legacy_raw_option_type(tmp_path: Path):
    """Rows persisted before normalize_option_type existed store raw 'C'/'P'.

    _tag_history must self-heal those on every run so strategy_tagger and
    roll_detector (which compare against 'CALL'/'PUT') can match them.
    """
    history = tmp_path / "trades_history.csv"
    pd.DataFrame(
        [
            {
                "trade_id": "LEGACY-1",
                "date": "2026-07-01",
                "datetime": "2026-07-01T13:54:18+00:00",
                "symbol": "FSLY  260717P00015000",
                "underlying": "FSLY",
                "asset_type": "OPT",
                "option_type": "P",
                "strike": 15.0,
                "expiration": "2099-07-17",
                "quantity": -5.0,
                "price": 0.70,
                "proceeds": 350.0,
                "commission": 0.0,
                "pnl_realized": None,
                "currency": "USD",
                "open_close": "O",
                "source": "api",
                "roll_id": None,
                "strategy": None,
            }
        ]
    ).to_csv(history, index=False)

    _tag_history(history)

    result = pd.read_csv(history, dtype={"trade_id": str})
    assert result["option_type"].tolist() == ["PUT"]
    assert result["strategy"].tolist() == ["csp"]
