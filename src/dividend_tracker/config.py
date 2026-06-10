from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal, Optional

import yaml


TechnicalModel = Literal["lux", "smc", "rsi-sma"]
CeilingMethod = Literal["trailing", "average_6y"]
DySource = Literal["trailing", "forward", "average_6y"]


@dataclass(frozen=True)
class DividendSettings:
    min_dy: float = 0.06
    dy_source: DySource = "trailing"
    currency_br: str = "BRL"
    currency_us: str = "USD"


@dataclass(frozen=True)
class DividendAssetConfig:
    ticker: str
    sector: str
    name: str
    target_weight: float
    technical_model: TechnicalModel
    market: Literal["BR", "US"]
    min_dy: Optional[float] = None
    ceiling_method: Optional[CeilingMethod] = None
    notes: Optional[str] = None

    @property
    def yahoo_ticker(self) -> str:
        if self.market == "BR" and not self.ticker.endswith(".SA"):
            return f"{self.ticker}.SA"
        return self.ticker


@dataclass(frozen=True)
class DividendPortfolioConfig:
    settings: DividendSettings
    br_assets: list[DividendAssetConfig]
    us_assets: list[DividendAssetConfig]

    @property
    def assets(self) -> list[DividendAssetConfig]:
        return [*self.br_assets, *self.us_assets]

    def resolve_min_dy(self, asset: DividendAssetConfig) -> float:
        """Return asset min_dy override, falling back to portfolio global."""
        return asset.min_dy if asset.min_dy is not None else self.settings.min_dy

    def resolve_ceiling_method(self, asset: DividendAssetConfig) -> CeilingMethod:
        """Return asset ceiling method override, falling back to portfolio global."""
        if asset.ceiling_method is not None:
            return asset.ceiling_method
        if self.settings.dy_source == "average_6y":
            return "average_6y"
        return "trailing"


def load_portfolio_config(
    path: str | Path = "config/dividend_portfolio.yaml",
) -> DividendPortfolioConfig:
    config_path = Path(path)
    with config_path.open(encoding="utf-8") as config_file:
        raw_config = yaml.safe_load(config_file) or {}
    if not isinstance(raw_config, dict):
        raise ValueError("Dividend portfolio config must be a YAML mapping")
    return parse_portfolio_config(raw_config)


def parse_portfolio_config(raw_config: dict[str, Any]) -> DividendPortfolioConfig:
    settings = _parse_settings(raw_config.get("settings", {}))
    br_assets = _parse_assets(raw_config.get("br_assets", []), market="BR")
    us_assets = _parse_assets(raw_config.get("us_assets", []), market="US")
    if not br_assets and not us_assets:
        raise ValueError("Dividend portfolio config must include at least one asset")
    return DividendPortfolioConfig(
        settings=settings,
        br_assets=br_assets,
        us_assets=us_assets,
    )


def _parse_settings(raw_settings: Any) -> DividendSettings:
    if raw_settings is None:
        raw_settings = {}
    if not isinstance(raw_settings, dict):
        raise ValueError("settings must be a mapping")

    min_dy = float(raw_settings.get("min_dy", 0.06))
    if min_dy <= 0:
        raise ValueError("settings.min_dy must be greater than zero")

    dy_source = raw_settings.get("dy_source", "trailing")
    if dy_source not in {"trailing", "forward", "average_6y"}:
        raise ValueError("settings.dy_source must be trailing, forward, or average_6y")

    return DividendSettings(
        min_dy=min_dy,
        dy_source=dy_source,
        currency_br=str(raw_settings.get("currency_br", "BRL")),
        currency_us=str(raw_settings.get("currency_us", "USD")),
    )


def _parse_assets(
    raw_assets: Any,
    market: Literal["BR", "US"],
) -> list[DividendAssetConfig]:
    if raw_assets is None:
        return []
    if not isinstance(raw_assets, list):
        raise ValueError(f"{market} assets must be a list")

    assets: list[DividendAssetConfig] = []
    for index, raw_asset in enumerate(raw_assets):
        if not isinstance(raw_asset, dict):
            raise ValueError(f"{market} asset at index {index} must be a mapping")
        assets.append(_parse_asset(raw_asset, market=market, index=index))
    return assets


def _parse_asset(
    raw_asset: dict[str, Any],
    market: Literal["BR", "US"],
    index: int,
) -> DividendAssetConfig:
    required_fields = ("ticker", "sector", "name", "target_weight", "technical_model")
    missing_fields = [field for field in required_fields if field not in raw_asset]
    if missing_fields:
        joined_fields = ", ".join(missing_fields)
        raise ValueError(f"{market} asset at index {index} missing: {joined_fields}")

    technical_model = raw_asset["technical_model"]
    if technical_model not in {"lux", "smc", "rsi-sma"}:
        raise ValueError(
            f"{market} asset at index {index} has unsupported technical_model"
        )

    target_weight = float(raw_asset["target_weight"])
    if target_weight < 0:
        raise ValueError(f"{market} asset at index {index} has negative target_weight")

    min_dy = raw_asset.get("min_dy")
    resolved_asset_min_dy = float(min_dy) if min_dy is not None else None
    if resolved_asset_min_dy is not None and resolved_asset_min_dy <= 0:
        raise ValueError(f"{market} asset at index {index} has non-positive min_dy")

    ceiling_method = raw_asset.get("ceiling_method")
    if ceiling_method is not None and ceiling_method not in {"trailing", "average_6y"}:
        raise ValueError(
            f"{market} asset at index {index} has unsupported ceiling_method"
        )

    return DividendAssetConfig(
        ticker=str(raw_asset["ticker"]).upper(),
        sector=str(raw_asset["sector"]),
        name=str(raw_asset["name"]),
        target_weight=target_weight,
        technical_model=technical_model,
        market=market,
        min_dy=resolved_asset_min_dy,
        ceiling_method=ceiling_method,
        notes=str(raw_asset["notes"]) if raw_asset.get("notes") is not None else None,
    )
