"""Apply official BCB PTAX rates to canonical crypto records."""

from datetime import date
from typing import Callable, Protocol

from crypto_trades.classifier import STABLE_COINS
from crypto_trades.models import CryptoTrade, EarnRecord
from irpf_report.ptax import get_ptax


class PtaxLookup(Protocol):
    def __call__(self, trade_date: date) -> float | None:
        ...


ProgressCallback = Callable[[int, int], None]


def enrich_trades(
    trades: list[CryptoTrade],
    lookup: PtaxLookup = get_ptax,
    on_progress: ProgressCallback | None = None,
) -> list[CryptoTrade]:
    """Enrich trades in place with the official PTAX rate and BRL value."""
    for completed, trade in enumerate(trades, start=1):
        rate = lookup(date.fromisoformat(trade.date))
        trade.ptax_bcb = rate
        if rate:
            if not trade.total_usdt and trade.value_brl_binance:
                trade.total_usdt = trade.value_brl_binance / rate
                trade.price_usdt = (
                    trade.total_usdt / trade.quantity if trade.quantity else 0.0
                )
            trade.value_brl_ptax = trade.total_usdt * rate
        if on_progress:
            on_progress(completed, len(trades))
    return trades


def enrich_earnings(
    earnings: list[EarnRecord],
    lookup: PtaxLookup = get_ptax,
    on_progress: ProgressCallback | None = None,
) -> list[EarnRecord]:
    """Enrich Simple Earn records with PTAX, preserving Binance BRL values."""
    for completed, earning in enumerate(earnings, start=1):
        rate = lookup(date.fromisoformat(earning.date))
        earning.ptax_bcb = rate
        if rate:
            earning.value_brl_ptax = (
                earning.quantity * rate
                if earning.asset in STABLE_COINS
                else earning.value_brl_binance
            )
        if on_progress:
            on_progress(completed, len(earnings))
    return earnings
