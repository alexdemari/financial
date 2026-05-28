"""Options liquidity filter for daily report.

Fetches ATM options metrics via yfinance and classifies symbols as
GOOD / OK / ILLIQUID based on open interest, daily volume, and bid-ask spread.
"""

from __future__ import annotations

import logging
import warnings
from dataclasses import dataclass

import pandas as pd

try:
    import numpy as np
    import yfinance as yf

    _YF_AVAILABLE = True
except ImportError:
    yf = None  # type: ignore[assignment]
    np = None  # type: ignore[assignment]
    _YF_AVAILABLE = False

logger = logging.getLogger(__name__)

# Thresholds
_GOOD_MIN_OI = 5_000
_GOOD_MAX_SPREAD_PCT = 10.0
_GOOD_MIN_VOL = 200
_GOOD_MIN_IV_RANK = 30.0

_OK_MIN_OI = 1_000
_OK_MAX_SPREAD_PCT = 20.0
_OK_MIN_VOL = 50
_OK_MIN_IV_RANK = 15.0

VERDICT_GOOD = "GOOD"
VERDICT_OK = "OK"
VERDICT_ILLIQUID = "ILLIQUID"
VERDICT_NO_QUOTES = "NO_QUOTES"  # liquid but market closed / no live bid-ask
VERDICT_NO_OPTIONS = "NO_OPTIONS"
VERDICT_ERROR = "ERROR"

OPTIONS_DISPLAY_COLUMNS = [
    "symbol",
    "strategy",
    "side",
    "price",
    "n_exps",
    "total_oi",
    "daily_vol",
    "atm_spread_pct",
    "iv_rank",
    "nearest_expiry",
    "verdict",
]


@dataclass(frozen=True)
class OptionsMetrics:
    symbol: str
    side: str | None
    price: float | None
    n_exps: int
    total_oi: int
    daily_vol: int
    atm_spread_pct: float | None
    iv_rank: float | None
    nearest_expiry: str | None
    verdict: str
    error: str | None = None


def _classify(
    total_oi: int,
    daily_vol: int,
    spread_pct: float | None,
    iv_rank: float | None,
) -> str:
    iv_ok_good = iv_rank is None or iv_rank >= _GOOD_MIN_IV_RANK
    iv_ok_ok = iv_rank is None or iv_rank >= _OK_MIN_IV_RANK

    if spread_pct is None:
        # No live quotes (market closed or pre-market) — classify on OI+vol only
        if total_oi >= _GOOD_MIN_OI and daily_vol >= _GOOD_MIN_VOL and iv_ok_good:
            return VERDICT_NO_QUOTES
        if total_oi >= _OK_MIN_OI and daily_vol >= _OK_MIN_VOL and iv_ok_ok:
            return VERDICT_NO_QUOTES
        return VERDICT_ILLIQUID

    if (
        total_oi >= _GOOD_MIN_OI
        and spread_pct <= _GOOD_MAX_SPREAD_PCT
        and daily_vol >= _GOOD_MIN_VOL
        and iv_ok_good
    ):
        return VERDICT_GOOD
    if (
        total_oi >= _OK_MIN_OI
        and spread_pct <= _OK_MAX_SPREAD_PCT
        and daily_vol >= _OK_MIN_VOL
        and iv_ok_ok
    ):
        return VERDICT_OK
    return VERDICT_ILLIQUID


def _compute_iv_rank(ticker: "yf.Ticker") -> float | None:  # type: ignore[name-defined]
    """HV-proxy IV rank: 30-day realized vol rank over 1Y window."""
    if np is None:
        return None
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            hist = ticker.history(period="1y")
        if hist.empty or len(hist) < 32:
            return None
        log_ret = np.log(hist["Close"] / hist["Close"].shift(1)).dropna()
        hv = log_ret.rolling(30).std() * np.sqrt(252) * 100
        hv = hv.dropna()
        if len(hv) < 2:
            return None
        low, high, current = float(hv.min()), float(hv.max()), float(hv.iloc[-1])
        if high == low:
            return None
        return round((current - low) / (high - low) * 100, 1)
    except Exception:
        return None


def _fetch_one(symbol: str, side: str | None) -> OptionsMetrics:
    if not _YF_AVAILABLE:
        return OptionsMetrics(
            symbol=symbol,
            side=side,
            price=None,
            n_exps=0,
            total_oi=0,
            daily_vol=0,
            atm_spread_pct=None,
            iv_rank=None,
            nearest_expiry=None,
            verdict=VERDICT_ERROR,
            error="yfinance not installed",
        )

    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            t = yf.Ticker(symbol)
            exps = t.options

        if not exps:
            return OptionsMetrics(
                symbol=symbol,
                side=side,
                price=None,
                n_exps=0,
                total_oi=0,
                daily_vol=0,
                atm_spread_pct=None,
                iv_rank=None,
                nearest_expiry=None,
                verdict=VERDICT_NO_OPTIONS,
            )

        price = t.fast_info.last_price
        chain = t.option_chain(exps[0])
        calls = chain.calls
        puts = chain.puts

        total_oi = int(
            calls["openInterest"].fillna(0).sum() + puts["openInterest"].fillna(0).sum()
        )
        daily_vol = int(
            calls["volume"].fillna(0).sum() + puts["volume"].fillna(0).sum()
        )

        # ATM spread: try up to 3 expiries to find live bid/ask quotes
        spread_pct: float | None = None
        for exp in exps[:3]:
            if exp != exps[0]:
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore")
                    exp_chain = t.option_chain(exp)
                exp_calls = exp_chain.calls
            else:
                exp_calls = calls
            atm = exp_calls[
                (exp_calls["strike"] > price * 0.95)
                & (exp_calls["strike"] < price * 1.05)
            ]
            atm_quoted = atm[(atm["bid"] > 0) | (atm["ask"] > 0)]
            if atm_quoted.empty:
                continue
            best = atm_quoted.sort_values("openInterest", ascending=False).iloc[0]
            bid = float(best["bid"])
            ask = float(best["ask"])
            mid = (bid + ask) / 2
            if mid > 0:
                spread_pct = round((ask - bid) / mid * 100, 1)
                break

        iv_rank = _compute_iv_rank(t)
        verdict = _classify(total_oi, daily_vol, spread_pct, iv_rank)

        return OptionsMetrics(
            symbol=symbol,
            side=side,
            price=round(float(price), 2) if price else None,
            n_exps=len(exps),
            total_oi=total_oi,
            daily_vol=daily_vol,
            atm_spread_pct=spread_pct,
            iv_rank=iv_rank,
            nearest_expiry=exps[0],
            verdict=verdict,
        )

    except Exception as exc:
        logger.warning("Options fetch failed for %s: %s", symbol, exc)
        return OptionsMetrics(
            symbol=symbol,
            side=side,
            price=None,
            n_exps=0,
            total_oi=0,
            daily_vol=0,
            atm_spread_pct=None,
            iv_rank=None,
            nearest_expiry=None,
            verdict=VERDICT_ERROR,
            error=str(exc),
        )


def fetch_options_liquidity(
    symbol_side_pairs: list[tuple[str, str | None, str]],
) -> pd.DataFrame:
    """Fetch options liquidity for a list of (symbol, side, strategy) triples.

    Returns a DataFrame with columns matching OPTIONS_DISPLAY_COLUMNS.
    Deduplicates by symbol (keeps first occurrence — caller controls priority order).
    """
    seen: set[str] = set()
    unique_pairs: list[tuple[str, str | None, str]] = []
    for sym, side, strategy in symbol_side_pairs:
        if sym not in seen:
            seen.add(sym)
            unique_pairs.append((sym, side, strategy))

    rows = []
    for sym, side, strategy in unique_pairs:
        m = _fetch_one(sym, side)
        rows.append(
            {
                "symbol": m.symbol,
                "strategy": strategy,
                "side": m.side or "—",
                "price": m.price,
                "n_exps": m.n_exps,
                "total_oi": m.total_oi,
                "daily_vol": m.daily_vol,
                "atm_spread_pct": m.atm_spread_pct,
                "iv_rank": m.iv_rank,
                "nearest_expiry": m.nearest_expiry or "—",
                "verdict": m.verdict,
            }
        )

    if not rows:
        return pd.DataFrame(columns=OPTIONS_DISPLAY_COLUMNS)

    return pd.DataFrame(rows)


def filter_tradeable(options_df: pd.DataFrame) -> pd.DataFrame:
    """Return GOOD, OK, and NO_QUOTES rows, sorted by verdict then total_oi desc."""
    if options_df.empty:
        return options_df
    tradeable = options_df[
        options_df["verdict"].isin([VERDICT_GOOD, VERDICT_OK, VERDICT_NO_QUOTES])
    ].copy()
    verdict_order = {VERDICT_GOOD: 0, VERDICT_OK: 1, VERDICT_NO_QUOTES: 2}
    tradeable["_ord"] = tradeable["verdict"].map(verdict_order)
    tradeable = tradeable.sort_values(["_ord", "total_oi"], ascending=[True, False])
    return tradeable.drop(columns="_ord").reset_index(drop=True)
