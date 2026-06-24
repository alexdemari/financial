from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path

from irpf_report.ptax import CACHE_DIR, get_ptax
from irpf_report.trades import Trade


@dataclass
class EnrichedTrade:
    date: date
    symbol: str
    asset_type: str
    quantity: float
    proceeds_usd: float
    cost_usd: float
    pnl_usd: float
    ptax_rate: float | None
    proceeds_brl: float | None
    cost_brl: float | None
    pnl_brl: float | None


@dataclass
class MonthSummary:
    month: str  # "Jan/YYYY"
    gross_gain_brl: float
    gross_loss_brl: float
    net_brl: float


@dataclass
class AssetTypeSummary:
    asset_type: str
    trade_count: int
    gross_gain_usd: float
    gross_loss_usd: float
    net_usd: float
    gross_gain_brl: float
    gross_loss_brl: float
    net_brl: float
    brl_incomplete: bool  # True if any trade in this bucket is missing PTAX


@dataclass
class Totals:
    gain_usd: float
    loss_usd: float
    net_usd: float
    gain_brl: float
    loss_brl: float
    net_brl: float
    brl_incomplete: bool  # True when ≥1 trade has ptax_rate=None


def enrich_trades(
    trades: list[Trade], cache_dir: Path = CACHE_DIR
) -> list[EnrichedTrade]:
    enriched: list[EnrichedTrade] = []
    for t in trades:
        ptax = get_ptax(t.date, cache_dir=cache_dir)
        if ptax is not None:
            proceeds_brl = t.proceeds_usd * ptax
            cost_brl = t.cost_usd * ptax
            pnl_brl = t.pnl_usd * ptax
        else:
            proceeds_brl = cost_brl = pnl_brl = None
        enriched.append(
            EnrichedTrade(
                date=t.date,
                symbol=t.symbol,
                asset_type=t.asset_type,
                quantity=t.quantity,
                proceeds_usd=t.proceeds_usd,
                cost_usd=t.cost_usd,
                pnl_usd=t.pnl_usd,
                ptax_rate=ptax,
                proceeds_brl=proceeds_brl,
                cost_brl=cost_brl,
                pnl_brl=pnl_brl,
            )
        )
    return enriched


_MONTH_NAMES = [
    "Jan",
    "Feb",
    "Mar",
    "Apr",
    "May",
    "Jun",
    "Jul",
    "Aug",
    "Sep",
    "Oct",
    "Nov",
    "Dec",
]


def aggregate_by_month(trades: list[EnrichedTrade]) -> list[MonthSummary]:
    buckets: dict[tuple[int, int], list[float]] = {}
    for t in trades:
        if t.pnl_brl is None:
            continue
        key = (t.date.year, t.date.month)
        buckets.setdefault(key, []).append(t.pnl_brl)

    summaries: list[MonthSummary] = []
    for year, month in sorted(buckets):
        pnls = buckets[(year, month)]
        gains = sum(p for p in pnls if p > 0)
        losses = sum(p for p in pnls if p < 0)
        summaries.append(
            MonthSummary(
                month=f"{_MONTH_NAMES[month - 1]}/{year}",
                gross_gain_brl=gains,
                gross_loss_brl=losses,
                net_brl=gains + losses,
            )
        )
    return summaries


def aggregate_by_asset_type(trades: list[EnrichedTrade]) -> list[AssetTypeSummary]:
    buckets: dict[str, list[EnrichedTrade]] = {}
    for t in trades:
        buckets.setdefault(t.asset_type, []).append(t)

    summaries: list[AssetTypeSummary] = []
    for asset_type in sorted(buckets):
        group = buckets[asset_type]
        incomplete = any(t.ptax_rate is None for t in group)
        gain_usd = sum(t.pnl_usd for t in group if t.pnl_usd > 0)
        loss_usd = sum(t.pnl_usd for t in group if t.pnl_usd < 0)
        gain_brl = sum(
            t.pnl_brl for t in group if t.pnl_brl is not None and t.pnl_brl > 0
        )
        loss_brl = sum(
            t.pnl_brl for t in group if t.pnl_brl is not None and t.pnl_brl < 0
        )
        summaries.append(
            AssetTypeSummary(
                asset_type=asset_type,
                trade_count=len(group),
                gross_gain_usd=gain_usd,
                gross_loss_usd=loss_usd,
                net_usd=gain_usd + loss_usd,
                gross_gain_brl=gain_brl,
                gross_loss_brl=loss_brl,
                net_brl=gain_brl + loss_brl,
                brl_incomplete=incomplete,
            )
        )
    return summaries


def compute_totals(trades: list[EnrichedTrade]) -> Totals:
    missing_ptax = any(t.ptax_rate is None for t in trades)
    gain_usd = sum(t.pnl_usd for t in trades if t.pnl_usd > 0)
    loss_usd = sum(t.pnl_usd for t in trades if t.pnl_usd < 0)
    gain_brl = sum(t.pnl_brl for t in trades if t.pnl_brl is not None and t.pnl_brl > 0)
    loss_brl = sum(t.pnl_brl for t in trades if t.pnl_brl is not None and t.pnl_brl < 0)
    return Totals(
        gain_usd=gain_usd,
        loss_usd=loss_usd,
        net_usd=gain_usd + loss_usd,
        gain_brl=gain_brl,
        loss_brl=loss_brl,
        net_brl=gain_brl + loss_brl,
        brl_incomplete=missing_ptax,
    )
