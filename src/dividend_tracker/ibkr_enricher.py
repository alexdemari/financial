from dataclasses import dataclass
from pathlib import Path

import pandas as pd


@dataclass
class IBKRHolding:
    symbol: str
    quantity: float
    market_value: float
    cost_basis: float


def load_ibkr_stk_positions(
    positions_csv: Path,
) -> tuple[dict[str, IBKRHolding], float | None]:
    """
    Reads ibkr_positions CSV, returns (holdings_by_symbol, available_cash).
    Filters to STK/ETF rows only. available_cash taken from first row.
    """
    df = pd.read_csv(positions_csv)
    available_cash: float | None = None
    if "available_cash" in df.columns and not df.empty:
        raw = df["available_cash"].iloc[0]
        if pd.notna(raw):
            available_cash = float(raw)

    stk = df[df["type"].isin(["STK", "ETF"])].copy()
    holdings: dict[str, IBKRHolding] = {
        row["symbol"].upper(): IBKRHolding(
            symbol=row["symbol"].upper(),
            quantity=float(row["qty"]),
            market_value=float(row["market_value"]),
            cost_basis=float(row["cost_basis"]),
        )
        for _, row in stk.iterrows()
    }
    return holdings, available_cash


def project_annual_income(
    holdings: dict[str, IBKRHolding],
    dividend_data: dict[str, float],
) -> list[dict]:
    """
    Returns income projection dicts for held assets that have dividend data.
    Skips symbols absent from dividend_data without raising.
    """
    results = []
    for symbol, holding in holdings.items():
        annual_div = dividend_data.get(symbol)
        if annual_div is None:
            continue
        projected = holding.quantity * annual_div
        avg_cost_per_share = (
            holding.cost_basis / holding.quantity if holding.quantity > 0 else 0.0
        )
        dy_on_cost = (
            (annual_div / avg_cost_per_share * 100) if avg_cost_per_share > 0 else 0.0
        )
        results.append(
            {
                "symbol": symbol,
                "shares": holding.quantity,
                "annual_div_per_share": annual_div,
                "projected_annual_income_usd": projected,
                "dy_on_cost_pct": dy_on_cost,
            }
        )
    return results
