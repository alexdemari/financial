"""
Comparative backtest: technical model selection for the dividend portfolio.

For each asset, compares all supported technical models (lux, smc, rsi-sma)
over the full available OHLC history. Each BUY signal is evaluated over a
45-calendar-day forward window.

Metrics per model:
  precision:       fraction of BUY signals with close[t+45] >= close[t] * 1.05
  false_positive:  fraction of BUY signals with close[t+45] <= close[t] * 0.95
  neutral:         fraction of signals between the two thresholds

A model replaces the current one in the YAML only when:
  delta_precision > 5 percentage points AND total evaluable signals >= 5.

Usage:
  PYTHONPATH=src uv run python -m dividend_tracker.backtest \\
    --config config/dividend_portfolio.yaml \\
    --data-dir data/stocks \\
    --output reports/backtest/dividend_model_comparison.md
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

import pandas as pd
import yaml

from dividend_tracker.config import (
    DividendAssetConfig,
    DividendPortfolioConfig,
    load_portfolio_config,
)
from stock_analyzer.analyzer import StockDataAnalyzer
from stock_analyzer.enums import Signal


EVALUATION_DAYS = 45
GAIN_THRESHOLD = 0.05
LOSS_THRESHOLD = -0.05
MIN_DELTA_PP = 5.0
MIN_SIGNALS = 5
ALL_MODELS: list[str] = ["lux", "smc", "rsi-sma"]


@dataclass
class ModelResult:
    model: str
    total_signals: int
    precision: float
    false_positive: float
    neutral: float
    period_start: date | None
    period_end: date | None


@dataclass
class AssetBacktestResult:
    ticker: str
    current_model: str
    models: dict[str, ModelResult]
    recommended_model: str
    changed: bool
    change_reason: str


def run_backtest(
    portfolio_config: DividendPortfolioConfig,
    data_dir: str | Path = "data/stocks",
) -> list[AssetBacktestResult]:
    results = []
    for asset in portfolio_config.assets:
        results.append(_backtest_asset(asset, data_dir=data_dir))
    return results


def _backtest_asset(
    asset: DividendAssetConfig,
    data_dir: str | Path,
) -> AssetBacktestResult:
    symbol = asset.yahoo_ticker
    try:
        analyzer = StockDataAnalyzer(signal_model="lux")
        ohlc_df = analyzer.load_local_data(symbol, data_dir=data_dir, interval="1d")
    except Exception as exc:
        return AssetBacktestResult(
            ticker=asset.ticker,
            current_model=asset.technical_model,
            models={},
            recommended_model=asset.technical_model,
            changed=False,
            change_reason=f"OHLC unavailable: {exc}",
        )

    if ohlc_df.empty or len(ohlc_df) < 50:
        return AssetBacktestResult(
            ticker=asset.ticker,
            current_model=asset.technical_model,
            models={},
            recommended_model=asset.technical_model,
            changed=False,
            change_reason=f"Insufficient bars: {len(ohlc_df)}",
        )

    model_results: dict[str, ModelResult] = {}
    for model in ALL_MODELS:
        model_results[model] = _evaluate_model(model, symbol, ohlc_df)

    current = model_results[asset.technical_model]
    best_model = max(model_results, key=lambda m: model_results[m].precision)
    best = model_results[best_model]
    delta_pp = (best.precision - current.precision) * 100.0

    if (
        best_model != asset.technical_model
        and delta_pp > MIN_DELTA_PP
        and current.total_signals >= MIN_SIGNALS
    ):
        changed = True
        recommended = best_model
        change_reason = (
            f"{best_model} precision {best.precision:.1%} vs "
            f"{asset.technical_model} {current.precision:.1%} (+{delta_pp:.1f}pp)"
        )
    else:
        changed = False
        recommended = asset.technical_model
        if best_model == asset.technical_model:
            change_reason = "Current model is best"
        elif delta_pp <= MIN_DELTA_PP:
            change_reason = f"Delta {delta_pp:.1f}pp below {MIN_DELTA_PP}pp threshold"
        else:
            change_reason = f"Too few signals ({current.total_signals} < {MIN_SIGNALS})"

    return AssetBacktestResult(
        ticker=asset.ticker,
        current_model=asset.technical_model,
        models=model_results,
        recommended_model=recommended,
        changed=changed,
        change_reason=change_reason,
    )


def _evaluate_model(
    model: str,
    symbol: str,
    ohlc_df: pd.DataFrame,
) -> ModelResult:
    close = ohlc_df["Close"].copy()
    # Mixed-offset CSV dates (DST transitions) require utc=True before stripping tz.
    idx = pd.to_datetime(close.index, utc=True)
    close.index = idx.tz_localize(None)
    period_start = close.index[0].date() if not close.empty else None
    period_end = close.index[-1].date() if not close.empty else None

    try:
        analyzer = StockDataAnalyzer(signal_model=model)
        historical = analyzer.generate_historical_signals(symbol, ohlc_df)
    except Exception:
        return ModelResult(
            model=model,
            total_signals=0,
            precision=0.0,
            false_positive=0.0,
            neutral=0.0,
            period_start=period_start,
            period_end=period_end,
        )

    if historical.empty or "combined_signal" not in historical.columns:
        return ModelResult(
            model=model,
            total_signals=0,
            precision=0.0,
            false_positive=0.0,
            neutral=0.0,
            period_start=period_start,
            period_end=period_end,
        )

    buy_signals = historical[historical["combined_signal"].isin([Signal.BUY, 1])]

    # Historical signals have a 'date' column (not a date index).
    date_col = "date" if "date" in buy_signals.columns else None

    precision_count = 0
    fp_count = 0
    neutral_count = 0
    evaluable = 0

    for _, row in buy_signals.iterrows():
        raw_date = row[date_col] if date_col else row.name
        signal_ts = pd.Timestamp(raw_date)
        if signal_ts.tzinfo is not None:
            signal_ts = signal_ts.tz_convert("UTC").tz_localize(None)
        target_ts = signal_ts + timedelta(days=EVALUATION_DAYS)

        try:
            entry_price = float(close.asof(signal_ts))
        except Exception:
            continue
        if pd.isna(entry_price) or entry_price <= 0:
            continue

        future_close = close[close.index >= target_ts]
        if future_close.empty:
            continue

        exit_price = float(future_close.iloc[0])
        evaluable += 1
        change = (exit_price - entry_price) / entry_price
        if change >= GAIN_THRESHOLD:
            precision_count += 1
        elif change <= LOSS_THRESHOLD:
            fp_count += 1
        else:
            neutral_count += 1

    if evaluable == 0:
        precision = false_positive = neutral = 0.0
    else:
        precision = precision_count / evaluable
        false_positive = fp_count / evaluable
        neutral = neutral_count / evaluable

    return ModelResult(
        model=model,
        total_signals=evaluable,
        precision=precision,
        false_positive=false_positive,
        neutral=neutral,
        period_start=period_start,
        period_end=period_end,
    )


def apply_yaml_updates(
    config_path: str | Path,
    results: list[AssetBacktestResult],
) -> list[str]:
    """Update technical_model in YAML for assets where a better model was found."""
    changed_assets = [r for r in results if r.changed]
    if not changed_assets:
        return []

    config_path = Path(config_path)
    with config_path.open(encoding="utf-8") as fh:
        raw = yaml.safe_load(fh)

    update_map = {r.ticker: r.recommended_model for r in changed_assets}

    for section in ("br_assets", "us_assets"):
        for asset in raw.get(section, []):
            ticker = str(asset.get("ticker", "")).upper()
            if ticker in update_map:
                asset["technical_model"] = update_map[ticker]

    with config_path.open("w", encoding="utf-8") as fh:
        yaml.dump(
            raw, fh, allow_unicode=True, sort_keys=False, default_flow_style=False
        )

    return [r.ticker for r in changed_assets]


def write_report(
    results: list[AssetBacktestResult],
    output_path: str | Path,
    run_date: date,
    yaml_updated: list[str],
) -> Path:
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    lines: list[str] = []
    lines.append("# Backtest Comparativo — Modelos Técnicos (Dividend Portfolio)")
    lines.append(f"\nData: {run_date}")
    lines.append(
        f"Janela de avaliação: {EVALUATION_DAYS} dias calendário por sinal BUY"
    )
    lines.append(
        f"Threshold de precisão: ganho ≥ {GAIN_THRESHOLD:.0%} / queda ≥ {abs(LOSS_THRESHOLD):.0%}"
    )
    lines.append(
        f"Critério de troca: delta precisão > {MIN_DELTA_PP}pp e sinais ≥ {MIN_SIGNALS}"
    )
    lines.append("\n---\n")

    lines.append("## Resultados por Ativo\n")

    for result in results:
        lines.append(f"### {result.ticker}")
        lines.append(f"- Modelo atual: `{result.current_model}`")
        lines.append(f"- Modelo recomendado: `{result.recommended_model}`")
        updated_note = " ✅ YAML atualizado" if result.ticker in yaml_updated else ""
        lines.append(f"- Decisão: {result.change_reason}{updated_note}")

        if not result.models:
            lines.append("- Status: dados insuficientes\n")
            continue

        lines.append("")
        lines.append(
            "| Modelo | Sinais | Precisão | Falso Positivo | Neutro | Período |"
        )
        lines.append(
            "|--------|--------|----------|----------------|--------|---------|"
        )

        for model_name in ALL_MODELS:
            if model_name not in result.models:
                continue
            m = result.models[model_name]
            period = ""
            if m.period_start and m.period_end:
                period = f"{m.period_start} → {m.period_end}"
            marker = " ◀" if model_name == result.recommended_model else ""
            lines.append(
                f"| `{model_name}`{marker} | {m.total_signals} "
                f"| {m.precision:.1%} | {m.false_positive:.1%} "
                f"| {m.neutral:.1%} | {period} |"
            )
        lines.append("")

    lines.append("---\n")
    lines.append("## Sumário de Mudanças\n")

    changed = [r for r in results if r.changed]
    if yaml_updated:
        lines.append(
            "Os seguintes ativos tiveram `technical_model` atualizado no YAML:\n"
        )
        for r in changed:
            verb = (
                "atualizado"
                if r.ticker in yaml_updated
                else "recomendado (não aplicado)"
            )
            lines.append(
                f"- **{r.ticker}**: `{r.current_model}` → `{r.recommended_model}` — {verb} ({r.change_reason})"
            )
    elif changed:
        lines.append(
            "Os seguintes ativos têm modelo recomendado diferente do atual (delta > 5pp). "
            "Execute `just backtest-dividends-apply` para aplicar as mudanças no YAML:\n"
        )
        for r in changed:
            lines.append(
                f"- **{r.ticker}**: `{r.current_model}` → `{r.recommended_model}` ({r.change_reason})"
            )
    else:
        lines.append(
            "Nenhuma mudança recomendada. Todos os deltas abaixo de 5pp ou sinais insuficientes."
        )

    lines.append(
        "\n> Metodologia: precisão = sinais BUY com alta ≥5% em 45 dias / total de sinais avaliáveis. "
        "Sinais no final da série sem janela completa são descartados."
    )

    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return output_path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Backtest comparativo de modelos técnicos"
    )
    parser.add_argument("--config", default="config/dividend_portfolio.yaml")
    parser.add_argument("--data-dir", default="data/stocks")
    parser.add_argument(
        "--output",
        default="reports/backtest/dividend_model_comparison.md",
    )
    parser.add_argument(
        "--update-yaml",
        action="store_true",
        help="Apply model changes to YAML when delta > 5pp (default: report only)",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    portfolio_config = load_portfolio_config(args.config)
    results = run_backtest(portfolio_config, data_dir=args.data_dir)

    yaml_updated: list[str] = []
    if args.update_yaml:
        yaml_updated = apply_yaml_updates(args.config, results)
        if yaml_updated:
            print(f"YAML atualizado para: {', '.join(yaml_updated)}")

    output_path = write_report(
        results,
        output_path=args.output,
        run_date=date.today(),
        yaml_updated=yaml_updated,
    )
    print(f"Relatorio gerado: {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
