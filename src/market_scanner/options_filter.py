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
    import yfinance as yf

    _YF_AVAILABLE = True
except ImportError:
    yf = None  # type: ignore[assignment]
    _YF_AVAILABLE = False

logger = logging.getLogger(__name__)

# Thresholds
_GOOD_MIN_OI = 5_000
_GOOD_MAX_SPREAD_PCT = 10.0
_GOOD_MIN_VOL = 200

_OK_MIN_OI = 1_000
_OK_MAX_SPREAD_PCT = 20.0
_OK_MIN_VOL = 50

VERDICT_GOOD = "GOOD"
VERDICT_OK = "OK"
VERDICT_ILLIQUID = "ILLIQUID"
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
    nearest_expiry: str | None
    verdict: str
    error: str | None = None


def _classify(total_oi: int, daily_vol: int, spread_pct: float | None) -> str:
    if spread_pct is None:
        return VERDICT_ILLIQUID
    if (
        total_oi >= _GOOD_MIN_OI
        and spread_pct <= _GOOD_MAX_SPREAD_PCT
        and daily_vol >= _GOOD_MIN_VOL
    ):
        return VERDICT_GOOD
    if (
        total_oi >= _OK_MIN_OI
        and spread_pct <= _OK_MAX_SPREAD_PCT
        and daily_vol >= _OK_MIN_VOL
    ):
        return VERDICT_OK
    return VERDICT_ILLIQUID


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

        # ATM call: within 5% of current price
        atm = calls[(calls["strike"] > price * 0.95) & (calls["strike"] < price * 1.05)]
        spread_pct: float | None = None
        if not atm.empty:
            best = atm.sort_values("openInterest", ascending=False).iloc[0]
            bid = float(best["bid"])
            ask = float(best["ask"])
            mid = (bid + ask) / 2
            if mid > 0:
                spread_pct = round((ask - bid) / mid * 100, 1)

        verdict = _classify(total_oi, daily_vol, spread_pct)

        return OptionsMetrics(
            symbol=symbol,
            side=side,
            price=round(float(price), 2) if price else None,
            n_exps=len(exps),
            total_oi=total_oi,
            daily_vol=daily_vol,
            atm_spread_pct=spread_pct,
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
                "nearest_expiry": m.nearest_expiry or "—",
                "verdict": m.verdict,
            }
        )

    if not rows:
        return pd.DataFrame(columns=OPTIONS_DISPLAY_COLUMNS)

    return pd.DataFrame(rows)


def filter_tradeable(options_df: pd.DataFrame) -> pd.DataFrame:
    """Return only GOOD and OK rows, sorted by verdict then total_oi desc."""
    if options_df.empty:
        return options_df
    tradeable = options_df[
        options_df["verdict"].isin([VERDICT_GOOD, VERDICT_OK])
    ].copy()
    verdict_order = {VERDICT_GOOD: 0, VERDICT_OK: 1}
    tradeable["_ord"] = tradeable["verdict"].map(verdict_order)
    tradeable = tradeable.sort_values(["_ord", "total_oi"], ascending=[True, False])
    return tradeable.drop(columns="_ord").reset_index(drop=True)
