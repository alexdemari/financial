from dataclasses import dataclass

from dividend_tracker.config import DividendAssetConfig
from dividend_tracker.price_ceiling import PriceCeilingResult


@dataclass(frozen=True)
class AssetDecision:
    asset: DividendAssetConfig
    price_ceiling: PriceCeilingResult
    action: str  # "BUY" | "OVERPRICED"


def evaluate_asset(
    asset: DividendAssetConfig,
    price_ceiling: PriceCeilingResult,
) -> AssetDecision:
    action = "BUY" if price_ceiling.is_below_or_equal_ceiling else "OVERPRICED"
    return AssetDecision(asset=asset, price_ceiling=price_ceiling, action=action)
