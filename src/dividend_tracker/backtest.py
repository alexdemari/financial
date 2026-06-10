"""
Comparative backtest: technical model selection for the dividend portfolio.

For each asset, compares all supported technical models (lux, smc, rsi-sma).
Each BUY signal is evaluated over a 45-calendar-day forward window.

Metrics per model:
  precision:       fraction of BUY signals with close[t+45] >= close[t] * 1.05
  false_positive:  fraction of BUY signals with close[t+45] <= close[t] * 0.95
  max_drawdown:    worst low reached inside the 45-day window vs entry price

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
DEFAULT_START_DATE = "2022-01-01"
DEFAULT_END_DATE = "2026-05-31"


@dataclass
class ModelResult:
    model: str
    total_signals: int
    precision: float
    false_positive: float
    neutral: float
    max_drawdown: float
    period_start: date | None
    period_end: date | None


@dataclass
class AssetBacktestResult:
    config_ticker: str
    ticker: str
    current_model: str
    models: dict[str, ModelResult]
    recommended_model: str
    changed: bool
    change_reason: str


def run_backtest(
    portfolio_config: DividendPortfolioConfig,
    data_dir: str | Path = "data/stocks",
    start_date: str | None = DEFAULT_START_DATE,
    end_date: str | None = DEFAULT_END_DATE,
) -> list[AssetBacktestResult]:
    results = []
    for asset in portfolio_config.assets:
        results.append(
            _backtest_asset(
                asset,
                data_dir=data_dir,
                start_date=start_date,
                end_date=end_date,
            )
        )
    return results


def _backtest_asset(
    asset: DividendAssetConfig,
    data_dir: str | Path,
    start_date: str | None,
    end_date: str | None,
) -> AssetBacktestResult:
    symbol = asset.yahoo_ticker
    try:
        analyzer = StockDataAnalyzer(signal_model="lux")
        ohlc_df = analyzer.load_local_data(symbol, data_dir=data_dir, interval="1d")
    except Exception as exc:
        return AssetBacktestResult(
            config_ticker=asset.ticker,
            ticker=symbol,
            current_model=asset.technical_model,
            models={},
            recommended_model=asset.technical_model,
            changed=False,
            change_reason=f"OHLC unavailable: {exc}",
        )

    if ohlc_df.empty or len(ohlc_df) < 50:
        return AssetBacktestResult(
            config_ticker=asset.ticker,
            ticker=symbol,
            current_model=asset.technical_model,
            models={},
            recommended_model=asset.technical_model,
            changed=False,
            change_reason=f"Insufficient bars: {len(ohlc_df)}",
        )

    model_results: dict[str, ModelResult] = {}
    for model in ALL_MODELS:
        model_results[model] = _evaluate_model(
            model,
            symbol,
            ohlc_df,
            start_date=start_date,
            end_date=end_date,
        )

    current = model_results[asset.technical_model]
    best_model = max(model_results, key=lambda m: model_results[m].precision)
    best = model_results[best_model]
    delta_pp = (best.precision - current.precision) * 100.0

    if (
        best_model != asset.technical_model
        and delta_pp > MIN_DELTA_PP
        and best.total_signals >= MIN_SIGNALS
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
            change_reason = f"Too few signals ({best.total_signals} < {MIN_SIGNALS})"

    return AssetBacktestResult(
        config_ticker=asset.ticker,
        ticker=symbol,
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
    start_date: str | None,
    end_date: str | None,
) -> ModelResult:
    close = ohlc_df["Close"].copy()
    low = ohlc_df["Low"].copy()
    # Mixed-offset CSV dates (DST transitions) require utc=True before stripping tz.
    idx = pd.to_datetime(close.index, utc=True)
    close.index = idx.tz_localize(None)
    low.index = close.index
    requested_start = pd.Timestamp(start_date) if start_date else close.index[0]
    requested_end = pd.Timestamp(end_date) if end_date else close.index[-1]
    evaluation_close = close[
        (close.index >= requested_start) & (close.index <= requested_end)
    ]
    period_start = (
        evaluation_close.index[0].date() if not evaluation_close.empty else None
    )
    period_end = (
        evaluation_close.index[-1].date() if not evaluation_close.empty else None
    )

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
            max_drawdown=0.0,
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
            max_drawdown=0.0,
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
    worst_drawdown = 0.0

    for _, row in buy_signals.iterrows():
        raw_date = row[date_col] if date_col else row.name
        signal_ts = pd.Timestamp(raw_date)
        if signal_ts.tzinfo is not None:
            signal_ts = signal_ts.tz_convert("UTC").tz_localize(None)
        if signal_ts < requested_start or signal_ts > requested_end:
            continue
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
        forward_lows = low[(low.index >= signal_ts) & (low.index <= target_ts)]
        forward_lows = forward_lows[forward_lows > 0]
        if not forward_lows.empty:
            signal_drawdown = (float(forward_lows.min()) - entry_price) / entry_price
            worst_drawdown = min(worst_drawdown, signal_drawdown)

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
        max_drawdown=worst_drawdown,
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

    update_map = {r.config_ticker: r.recommended_model for r in changed_assets}

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
    start_date: str | None,
    end_date: str | None,
) -> Path:
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    covered_start, covered_end = _covered_period(results)
    requested_period = _format_requested_period(start_date, end_date)
    covered_period = _format_period(covered_start, covered_end)

    lines: list[str] = []
    lines.append(
        "# Backtest — Comparativo de modelos técnicos para carteira de dividendos"
    )
    lines.append(f"Data de geração: {run_date}")
    lines.append(f"Período solicitado: {requested_period}")
    lines.append(f"Período coberto: {covered_period}")
    lines.append("")
    lines.append("## Metodologia")
    lines.append("- Sinal de compra: BUY gerado pelo modelo técnico")
    lines.append(
        "- Observação: WATCH é uma classificação do `dividend_tracker` sobre sinal recente; "
        "o `stock_analyzer` histórico expõe BUY/HOLD/SELL, então o backtest mede BUY"
    )
    lines.append(f"- Janela de avaliação: {EVALUATION_DAYS} dias após o sinal")
    lines.append(f"- Critério de sucesso: alta ≥ {GAIN_THRESHOLD:.0%} no período")
    lines.append(
        f"- Critério de falso positivo: queda ≥ {abs(LOSS_THRESHOLD):.0%} no período"
    )
    lines.append(
        "- Drawdown máximo: pior mínima dentro da janela de 45 dias contra o preço de entrada"
    )
    lines.append(
        f"- Critério de atualização: delta precisão > {MIN_DELTA_PP:.0f}pp "
        f"e modelo recomendado com pelo menos {MIN_SIGNALS} sinais"
    )
    lines.append("")
    lines.append("## Resultados por ativo")
    lines.append("")

    for result in results:
        lines.append(f"### {result.ticker}")

        if not result.models:
            lines.append("")
            lines.append(
                f"**Modelo recomendado: {result.recommended_model} — {result.change_reason}**"
            )
            lines.append("")
            continue

        lines.append("")
        lines.append(
            "| Modelo | Sinais | Precisão | Falsos+ | Drawdown máx | Recomendação |"
        )
        lines.append(
            "|--------|--------|----------|---------|--------------|--------------|"
        )

        for model_name in ALL_MODELS:
            if model_name not in result.models:
                continue
            m = result.models[model_name]
            recommendation = _model_recommendation(result, model_name)
            lines.append(
                f"| {model_name} | {m.total_signals} "
                f"| {m.precision:.1%} | {m.false_positive:.1%} "
                f"| {m.max_drawdown:.1%} | {recommendation} |"
            )
        lines.append("")
        lines.append(
            f"**Modelo recomendado: {result.recommended_model} — {result.change_reason}**"
        )
        lines.append("")

    lines.append("## Resumo consolidado")
    lines.append("")
    lines.append(
        "| Ativo | Modelo atual | Melhor modelo | Precisão atual | Precisão melhor | Mudar? |"
    )
    lines.append(
        "|-------|--------------|---------------|----------------|-----------------|--------|"
    )
    for result in results:
        current = result.models.get(result.current_model)
        best_model = _best_model(result)
        best = result.models.get(best_model) if best_model else None
        current_precision = f"{current.precision:.1%}" if current else "n/a"
        best_precision = f"{best.precision:.1%}" if best else "n/a"
        change_label = "Sim" if result.changed else "Não"
        lines.append(
            f"| {result.ticker} | {result.current_model} | {best_model or result.recommended_model} "
            f"| {current_precision} | {best_precision} | {change_label} |"
        )

    lines.append("")
    lines.append("## Decisões")
    lines.append("")
    _append_decision_sections(lines, results, yaml_updated)

    if yaml_updated:
        lines.append("")
        lines.append(f"YAML atualizado para: {', '.join(yaml_updated)}")

    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return output_path


def _covered_period(
    results: list[AssetBacktestResult],
) -> tuple[date | None, date | None]:
    starts: list[date] = []
    ends: list[date] = []
    for result in results:
        for model_result in result.models.values():
            if model_result.period_start is not None:
                starts.append(model_result.period_start)
            if model_result.period_end is not None:
                ends.append(model_result.period_end)
    return (min(starts) if starts else None, max(ends) if ends else None)


def _format_requested_period(start_date: str | None, end_date: str | None) -> str:
    if start_date and end_date:
        return f"{start_date} a {end_date}"
    if start_date:
        return f"a partir de {start_date}"
    if end_date:
        return f"ate {end_date}"
    return "historico completo disponivel"


def _format_period(start_date: date | None, end_date: date | None) -> str:
    if start_date is None or end_date is None:
        return "sem dados avaliaveis"
    return f"{start_date} a {end_date}"


def _best_model(result: AssetBacktestResult) -> str | None:
    if not result.models:
        return None
    return max(result.models, key=lambda model: result.models[model].precision)


def _best_result(result: AssetBacktestResult) -> ModelResult | None:
    best_model = _best_model(result)
    if best_model is None:
        return None
    return result.models[best_model]


def _model_recommendation(result: AssetBacktestResult, model_name: str) -> str:
    if model_name == result.recommended_model and model_name == result.current_model:
        return "Atual / manter"
    if model_name == result.recommended_model:
        return "Recomendado"
    if model_name == result.current_model:
        return "Atual"
    return "-"


def _append_decision_sections(
    lines: list[str],
    results: list[AssetBacktestResult],
    yaml_updated: list[str],
) -> None:
    current_is_best = [
        result for result in results if _best_model(result) == result.current_model
    ]
    changed = [result for result in results if result.changed]
    insufficient = []
    for result in results:
        best_result = _best_result(result)
        if (
            _best_model(result) != result.current_model
            and best_result is not None
            and best_result.total_signals < MIN_SIGNALS
        ):
            insufficient.append(result)
    insignificant = [
        result
        for result in results
        if result not in current_is_best
        and result not in changed
        and result not in insufficient
        and result.models
    ]

    lines.append("### Ativos onde o modelo atual é o melhor -> manter")
    if current_is_best:
        for result in current_is_best:
            lines.append(f"- {result.ticker}: `{result.current_model}`")
    else:
        lines.append("- Nenhum")

    lines.append("")
    lines.append(
        "### Ativos onde outro modelo é significativamente melhor -> atualizar YAML"
    )
    if changed:
        for result in changed:
            status = "atualizado" if result.ticker in yaml_updated else "nao aplicado"
            lines.append(
                f"- {result.ticker}: `{result.current_model}` -> "
                f"`{result.recommended_model}` ({status}; {result.change_reason})"
            )
    else:
        lines.append("- Nenhum")

    lines.append("")
    lines.append(
        "### Ativos sem diferença significativa (< 5pp) -> manter modelo atual por simplicidade"
    )
    if insignificant:
        for result in insignificant:
            lines.append(f"- {result.ticker}: {result.change_reason}")
    else:
        lines.append("- Nenhum")

    lines.append("")
    lines.append("### Ativos com melhor precisão bruta, mas sinais insuficientes")
    if insufficient:
        for result in insufficient:
            lines.append(f"- {result.ticker}: {result.change_reason}")
    else:
        lines.append("- Nenhum")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Backtest comparativo de modelos técnicos"
    )
    parser.add_argument("--config", default="config/dividend_portfolio.yaml")
    parser.add_argument("--data-dir", default="data/stocks")
    parser.add_argument("--start-date", default=DEFAULT_START_DATE)
    parser.add_argument("--end-date", default=DEFAULT_END_DATE)
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
    results = run_backtest(
        portfolio_config,
        data_dir=args.data_dir,
        start_date=args.start_date,
        end_date=args.end_date,
    )

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
        start_date=args.start_date,
        end_date=args.end_date,
    )
    print(f"Relatorio gerado: {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
