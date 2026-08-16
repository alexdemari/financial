from __future__ import annotations

from datetime import date
from types import SimpleNamespace
from unittest.mock import MagicMock

import pandas as pd
import pytest

import market_scanner.options_screener as screener
from market_scanner.options_screener import (
    OptionsCandidate,
    classify_iv_quadrant,
    compute_iv_percentiles,
    fetch_ibkr_iv_data,
    fetch_ibkr_underlying_iv_history,
    map_strategy,
    score_candidate,
    screen_options_candidates,
)


AS_OF_DATE = date(2026, 7, 9)
EXPIRATION = "2026-08-14"


@pytest.fixture(autouse=True)
def _ibkr_gateway_unavailable(monkeypatch):
    """Default: IBKR Gateway unreachable — `_evaluate_symbol` falls back to
    the legacy yfinance-only IV path. Real network calls are never allowed
    in tests (AGENTS.md); tests that want the IBKR-available path patch
    `ibkr_positions.client.IBKRClient` themselves, overriding this."""
    from ibkr_positions.client import IBKRConnectionError

    client_cls = MagicMock()
    client_cls.return_value.connect.side_effect = IBKRConnectionError(
        "mock: gateway unavailable in tests"
    )
    monkeypatch.setattr("ibkr_positions.client.IBKRClient", client_cls)
    return client_cls


def _scanner_row(
    symbol: str = "NVDA",
    market_state: str = "pullback",
    adjusted_alignment: str = "bullish_aligned",
    action_bucket: str = "candidate",
) -> dict:
    return {
        "symbol": symbol,
        "action_bucket": action_bucket,
        "market_state": market_state,
        "adjusted_alignment": adjusted_alignment,
    }


def _option_chain(
    *,
    bid: float = 2.80,
    ask: float = 3.00,
    strike: float = 100.0,
    delta: float = -0.24,
    implied_volatility: float = 0.35,
    volume: int = 700,
    open_interest: int = 2_000,
) -> MagicMock:
    contracts = pd.DataFrame(
        [
            {
                "strike": strike,
                "bid": bid,
                "ask": ask,
                "delta": delta,
                "impliedVolatility": implied_volatility,
                "volume": volume,
                "openInterest": open_interest,
            }
        ]
    )
    chain = MagicMock()
    chain.puts = contracts
    chain.calls = contracts.assign(delta=abs(delta))
    return chain


def _ticker(chain: MagicMock | None = None) -> MagicMock:
    ticker = MagicMock()
    ticker.options = [EXPIRATION]
    ticker.fast_info = SimpleNamespace(
        last_price=105.0,
        market_cap=100_000_000_000,
        ten_day_average_volume=5_000_000,
    )
    ticker.calendar = None
    ticker.option_chain.return_value = chain or _option_chain()
    return ticker


def _patch_yfinance(monkeypatch, ticker: MagicMock) -> None:
    yf_mock = MagicMock()
    yf_mock.Ticker.return_value = ticker
    monkeypatch.setattr(screener, "_YF_AVAILABLE", True)
    monkeypatch.setattr(screener, "yf", yf_mock)


def test_map_strategy_pullback_bullish_returns_csp() -> None:
    assert map_strategy("pullback", "bullish_aligned") == "CSP"


def test_map_strategy_extended_bullish_returns_cc() -> None:
    assert map_strategy("extended", "bullish_aligned") == "CC"


def test_map_strategy_conflicted_returns_none() -> None:
    assert map_strategy("extended", "conflicted") is None


def test_layer1_excludes_low_ivr(monkeypatch) -> None:
    ticker = _ticker()
    _patch_yfinance(monkeypatch, ticker)
    monkeypatch.setattr(screener, "compute_ivr", lambda _ticker, _iv: 18.0)

    candidates, exclusions = screen_options_candidates(
        [_scanner_row()],
        as_of_date=AS_OF_DATE,
    )

    assert candidates == []
    assert exclusions[0]["symbol"] == "NVDA"
    assert "IVR 18" in exclusions[0]["reason"]


def test_layer1_excludes_earnings_within_dte(monkeypatch) -> None:
    ticker = _ticker()
    ticker.calendar = {"Earnings Date": date(2026, 8, 1)}
    _patch_yfinance(monkeypatch, ticker)
    monkeypatch.setattr(screener, "compute_ivr", lambda _ticker, _iv: 70.0)

    candidates, exclusions = screen_options_candidates(
        [_scanner_row()],
        as_of_date=AS_OF_DATE,
    )

    assert candidates == []
    assert "earnings 2026-08-01" in exclusions[0]["reason"]


def test_layer3_excludes_wide_spread(monkeypatch) -> None:
    ticker = _ticker(_option_chain(bid=0.50, ask=1.50))
    _patch_yfinance(monkeypatch, ticker)
    monkeypatch.setattr(screener, "compute_ivr", lambda _ticker, _iv: 70.0)

    candidates, exclusions = screen_options_candidates(
        [_scanner_row()],
        as_of_date=AS_OF_DATE,
    )

    assert candidates == []
    assert "spread" in exclusions[0]["reason"]


def test_layer3_excludes_low_monthly_return(monkeypatch) -> None:
    ticker = _ticker(_option_chain(bid=0.59, ask=0.61, strike=1_000.0))
    _patch_yfinance(monkeypatch, ticker)
    monkeypatch.setattr(screener, "compute_ivr", lambda _ticker, _iv: 70.0)

    candidates, exclusions = screen_options_candidates(
        [_scanner_row()],
        as_of_date=AS_OF_DATE,
    )

    assert candidates == []
    assert "retorno mensal" in exclusions[0]["reason"]


def test_score_ranking_ivr_weight() -> None:
    high_ivr = _candidate(symbol="A", ivr_approx=80.0, monthly_return_pct=0.8)
    high_return = _candidate(symbol="B", ivr_approx=40.0, monthly_return_pct=1.2)

    assert score_candidate(high_ivr) > score_candidate(high_return)


def test_classify_quadrant_venda_confiante() -> None:
    assert classify_iv_quadrant(70.0, 80.0) == "venda_confiante"


def test_classify_quadrant_spike_pontual() -> None:
    assert classify_iv_quadrant(75.0, 20.0) == "spike_pontual"


def test_classify_quadrant_ambiente_comprimido() -> None:
    assert classify_iv_quadrant(20.0, 80.0) == "ambiente_comprimido"


def test_classify_quadrant_indefinido_when_ivp_missing() -> None:
    assert classify_iv_quadrant(70.0, None) == "indefinido"


def test_fetch_ibkr_iv_data_handles_invalid_flag(monkeypatch) -> None:
    client = MagicMock()
    client.return_value.get_option_market_data.return_value = {
        "implied_vol": {"annual_iv": -1, "is_valid": False},
    }
    monkeypatch.setattr("ibkr_positions.client.IBKRClient", client)

    result = fetch_ibkr_iv_data(
        {"symbol": "AAPL", "expiration": EXPIRATION, "strike": 100, "right": "PUT"}
    )

    assert result["iv_source"] == "unavailable"
    assert result["iv_percentile_52w"] is None


def test_fetch_ibkr_iv_data_uses_ibkr_date_format(monkeypatch) -> None:
    client = MagicMock()
    client.return_value.get_option_market_data.return_value = {"implied_vol": 0.28}
    monkeypatch.setattr("ibkr_positions.client.IBKRClient", client)

    fetch_ibkr_iv_data(
        {"symbol": "AAPL", "expiration": "2026-08-14", "strike": 100, "right": "PUT"}
    )

    call_kwargs = client.return_value.get_option_market_data.call_args.kwargs
    assert call_kwargs["expiration"] == "20260814"


def test_fetch_ibkr_iv_data_skips_network_when_client_is_none() -> None:
    result = fetch_ibkr_iv_data(
        {"symbol": "AAPL", "expiration": EXPIRATION, "strike": 100, "right": "PUT"},
        client=None,
    )

    assert result["iv_source"] == "unavailable"


def test_fetch_ibkr_iv_data_reuses_percentiles_from_shared_history(monkeypatch) -> None:
    client = MagicMock()
    client.get_option_market_data.return_value = {"implied_vol": 0.30}

    result = fetch_ibkr_iv_data(
        {"symbol": "AAPL", "expiration": EXPIRATION, "strike": 100, "right": "PUT"},
        iv_history=[0.20] * 64 + [0.30],  # exactly 65 bars: full 13w window
        client=client,
    )

    assert result["iv_source"] == "ibkr"
    assert result["iv_underlying_pct"] == 30.0
    assert result["iv_percentile_13w"] == 100.0
    assert result["iv_percentile_26w"] is None  # < 130 bars of history here
    client.connect.assert_not_called()  # reused shared connection, no reconnect
    client.disconnect.assert_not_called()


def test_compute_iv_percentiles_ranks_current_within_window() -> None:
    history = [0.10 + 0.01 * i for i in range(65)]  # strictly increasing, current=high

    percentiles = compute_iv_percentiles(history)

    assert percentiles["13w"] == 100.0
    assert percentiles["26w"] is None
    assert percentiles["52w"] is None


def test_compute_iv_percentiles_empty_history_returns_none() -> None:
    assert compute_iv_percentiles([]) == {"13w": None, "26w": None, "52w": None}


def test_fetch_ibkr_underlying_iv_history_returns_series() -> None:
    client = MagicMock()
    client.get_underlying_iv_history.return_value = [
        {"date": date(2026, 7, 1), "iv": 0.20},
        {"date": date(2026, 7, 2), "iv": 0.22},
    ]

    history = fetch_ibkr_underlying_iv_history("AAPL", client=client)

    assert history == [0.20, 0.22]
    client.connect.assert_not_called()  # shared client — caller owns lifecycle


def test_fetch_ibkr_underlying_iv_history_never_raises_on_error() -> None:
    client = MagicMock()
    client.get_underlying_iv_history.side_effect = RuntimeError("boom")

    assert fetch_ibkr_underlying_iv_history("AAPL", client=client) == []


def test_score_uses_real_ivp_weights() -> None:
    candidate = _candidate(symbol="A", ivr_approx=60.0, monthly_return_pct=1.0)
    candidate = OptionsCandidate(**(candidate.__dict__ | {"iv_percentile_52w": 80.0}))

    assert score_candidate(candidate) == 0.625


def test_score_falls_back_to_legacy_weights_when_ivp_missing() -> None:
    candidate = _candidate(symbol="A", ivr_approx=60.0, monthly_return_pct=1.0)

    assert score_candidate(candidate) == 0.56


def test_screen_completes_without_crash_on_ibkr_error(monkeypatch) -> None:
    # IBKR Gateway unavailable is the default via the autouse
    # `_ibkr_gateway_unavailable` fixture — screening must still complete,
    # falling back to legacy yfinance-only IV/scoring for every candidate.
    ticker = _ticker()
    _patch_yfinance(monkeypatch, ticker)
    monkeypatch.setattr(screener, "compute_ivr", lambda _ticker, _iv: 70.0)

    candidates, exclusions = screen_options_candidates(
        [_scanner_row()], as_of_date=AS_OF_DATE
    )

    assert len(candidates) == 1
    assert candidates[0].iv_source == "unavailable"
    assert exclusions == []


def test_existing_position_excluded(monkeypatch) -> None:
    monkeypatch.setattr(screener, "_load_open_position_symbols", lambda _path: {"NVDA"})

    candidates, exclusions = screen_options_candidates(
        [_scanner_row()],
        portfolio_path="options_tracker.csv",
        as_of_date=AS_OF_DATE,
    )

    assert candidates == []
    assert exclusions == [{"symbol": "NVDA", "reason": "já em posição aberta"}]


def test_screen_completes_without_crash_on_network_error(monkeypatch) -> None:
    yf_mock = MagicMock()
    yf_mock.Ticker.side_effect = RuntimeError("network error")
    monkeypatch.setattr(screener, "_YF_AVAILABLE", True)
    monkeypatch.setattr(screener, "yf", yf_mock)

    candidates, exclusions = screen_options_candidates(
        [_scanner_row()],
        as_of_date=AS_OF_DATE,
    )

    assert candidates == []
    assert "network error" in exclusions[0]["reason"]


def test_screen_respects_top_n(monkeypatch) -> None:
    ticker = _ticker()
    _patch_yfinance(monkeypatch, ticker)
    monkeypatch.setattr(screener, "compute_ivr", lambda _ticker, _iv: 70.0)

    candidates, exclusions = screen_options_candidates(
        [_scanner_row("A"), _scanner_row("B")],
        top_n=1,
        as_of_date=AS_OF_DATE,
    )

    assert exclusions == []
    assert [candidate.symbol for candidate in candidates] == ["A"]


def _candidate(
    *,
    symbol: str,
    ivr_approx: float,
    monthly_return_pct: float,
    spread_pct: float = 4.0,
) -> OptionsCandidate:
    return OptionsCandidate(
        symbol=symbol,
        strategy="CSP",
        expiration=EXPIRATION,
        dte=36,
        strike=100.0,
        option_type="PUT",
        delta=0.24,
        iv_pct=35.0,
        ivr_approx=ivr_approx,
        bid=2.8,
        ask=3.0,
        mid=2.9,
        spread_pct=spread_pct,
        premium=2.9,
        collateral=10_000.0,
        monthly_return_pct=monthly_return_pct,
        market_state="pullback",
        adjusted_alignment="bullish_aligned",
        earnings_date=None,
        score=0.0,
    )
