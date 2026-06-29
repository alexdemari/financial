from __future__ import annotations

import csv
import sys
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import pandas as pd


@dataclass
class Trade:
    date: date
    symbol: str
    asset_type: str  # STK | OPT | ETF
    quantity: float
    proceeds_usd: float
    cost_usd: float
    pnl_usd: float
    currency: str


_ASSET_TYPE_MAP = {
    "Stocks": "STK",
    "Equity and Index Options": "OPT",
    "Options": "OPT",
}


def _normalize_asset_type(raw: str) -> str:
    return _ASSET_TYPE_MAP.get(raw.strip(), raw.strip()[:3].upper())


def parse_ibkr_csv(path: Path) -> list[Trade]:
    """Parse IBKR trades CSV export; return only closed USD-denominated trade rows."""
    trades: list[Trade] = []
    skipped_currencies: set[str] = set()

    with path.open(newline="", encoding="utf-8-sig") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            discriminator = row.get("DataDiscriminator", "").strip()
            code = row.get("Code", "").strip()
            if discriminator != "Trade":
                continue
            # Keep rows that represent a closed leg: Code contains "C"
            if "C" not in code.split(";"):
                continue
            try:
                trade_date = date.fromisoformat(row["Date/Time"].strip()[:10])
                symbol = row["Symbol"].strip()
                asset_type = _normalize_asset_type(row.get("Asset Category", "STK"))
                quantity = float(row["Quantity"].replace(",", ""))
                proceeds_usd = float(row["Proceeds"].replace(",", ""))
                cost_usd = abs(float(row["Basis"].replace(",", "")))
                pnl_usd = float(row["Realized P/L"].replace(",", ""))
                currency = row.get("Currency", "USD").strip()
            except (KeyError, ValueError):
                continue

            if currency != "USD":
                skipped_currencies.add(currency)
                continue

            trades.append(
                Trade(
                    date=trade_date,
                    symbol=symbol,
                    asset_type=asset_type,
                    quantity=quantity,
                    proceeds_usd=proceeds_usd,
                    cost_usd=cost_usd,
                    pnl_usd=pnl_usd,
                    currency=currency,
                )
            )

    if skipped_currencies:
        print(
            f"Warning: skipped {len(skipped_currencies)} non-USD currency(ies): "
            f"{', '.join(sorted(skipped_currencies))}. Only USD trades are supported.",
            file=sys.stderr,
        )

    return trades


def parse_history_csv(path: Path, year: int) -> list[Trade]:
    """Parse closed USD trades for a calendar year from canonical trade history."""
    history = pd.read_csv(path, dtype={"trade_id": str, "pnl_realized": float})
    year_prefix = f"{year}-"
    filtered_history = history[
        history["date"].astype(str).str.startswith(year_prefix)
        & history["asset_type"].isin(("STK", "OPT", "ETF"))
        & history["open_close"].str.contains("C", na=False)
    ]

    trades: list[Trade] = []
    skipped_currencies: set[str] = set()
    for _, row in filtered_history.iterrows():
        if pd.isna(row["pnl_realized"]):
            print(
                f"⚠ Skipping {row['symbol']} {row['date']}: "
                "pnl_realized missing (run just ibkr-flex-fetch)"
            )
            continue

        currency = str(row["currency"]).strip()
        if currency != "USD":
            skipped_currencies.add(currency)
            continue

        proceeds_usd = float(row["proceeds"])
        pnl_usd = float(row["pnl_realized"])
        trades.append(
            Trade(
                date=date.fromisoformat(str(row["date"])),
                symbol=str(row["symbol"]),
                asset_type=str(row["asset_type"]),
                quantity=float(row["quantity"]),
                proceeds_usd=proceeds_usd,
                cost_usd=proceeds_usd - pnl_usd,
                pnl_usd=pnl_usd,
                currency=currency,
            )
        )

    if skipped_currencies:
        print(
            f"Warning: skipped {len(skipped_currencies)} non-USD currency(ies): "
            f"{', '.join(sorted(skipped_currencies))}. Only USD trades are supported.",
            file=sys.stderr,
        )

    return trades
