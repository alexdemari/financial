"""Portfolio tracker — reads options_tracker.csv and returns open positions.

The CSV uses semicolon delimiters and European decimal format (comma as decimal separator).
Open positions are rows where the Close Date column (index 18) is empty and Asset (index 3)
is non-empty.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date
from pathlib import Path

logger = logging.getLogger(__name__)

# Column indices in options_tracker.csv
_COL_DATE = 0
_COL_ASSET = 3
_COL_TYPE = 5  # PUT | CALL
_COL_CV = 6  # C (buy) | V (sell)
_COL_EXPIRY = 7
_COL_STRIKE = 8
_COL_PREMIUM = 9
_COL_CONTRACTS = 10
_COL_DELTA = 13
_COL_IV = 14
_COL_CLOSE_DATE = 18
_COL_SIGNAL_SOURCE = 25

_DEFAULT_EXIT_RULE = "alignment_break"


@dataclass(frozen=True)
class Position:
    symbol: str
    side: str  # bullish | bearish
    entry_date: date
    option_type: str  # call | put
    option_direction: str  # long | short
    option_strike: float
    option_expiry: date
    premium_paid: float
    contracts: int
    delta: float | None
    iv: float | None
    signal_source: str  # lux | smc | dual | —
    recommended_exit_rule: str = _DEFAULT_EXIT_RULE


def _parse_european_float(s: str) -> float | None:
    """Convert European decimal '1,45' or '-0,78' to float. Returns None if empty."""
    s = s.strip().replace(".", "").replace(",", ".")
    if not s:
        return None
    try:
        return float(s)
    except ValueError:
        return None


def _parse_date(s: str) -> date | None:
    """Parse DD/MM/YYYY or YYYY-MM-DD date string."""
    s = s.strip()
    if not s:
        return None
    try:
        if "-" in s:
            return date.fromisoformat(s)
        d, m, y = s.split("/")
        return date(int(y), int(m), int(d))
    except (ValueError, AttributeError):
        return None


def _derive_side(option_type: str, direction: str) -> str:
    """Derive scanner side from option type and open direction.

    SHORT PUT  (V, PUT)  → bullish (profit if stock stays above strike)
    LONG PUT   (C, PUT)  → bearish (profit if stock falls below strike)
    SHORT CALL (V, CALL) → bearish (profit if stock stays below strike)
    LONG CALL  (C, CALL) → bullish (profit if stock rises above strike)
    """
    opt = option_type.strip().upper()
    cv = direction.strip().upper()
    if opt == "PUT" and cv == "V":
        return "bullish"
    if opt == "PUT" and cv == "C":
        return "bearish"
    if opt == "CALL" and cv == "V":
        return "bearish"
    if opt == "CALL" and cv == "C":
        return "bullish"
    return "bullish"


def _derive_option_direction(cv: str) -> str:
    return "short" if cv.strip().upper() == "V" else "long"


def load_open_positions(csv_path: Path | str) -> list[Position]:
    """Parse options_tracker.csv and return rows where Close Date is empty.

    Returns an empty list if the file does not exist or has no open positions.
    """
    path = Path(csv_path)
    if not path.exists():
        logger.debug("Portfolio file not found: %s", path)
        return []

    try:
        content = path.read_bytes().decode("utf-8-sig")
    except Exception as exc:
        logger.warning("Failed to read portfolio file %s: %s", path, exc)
        return []

    lines = content.splitlines()
    if len(lines) < 2:
        return []

    positions: list[Position] = []
    for line_num, line in enumerate(lines[1:], start=2):
        line = line.strip()
        if not line:
            continue
        cols = line.split(";")

        # Skip rows without Asset
        symbol = cols[_COL_ASSET].strip() if len(cols) > _COL_ASSET else ""
        if not symbol:
            continue

        # Only open positions (no Close Date)
        close_date_str = (
            cols[_COL_CLOSE_DATE].strip() if len(cols) > _COL_CLOSE_DATE else ""
        )
        if close_date_str:
            continue

        entry_date = _parse_date(cols[_COL_DATE]) if len(cols) > _COL_DATE else None
        if entry_date is None:
            logger.debug("Skipping row %d: invalid entry date", line_num)
            continue

        option_type_raw = cols[_COL_TYPE].strip() if len(cols) > _COL_TYPE else ""
        cv_raw = cols[_COL_CV].strip() if len(cols) > _COL_CV else ""
        option_expiry = (
            _parse_date(cols[_COL_EXPIRY]) if len(cols) > _COL_EXPIRY else None
        )
        if option_expiry is None:
            logger.debug("Skipping row %d: invalid expiry date", line_num)
            continue

        strike = (
            _parse_european_float(cols[_COL_STRIKE])
            if len(cols) > _COL_STRIKE
            else None
        )
        premium = (
            _parse_european_float(cols[_COL_PREMIUM])
            if len(cols) > _COL_PREMIUM
            else None
        )
        contracts_raw = (
            cols[_COL_CONTRACTS].strip() if len(cols) > _COL_CONTRACTS else ""
        )
        delta = (
            _parse_european_float(cols[_COL_DELTA]) if len(cols) > _COL_DELTA else None
        )
        iv = _parse_european_float(cols[_COL_IV]) if len(cols) > _COL_IV else None
        signal_source = (
            cols[_COL_SIGNAL_SOURCE].strip() if len(cols) > _COL_SIGNAL_SOURCE else "—"
        )
        if not signal_source:
            signal_source = "—"

        try:
            contracts = int(contracts_raw)
        except (ValueError, TypeError):
            contracts = 0

        if strike is None or premium is None:
            logger.debug("Skipping row %d: missing strike or premium", line_num)
            continue

        side = _derive_side(option_type_raw, cv_raw)
        option_direction = _derive_option_direction(cv_raw)

        positions.append(
            Position(
                symbol=symbol,
                side=side,
                entry_date=entry_date,
                option_type=option_type_raw.lower(),
                option_direction=option_direction,
                option_strike=strike,
                option_expiry=option_expiry,
                premium_paid=premium,
                contracts=contracts,
                delta=delta,
                iv=iv,
                signal_source=signal_source,
                recommended_exit_rule=_DEFAULT_EXIT_RULE,
            )
        )

    return positions


def positions_to_df(positions: list[Position]) -> "pd.DataFrame":  # noqa: F821
    import pandas as pd

    if not positions:
        return pd.DataFrame()
    return pd.DataFrame(
        [
            {
                "symbol": p.symbol,
                "side": p.side,
                "entry_date": p.entry_date.isoformat(),
                "option_type": p.option_type,
                "option_direction": p.option_direction,
                "option_strike": p.option_strike,
                "option_expiry": p.option_expiry.isoformat(),
                "premium_paid": p.premium_paid,
                "contracts": p.contracts,
                "delta": p.delta,
                "iv": p.iv,
                "signal_source": p.signal_source,
                "recommended_exit_rule": p.recommended_exit_rule,
            }
            for p in positions
        ]
    )
