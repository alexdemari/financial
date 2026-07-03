from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path

import pandas as pd

from web.readers.common import PROJECT_ROOT, file_mtime

IBKR_HISTORY = PROJECT_ROOT / "data/ibkr/trades_history.csv"
BTG_OPCOES = PROJECT_ROOT / "data/btg/btg_opcoes_trades.csv"
BTG_GERAL = PROJECT_ROOT / "data/btg/btg_geral_trades.csv"


@dataclass(frozen=True)
class TradeRow:
    date: str
    broker: str
    symbol: str
    underlying: str
    asset_type: str
    direction: str
    quantity: float
    price: float
    proceeds: float
    commission: float
    pnl_realized: float | None
    currency: str
    strategy: str | None
    option_type: str | None
    strike: float | None
    expiration: str | None


def read_all_trades() -> list[dict]:
    """Read and merge realized trades from every available broker source."""
    trades = _read_ibkr_trades()
    trades.extend(_read_btg_trades(BTG_OPCOES, broker="BTG-Opções"))
    trades.extend(_read_btg_trades(BTG_GERAL, broker="BTG-Geral"))
    trades.sort(key=lambda trade: trade["date"], reverse=True)
    return trades


def _read_ibkr_trades() -> list[dict]:
    if not IBKR_HISTORY.exists():
        return []
    history = pd.read_csv(IBKR_HISTORY, dtype={"trade_id": str})
    if not {"open_close", "pnl_realized"}.issubset(history.columns):
        return []
    closed_trades = history[
        history["open_close"].astype("string").str.contains("C", na=False)
        & history["pnl_realized"].notna()
    ]
    return [asdict(_ibkr_row_to_trade(row)) for _, row in closed_trades.iterrows()]


def _read_btg_trades(path: Path, broker: str) -> list[dict]:
    """Read canonical BTG trades. BTG movimentação rows are always settled
    trades; unlike IBKR, BTG never reports a per-trade pnl_realized, so no
    realized/unrealized filter applies here."""
    if not path.exists():
        return []
    history = pd.read_csv(path)
    if "date" not in history.columns:
        return []
    return [asdict(_btg_row_to_trade(row, broker)) for _, row in history.iterrows()]


def read_monthly_summary(trades: list[dict]) -> list[dict]:
    """Aggregate gains and losses by calendar month and currency.

    Trades with unknown pnl_realized (e.g. BTG movimentações, which never
    report per-trade P&L) are excluded — counting them as zero-P&L would
    misrepresent unknown outcomes as break-even and inflate trade_count.
    """
    summaries: dict[tuple[str, str], dict] = {}
    for trade in trades:
        if trade["pnl_realized"] is None:
            continue
        month = str(trade["date"])[:7]
        currency = str(trade["currency"])
        summary = summaries.setdefault(
            (month, currency),
            {
                "month": month,
                "currency": currency,
                "gross_gains": 0.0,
                "gross_losses": 0.0,
                "net_pnl": 0.0,
                "trade_count": 0,
            },
        )
        pnl_realized = float(trade["pnl_realized"])
        if pnl_realized >= 0:
            summary["gross_gains"] += pnl_realized
        else:
            summary["gross_losses"] += pnl_realized
        summary["net_pnl"] += pnl_realized
        summary["trade_count"] += 1
    return sorted(
        summaries.values(),
        key=lambda summary: (summary["month"], summary["currency"]),
        reverse=True,
    )


def read_trade_sources() -> dict[str, dict | None]:
    """Return path and modification time for each available source."""
    return {
        name: (
            {"path": _display_path(path), "last_updated": file_mtime(path)}
            if path.exists()
            else None
        )
        for name, path in (
            ("ibkr", IBKR_HISTORY),
            ("btg_opcoes", BTG_OPCOES),
            ("btg_geral", BTG_GERAL),
        )
    }


def _display_path(path: Path) -> str:
    try:
        return str(path.relative_to(PROJECT_ROOT))
    except ValueError:
        return str(path)


def _ibkr_row_to_trade(row: pd.Series) -> TradeRow:
    quantity = _float(row.get("quantity"))
    return TradeRow(
        date=_date_text(row.get("date")),
        broker="IBKR",
        symbol=_text(row.get("symbol")) or "",
        underlying=_text(row.get("underlying")) or "",
        asset_type=_text(row.get("asset_type")) or "",
        direction="BUY" if quantity > 0 else "SELL",
        quantity=quantity,
        price=_float(row.get("price")),
        proceeds=_float(row.get("proceeds")),
        commission=_float(row.get("commission")),
        pnl_realized=_optional_float(row.get("pnl_realized")),
        currency=_text(row.get("currency")) or "USD",
        strategy=_text(row.get("strategy")),
        option_type=_text(row.get("option_type")),
        strike=_optional_float(row.get("strike")),
        expiration=_optional_date_text(row.get("expiration")),
    )


def _btg_row_to_trade(row: pd.Series, broker: str) -> TradeRow:
    symbol = _text(row.get("symbol")) or ""
    return TradeRow(
        date=_date_text(row.get("date")),
        broker=broker,
        symbol=symbol,
        underlying=_text(row.get("underlying")) or symbol,
        asset_type=_normalize_btg_asset_type(row.get("asset_type")),
        direction=(_text(row.get("direction")) or "").upper(),
        quantity=_float(row.get("quantity")),
        price=_float(row.get("price")),
        proceeds=_float(row.get("proceeds")),
        commission=_float(row.get("commission")),
        pnl_realized=_optional_float(row.get("pnl_realized")),
        currency=_text(row.get("currency")) or "BRL",
        strategy=_text(row.get("strategy")),
        option_type=_text(row.get("option_type")),
        strike=_optional_float(_first_present(row, "strike", "preco_exercicio")),
        expiration=_optional_date_text(row.get("expiration")),
    )


def _normalize_btg_asset_type(value: object) -> str:
    asset_type = (_text(value) or "").upper()
    return {"ACAO": "STK", "AÇÃO": "STK"}.get(asset_type, asset_type)


def _first_present(row: pd.Series, *columns: str) -> object:
    for column in columns:
        value = row.get(column)
        if value is not None and not pd.isna(value) and value != "":
            return value
    return None


def _float(value: object) -> float:
    try:
        return float(value) if not pd.isna(value) else 0.0
    except (TypeError, ValueError):
        return 0.0


def _optional_float(value: object) -> float | None:
    return None if pd.isna(value) or value in (None, "") else _float(value)


def _text(value: object) -> str | None:
    if value is None or pd.isna(value):
        return None
    text = str(value).strip()
    return text or None


def _date_text(value: object) -> str:
    return pd.to_datetime(value).date().isoformat()


def _optional_date_text(value: object) -> str | None:
    return None if value is None or pd.isna(value) or value == "" else _date_text(value)
