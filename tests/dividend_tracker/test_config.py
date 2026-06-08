from pathlib import Path

import pytest

from dividend_tracker.config import load_portfolio_config, parse_portfolio_config


def test_load_portfolio_config_parses_assets(tmp_path: Path):
    config_path = tmp_path / "portfolio.yaml"
    config_path.write_text(
        """
settings:
  min_dy: 0.07
  dy_source: trailing
br_assets:
  - ticker: EGIE3
    sector: Energia
    name: Engie
    target_weight: 0.5
    technical_model: smc
us_assets:
  - ticker: SCHD
    sector: ETF
    name: SCHD
    target_weight: 0.5
    technical_model: lux
""",
        encoding="utf-8",
    )

    config = load_portfolio_config(config_path)

    assert config.settings.min_dy == 0.07
    assert config.br_assets[0].ticker == "EGIE3"
    assert config.br_assets[0].yahoo_ticker == "EGIE3.SA"
    assert config.us_assets[0].yahoo_ticker == "SCHD"


def test_resolve_min_dy_uses_asset_override():
    config = parse_portfolio_config(
        {
            "settings": {"min_dy": 0.06},
            "us_assets": [
                {
                    "ticker": "PEP",
                    "sector": "Consumer Staples",
                    "name": "PepsiCo",
                    "target_weight": 0.0,
                    "technical_model": "smc",
                    "min_dy": 0.038,
                }
            ],
        }
    )

    assert config.resolve_min_dy(config.us_assets[0]) == 0.038


def test_resolve_min_dy_falls_back_to_global():
    config = parse_portfolio_config(
        {
            "settings": {"min_dy": 0.06},
            "us_assets": [
                {
                    "ticker": "SCHD",
                    "sector": "ETF",
                    "name": "SCHD",
                    "target_weight": 1.0,
                    "technical_model": "lux",
                }
            ],
        }
    )

    assert config.resolve_min_dy(config.us_assets[0]) == 0.06


def test_asset_without_min_dy_field_loads_correctly():
    config = parse_portfolio_config(
        {
            "settings": {"min_dy": 0.06},
            "us_assets": [
                {
                    "ticker": "SCHD",
                    "sector": "ETF",
                    "name": "SCHD",
                    "target_weight": 1.0,
                    "technical_model": "lux",
                }
            ],
        }
    )

    assert config.us_assets[0].min_dy is None


def test_asset_with_notes_field_loads_correctly():
    config = parse_portfolio_config(
        {
            "settings": {"min_dy": 0.06},
            "us_assets": [
                {
                    "ticker": "PEP",
                    "sector": "Consumer Staples",
                    "name": "PepsiCo",
                    "target_weight": 0.0,
                    "technical_model": "smc",
                    "notes": "Dividend King",
                }
            ],
        }
    )

    assert config.us_assets[0].notes == "Dividend King"


def test_asset_with_zero_target_weight_loads_correctly():
    config = parse_portfolio_config(
        {
            "settings": {"min_dy": 0.06},
            "us_assets": [
                {
                    "ticker": "PEP",
                    "sector": "Consumer Staples",
                    "name": "PepsiCo",
                    "target_weight": 0.0,
                    "technical_model": "smc",
                }
            ],
        }
    )

    assert config.us_assets[0].target_weight == 0.0


def test_parse_portfolio_config_requires_asset_fields():
    with pytest.raises(ValueError, match="missing: sector"):
        parse_portfolio_config(
            {
                "br_assets": [
                    {
                        "ticker": "EGIE3",
                        "name": "Engie",
                        "target_weight": 1.0,
                        "technical_model": "smc",
                    }
                ]
            }
        )


def test_parse_portfolio_config_rejects_invalid_model():
    with pytest.raises(ValueError, match="unsupported technical_model"):
        parse_portfolio_config(
            {
                "us_assets": [
                    {
                        "ticker": "SCHD",
                        "sector": "ETF",
                        "name": "SCHD",
                        "target_weight": 1.0,
                        "technical_model": "macd",
                    }
                ]
            }
        )


def test_parse_portfolio_config_rejects_empty_portfolio():
    with pytest.raises(ValueError, match="at least one asset"):
        parse_portfolio_config({"settings": {"min_dy": 0.06}})
