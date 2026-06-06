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
    is_filtered: bool = False
    filter_reason: str = ""
    strategy: str = "none"


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
    is_filtered: bool = False,
    filter_reason: str = "",
    strategy: str = "none",
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
        is_filtered=is_filtered,
        filter_reason=filter_reason,
        strategy=strategy,
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


def summarize_trade_records(
    records: list[dict],
    *,
    max_return_cap: float = float("inf"),
    max_loss: float = float("-inf"),
) -> list[dict]:
    return summarize_trade_records_by(
        records,
        group_columns=[
            "exit_rule",
            "ranking_mode",
            "side",
            "strategy",
            "entry_alignment",
        ],
        max_return_cap=max_return_cap,
        max_loss=max_loss,
    )


def summarize_symbol_trade_records(
    records: list[dict],
    *,
    max_return_cap: float = float("inf"),
    max_loss: float = float("-inf"),
) -> list[dict]:
    return summarize_trade_records_by(
        records,
        group_columns=[
            "symbol",
            "exit_rule",
            "ranking_mode",
            "side",
            "entry_alignment",
        ],
        max_return_cap=max_return_cap,
        max_loss=max_loss,
    )


def summarize_trade_records_by(
    records: list[dict],
    *,
    group_columns: list[str],
    max_return_cap: float = float("inf"),
    max_loss: float = float("-inf"),
) -> list[dict]:
    if not records:
        return []

    trades_df = pd.DataFrame(records)
    # Ensure optional columns used in grouping have defaults so older records
    # without the field do not raise KeyError.
    if "strategy" in group_columns and "strategy" not in trades_df.columns:
        trades_df["strategy"] = "none"
    rows: list[dict] = []

    grouped = trades_df.groupby(
        group_columns,
        dropna=False,
        sort=False,
    )
    for group_values, group in grouped:
        if not isinstance(group_values, tuple):
            group_values = (group_values,)
        directional = pd.to_numeric(group["directional_return"], errors="coerce")
        # Apply metric-level caps for summary statistics only.
        # max_loss is e.g. -1.0 meaning -100%; max_return_cap is e.g. 5.0 meaning +500%.
        # Raw CSV trade records are never modified.
        capped = directional.clip(lower=max_loss, upper=max_return_cap)
        wins = capped[capped > 0]
        losses = capped[capped <= 0]
        win_rate = float((capped > 0).mean()) if not capped.empty else None
        loss_rate = float((capped <= 0).mean()) if not capped.empty else None
        avg_win = float(wins.mean()) if not wins.empty else 0.0
        avg_loss = float(abs(losses.mean())) if not losses.empty else 0.0
        expectancy = None
        if win_rate is not None and loss_rate is not None:
            expectancy = (win_rate * avg_win) - (loss_rate * avg_loss)

        winning_sum = float(wins.sum()) if not wins.empty else 0.0
        losing_sum = float(losses.sum()) if not losses.empty else 0.0
        if losses.empty or abs(losing_sum) == 0.0:
            profit_factor = None
        elif wins.empty:
            profit_factor = 0.0
        else:
            profit_factor = winning_sum / abs(losing_sum)

        row = {column: value for column, value in zip(group_columns, group_values)} | {
            "total_trades": int(len(group)),
            "win_rate": win_rate,
            "loss_rate": loss_rate,
            "avg_return": float(pd.to_numeric(group["raw_return"]).mean()),
            "median_return": float(pd.to_numeric(group["raw_return"]).median()),
            "avg_directional_return": (
                float(capped.mean()) if not capped.empty else None
            ),
            "median_directional_return": (
                float(capped.median()) if not capped.empty else None
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
            "best_trade": (float(capped.max()) if not capped.empty else None),
            "worst_trade": (float(capped.min()) if not capped.empty else None),
        }
        rows.append(row)

    return rows
