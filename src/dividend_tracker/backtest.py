"""
Comparative backtest: technical model selection for the dividend portfolio.

For each asset, compares all supported technical models (lux, smc, rsi-sma).
Each BUY signal is evaluated over a 45-calendar-day and 90-calendar-day forward window.

Metrics per model:
  precision:           fraction of BUY signals with close[t+45] >= close[t] * 1.05
  precision_90d:       fraction of BUY signals with close[t+90] >= close[t] * 1.05
  false_positive:      fraction of BUY signals with close[t+45] <= close[t] * 0.95
  avg_return_45d:      mean return 45 days after signal
  best_signal_return:  best individual 45d return
  worst_signal_return: worst individual 45d return
  max_dd_post_signal:  avg max drawdown between signal and day 45
  max_drawdown:        worst single drawdown in window
  combined_signals:    signals where model says BUY AND price <= price_ceiling

A model replaces the current one in the YAML only when:
  delta_precision > 5 percentage points AND total evaluable signals >= 5.

Usage:
  PYTHONPATH=src uv run python -m dividend_tracker.backtest \\
    --config config/dividend_portfolio.yaml \\
    --data-dir data/stocks \\
    --output reports/backtest/dividend_entry_points_10y.md
"""

from __future__ import annotations

import argparse
import logging
from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path

import pandas as pd
import yaml

from dividend_tracker.config import (
    DividendAssetConfig,
    DividendPortfolioConfig,
    load_portfolio_config,
)
from dividend_tracker.dividend_data import fetch_dividend_data
from dividend_tracker.price_ceiling import calculate_price_ceiling
from stock_analyzer.analyzer import StockDataAnalyzer
from stock_analyzer.enums import Signal


logger = logging.getLogger(__name__)

EVALUATION_DAYS = 45
EVALUATION_DAYS_90 = 90
GAIN_THRESHOLD = 0.05
LOSS_THRESHOLD = -0.05
MIN_DELTA_PP = 5.0
MIN_SIGNALS = 5
ALL_MODELS: list[str] = ["lux", "smc", "rsi-sma"]
DEFAULT_START_DATE = "2016-01-01"
DEFAULT_END_DATE = "2026-06-10"

# Historical analysis periods
HISTORICAL_PERIODS: dict[str, tuple[str, str]] = {
    "Crise brasileira 2015-2016": ("2015-01-01", "2016-12-31"),
    "COVID marco/2020": ("2020-02-01", "2020-06-30"),
    "Ciclo de Selic alta 2022-2026": ("2022-01-01", "2026-06-10"),
}

# Sweet-spot signal frequency thresholds for dividend portfolio
SWEET_SPOT_MIN_SIGNALS_PER_YEAR = 4
SWEET_SPOT_MAX_SIGNALS_PER_YEAR = 12
LOW_COMBINED_SIGNALS_PER_YEAR_THRESHOLD = 3
HIGH_SIGNALS_PER_YEAR_THRESHOLD = 15


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
    # Extended metrics
    precision_90d: float = 0.0
    avg_return_45d: float = 0.0
    best_signal_return: float = 0.0
    worst_signal_return: float = 0.0
    max_dd_post_signal: float = 0.0
    combined_signals: int = 0

    @property
    def signals_per_year(self) -> float:
        """Annualised signal rate based on period covered."""
        if self.period_start is None or self.period_end is None:
            return 0.0
        days_covered = (self.period_end - self.period_start).days
        if days_covered <= 0:
            return 0.0
        return self.total_signals / (days_covered / 365.25)

    @property
    def combined_signals_per_year(self) -> float:
        """Annualised combined-signal rate."""
        if self.period_start is None or self.period_end is None:
            return 0.0
        days_covered = (self.period_end - self.period_start).days
        if days_covered <= 0:
            return 0.0
        return self.combined_signals / (days_covered / 365.25)


@dataclass
class AssetBacktestResult:
    config_ticker: str
    ticker: str
    current_model: str
    models: dict[str, ModelResult]
    recommended_model: str
    changed: bool
    change_reason: str
    # per-period signal counts: {period_name: {model_name: signal_count}}
    period_signals: dict[str, dict[str, int]] = field(default_factory=dict)


def run_backtest(
    portfolio_config: DividendPortfolioConfig,
    data_dir: str | Path = "data/stocks",
    start_date: str | None = DEFAULT_START_DATE,
    end_date: str | None = DEFAULT_END_DATE,
    dividend_cache_dir: str | Path = "data/dividends",
) -> list[AssetBacktestResult]:
    results = []
    for asset in portfolio_config.assets:
        results.append(
            _backtest_asset(
                asset,
                data_dir=data_dir,
                start_date=start_date,
                end_date=end_date,
                dividend_cache_dir=dividend_cache_dir,
                portfolio_config=portfolio_config,
            )
        )
    return results


def _backtest_asset(
    asset: DividendAssetConfig,
    data_dir: str | Path,
    start_date: str | None,
    end_date: str | None,
    dividend_cache_dir: str | Path,
    portfolio_config: DividendPortfolioConfig,
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

    # Load dividend cache for combined signal calculation
    dividend_ceiling = _load_price_ceiling(
        asset=asset,
        portfolio_config=portfolio_config,
        dividend_cache_dir=dividend_cache_dir,
    )

    model_results: dict[str, ModelResult] = {}
    for model in ALL_MODELS:
        model_results[model] = _evaluate_model(
            model,
            symbol,
            ohlc_df,
            start_date=start_date,
            end_date=end_date,
            price_ceiling=dividend_ceiling,
        )

    # Compute period-level signal counts for historical analysis
    period_signals = _compute_period_signals(symbol, ohlc_df)

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
        period_signals=period_signals,
    )


def _load_price_ceiling(
    asset: DividendAssetConfig,
    portfolio_config: DividendPortfolioConfig,
    dividend_cache_dir: str | Path,
) -> float | None:
    """Return the current price ceiling for an asset, or None if unavailable."""
    cache_path = Path(dividend_cache_dir) / f"{asset.ticker.upper()}.csv"
    if not cache_path.exists():
        return None
    try:
        dividend_data = fetch_dividend_data(
            ticker=asset.ticker,
            br=(asset.market == "BR"),
            cache_dir=dividend_cache_dir,
            local_only=True,
        )
        min_dy = portfolio_config.resolve_min_dy(asset)
        ceiling_method = portfolio_config.resolve_ceiling_method(asset)
        ceiling_result = calculate_price_ceiling(
            ticker=asset.ticker,
            min_dy=min_dy,
            dividend_data=dividend_data,
            br=(asset.market == "BR"),
            local_only=True,
            ceiling_method=ceiling_method,
        )
        return ceiling_result.price_ceiling
    except Exception as exc:
        logger.debug("Could not compute price ceiling for %s: %s", asset.ticker, exc)
        return None


def calculate_combined_signals(
    buy_signal_dates: list[pd.Timestamp],
    close_series: pd.Series,
    price_ceiling: float | None,
) -> int:
    """Count signals where model says BUY AND entry price <= price_ceiling.

    If price_ceiling is None (dividend data not cached), returns total signals —
    we assume all signals are valid because we lack data to filter.
    """
    if price_ceiling is None:
        return len(buy_signal_dates)

    combined = 0
    for signal_ts in buy_signal_dates:
        try:
            entry_price = float(close_series.asof(signal_ts))
        except Exception:
            continue
        if pd.isna(entry_price) or entry_price <= 0:
            continue
        if entry_price <= price_ceiling:
            combined += 1
    return combined


def analyze_historical_period(
    results: list[AssetBacktestResult],
    period_name: str,
    period_start: str,
    period_end: str,
) -> dict[str, dict[str, int]]:
    """Return signal counts per asset+model for a given historical period.

    Returns: {ticker: {model: signal_count}}
    """
    period_data: dict[str, dict[str, int]] = {}
    for result in results:
        period_data[result.ticker] = result.period_signals.get(period_name, {})
    return period_data


def _compute_period_signals(
    symbol: str,
    ohlc_df: pd.DataFrame,
) -> dict[str, dict[str, int]]:
    """Compute signal counts for each predefined historical period per model."""
    period_signal_counts: dict[str, dict[str, int]] = {}

    close = ohlc_df["Close"].copy()
    idx = pd.to_datetime(close.index, utc=True)
    close.index = idx.tz_localize(None)

    for period_name, (period_start_str, period_end_str) in HISTORICAL_PERIODS.items():
        model_counts: dict[str, int] = {}
        period_start_ts = pd.Timestamp(period_start_str)
        period_end_ts = pd.Timestamp(period_end_str)

        for model_name in ALL_MODELS:
            try:
                analyzer = StockDataAnalyzer(signal_model=model_name)
                historical = analyzer.generate_historical_signals(symbol, ohlc_df)
            except Exception:
                model_counts[model_name] = 0
                continue

            if historical.empty or "combined_signal" not in historical.columns:
                model_counts[model_name] = 0
                continue

            buy_signals = historical[
                historical["combined_signal"].isin([Signal.BUY, 1])
            ]
            date_col = "date" if "date" in buy_signals.columns else None

            count = 0
            for _, row in buy_signals.iterrows():
                raw_date = row[date_col] if date_col else row.name
                signal_ts = pd.Timestamp(raw_date)
                if signal_ts.tzinfo is not None:
                    signal_ts = signal_ts.tz_convert("UTC").tz_localize(None)
                if period_start_ts <= signal_ts <= period_end_ts:
                    count += 1
            model_counts[model_name] = count
        period_signal_counts[period_name] = model_counts

    return period_signal_counts


def _evaluate_model(
    model: str,
    symbol: str,
    ohlc_df: pd.DataFrame,
    start_date: str | None,
    end_date: str | None,
    price_ceiling: float | None = None,
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

    empty_result = ModelResult(
        model=model,
        total_signals=0,
        precision=0.0,
        false_positive=0.0,
        neutral=0.0,
        max_drawdown=0.0,
        period_start=period_start,
        period_end=period_end,
    )

    try:
        analyzer = StockDataAnalyzer(signal_model=model)
        historical = analyzer.generate_historical_signals(symbol, ohlc_df)
    except Exception:
        return empty_result

    if historical.empty or "combined_signal" not in historical.columns:
        return empty_result

    buy_signals = historical[historical["combined_signal"].isin([Signal.BUY, 1])]

    # Historical signals have a 'date' column (not a date index).
    date_col = "date" if "date" in buy_signals.columns else None

    precision_count = 0
    precision_90d_count = 0
    fp_count = 0
    neutral_count = 0
    evaluable = 0
    evaluable_90d = 0
    worst_drawdown = 0.0
    individual_returns_45d: list[float] = []
    drawdowns_per_signal: list[float] = []
    buy_signal_timestamps: list[pd.Timestamp] = []

    for _, row in buy_signals.iterrows():
        raw_date = row[date_col] if date_col else row.name
        signal_ts = pd.Timestamp(raw_date)
        if signal_ts.tzinfo is not None:
            signal_ts = signal_ts.tz_convert("UTC").tz_localize(None)
        if signal_ts < requested_start or signal_ts > requested_end:
            continue
        buy_signal_timestamps.append(signal_ts)

        target_ts_45 = signal_ts + timedelta(days=EVALUATION_DAYS)
        target_ts_90 = signal_ts + timedelta(days=EVALUATION_DAYS_90)

        try:
            entry_price = float(close.asof(signal_ts))
        except Exception:
            continue
        if pd.isna(entry_price) or entry_price <= 0:
            continue

        future_close_45 = close[close.index >= target_ts_45]
        if future_close_45.empty:
            continue

        exit_price_45 = float(future_close_45.iloc[0])
        forward_lows = low[(low.index >= signal_ts) & (low.index <= target_ts_45)]
        forward_lows = forward_lows[forward_lows > 0]

        signal_drawdown = 0.0
        if not forward_lows.empty:
            signal_drawdown = (float(forward_lows.min()) - entry_price) / entry_price
            worst_drawdown = min(worst_drawdown, signal_drawdown)
            drawdowns_per_signal.append(signal_drawdown)

        evaluable += 1
        change_45 = (exit_price_45 - entry_price) / entry_price
        individual_returns_45d.append(change_45)

        if change_45 >= GAIN_THRESHOLD:
            precision_count += 1
        elif change_45 <= LOSS_THRESHOLD:
            fp_count += 1
        else:
            neutral_count += 1

        # 90-day precision
        future_close_90 = close[close.index >= target_ts_90]
        if not future_close_90.empty:
            exit_price_90 = float(future_close_90.iloc[0])
            change_90 = (exit_price_90 - entry_price) / entry_price
            evaluable_90d += 1
            if change_90 >= GAIN_THRESHOLD:
                precision_90d_count += 1

    # Compute combined signals (BUY model + price <= ceiling)
    combined_signals = calculate_combined_signals(
        buy_signal_timestamps, close, price_ceiling
    )

    if evaluable == 0:
        precision = false_positive = neutral = 0.0
        avg_return_45d = best_signal_return = worst_signal_return = 0.0
        max_dd_post_signal = 0.0
    else:
        precision = precision_count / evaluable
        false_positive = fp_count / evaluable
        neutral = neutral_count / evaluable
        avg_return_45d = sum(individual_returns_45d) / len(individual_returns_45d)
        best_signal_return = max(individual_returns_45d)
        worst_signal_return = min(individual_returns_45d)
        max_dd_post_signal = (
            sum(drawdowns_per_signal) / len(drawdowns_per_signal)
            if drawdowns_per_signal
            else 0.0
        )

    precision_90d = precision_90d_count / evaluable_90d if evaluable_90d > 0 else 0.0

    return ModelResult(
        model=model,
        total_signals=evaluable,
        precision=precision,
        false_positive=false_positive,
        neutral=neutral,
        max_drawdown=worst_drawdown,
        period_start=period_start,
        period_end=period_end,
        precision_90d=precision_90d,
        avg_return_45d=avg_return_45d,
        best_signal_return=best_signal_return,
        worst_signal_return=worst_signal_return,
        max_dd_post_signal=max_dd_post_signal,
        combined_signals=combined_signals,
    )


def apply_yaml_updates(
    config_path: str | Path,
    results: list[AssetBacktestResult],
    update_model: bool = True,
    update_backtest_ref: bool = False,
    run_date: date | None = None,
) -> list[str]:
    """Update technical_model and optional backtest_ref fields in YAML.

    Uses PyYAML dump — YAML comments are not preserved.
    """
    changed_assets = [r for r in results if r.changed]
    ref_assets = results if update_backtest_ref else []

    if not changed_assets and not ref_assets:
        return []

    config_path = Path(config_path)
    with config_path.open(encoding="utf-8") as fh:
        raw = yaml.safe_load(fh)

    update_map = {r.config_ticker: r for r in results}
    effective_run_date = run_date or date.today()

    for section in ("br_assets", "us_assets"):
        for asset in raw.get(section, []):
            ticker = str(asset.get("ticker", "")).upper()
            if ticker not in update_map:
                continue
            result = update_map[ticker]
            if update_model and result.changed:
                asset["technical_model"] = result.recommended_model
            if update_backtest_ref:
                recommended_result = result.models.get(result.recommended_model)
                asset["backtest_ref"] = str(effective_run_date)
                if recommended_result is not None:
                    asset["backtest_precision"] = round(recommended_result.precision, 4)
                    asset["backtest_signals_per_year"] = round(
                        recommended_result.signals_per_year, 1
                    )

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
    covered_period_str = _format_period(covered_start, covered_end)

    lines: list[str] = []

    # Title block
    lines.append("# Backtest de pontos de entrada — Carteira de dividendos")
    lines.append(f"Período: {requested_period}")
    lines.append(f"Gerado em: {run_date}")
    lines.append(f"Período coberto pelos dados: {covered_period_str}")
    lines.append("")

    # Metodologia
    lines.append("## Metodologia")
    lines.append("- Sinal de compra: BUY gerado pelo modelo técnico")
    lines.append(
        "- Observação: WATCH é uma classificação do `dividend_tracker` sobre sinal recente; "
        "o `stock_analyzer` histórico expõe BUY/HOLD/SELL, então o backtest mede BUY"
    )
    lines.append(f"- Janela de avaliação 45d: {EVALUATION_DAYS} dias após o sinal")
    lines.append(f"- Janela de avaliação 90d: {EVALUATION_DAYS_90} dias após o sinal")
    lines.append(f"- Critério de sucesso: alta >= {GAIN_THRESHOLD:.0%} no período")
    lines.append(
        f"- Critério de falso positivo: queda >= {abs(LOSS_THRESHOLD):.0%} no período"
    )
    lines.append(
        "- Drawdown máximo pós-sinal: média das piores mínimas dentro da janela de 45 dias"
    )
    lines.append(
        "- Sinais combinados: sinal BUY do modelo E preço de entrada <= preço teto (dividend cache)"
    )
    lines.append(
        f"- Critério de atualização: delta precisão > {MIN_DELTA_PP:.0f}pp "
        f"e modelo recomendado com pelo menos {MIN_SIGNALS} sinais"
    )
    lines.append("")

    # Resumo executivo
    lines.append("## Resumo executivo")
    lines.append("")
    lines.append("### Frequência de sinais por modelo (média todos os ativos)")
    lines.append("")
    lines.append("| Modelo | Sinais/ano (média) | Melhor precisão | Mais frequente |")
    lines.append("|--------|-------------------|-----------------|----------------|")

    for model_name in ALL_MODELS:
        model_signal_rates = [
            r.models[model_name].signals_per_year
            for r in results
            if model_name in r.models and r.models[model_name].total_signals > 0
        ]
        model_precisions = [
            r.models[model_name].precision
            for r in results
            if model_name in r.models and r.models[model_name].total_signals > 0
        ]
        avg_rate = (
            sum(model_signal_rates) / len(model_signal_rates)
            if model_signal_rates
            else 0.0
        )
        best_prec = max(model_precisions) if model_precisions else 0.0
        most_frequent_asset = ""
        best_rate = 0.0
        for result in results:
            if model_name in result.models:
                rate = result.models[model_name].signals_per_year
                if rate > best_rate:
                    best_rate = rate
                    most_frequent_asset = result.ticker
        lines.append(
            f"| {model_name} | {avg_rate:.1f} | {best_prec:.1%} | {most_frequent_asset} |"
        )

    lines.append("")
    lines.append("### Ranking de precisão consolidado (top 10)")
    lines.append("")
    lines.append("| Posição | Ativo + Modelo | Precisão 45d | Sinais/ano | Falsos+ |")
    lines.append("|---------|----------------|--------------|------------|---------|")

    ranking_rows: list[tuple[str, str, float, float, float]] = []
    for result in results:
        for model_name, model_result in result.models.items():
            if model_result.total_signals >= MIN_SIGNALS:
                ranking_rows.append(
                    (
                        result.ticker,
                        model_name,
                        model_result.precision,
                        model_result.signals_per_year,
                        model_result.false_positive,
                    )
                )

    ranking_rows.sort(key=lambda x: x[2], reverse=True)
    for position, (ticker, model_name, prec, rate, fp) in enumerate(
        ranking_rows[:10], start=1
    ):
        lines.append(
            f"| {position} | {ticker} + {model_name} | {prec:.1%} | {rate:.1f} | {fp:.1%} |"
        )

    lines.append("")
    lines.append("---")
    lines.append("")

    # Resultados detalhados por ativo
    lines.append("## Resultados detalhados por ativo")
    lines.append("")

    for result in results:
        asset_display = result.config_ticker
        lines.append(f"### {asset_display}")
        lines.append("")

        if not result.models:
            lines.append(f"Sem dados disponíveis: {result.change_reason}")
            lines.append("")
            lines.append(f"**Modelo recomendado: {result.recommended_model}**")
            lines.append("")
            continue

        any_model = next(iter(result.models.values()))
        period_start_str = (
            str(any_model.period_start) if any_model.period_start else "N/A"
        )
        period_end_str = str(any_model.period_end) if any_model.period_end else "N/A"
        lines.append(
            f"Período coberto: {period_start_str} a {period_end_str} | "
            "Percentual do tempo abaixo do preço teto: N/A (requer série histórica de preços)"
        )
        lines.append("")
        lines.append(
            "| Modelo | Sinais | /ano | Combinados | Precisão 45d | Precisão 90d "
            "| Falsos+ | Retorno médio 45d | Max DD pós-sinal |"
        )
        lines.append(
            "|--------|--------|------|------------|--------------|-------------- "
            "|---------|-------------------|-----------------|"
        )

        for model_name in ALL_MODELS:
            if model_name not in result.models:
                continue
            m = result.models[model_name]
            lines.append(
                f"| {model_name} | {m.total_signals} | {m.signals_per_year:.1f} "
                f"| {m.combined_signals} | {m.precision:.1%} | {m.precision_90d:.1%} "
                f"| {m.false_positive:.1%} | {m.avg_return_45d:+.1%} | {m.max_dd_post_signal:.1%} |"
            )
        lines.append("")

        recommended_model_result = result.models.get(result.recommended_model)
        if recommended_model_result is not None:
            rec_prec = f"{recommended_model_result.precision:.1%}"
            rec_rate = f"{recommended_model_result.signals_per_year:.1f}"
            freq_label = _frequency_label(recommended_model_result.signals_per_year)
            rational = (
                f"precisão {rec_prec}, {rec_rate} sinais/ano — frequência {freq_label}"
            )
        else:
            rational = result.change_reason

        lines.append(
            f"**Modelo recomendado: {result.recommended_model}**  "
            f"Racional: {rational}"
        )
        lines.append("")

    lines.append("---")
    lines.append("")

    # Análise de frequência
    lines.append("## Análise de frequência")
    lines.append("")
    lines.append(
        f"### Sweet spot para carteira de dividendos: "
        f"{SWEET_SPOT_MIN_SIGNALS_PER_YEAR}–{SWEET_SPOT_MAX_SIGNALS_PER_YEAR} sinais/ano por ativo"
    )
    lines.append("")

    low_combined: list[str] = []
    high_signals_list: list[str] = []
    for result in results:
        rec_model_result = result.models.get(result.recommended_model)
        if rec_model_result is None:
            continue
        combined_rate = rec_model_result.combined_signals_per_year
        signal_rate = rec_model_result.signals_per_year
        if combined_rate < LOW_COMBINED_SIGNALS_PER_YEAR_THRESHOLD:
            low_combined.append(
                f"- {result.config_ticker} ({result.recommended_model}): "
                f"{combined_rate:.1f} sinais combinados/ano"
            )
        if signal_rate > HIGH_SIGNALS_PER_YEAR_THRESHOLD:
            high_signals_list.append(
                f"- {result.config_ticker} ({result.recommended_model}): "
                f"{signal_rate:.1f} sinais/ano"
            )

    lines.append(
        f"### Ativos com poucos sinais combinados (< {LOW_COMBINED_SIGNALS_PER_YEAR_THRESHOLD}/ano)"
    )
    if low_combined:
        lines.extend(low_combined)
    else:
        lines.append("- Nenhum")
    lines.append("")

    lines.append(
        f"### Ativos com sinais excessivos (> {HIGH_SIGNALS_PER_YEAR_THRESHOLD}/ano)"
    )
    if high_signals_list:
        lines.extend(high_signals_list)
    else:
        lines.append("- Nenhum")
    lines.append("")

    lines.append("---")
    lines.append("")

    # Análise de ciclos históricos
    lines.append("## Análise de ciclos históricos")
    lines.append("")

    for period_name, (period_start_str, period_end_str) in HISTORICAL_PERIODS.items():
        lines.append(f"### {period_name}")
        lines.append(f"Período: {period_start_str} a {period_end_str}")
        lines.append("")
        lines.append("| Ativo | lux | smc | rsi-sma |")
        lines.append("|-------|-----|-----|---------|")
        for result in results:
            period_counts = result.period_signals.get(period_name, {})
            lux_count = period_counts.get("lux", 0)
            smc_count = period_counts.get("smc", 0)
            rsi_count = period_counts.get("rsi-sma", 0)
            lines.append(
                f"| {result.config_ticker} | {lux_count} | {smc_count} | {rsi_count} |"
            )
        lines.append("")

    lines.append("---")
    lines.append("")

    # Decisões — atualização do YAML
    lines.append("## Decisões — atualização do YAML")
    lines.append("")
    _append_decision_sections(lines, results, yaml_updated)

    if yaml_updated:
        lines.append("")
        lines.append(f"YAML atualizado para: {', '.join(yaml_updated)}")

    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return output_path


def _frequency_label(signals_per_year: float) -> str:
    if signals_per_year < SWEET_SPOT_MIN_SIGNALS_PER_YEAR:
        return "baixa"
    if signals_per_year > SWEET_SPOT_MAX_SIGNALS_PER_YEAR:
        return "alta"
    return "adequada"


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

    lines.append("### Modelos mantidos (delta < 5pp ou modelo atual já melhor)")
    kept = current_is_best + insignificant
    if kept:
        for result in kept:
            lines.append(f"- {result.ticker}: `{result.current_model}`")
    else:
        lines.append("- Nenhum")

    lines.append("")
    lines.append("### Modelos atualizados (delta > 5pp)")
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
    lines.append("### Ativos com sinais combinados < 3/ano (considerar relaxar min_dy)")
    low_combined_assets = []
    for result in results:
        rec_model_result = result.models.get(result.recommended_model)
        if rec_model_result is not None:
            if (
                rec_model_result.combined_signals_per_year
                < LOW_COMBINED_SIGNALS_PER_YEAR_THRESHOLD
            ):
                low_combined_assets.append(
                    f"- {result.config_ticker} ({result.recommended_model}): "
                    f"{rec_model_result.combined_signals_per_year:.1f} combinados/ano"
                )
    if low_combined_assets:
        lines.extend(low_combined_assets)
    else:
        lines.append("- Nenhum")

    lines.append("")
    lines.append("### Ativos com sinais insuficientes para comparação (< 5 sinais)")
    if insufficient:
        for result in insufficient:
            lines.append(f"- {result.ticker}: {result.change_reason}")
    else:
        lines.append("- Nenhum")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Backtest 10 anos — pontos de entrada por ativo e modelo"
    )
    parser.add_argument("--config", default="config/dividend_portfolio.yaml")
    parser.add_argument("--data-dir", default="data/stocks")
    parser.add_argument("--dividend-cache-dir", default="data/dividends")
    parser.add_argument("--start-date", default=DEFAULT_START_DATE)
    parser.add_argument("--end-date", default=DEFAULT_END_DATE)
    parser.add_argument(
        "--output",
        default="reports/backtest/dividend_entry_points_10y.md",
    )
    parser.add_argument(
        "--update-yaml",
        action="store_true",
        help=(
            "Apply model changes AND write backtest_ref fields to YAML "
            "when delta > 5pp (default: report only)"
        ),
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
        dividend_cache_dir=args.dividend_cache_dir,
    )

    yaml_updated: list[str] = []
    if args.update_yaml:
        yaml_updated = apply_yaml_updates(
            args.config,
            results,
            update_model=True,
            update_backtest_ref=True,
            run_date=date.today(),
        )
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
