from unittest.mock import MagicMock

import pytest

from market_scanner.macro_context import (
    MacroSnapshot,
    fetch_macro,
    format_macro_block,
    format_macro_prompt_block,
)


def _make_snap(**kwargs) -> MacroSnapshot:
    defaults = dict(
        selic_pct=14.75,
        usd_brl=5.8901,
        sp500_close=5473.0,
        sp500_change_pct=0.43,
        ibov_close=137420.0,
        ibov_change_pct=-0.22,
        fetched_at="2026-06-24T12:00:00+00:00",
    )
    defaults.update(kwargs)
    return MacroSnapshot(**defaults)


def _make_fast_info(last_price: float, previous_close: float) -> MagicMock:
    info = MagicMock()
    info.last_price = last_price
    info.previous_close = previous_close
    return info


# ---------------------------------------------------------------------------
# fetch_macro
# ---------------------------------------------------------------------------


def test_fetch_macro_returns_snapshot_on_success(monkeypatch):
    selic_json = b'[{"valor": "14.75"}]'
    ptax_json = b'{"value": [{"cotacaoVenda": 5.8901}]}'

    def fake_urlopen(url, timeout=5):
        ctx = MagicMock()
        if "bcdata.sgs.432" in url:
            ctx.__enter__ = lambda s: MagicMock(read=lambda: selic_json)
        else:
            ctx.__enter__ = lambda s: MagicMock(read=lambda: ptax_json)
        ctx.__exit__ = MagicMock(return_value=False)
        return ctx

    monkeypatch.setattr(
        "market_scanner.macro_context.urllib.request.urlopen", fake_urlopen
    )

    mock_ticker = MagicMock()
    mock_ticker.fast_info = _make_fast_info(5473.0, 5449.5)
    monkeypatch.setattr("yfinance.Ticker", lambda sym: mock_ticker)

    snap = fetch_macro()

    assert snap.selic_pct == pytest.approx(14.75)
    assert snap.usd_brl == pytest.approx(5.8901)
    assert snap.sp500_close == pytest.approx(5473.0)
    assert snap.sp500_change_pct is not None
    assert snap.ibov_close == pytest.approx(5473.0)
    assert snap.fetched_at != ""


def test_fetch_macro_degrades_when_bcb_selic_fails(monkeypatch):
    ptax_json = b'{"value": [{"cotacaoVenda": 5.89}]}'

    def fake_urlopen(url, timeout=5):
        if "bcdata.sgs.432" in url:
            raise OSError("network error")
        ctx = MagicMock()
        ctx.__enter__ = lambda s: MagicMock(read=lambda: ptax_json)
        ctx.__exit__ = MagicMock(return_value=False)
        return ctx

    monkeypatch.setattr(
        "market_scanner.macro_context.urllib.request.urlopen", fake_urlopen
    )

    mock_ticker = MagicMock()
    mock_ticker.fast_info = _make_fast_info(5000.0, 4975.0)
    monkeypatch.setattr("yfinance.Ticker", lambda sym: mock_ticker)

    snap = fetch_macro()

    assert snap.selic_pct is None
    assert snap.usd_brl == pytest.approx(5.89)
    assert snap.sp500_close is not None


def test_fetch_macro_degrades_when_ptax_fails(monkeypatch):
    selic_json = b'[{"valor": "14.75"}]'

    def fake_urlopen(url, timeout=5):
        if "PTAX" in url:
            raise OSError("network error")
        ctx = MagicMock()
        ctx.__enter__ = lambda s: MagicMock(read=lambda: selic_json)
        ctx.__exit__ = MagicMock(return_value=False)
        return ctx

    monkeypatch.setattr(
        "market_scanner.macro_context.urllib.request.urlopen", fake_urlopen
    )

    mock_ticker = MagicMock()
    mock_ticker.fast_info = _make_fast_info(5000.0, 4975.0)
    monkeypatch.setattr("yfinance.Ticker", lambda sym: mock_ticker)

    snap = fetch_macro()

    assert snap.selic_pct == pytest.approx(14.75)
    assert snap.usd_brl is None
    assert snap.sp500_close is not None


def test_fetch_macro_degrades_when_yfinance_fails(monkeypatch):
    selic_json = b'[{"valor": "14.75"}]'
    ptax_json = b'{"value": [{"cotacaoVenda": 5.89}]}'

    def fake_urlopen(url, timeout=5):
        ctx = MagicMock()
        if "bcdata.sgs.432" in url:
            ctx.__enter__ = lambda s: MagicMock(read=lambda: selic_json)
        else:
            ctx.__enter__ = lambda s: MagicMock(read=lambda: ptax_json)
        ctx.__exit__ = MagicMock(return_value=False)
        return ctx

    monkeypatch.setattr(
        "market_scanner.macro_context.urllib.request.urlopen", fake_urlopen
    )
    monkeypatch.setattr(
        "yfinance.Ticker", MagicMock(side_effect=RuntimeError("yf down"))
    )

    snap = fetch_macro()

    assert snap.selic_pct == pytest.approx(14.75)
    assert snap.usd_brl == pytest.approx(5.89)
    assert snap.sp500_close is None
    assert snap.sp500_change_pct is None
    assert snap.ibov_close is None
    assert snap.ibov_change_pct is None


# ---------------------------------------------------------------------------
# format_macro_block
# ---------------------------------------------------------------------------


def test_format_macro_block_shows_na_for_missing_fields():
    snap = MacroSnapshot(
        selic_pct=None,
        usd_brl=None,
        sp500_close=None,
        sp500_change_pct=None,
        ibov_close=None,
        ibov_change_pct=None,
        fetched_at="2026-06-24T00:00:00+00:00",
    )
    block = format_macro_block(snap)

    assert "N/A" in block
    assert "Selic" in block
    assert "USD/BRL" in block
    assert "S&P 500" in block
    assert "Ibovespa" in block


def test_format_macro_block_renders_values():
    snap = _make_snap()
    block = format_macro_block(snap)

    assert "14.75%" in block
    assert "5.8901" in block
    assert "2026-06-24" in block


# ---------------------------------------------------------------------------
# format_macro_prompt_block
# ---------------------------------------------------------------------------


def test_format_macro_prompt_block_under_150_tokens():
    snap = _make_snap()
    text = format_macro_prompt_block(snap)
    assert len(text.split()) < 150


def test_format_macro_prompt_block_na_when_all_none():
    snap = MacroSnapshot(
        selic_pct=None,
        usd_brl=None,
        sp500_close=None,
        sp500_change_pct=None,
        ibov_close=None,
        ibov_change_pct=None,
        fetched_at="2026-06-24T00:00:00+00:00",
    )
    text = format_macro_prompt_block(snap)
    assert "N/A" in text
    assert len(text.split()) < 150
