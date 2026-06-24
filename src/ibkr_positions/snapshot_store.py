from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path

from ibkr_positions.models import Portfolio
from ibkr_positions.risk import margin_utilization, portfolio_net_delta

HISTORY_PATH = Path("data/ibkr/history.jsonl")


def _build_snapshot(portfolio: Portfolio, today: str) -> dict:
    positions = portfolio.positions
    opt_positions = [p for p in positions if p.asset_type == "OPT"]
    stk_positions = [p for p in positions if p.asset_type in ("STK", "ETF")]
    short_opts = [p for p in opt_positions if p.quantity < 0]

    options_premium_received = sum(abs(p.cost_basis) for p in short_opts)
    options_current_value = sum(p.market_value for p in opt_positions)
    options_pnl = sum(p.unrealized_pnl for p in opt_positions)
    stk_pnl = sum(p.unrealized_pnl for p in stk_positions)
    unrealized_pnl = sum(p.unrealized_pnl for p in positions)
    invested = sum(p.market_value for p in positions if p.asset_type != "CASH")

    margin_util = margin_utilization(portfolio.summary)
    net_delta = portfolio_net_delta(portfolio)

    return {
        "date": today,
        "nlv": portfolio.summary.net_liquidation,
        "cash": portfolio.summary.total_cash,
        "invested": invested,
        "unrealized_pnl": unrealized_pnl,
        "options_premium_received": options_premium_received,
        "options_current_value": options_current_value,
        "options_pnl": options_pnl,
        "stk_pnl": stk_pnl,
        "margin_utilization": margin_util,
        "net_delta_approx": net_delta,
    }


def append_snapshot(portfolio: Portfolio, history_path: Path = HISTORY_PATH) -> None:
    """Upsert today's snapshot into the JSONL history file."""
    today = date.today().isoformat()
    snapshot = _build_snapshot(portfolio, today)

    history_path.parent.mkdir(parents=True, exist_ok=True)

    entries: dict[str, dict] = {}
    if history_path.exists():
        for line in history_path.read_text().splitlines():
            line = line.strip()
            if line:
                entry = json.loads(line)
                entries[entry["date"]] = entry

    entries[today] = snapshot
    history_path.write_text("\n".join(json.dumps(e) for e in entries.values()) + "\n")


def load_history(
    history_path: Path = HISTORY_PATH, days: int | None = None
) -> list[dict]:
    """Return history entries sorted by date ascending, optionally capped to last N days."""
    if not history_path.exists():
        return []
    entries = [
        json.loads(line)
        for line in history_path.read_text().splitlines()
        if line.strip()
    ]
    entries.sort(key=lambda e: e["date"])
    if days is not None:
        entries = entries[-days:]
    return entries


def _print_history_table(entries: list[dict]) -> None:
    if not entries:
        print("No history found.")
        return

    n = len(entries)
    print(f"\nIBKR Account History — last {n} day(s)\n")

    print(
        "| Date       | NLV ($)     | Cash ($)    | Unreal. P&L | OPT P&L    | Premium Rcvd |"
    )
    print(
        "|------------|-------------|-------------|-------------|------------|--------------|"
    )

    def fmt_money(v: float) -> str:
        return f"${v:>11,.2f}"

    def fmt_pnl(v: float) -> str:
        sign = "+" if v >= 0 else ""
        return f"{sign}${v:>10,.2f}"

    for e in entries:
        print(
            f"| {e['date']} "
            f"| {fmt_money(e['nlv'])} "
            f"| {fmt_money(e['cash'])} "
            f"| {fmt_pnl(e['unrealized_pnl'])} "
            f"| {fmt_pnl(e['options_pnl'])} "
            f"| {fmt_money(e['options_premium_received'])} |"
        )

    print()

    first_nlv = entries[0]["nlv"]
    last_nlv = entries[-1]["nlv"]
    nlv_change = last_nlv - first_nlv
    nlv_pct = (nlv_change / first_nlv * 100) if first_nlv else 0.0
    sign = "+" if nlv_change >= 0 else ""
    print(f"NLV change ({n}d): {sign}${nlv_change:,.2f} ({sign}{nlv_pct:.2f}%)")
    print(
        f"Premium received (latest snapshot): ${entries[-1]['options_premium_received']:,.2f}"
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="IBKR account history summary")
    parser.add_argument(
        "--history",
        type=Path,
        default=HISTORY_PATH,
        help="Path to history JSONL file",
    )
    parser.add_argument(
        "--days",
        type=int,
        default=None,
        help="Limit output to last N days",
    )
    args = parser.parse_args(argv)
    entries = load_history(history_path=args.history, days=args.days)
    _print_history_table(entries)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
