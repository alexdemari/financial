"""Brazilian moving weighted-average cost basis for crypto assets."""

import json
from datetime import datetime
from pathlib import Path

from crypto_trades.models import AssetCostBasis, CryptoTrade


def compute_cost_basis(trades: list[CryptoTrade]) -> dict[str, AssetCostBasis]:
    """Calculate moving weighted-average PTAX cost per asset."""
    basis: dict[str, AssetCostBasis] = {}
    for trade in sorted(trades, key=lambda item: item.datetime):
        asset_basis = basis.setdefault(trade.asset, AssetCostBasis(asset=trade.asset))
        if trade.trade_type in {"BUY", "SWAP_BUY"}:
            total_quantity = asset_basis.quantity + trade.quantity
            total_cost = (
                asset_basis.quantity * asset_basis.avg_cost_brl_ptax
                + trade.value_brl_ptax
            )
            total_usdt_cost = (
                asset_basis.quantity * asset_basis.avg_cost_usdt + trade.total_usdt
            )
            asset_basis.avg_cost_brl_ptax = (
                total_cost / total_quantity if total_quantity else 0.0
            )
            asset_basis.avg_cost_usdt = (
                total_usdt_cost / total_quantity if total_quantity else 0.0
            )
            asset_basis.quantity = total_quantity
            asset_basis.total_invested_brl += trade.value_brl_ptax
            asset_basis.trades_count += 1
        elif trade.trade_type in {"SELL", "SWAP_SELL"}:
            asset_basis.quantity = max(0.0, asset_basis.quantity - trade.quantity)
            asset_basis.trades_count += 1
    return basis


def save_cost_basis(path: Path, basis: dict[str, AssetCostBasis]) -> None:
    """Save a JSON cost-basis snapshot for reporting and IRPF."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "updated_at": datetime.now().isoformat(timespec="seconds"),
                "assets": {asset: vars(item) for asset, item in basis.items()},
            },
            indent=2,
        ),
        encoding="utf-8",
    )
