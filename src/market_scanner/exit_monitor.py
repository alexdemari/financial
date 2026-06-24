"""Exit trigger monitor — evaluates open positions against today's scanner output.

Reuses exits.py functions directly. No new exit logic is introduced here.
"""

from __future__ import annotations

import argparse
import logging
from datetime import date
from pathlib import Path

import pandas as pd

from market_scanner.exits import (
    exit_after_n_bars,
    exit_on_alignment_break,
    exit_on_bucket_downgrade,
    exit_on_late_state,
    exit_on_opposite_signal,
)
from market_scanner.portfolio import Position, load_open_positions

logger = logging.getLogger(__name__)

EXIT_STATUS_EXIT = "EXIT ⚠️"
EXIT_STATUS_WATCH = "WATCH ~"
EXIT_STATUS_HOLD = "HOLD"

_BARS_N_RULES: dict[str, int] = {
    "bars_5": 5,
    "bars_10": 10,
    "bars_20": 20,
}
_WATCH_BUFFER = 2  # days before bars_N limit to raise WATCH

DEFAULT_DTE_EXIT_DAYS = 7
DEFAULT_DTE_WATCH_DAYS = 14

_POSITIONS_EVAL_COLUMNS = [
    "symbol",
    "side",
    "option_type",
    "option_direction",
    "option_strike",
    "option_expiry",
    "entry_date",
    "days_held",
    "dte",
    "premium_paid",
    "contracts",
    "delta",
    "iv",
    "signal_source",
    "recommended_exit_rule",
    "market_state",
    "action_bucket",
    "adjusted_alignment",
    "exit_status",
    "exit_reason",
]

_STATUS_ORDER = {EXIT_STATUS_EXIT: 0, EXIT_STATUS_WATCH: 1, EXIT_STATUS_HOLD: 2}


def _lookup_exit_rule(
    symbol: str,
    side: str,
    recommendations_df: pd.DataFrame | None,
) -> str | None:
    """Return recommended_exit_rule from backtest recs for (symbol, side), or None."""
    if recommendations_df is None or recommendations_df.empty:
        return None
    mask = (
        recommendations_df["symbol"].eq(symbol)
        & recommendations_df["side"].eq(side)
        & recommendations_df["qualified"].eq(True)
    )
    rows = recommendations_df[mask]
    if rows.empty:
        return None
    return str(rows.iloc[0]["recommended_exit_rule"])


def _dte_status(
    expiry: date,
    as_of: date,
    dte_exit_days: int,
    dte_watch_days: int,
) -> tuple[str, str] | None:
    """Return (status, reason) if DTE threshold breached, else None."""
    dte = (expiry - as_of).days
    if dte <= dte_exit_days:
        return EXIT_STATUS_EXIT, f"DTE: {dte} days to expiry (exit ≤ {dte_exit_days})"
    if dte <= dte_watch_days:
        return (
            EXIT_STATUS_WATCH,
            f"DTE: {dte} days to expiry (watch ≤ {dte_watch_days})",
        )
    return None


def _worst_status(
    a: tuple[str, str],
    b: tuple[str, str],
) -> tuple[str, str]:
    return a if _STATUS_ORDER.get(a[0], 99) <= _STATUS_ORDER.get(b[0], 99) else b


def _evaluate_one(
    position: Position,
    scan_row: dict | None,
    days_held: int | None,
    as_of_date: date = date.today(),
    dte_exit_days: int = DEFAULT_DTE_EXIT_DAYS,
    dte_watch_days: int = DEFAULT_DTE_WATCH_DAYS,
) -> tuple[str, str]:
    """Return (exit_status, exit_reason) for a single position."""
    rule = position.recommended_exit_rule

    dte_result = _dte_status(
        position.option_expiry, as_of_date, dte_exit_days, dte_watch_days
    )

    if scan_row is None:
        base = (EXIT_STATUS_WATCH, "symbol not in scan")
        return _worst_status(base, dte_result) if dte_result else base

    def _merge(base: tuple[str, str]) -> tuple[str, str]:
        return _worst_status(base, dte_result) if dte_result else base

    # bars_N rules
    if rule in _BARS_N_RULES:
        limit = _BARS_N_RULES[rule]
        if days_held is None:
            logger.warning(
                "Cannot evaluate %s for %s: entry date unavailable",
                rule,
                position.symbol,
            )
            return _merge((EXIT_STATUS_WATCH, f"{rule}: entry date unavailable"))
        if exit_after_n_bars(days_held, limit):
            return _merge(
                (EXIT_STATUS_EXIT, f"{rule}: {days_held} days held (limit {limit})")
            )
        if days_held >= limit - _WATCH_BUFFER:
            return _merge((EXIT_STATUS_WATCH, f"{rule}: {days_held}/{limit} days"))
        return _merge((EXIT_STATUS_HOLD, ""))

    if rule == "alignment_break":
        if exit_on_alignment_break(scan_row, position.side):
            alignment = scan_row.get("adjusted_alignment", "?")
            return _merge((EXIT_STATUS_EXIT, f"alignment_break: now {alignment}"))
        return _merge((EXIT_STATUS_HOLD, ""))

    if rule == "bucket_downgrade":
        bucket = scan_row.get("action_bucket", "")
        if exit_on_bucket_downgrade(scan_row):
            if bucket == "watchlist":
                return _merge((EXIT_STATUS_WATCH, f"bucket_downgrade: now {bucket}"))
            return _merge((EXIT_STATUS_EXIT, f"bucket_downgrade: now {bucket}"))
        return _merge((EXIT_STATUS_HOLD, ""))

    if rule == "late_state":
        if exit_on_late_state(scan_row):
            state = scan_row.get("market_state", "?")
            return _merge((EXIT_STATUS_EXIT, f"late_state: now {state}"))
        return _merge((EXIT_STATUS_HOLD, ""))

    if rule == "opposite_signal":
        if exit_on_opposite_signal(scan_row, position.side):
            alignment = scan_row.get("adjusted_alignment", "?")
            return _merge((EXIT_STATUS_EXIT, f"opposite_signal: now {alignment}"))
        return _merge((EXIT_STATUS_HOLD, ""))

    # Unknown rule — conservatively HOLD
    logger.warning("Unknown exit rule '%s' for %s", rule, position.symbol)
    return _merge((EXIT_STATUS_HOLD, f"unknown rule: {rule}"))


def evaluate_positions(
    positions: list[Position],
    scan_df: pd.DataFrame,
    recommendations_df: pd.DataFrame | None = None,
    as_of_date: date | None = None,
    dte_exit_days: int = DEFAULT_DTE_EXIT_DAYS,
    dte_watch_days: int = DEFAULT_DTE_WATCH_DAYS,
) -> pd.DataFrame:
    """Evaluate each open position against today's scan_df.

    Returns a DataFrame sorted EXIT → WATCH → HOLD.
    """
    if not positions:
        return pd.DataFrame(columns=_POSITIONS_EVAL_COLUMNS)

    today = as_of_date or date.today()

    # Build symbol lookup: symbol → first matching row dict
    scan_index: dict[str, dict] = {}
    if not scan_df.empty and "symbol" in scan_df.columns:
        for _, row in scan_df.iterrows():
            sym = row.get("symbol")
            if sym and sym not in scan_index:
                scan_index[sym] = row.to_dict()

    rows = []
    for pos in positions:
        days_held = (today - pos.entry_date).days if pos.entry_date else None

        # Override exit rule from backtest recommendations if available
        rule_override = _lookup_exit_rule(pos.symbol, pos.side, recommendations_df)
        effective_rule = rule_override if rule_override else pos.recommended_exit_rule

        # Update position's exit rule for evaluation
        effective_pos = Position(
            symbol=pos.symbol,
            side=pos.side,
            entry_date=pos.entry_date,
            option_type=pos.option_type,
            option_direction=pos.option_direction,
            option_strike=pos.option_strike,
            option_expiry=pos.option_expiry,
            premium_paid=pos.premium_paid,
            contracts=pos.contracts,
            delta=pos.delta,
            iv=pos.iv,
            signal_source=pos.signal_source,
            recommended_exit_rule=effective_rule,
        )

        scan_row = scan_index.get(pos.symbol)
        exit_status, exit_reason = _evaluate_one(
            effective_pos,
            scan_row,
            days_held,
            as_of_date=today,
            dte_exit_days=dte_exit_days,
            dte_watch_days=dte_watch_days,
        )

        rows.append(
            {
                "symbol": pos.symbol,
                "side": pos.side,
                "option_type": pos.option_type,
                "option_direction": pos.option_direction,
                "option_strike": pos.option_strike,
                "option_expiry": pos.option_expiry.isoformat(),
                "entry_date": pos.entry_date.isoformat() if pos.entry_date else "",
                "days_held": days_held,
                "dte": (pos.option_expiry - today).days,
                "premium_paid": pos.premium_paid,
                "contracts": pos.contracts,
                "delta": pos.delta,
                "iv": pos.iv,
                "signal_source": pos.signal_source,
                "recommended_exit_rule": effective_rule,
                "market_state": scan_row.get("market_state", "—") if scan_row else "—",
                "action_bucket": scan_row.get("action_bucket", "—")
                if scan_row
                else "—",
                "adjusted_alignment": scan_row.get("adjusted_alignment", "—")
                if scan_row
                else "—",
                "exit_status": exit_status,
                "exit_reason": exit_reason,
            }
        )

    if not rows:
        return pd.DataFrame(columns=_POSITIONS_EVAL_COLUMNS)

    result = pd.DataFrame(rows)
    result["_sort"] = result["exit_status"].map(_STATUS_ORDER).fillna(99)
    result = result.sort_values("_sort").drop(columns="_sort").reset_index(drop=True)
    return result


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser("Exit trigger monitor for open options positions")
    parser.add_argument("--scan", required=True, help="scan CSV from scan.py")
    parser.add_argument("--portfolio", required=True, help="options_tracker.csv path")
    parser.add_argument(
        "--recommendations",
        default=None,
        help="execution_recommended_rules.csv (optional)",
    )
    parser.add_argument(
        "--dte-exit-days",
        type=int,
        default=DEFAULT_DTE_EXIT_DAYS,
        help=f"DTE threshold for EXIT signal (default: {DEFAULT_DTE_EXIT_DAYS})",
    )
    parser.add_argument(
        "--dte-watch-days",
        type=int,
        default=DEFAULT_DTE_WATCH_DAYS,
        help=f"DTE threshold for WATCH signal (default: {DEFAULT_DTE_WATCH_DAYS})",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    from tabulate import tabulate

    parser = build_parser()
    args = parser.parse_args(argv)

    positions = load_open_positions(Path(args.portfolio))
    if not positions:
        print("No open positions found.")
        return 0

    scan_df = pd.read_csv(args.scan)
    recommendations_df: pd.DataFrame | None = None
    if args.recommendations:
        rec_path = Path(args.recommendations)
        if rec_path.exists():
            recommendations_df = pd.read_csv(rec_path)

    result = evaluate_positions(
        positions,
        scan_df,
        recommendations_df,
        dte_exit_days=args.dte_exit_days,
        dte_watch_days=args.dte_watch_days,
    )

    display_cols = [
        "symbol",
        "side",
        "option_type",
        "option_direction",
        "option_strike",
        "option_expiry",
        "entry_date",
        "days_held",
        "dte",
        "recommended_exit_rule",
        "market_state",
        "action_bucket",
        "exit_status",
        "exit_reason",
    ]
    display = result[[c for c in display_cols if c in result.columns]]
    print(tabulate(display, headers="keys", tablefmt="simple", showindex=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
