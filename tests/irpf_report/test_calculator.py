from __future__ import annotations

from datetime import date
from pathlib import Path
from unittest.mock import patch

import pytest

from irpf_report.calculator import (
    aggregate_by_asset_type,
    aggregate_by_month,
    compute_totals,
    enrich_trades,
)
from irpf_report.trades import Trade


def _trade(
    symbol: str,
    pnl_usd: float,
    trade_date: date,
    asset_type: str = "STK",
) -> Trade:
    return Trade(
        date=trade_date,
        symbol=symbol,
        asset_type=asset_type,
        quantity=10.0,
        proceeds_usd=abs(pnl_usd) + 100,
        cost_usd=100.0,
        pnl_usd=pnl_usd,
        currency="USD",
    )


def test_brl_conversion_multiplies_pnl_by_ptax(tmp_path: Path) -> None:
    trade = _trade("AAPL", pnl_usd=100.0, trade_date=date(2025, 3, 15))

    with patch("irpf_report.calculator.get_ptax", return_value=5.80):
        enriched = enrich_trades([trade], cache_dir=tmp_path)

    assert len(enriched) == 1
    assert enriched[0].ptax_rate == pytest.approx(5.80)
    assert enriched[0].pnl_brl == pytest.approx(580.00)


def test_brl_fields_are_none_when_ptax_missing(tmp_path: Path) -> None:
    trade = _trade("AAPL", pnl_usd=100.0, trade_date=date(2025, 3, 15))

    with patch("irpf_report.calculator.get_ptax", return_value=None):
        enriched = enrich_trades([trade], cache_dir=tmp_path)

    assert enriched[0].ptax_rate is None
    assert enriched[0].pnl_brl is None


def test_monthly_aggregation_groups_by_month(tmp_path: Path) -> None:
    trades_raw = [
        _trade("AAPL", 100.0, date(2025, 3, 1)),
        _trade("MSFT", 200.0, date(2025, 3, 15)),
        _trade("GOOG", -50.0, date(2025, 3, 20)),
        _trade("AMZN", 400.0, date(2025, 4, 5)),
        _trade("TSLA", 600.0, date(2025, 4, 22)),
    ]

    ptax_by_date = {
        date(2025, 3, 1): 5.80,
        date(2025, 3, 15): 5.80,
        date(2025, 3, 20): 5.80,
        date(2025, 4, 5): 5.90,
        date(2025, 4, 22): 5.90,
    }

    with patch(
        "irpf_report.calculator.get_ptax", side_effect=lambda d, **kw: ptax_by_date[d]
    ):
        enriched = enrich_trades(trades_raw, cache_dir=tmp_path)

    monthly = aggregate_by_month(enriched)

    assert len(monthly) == 2
    march = monthly[0]
    april = monthly[1]
    assert march.month == "Mar/2025"
    assert march.gross_gain_brl == pytest.approx((100.0 + 200.0) * 5.80)
    assert march.gross_loss_brl == pytest.approx(-50.0 * 5.80)
    assert april.month == "Apr/2025"
    assert april.gross_gain_brl == pytest.approx((400.0 + 600.0) * 5.90)


def test_compute_totals_brl_incomplete_when_ptax_missing(tmp_path: Path) -> None:
    trades_raw = [
        _trade("AAPL", 200.0, date(2025, 3, 15)),
        _trade("MSFT", 100.0, date(2025, 4, 10)),
    ]
    ptax_by_date: dict[date, float | None] = {
        date(2025, 3, 15): 5.80,
        date(2025, 4, 10): None,  # BCB unavailable
    }

    with patch(
        "irpf_report.calculator.get_ptax", side_effect=lambda d, **kw: ptax_by_date[d]
    ):
        enriched = enrich_trades(trades_raw, cache_dir=tmp_path)

    totals = compute_totals(enriched)

    assert totals.brl_incomplete is True
    # Only AAPL has BRL; MSFT excluded from gain_brl
    assert totals.gain_brl == pytest.approx(200.0 * 5.80)


def test_asset_type_aggregation_groups_correctly(tmp_path: Path) -> None:
    trades_raw = [
        _trade("AAPL", 100.0, date(2025, 3, 1), asset_type="STK"),
        _trade("MSFT", 200.0, date(2025, 3, 2), asset_type="STK"),
        _trade("PEP 250718P140", 50.0, date(2025, 3, 3), asset_type="OPT"),
    ]

    with patch("irpf_report.calculator.get_ptax", return_value=5.80):
        enriched = enrich_trades(trades_raw, cache_dir=tmp_path)

    summaries = aggregate_by_asset_type(enriched)

    assert len(summaries) == 2
    opt = next(s for s in summaries if s.asset_type == "OPT")
    stk = next(s for s in summaries if s.asset_type == "STK")
    assert stk.trade_count == 2
    assert stk.net_usd == pytest.approx(300.0)
    assert stk.net_brl == pytest.approx(300.0 * 5.80)
    assert opt.trade_count == 1
    assert opt.net_usd == pytest.approx(50.0)
    assert opt.brl_incomplete is False
