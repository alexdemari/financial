"""Rank options candidates for premium-selling setups.

This module is intentionally separate from options_filter.py. The older module
keeps the lightweight liquidity verdict used by --options-filter; this module
builds contract-level CSP/CC candidates for the opt-in --options-screener flow.
"""

from __future__ import annotations

import asyncio
import logging
import math
import threading
import warnings
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

import pandas as pd

try:
    import numpy as np
    import yfinance as yf

    _YF_AVAILABLE = True
except ImportError:
    np = None  # type: ignore[assignment]
    yf = None  # type: ignore[assignment]
    _YF_AVAILABLE = False

logger = logging.getLogger(__name__)

IVR_THRESHOLD = 50.0
IVP_THRESHOLD = 50.0
WEIGHTS_FULLY_REAL = {
    "ivr_real": 0.25,
    "ivp_real": 0.25,
    "return": 0.35,
    "spread": 0.15,
}
WEIGHTS_PARTIAL_REAL = {"iv_real": 0.30, "return": 0.45, "spread": 0.25}
WEIGHTS_LEGACY = {"ivr_approx": 0.40, "return": 0.40, "spread": 0.20}
_IBKR_REQUEST_LOCK = threading.Lock()


LAYER1_FILTERS = {
    "min_option_volume": 500,
    "min_open_interest": 1_000,
    "min_stock_volume": 1_000_000,
    "min_market_cap_b": 5,
    "iv_min_pct": 20,
    "iv_max_pct": 60,
    "ivr_min": 30,
    "earnings_buffer_days": 5,
    "min_price": 10.0,
}

LAYER3_FILTERS = {
    "dte_min": 30,
    "dte_max": 45,
    "delta_min": 0.18,
    "delta_max": 0.32,
    "spread_max_pct": 10.0,
    "min_premium": 0.50,
    "min_monthly_return": 0.005,
}

STRATEGY_MAP = {
    ("pullback", "bullish_aligned"): "CSP",
    ("pullback", "early_bullish"): "CSP",
    ("pullback", "bullish_watch"): "CSP",
    ("range", "bullish_aligned"): "CSP",
    ("range", "range_watchlist"): "CSP",
    ("early_trend", "early_bullish"): "CSP",
    ("extended", "bullish_aligned"): "CC",
    ("extended", "bullish_trend"): "CC",
    ("exhaustion", "bullish_aligned"): "CC",
    ("exhaustion", "bearish_aligned"): "CC",
    ("extended", "conflicted"): None,
    ("unknown", "*"): None,
}


@dataclass(frozen=True)
class OptionsCandidate:
    symbol: str
    strategy: str
    expiration: str
    dte: int
    strike: float
    option_type: str
    delta: float
    iv_pct: float
    ivr_approx: float | None
    bid: float
    ask: float
    mid: float
    spread_pct: float
    premium: float
    collateral: float
    monthly_return_pct: float
    market_state: str
    adjusted_alignment: str
    earnings_date: str | None
    ivr_real: float | None = None
    iv_underlying_pct: float | None = None
    iv_contract_pct: float | None = None
    iv_percentile_13w: float | None = None
    iv_percentile_26w: float | None = None
    iv_percentile_52w: float | None = None
    iv_quadrant: str = "indefinido"
    iv_source: str = "unavailable"
    score: float = 0.0


def map_strategy(market_state: str, adjusted_alignment: str) -> str | None:
    key = (market_state, adjusted_alignment)
    if key in STRATEGY_MAP:
        return STRATEGY_MAP[key]
    wildcard_key = (market_state, "*")
    if wildcard_key in STRATEGY_MAP:
        return STRATEGY_MAP[wildcard_key]
    if "bullish" in adjusted_alignment and market_state != "extended":
        return "CSP"
    return None


def compute_ivr(ticker: "yf.Ticker", current_iv: float) -> float | None:  # type: ignore[name-defined]
    """Approximate IV Rank using current IV versus 20-day HV range over 1Y."""
    if np is None:
        return None
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            hist = ticker.history(period="1y")
        if hist.empty or "Close" not in hist.columns:
            return None
        returns = hist["Close"].pct_change().dropna()
        hv_series = returns.rolling(20).std() * (252**0.5) * 100
        hv_series = hv_series.dropna()
        if hv_series.empty:
            return None
        hv_52w_low = float(hv_series.min())
        hv_52w_high = float(hv_series.max())
        if hv_52w_high <= hv_52w_low:
            return None
        ivr = (current_iv - hv_52w_low) / (hv_52w_high - hv_52w_low) * 100
        return round(max(0.0, min(100.0, ivr)), 1)
    except Exception:
        return None


def classify_iv_quadrant(ivr_real: float | None, ivp_52w: float | None) -> str:
    if ivr_real is None or ivp_52w is None:
        return "indefinido"
    ivr_high = ivr_real >= IVR_THRESHOLD
    ivp_high = ivp_52w >= IVP_THRESHOLD
    if ivr_high and ivp_high:
        return "venda_confiante"
    if ivr_high and not ivp_high:
        return "spike_pontual"
    if not ivr_high and ivp_high:
        return "ambiente_comprimido"
    return "compra_premio"


def score_candidate(candidate: OptionsCandidate) -> float:
    return_score = min(candidate.monthly_return_pct / 2.0, 1.0)
    spread_score = 1.0 - min(candidate.spread_pct / 10.0, 1.0)
    has_ivr_real = candidate.ivr_real is not None
    has_ivp_real = candidate.iv_percentile_52w is not None

    if has_ivr_real and has_ivp_real:
        weights = WEIGHTS_FULLY_REAL
        return round(
            (candidate.ivr_real / 100.0) * weights["ivr_real"]
            + (candidate.iv_percentile_52w / 100.0) * weights["ivp_real"]
            + return_score * weights["return"]
            + spread_score * weights["spread"],
            4,
        )
    if has_ivp_real or has_ivr_real:
        real_value = candidate.iv_percentile_52w if has_ivp_real else candidate.ivr_real
        weights = WEIGHTS_PARTIAL_REAL
        return round(
            (real_value / 100.0) * weights["iv_real"]
            + return_score * weights["return"]
            + spread_score * weights["spread"],
            4,
        )

    weights = WEIGHTS_LEGACY
    return round(
        ((candidate.ivr_approx or 0.0) / 100.0) * weights["ivr_approx"]
        + return_score * weights["return"]
        + spread_score * weights["spread"],
        4,
    )


_UNSET = object()  # distinguishes "no client kwarg passed" from "client=None"

IV_PERCENTILE_WINDOWS = {"13w": 65, "26w": 130, "52w": 250}  # trading days


def _ensure_worker_event_loop() -> None:
    """ib_insync needs a default asyncio loop; worker threads start without one."""
    try:
        asyncio.get_event_loop()
    except RuntimeError:
        asyncio.set_event_loop(asyncio.new_event_loop())


def fetch_ibkr_underlying_iv_history(
    symbol: str,
    exchange: str = "SMART",
    client: Any = None,
) -> list[float]:
    """Fetch the underlying's daily option-implied-vol series; never raises.

    IBKR does not expose IV Percentile directly over the TWS API — this
    historical series is the raw input `compute_iv_percentiles` ranks the
    current IV against. Pass an already-connected `client` to reuse one
    connection across a symbol's contracts instead of reconnecting per call.
    """
    try:
        _ensure_worker_event_loop()
        owns_client = client is None
        if owns_client:
            from ibkr_positions.client import IBKRClient

            client = IBKRClient()
        with _IBKR_REQUEST_LOCK:
            if owns_client:
                client.connect()
            try:
                rows = client.get_underlying_iv_history(symbol, exchange=exchange)
            finally:
                if owns_client:
                    client.disconnect()
        return [
            float(row["iv"]) for row in rows if isinstance(row.get("iv"), int | float)
        ]
    except Exception as exc:
        logger.warning("IBKR IV history unavailable for %s: %s", symbol, exc)
        return []


def compute_iv_percentiles(iv_history: list[float]) -> dict[str, float | None]:
    """Rank the most recent IV reading within trailing windows of history.

    The last value in `iv_history` is "current" and is ranked (inclusive)
    against itself plus the prior N-1 trading days for each window —
    matching how IBKR's own IV Percentile is defined. A window returns None
    when `iv_history` doesn't cover its full trading-day span — a 26w
    percentile computed from 40 days of history would look precise while
    being nearly meaningless, so it is withheld rather than approximated.
    """
    if not iv_history:
        return dict.fromkeys(IV_PERCENTILE_WINDOWS, None)
    current = iv_history[-1]
    result: dict[str, float | None] = {}
    for label, size in IV_PERCENTILE_WINDOWS.items():
        if len(iv_history) < size:
            result[label] = None
            continue
        window = iv_history[-size:]
        rank = sum(1 for value in window if value <= current)
        result[label] = round(rank / len(window) * 100.0, 1)
    return result


def compute_iv_rank(iv_history: list[float]) -> float | None:
    """Compute real IV Rank over the complete trailing 52-week window."""
    window_size = IV_PERCENTILE_WINDOWS["52w"]
    if len(iv_history) < window_size:
        return None
    window = iv_history[-window_size:]
    low, high = min(window), max(window)
    if high <= low:
        return None
    rank = (window[-1] - low) / (high - low) * 100.0
    return round(max(0.0, min(100.0, rank)), 1)


def fetch_ibkr_iv_data(
    contract_id: int | str | dict[str, Any],
    iv_history: list[float] | None = None,
    exchange: str = "SMART",
    client: Any = _UNSET,
) -> dict[str, Any]:
    """Fetch and validate per-contract IBKR IV; never raises to the screener.

    `iv_history` (from `fetch_ibkr_underlying_iv_history`, one call per
    symbol) drives `iv_underlying_pct`/`iv_percentile_*`. `client=None`
    (as opposed to the omitted-kwarg default) signals the caller already
    knows IBKR is unreachable for this symbol — skip the network attempt
    entirely rather than retrying a doomed connection per contract.
    """
    empty = {
        "iv_underlying_pct": None,
        "iv_contract_pct": None,
        "iv_percentile_13w": None,
        "iv_percentile_26w": None,
        "iv_percentile_52w": None,
        "ivr_real": None,
        "iv_source": "unavailable",
    }
    if not isinstance(contract_id, dict):
        return empty
    if client is None:
        return empty
    try:
        _ensure_worker_event_loop()
        owns_client = client is _UNSET
        if owns_client:
            from ibkr_positions.client import IBKRClient

            client = IBKRClient()

        expiration_ibkr = date.fromisoformat(str(contract_id["expiration"])).strftime(
            "%Y%m%d"
        )
        with _IBKR_REQUEST_LOCK:
            if owns_client:
                client.connect()
            try:
                payload = client.get_option_market_data(
                    symbol=str(contract_id["symbol"]),
                    expiration=expiration_ibkr,
                    strike=float(contract_id["strike"]),
                    right=str(contract_id["right"]),
                    exchange=exchange,
                )
            finally:
                if owns_client:
                    client.disconnect()

        iv_contract_pct = _valid_metric(payload.get("implied_vol"))
        iv_underlying_pct = round(iv_history[-1] * 100.0, 2) if iv_history else None
        percentiles = compute_iv_percentiles(iv_history or [])
        ivr_real = compute_iv_rank(iv_history or [])
        result = {
            "iv_underlying_pct": iv_underlying_pct,
            "iv_contract_pct": iv_contract_pct,
            "iv_percentile_13w": percentiles["13w"],
            "iv_percentile_26w": percentiles["26w"],
            "iv_percentile_52w": percentiles["52w"],
            "ivr_real": ivr_real,
            "iv_source": (
                "ibkr"
                if iv_underlying_pct is not None or iv_contract_pct is not None
                else "unavailable"
            ),
        }
        return result
    except Exception as exc:
        logger.warning("IBKR IV unavailable for %s: %s", contract_id, exc)
        return empty


def _valid_metric(value: Any) -> float | None:
    if isinstance(value, dict):
        if value.get("is_valid") is False or value.get("isValid") is False:
            return None
        value = value.get("annual_iv", value.get("annual_pct", value.get("value")))
    converted = _to_float(value)
    if converted is None or converted <= 0:
        return None
    return round(converted * 100.0 if converted <= 3.0 else converted, 2)


def candidate_to_dict(candidate: OptionsCandidate) -> dict[str, Any]:
    return asdict(candidate)


def candidates_to_dataframe(candidates: list[OptionsCandidate]) -> pd.DataFrame:
    columns = list(OptionsCandidate.__dataclass_fields__.keys())
    if not candidates:
        return pd.DataFrame(columns=columns)
    return pd.DataFrame([candidate_to_dict(candidate) for candidate in candidates])


def write_candidates_csv(
    candidates: list[OptionsCandidate],
    output_path: str | Path,
) -> None:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    candidates_to_dataframe(candidates).to_csv(path, index=False)


def screen_options_candidates(
    scanner_rows: list[dict[str, Any]],
    *,
    top_n: int = 20,
    dte_min: int = 30,
    dte_max: int = 45,
    portfolio_path: str | Path | None = None,
    as_of_date: date | None = None,
) -> tuple[list[OptionsCandidate], list[dict[str, str]]]:
    """Apply asset, technical, and contract filters to scanner rows."""
    if as_of_date is None:
        as_of_date = date.today()

    open_symbols = _load_open_position_symbols(portfolio_path)
    exclusions: list[dict[str, str]] = []
    eligible: list[tuple[dict[str, Any], str]] = []

    for row in scanner_rows[:top_n]:
        symbol = str(row.get("symbol", "")).strip()
        if not symbol:
            continue
        action_bucket = str(row.get("action_bucket", ""))
        if action_bucket not in {"candidate", "watchlist"}:
            continue
        if symbol in open_symbols:
            exclusions.append({"symbol": symbol, "reason": "já em posição aberta"})
            continue
        strategy = map_strategy(
            str(row.get("market_state", "")),
            str(row.get("adjusted_alignment", "")),
        )
        if strategy is None:
            exclusions.append({"symbol": symbol, "reason": "sem estratégia CSP/CC"})
            continue
        eligible.append((row, strategy))

    if not eligible:
        return [], exclusions

    if not _YF_AVAILABLE:
        for row, _strategy in eligible:
            exclusions.append(
                {
                    "symbol": str(row.get("symbol", "")),
                    "reason": "yfinance not installed",
                }
            )
        return [], exclusions

    candidates: list[OptionsCandidate] = []
    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = {
            pool.submit(
                _evaluate_symbol,
                row,
                strategy,
                dte_min,
                dte_max,
                as_of_date,
            ): row
            for row, strategy in eligible
        }
        for future in as_completed(futures):
            symbol = str(futures[future].get("symbol", ""))
            try:
                symbol_candidates, symbol_exclusions = future.result()
            except Exception as exc:
                logger.warning("Options screener failed for %s: %s", symbol, exc)
                exclusions.append({"symbol": symbol, "reason": str(exc)})
                continue
            candidates.extend(symbol_candidates)
            exclusions.extend(symbol_exclusions)

    candidates.sort(
        key=lambda candidate: (
            candidate.ivr_real
            if candidate.ivr_real is not None
            else (candidate.ivr_approx if candidate.ivr_approx is not None else -1.0),
            candidate.score,
        ),
        reverse=True,
    )
    return candidates, exclusions


def _evaluate_symbol(
    row: dict[str, Any],
    strategy: str,
    dte_min: int,
    dte_max: int,
    as_of_date: date,
) -> tuple[list[OptionsCandidate], list[dict[str, str]]]:
    symbol = str(row.get("symbol", "")).strip()
    exclusions: list[dict[str, str]] = []

    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            ticker = yf.Ticker(symbol)  # type: ignore[union-attr]
            expirations = list(ticker.options)
    except Exception as exc:
        return [], [{"symbol": symbol, "reason": f"erro yfinance: {exc}"}]

    if not expirations:
        return [], [{"symbol": symbol, "reason": "sem opções"}]

    stock_price = _get_stock_price(ticker)
    if stock_price is None:
        return [], [{"symbol": symbol, "reason": "preço indisponível"}]
    if stock_price < LAYER1_FILTERS["min_price"]:
        return [], [{"symbol": symbol, "reason": f"preço {stock_price:.2f} < 10"}]

    asset_exclusion = _asset_filter_reason(ticker, stock_price)
    if asset_exclusion is not None:
        return [], [{"symbol": symbol, "reason": asset_exclusion}]

    target_expirations = _target_expirations(expirations, dte_min, dte_max, as_of_date)
    if not target_expirations:
        return [], [
            {"symbol": symbol, "reason": f"sem vencimento {dte_min}-{dte_max} DTE"}
        ]

    earnings_date = _get_earnings_date(ticker)
    if earnings_date is not None:
        for expiration, dte in target_expirations:
            buffer_end = expiration + timedelta(
                days=int(LAYER1_FILTERS["earnings_buffer_days"])
            )
            if as_of_date <= earnings_date <= buffer_end:
                return [], [
                    {
                        "symbol": symbol,
                        "reason": (
                            f"earnings {earnings_date.isoformat()} "
                            f"dentro do vencimento (DTE={dte})"
                        ),
                    }
                ]

    candidates: list[OptionsCandidate] = []
    rejection_reasons: list[str] = []
    option_type = "PUT" if strategy == "CSP" else "CALL"

    # One IBKR connection reused across every contract of this symbol
    # (each worker thread owns its connection — never shared across
    # threads) instead of reconnecting to Gateway per contract.
    from ibkr_positions.client import IBKRClient, IBKRConnectionError

    ibkr_client: IBKRClient | None = None
    try:
        candidate_client = IBKRClient()
        with _IBKR_REQUEST_LOCK:
            candidate_client.connect()
        ibkr_client = candidate_client
    except IBKRConnectionError as exc:
        logger.warning("IBKR Gateway unavailable for %s IV data: %s", symbol, exc)
    except Exception as exc:
        logger.warning("IBKR client init failed for %s: %s", symbol, exc)

    iv_history = (
        fetch_ibkr_underlying_iv_history(symbol, client=ibkr_client)
        if ibkr_client is not None
        else []
    )

    try:
        for expiration, dte in target_expirations:
            try:
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore")
                    chain = ticker.option_chain(expiration.isoformat())
            except Exception as exc:
                rejection_reasons.append(f"{expiration.isoformat()}: erro chain {exc}")
                continue

            contracts = chain.puts if option_type == "PUT" else chain.calls
            if contracts is None or contracts.empty:
                rejection_reasons.append(f"{expiration.isoformat()}: sem {option_type}")
                continue

            for contract in contracts.to_dict(orient="records"):
                candidate = _candidate_from_contract(
                    symbol=symbol,
                    strategy=strategy,
                    option_type=option_type,
                    contract=contract,
                    expiration=expiration,
                    dte=dte,
                    stock_price=stock_price,
                    market_state=str(row.get("market_state", "")),
                    adjusted_alignment=str(row.get("adjusted_alignment", "")),
                    earnings_date=earnings_date,
                    ticker=ticker,
                    ibkr_client=ibkr_client,
                    iv_history=iv_history,
                )
                if isinstance(candidate, OptionsCandidate):
                    candidates.append(candidate)
                else:
                    rejection_reasons.append(candidate)
    finally:
        if ibkr_client is not None:
            with _IBKR_REQUEST_LOCK:
                ibkr_client.disconnect()

    if candidates:
        return candidates, exclusions

    reason = _most_useful_rejection(rejection_reasons)
    return [], [{"symbol": symbol, "reason": reason}]


def _candidate_from_contract(
    *,
    symbol: str,
    strategy: str,
    option_type: str,
    contract: dict[str, Any],
    expiration: date,
    dte: int,
    stock_price: float,
    market_state: str,
    adjusted_alignment: str,
    earnings_date: date | None,
    ticker: "yf.Ticker",  # type: ignore[name-defined]
    ibkr_client: Any = None,
    iv_history: list[float] | None = None,
) -> OptionsCandidate | str:
    bid = _to_float(contract.get("bid"))
    ask = _to_float(contract.get("ask"))
    strike = _to_float(contract.get("strike"))
    volume = _to_float(contract.get("volume")) or 0.0
    open_interest = _to_float(contract.get("openInterest")) or 0.0
    iv_pct = _normalise_iv(contract.get("impliedVolatility"))

    if bid is None or ask is None or strike is None:
        return "contrato sem bid/ask/strike"
    if bid <= 0 or ask <= 0:
        return "contrato sem cotação"
    if volume < LAYER1_FILTERS["min_option_volume"]:
        return f"volume opções {volume:.0f} < 500"
    if open_interest < LAYER1_FILTERS["min_open_interest"]:
        return f"open interest {open_interest:.0f} < 1000"
    if iv_pct is None:
        return "IV indisponível"
    if iv_pct < LAYER1_FILTERS["iv_min_pct"]:
        return f"IV {iv_pct:.1f}% < 20%"
    if iv_pct > LAYER1_FILTERS["iv_max_pct"]:
        return f"IV {iv_pct:.1f}% > 60%"

    mid = (bid + ask) / 2.0
    if mid <= 0:
        return "mid inválido"
    spread_pct = (ask - bid) / mid * 100.0
    if spread_pct > LAYER3_FILTERS["spread_max_pct"]:
        return f"spread {spread_pct:.1f}% > 10%"
    if mid < LAYER3_FILTERS["min_premium"]:
        return f"prêmio {mid:.2f} < 0.50"

    delta = _extract_delta(contract, option_type, stock_price, strike, dte, iv_pct)
    abs_delta = abs(delta)
    if (
        abs_delta < LAYER3_FILTERS["delta_min"]
        or abs_delta > LAYER3_FILTERS["delta_max"]
    ):
        return f"delta {abs_delta:.2f} fora de 0.18-0.32"

    collateral = strike * 100.0 if strategy == "CSP" else stock_price * 100.0
    monthly_return_decimal = (mid * 100.0 / collateral) * (30.0 / dte)
    if monthly_return_decimal < LAYER3_FILTERS["min_monthly_return"]:
        return f"retorno mensal {monthly_return_decimal * 100.0:.2f}% < 0.50%"

    ivr_approx = compute_ivr(ticker, iv_pct)
    if ivr_approx is None:
        return "IVR indisponível"
    if ivr_approx < LAYER1_FILTERS["ivr_min"]:
        return f"IVR {ivr_approx:.0f} < 30"

    iv_data = fetch_ibkr_iv_data(
        {
            "symbol": symbol,
            "expiration": expiration.isoformat(),
            "strike": strike,
            "right": option_type,
        },
        iv_history=iv_history,
        client=ibkr_client,
    )
    ivr_for_filter = (
        iv_data["ivr_real"] if iv_data["ivr_real"] is not None else ivr_approx
    )
    if ivr_for_filter < LAYER1_FILTERS["ivr_min"]:
        return f"IVR {ivr_for_filter:.0f} < 30"
    if iv_data["iv_percentile_52w"] is None:
        logger.warning(
            "IBKR IV percentile unavailable for %s; using ivr_approx fallback",
            symbol,
        )
    iv_quadrant = classify_iv_quadrant(
        iv_data["ivr_real"] if iv_data["ivr_real"] is not None else ivr_approx,
        iv_data["iv_percentile_52w"],
    )

    candidate = OptionsCandidate(
        symbol=symbol,
        strategy=strategy,
        expiration=expiration.isoformat(),
        dte=dte,
        strike=round(strike, 2),
        option_type=option_type,
        delta=round(abs_delta, 2),
        iv_pct=round(iv_pct, 1),
        ivr_approx=ivr_approx,
        bid=round(bid, 2),
        ask=round(ask, 2),
        mid=round(mid, 2),
        spread_pct=round(spread_pct, 1),
        premium=round(mid, 2),
        collateral=round(collateral, 2),
        monthly_return_pct=round(monthly_return_decimal * 100.0, 2),
        market_state=market_state,
        adjusted_alignment=adjusted_alignment,
        earnings_date=earnings_date.isoformat() if earnings_date is not None else None,
        ivr_real=iv_data["ivr_real"],
        iv_underlying_pct=iv_data["iv_underlying_pct"],
        iv_contract_pct=iv_data["iv_contract_pct"],
        iv_percentile_13w=iv_data["iv_percentile_13w"],
        iv_percentile_26w=iv_data["iv_percentile_26w"],
        iv_percentile_52w=iv_data["iv_percentile_52w"],
        iv_quadrant=iv_quadrant,
        iv_source=(
            "ibkr"
            if iv_data["ivr_real"] is not None
            or iv_data["iv_percentile_52w"] is not None
            else "unavailable"
        ),
        score=0.0,
    )
    return candidate.__class__(
        **(asdict(candidate) | {"score": score_candidate(candidate)})
    )


def _asset_filter_reason(ticker: "yf.Ticker", stock_price: float) -> str | None:  # type: ignore[name-defined]
    fast_info = getattr(ticker, "fast_info", None)
    market_cap = _get_info_number(fast_info, "market_cap", "marketCap")
    if market_cap is None:
        market_cap = _get_info_number(getattr(ticker, "info", None), "marketCap")
    if market_cap is not None:
        min_market_cap = LAYER1_FILTERS["min_market_cap_b"] * 1_000_000_000
        if market_cap < min_market_cap:
            return f"market cap {market_cap / 1_000_000_000:.1f}B < 5B"

    average_volume = _get_info_number(
        fast_info,
        "ten_day_average_volume",
        "three_month_average_volume",
        "average_volume",
    )
    if average_volume is None:
        average_volume = _get_info_number(
            getattr(ticker, "info", None),
            "averageVolume",
            "averageVolume10days",
        )
    if (
        average_volume is not None
        and average_volume < LAYER1_FILTERS["min_stock_volume"]
    ):
        return f"volume ação {average_volume:.0f} < 1000000"

    if stock_price < LAYER1_FILTERS["min_price"]:
        return f"preço {stock_price:.2f} < 10"
    return None


def _target_expirations(
    expirations: list[str],
    dte_min: int,
    dte_max: int,
    as_of_date: date,
) -> list[tuple[date, int]]:
    result: list[tuple[date, int]] = []
    for expiration_raw in expirations:
        try:
            expiration = date.fromisoformat(str(expiration_raw))
        except ValueError:
            continue
        dte = (expiration - as_of_date).days
        if dte_min <= dte <= dte_max:
            result.append((expiration, dte))
    return result


def _get_stock_price(ticker: "yf.Ticker") -> float | None:  # type: ignore[name-defined]
    fast_info = getattr(ticker, "fast_info", None)
    price = _get_info_number(
        fast_info, "last_price", "lastPrice", "regular_market_price"
    )
    if price is not None:
        return price
    price = _get_info_number(getattr(ticker, "info", None), "regularMarketPrice")
    if price is not None:
        return price
    try:
        hist = ticker.history(period="5d")
    except Exception:
        return None
    if hist.empty or "Close" not in hist.columns:
        return None
    return float(hist["Close"].dropna().iloc[-1])


def _get_earnings_date(ticker: "yf.Ticker") -> date | None:  # type: ignore[name-defined]
    calendar = getattr(ticker, "calendar", None)
    if calendar is None:
        return None
    if isinstance(calendar, pd.DataFrame):
        for label in ("Earnings Date", "Earnings", "Earnings Average"):
            if label in calendar.index:
                return _coerce_date(calendar.loc[label].iloc[0])
            if label in calendar.columns and not calendar[label].empty:
                return _coerce_date(calendar[label].iloc[0])
    if isinstance(calendar, dict):
        for key in ("Earnings Date", "Earnings", "earningsDate"):
            value = calendar.get(key)
            if isinstance(value, list | tuple):
                value = value[0] if value else None
            parsed = _coerce_date(value)
            if parsed is not None:
                return parsed
    return _coerce_date(calendar)


def _load_open_position_symbols(portfolio_path: str | Path | None) -> set[str]:
    if portfolio_path is None:
        return set()
    try:
        from market_scanner.portfolio import load_open_positions

        return {position.symbol for position in load_open_positions(portfolio_path)}
    except Exception as exc:
        logger.warning(
            "Failed to read open options portfolio %s: %s", portfolio_path, exc
        )
        return set()


def _extract_delta(
    contract: dict[str, Any],
    option_type: str,
    stock_price: float,
    strike: float,
    dte: int,
    iv_pct: float,
) -> float:
    raw_delta = _to_float(contract.get("delta"))
    if raw_delta is not None:
        return raw_delta
    return _black_scholes_delta(
        option_type=option_type,
        stock_price=stock_price,
        strike=strike,
        dte=dte,
        iv_pct=iv_pct,
    )


def _black_scholes_delta(
    *,
    option_type: str,
    stock_price: float,
    strike: float,
    dte: int,
    iv_pct: float,
) -> float:
    volatility = iv_pct / 100.0
    time_to_expiry = max(dte / 365.0, 1 / 365.0)
    if stock_price <= 0 or strike <= 0 or volatility <= 0:
        return 0.0
    d1 = (
        math.log(stock_price / strike)
        + (0.5 * volatility * volatility) * time_to_expiry
    ) / (volatility * math.sqrt(time_to_expiry))
    call_delta = _normal_cdf(d1)
    if option_type == "CALL":
        return call_delta
    return call_delta - 1.0


def _normal_cdf(value: float) -> float:
    return 0.5 * (1.0 + math.erf(value / math.sqrt(2.0)))


def _normalise_iv(value: Any) -> float | None:
    converted = _to_float(value)
    if converted is None:
        return None
    return converted * 100.0 if converted <= 3.0 else converted


def _to_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        converted = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(converted):
        return None
    return converted


def _get_info_number(source: Any, *keys: str) -> float | None:
    if source is None:
        return None
    for key in keys:
        value = None
        if isinstance(source, dict):
            value = source.get(key)
        else:
            try:
                value = getattr(source, key)
            except Exception:
                value = None
            if value is None:
                try:
                    value = source[key]
                except Exception:
                    value = None
        converted = _to_float(value)
        if converted is not None:
            return converted
    return None


def _coerce_date(value: Any) -> date | None:
    if value is None:
        return None
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    try:
        timestamp = pd.Timestamp(value)
    except Exception:
        return None
    if pd.isna(timestamp):
        return None
    return timestamp.date()


def _most_useful_rejection(rejection_reasons: list[str]) -> str:
    if not rejection_reasons:
        return "nenhum contrato passou nos filtros"
    priority_fragments = [
        "IVR",
        "earnings",
        "spread",
        "retorno mensal",
        "delta",
        "open interest",
        "volume opções",
        "IV ",
    ]
    for fragment in priority_fragments:
        for reason in rejection_reasons:
            if fragment in reason:
                return reason
    return rejection_reasons[0]
