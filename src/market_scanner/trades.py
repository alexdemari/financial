from dataclasses import asdict, dataclass
from typing import Literal

import pandas as pd


TradeSide = Literal["bullish", "bearish"]


@dataclass(frozen=True)
class Trade:
    symbol: str
    side: TradeSide
    entry_date: str
    entry_price: float
    exit_date: str
    exit_price: float
    bars_held: int
    entry_alignment: str
    exit_reason: str
    raw_return: float
    directional_return: float
    mfe: float | None
    mae: float | None


def build_trade(
    *,
    symbol: str,
    side: TradeSide,
    entry_date: str,
    entry_price: float,
    exit_date: str,
    exit_price: float,
    bars_held: int,
    entry_alignment: str,
    exit_reason: str,
    mfe: float | None,
    mae: float | None,
) -> Trade:
    raw_return = (exit_price / entry_price) - 1.0
    directional_return = raw_return if side == "bullish" else -raw_return
    return Trade(
        symbol=symbol,
        side=side,
        entry_date=entry_date,
        entry_price=entry_price,
        exit_date=exit_date,
        exit_price=exit_price,
        bars_held=bars_held,
        entry_alignment=entry_alignment,
        exit_reason=exit_reason,
        raw_return=raw_return,
        directional_return=directional_return,
        mfe=mfe,
        mae=mae,
    )


def compute_trade_excursions(
    *,
    window: pd.DataFrame,
    entry_price: float,
    side: TradeSide,
    high_column: str,
    low_column: str,
) -> tuple[float | None, float | None]:
    if side == "bullish":
        mfe = (float(window[high_column].max()) / entry_price) - 1.0
        mae = (float(window[low_column].min()) / entry_price) - 1.0
        return mfe, mae

    mfe = 1.0 - (float(window[low_column].min()) / entry_price)
    mae = 1.0 - (float(window[high_column].max()) / entry_price)
    return mfe, mae


def trade_to_record(trade: Trade, *, exit_rule: str, ranking_mode: str) -> dict:
    record = asdict(trade)
    record["exit_rule"] = exit_rule
    record["ranking_mode"] = ranking_mode
    return record


def summarize_trade_records(records: list[dict]) -> list[dict]:
    if not records:
        return []

    trades_df = pd.DataFrame(records)
    rows: list[dict] = []

    grouped = trades_df.groupby(
        ["exit_rule", "ranking_mode", "side", "entry_alignment"],
        dropna=False,
        sort=False,
    )
    for group_values, group in grouped:
        directional = pd.to_numeric(group["directional_return"], errors="coerce")
        wins = directional[directional > 0]
        losses = directional[directional <= 0]
        win_rate = float((directional > 0).mean()) if not directional.empty else None
        loss_rate = float((directional <= 0).mean()) if not directional.empty else None
        avg_win = float(wins.mean()) if not wins.empty else 0.0
        avg_loss = float(abs(losses.mean())) if not losses.empty else 0.0
        expectancy = None
        if win_rate is not None and loss_rate is not None:
            expectancy = (win_rate * avg_win) - (loss_rate * avg_loss)

        winning_sum = float(wins.sum()) if not wins.empty else 0.0
        losing_sum = float(losses.sum()) if not losses.empty else 0.0
        if losses.empty:
            profit_factor = None
        elif wins.empty:
            profit_factor = 0.0
        else:
            profit_factor = winning_sum / abs(losing_sum)

        row = {
            "exit_rule": group_values[0],
            "ranking_mode": group_values[1],
            "side": group_values[2],
            "entry_alignment": group_values[3],
            "total_trades": int(len(group)),
            "win_rate": win_rate,
            "loss_rate": loss_rate,
            "avg_return": float(pd.to_numeric(group["raw_return"]).mean()),
            "median_return": float(pd.to_numeric(group["raw_return"]).median()),
            "avg_directional_return": (
                float(directional.mean()) if not directional.empty else None
            ),
            "median_directional_return": (
                float(directional.median()) if not directional.empty else None
            ),
            "avg_mfe": (
                float(pd.to_numeric(group["mfe"], errors="coerce").dropna().mean())
                if group["mfe"].notna().any()
                else None
            ),
            "avg_mae": (
                float(pd.to_numeric(group["mae"], errors="coerce").dropna().mean())
                if group["mae"].notna().any()
                else None
            ),
            "avg_bars_held": float(pd.to_numeric(group["bars_held"]).mean()),
            "expectancy": expectancy,
            "profit_factor": profit_factor,
            "best_trade": (float(directional.max()) if not directional.empty else None),
            "worst_trade": (
                float(directional.min()) if not directional.empty else None
            ),
        }
        rows.append(row)

    return rows
