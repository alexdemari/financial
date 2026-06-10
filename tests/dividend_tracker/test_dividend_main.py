from pathlib import Path

from dividend_tracker.decision import AssetDecision, TechnicalSignalResult
from dividend_tracker.main import main
from dividend_tracker.price_ceiling import PriceCeilingResult


def test_main_continues_after_single_asset_failure(monkeypatch, tmp_path: Path):
    config_path = tmp_path / "portfolio.yaml"
    output_path = tmp_path / "report.md"
    config_path.write_text(
        """
settings:
  min_dy: 0.06
us_assets:
  - ticker: GOOD
    sector: ETF
    name: Good ETF
    target_weight: 1.0
    technical_model: lux
    min_dy: 0.038
    ceiling_method: average_6y
  - ticker: BAD
    sector: ETF
    name: Bad ETF
    target_weight: 1.0
    technical_model: lux
""",
        encoding="utf-8",
    )
    used_data_dirs = []
    used_min_dy_values = []
    used_ceiling_methods = []

    def fake_fetch_dividend_data(ticker, br=False, local_only=False):
        if ticker == "BAD":
            raise FileNotFoundError("missing dividend cache")
        return object()

    def fake_calculate_price_ceiling(ticker, min_dy, **kwargs):
        used_min_dy_values.append(min_dy)
        used_ceiling_methods.append(kwargs["ceiling_method"])
        return PriceCeilingResult(
            ticker="GOOD",
            price_ceiling=50.0,
            current_dy=0.075,
            trailing_annual_dividends=3.0,
            current_price=40.0,
            margin_pct=0.25,
            min_dy=min_dy,
        )

    def fake_get_technical_signal(asset, data_dir, local_only):
        used_data_dirs.append(str(data_dir))
        return TechnicalSignalResult(
            signal="BUY",
            model=asset.technical_model,
            event_type="BUY",
            days_since_event=0,
            interpretation="mock",
        )

    def fake_evaluate_asset(asset, price_ceiling, technical_signal):
        return AssetDecision(
            asset=asset,
            price_ceiling=price_ceiling,
            technical_signal=technical_signal,
            decision="BUY",
            description="Comprar agora",
        )

    monkeypatch.setattr(
        "dividend_tracker.main.fetch_dividend_data", fake_fetch_dividend_data
    )
    monkeypatch.setattr(
        "dividend_tracker.main.calculate_price_ceiling", fake_calculate_price_ceiling
    )
    monkeypatch.setattr(
        "dividend_tracker.main.get_technical_signal", fake_get_technical_signal
    )
    monkeypatch.setattr("dividend_tracker.main.evaluate_asset", fake_evaluate_asset)

    exit_code = main(
        [
            "--config",
            str(config_path),
            "--output",
            str(output_path),
            "--local-only",
            "--data-dir",
            "/custom/stocks",
        ]
    )

    report = output_path.read_text(encoding="utf-8")
    assert exit_code == 0
    assert used_data_dirs == ["/custom/stocks"]
    assert used_min_dy_values == [0.038]
    assert used_ceiling_methods == ["average_6y"]
    assert "GOOD" in report
    assert "## Erros de processamento" in report
    assert "- BAD: missing dividend cache" in report
