from pathlib import Path
from time import sleep
from typing import List

import pandas as pd
from tabulate import tabulate

from stock_analyzer.analyzer import StockDataAnalyzer
from stock_analyzer.config import IndicatorConfig
from stock_analyzer.enums import Signal
from stock_analyzer.signals import AnalyzerSignalAdapter
from stock_data_manager.implementations.trading_view_tickers_download import (
    TradingViewDownloader,
)
from stock_data_manager.implementations.trading_view_tickers_reader import (
    TradingViewTickerExtractor,
)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "data" / "stocks"
SIGNAL_LABELS = {
    Signal.BUY: "BUY",
    Signal.SELL: "SELL",
    Signal.HOLD: "HOLD",
    1: "BUY",
    -1: "SELL",
    0: "HOLD",
}


def update_tickers_list(tickers_file: str):
    tv_downloader = TradingViewDownloader()
    tv_downloader.download(output_file=tickers_file)


def update_tickers_data(
    tickers_file: str, symbols: List[str] = None, sleep_time: float = 0.05
):
    tv_ticker_extrator = TradingViewTickerExtractor(tickers_file)
    tickers = tv_ticker_extrator.extract_tickers()

    symbols_to_update = symbols or tickers["symbol"].tolist()
    for symbol in symbols_to_update:
        sleep(sleep_time)
        StockDataAnalyzer.retrieve_data(symbol, data_dir=DATA_DIR, interval="1d")


def _signal_label(value) -> str:
    return SIGNAL_LABELS.get(value, str(value))


def _format_number(value, digits: int = 2) -> str:
    if value is None or pd.isna(value):
        return "-"
    return f"{float(value):.{digits}f}"


def _format_summary_rows(signal, model: str) -> list[list[str]]:
    rows = [
        ["Model", model],
        ["Date", str(signal.date)],
        ["Close", _format_number(signal.close_price)],
        ["Signal", _signal_label(signal.combined_signal)],
    ]

    if model == "lux":
        rows.extend(
            [
                ["Trend", str(signal.trend)],
                ["Strength", str(signal.strength)],
                ["Options Hint", str(signal.options_hint)],
                ["ADX", _format_number(signal.adx)],
                ["RSI", _format_number(signal.rsi)],
                ["Supertrend", _format_number(signal.supertrend)],
                ["Upper Zone", _format_number(signal.upper_zone)],
                ["Lower Zone", _format_number(signal.lower_zone)],
                ["Confirmation", _signal_label(signal.confirmation_signal)],
                ["Contrarian", _signal_label(signal.contrarian_signal)],
            ]
        )
        return rows

    if model == "smc":
        rows.extend(
            [
                ["Bias", str(signal.bias)],
                ["Range %", _format_number(signal.range_position_pct)],
                ["RSI", _format_number(signal.rsi)],
                ["EMA200", _format_number(signal.ema200)],
                ["Options Hint", str(signal.options_hint)],
                ["Swing High", "Y" if signal.swing_high_marker else ""],
                ["Swing Low", "Y" if signal.swing_low_marker else ""],
                ["In Premium", "Y" if signal.in_premium else ""],
                ["In Discount", "Y" if signal.in_discount else ""],
                ["Bullish Rejection", "Y" if signal.bullish_rejection else ""],
                ["Bearish Rejection", "Y" if signal.bearish_rejection else ""],
                ["Bullish Divergence", "Y" if signal.bullish_divergence else ""],
                ["Bearish Divergence", "Y" if signal.bearish_divergence else ""],
                ["Long Signal", "Y" if signal.long_signal else ""],
                ["Short Signal", "Y" if signal.short_signal else ""],
            ]
        )
        return rows

    if model == "rsi-sma":
        rows.extend(
            [
                ["RSI", _format_number(signal.rsi_value)],
                ["SMA", _format_number(signal.sma_value)],
                ["RSI Signal", _signal_label(signal.rsi_signal)],
                ["SMA Signal", _signal_label(signal.sma_signal)],
            ]
        )

    return rows


def _prepare_display_frame(df: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    display = df.loc[:, [col for col in columns if col in df.columns]].copy()
    for col in display.columns:
        if col == "combined_signal":
            display[col] = display[col].map(_signal_label)
        elif pd.api.types.is_bool_dtype(display[col]):
            display[col] = display[col].map({True: "Y", False: ""})
        elif pd.api.types.is_numeric_dtype(display[col]):
            display[col] = display[col].map(
                lambda value: _format_number(value) if pd.notna(value) else "-"
            )
        else:
            display[col] = display[col].astype(str)
    return display


def _render_recent_structure_markers(
    historical: pd.DataFrame, model: str, signal_rows: int
) -> list[str]:
    if model != "smc":
        return []

    structure_markers = historical[
        historical["swing_high_marker"] | historical["swing_low_marker"]
    ]
    if structure_markers.empty:
        return ["", "Recent Structure Markers", "No swing markers found."]

    markers = _prepare_display_frame(
        structure_markers.tail(signal_rows),
        [
            "date",
            "close",
            "signal_context",
            "options_hint",
            "swing_high_marker",
            "swing_low_marker",
        ],
    )
    return [
        "",
        f"Recent Structure Markers ({len(markers)})",
        tabulate(markers, headers="keys", tablefmt="simple", showindex=False),
    ]


def render_analysis_report(
    symbol: str,
    model: str,
    signal,
    historical: pd.DataFrame,
    adapter: AnalyzerSignalAdapter,
    recent_rows: int = 8,
    signal_rows: int = 5,
    full_history: bool = False,
) -> str:
    lines = [f"Symbol: {symbol}", ""]

    if signal is None:
        lines.append("No current signal available.")
        return "\n".join(lines)

    summary = tabulate(
        _format_summary_rows(signal, model),
        headers=["Metric", "Value"],
        tablefmt="plain",
    )
    lines.extend(
        [
            "Interpretation",
            adapter.interpret(signal),
            "",
            "Current Snapshot",
            summary,
        ]
    )

    if historical.empty:
        lines.extend(["", "No historical rows available."])
        return "\n".join(lines)

    recent = _prepare_display_frame(
        historical.tail(recent_rows),
        adapter.recent_columns(),
    )
    lines.extend(
        [
            "",
            f"Recent Rows ({len(recent)})",
            tabulate(recent, headers="keys", tablefmt="simple", showindex=False),
        ]
    )

    signal_events = historical[historical["combined_signal"] != Signal.HOLD]
    if signal_events.empty:
        lines.extend(["", "Recent Signal Events", "No non-HOLD events found."])
    else:
        events = _prepare_display_frame(
            signal_events.tail(signal_rows),
            adapter.event_columns(),
        )
        lines.extend(
            [
                "",
                f"Recent Signal Events ({len(events)})",
                tabulate(events, headers="keys", tablefmt="simple", showindex=False),
            ]
        )

    lines.extend(_render_recent_structure_markers(historical, model, signal_rows))

    if full_history:
        full_display = _prepare_display_frame(historical, list(historical.columns))
        lines.extend(
            [
                "",
                f"Full History ({len(full_display)} rows)",
                tabulate(
                    full_display,
                    headers="keys",
                    tablefmt="simple",
                    showindex=False,
                ),
            ]
        )

    return "\n".join(lines)


def main(argv=None) -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Stock Data Analyzer")
    parser.add_argument(
        "-s", "--symbol", type=str, required=True, help="Stock symbol to analyze"
    )
    parser.add_argument(
        "--model",
        choices=["rsi-sma", "lux", "smc"],
        default="rsi-sma",
        help="Signal model to use: rsi-sma, lux, or smc",
    )
    parser.add_argument(
        "--recent-rows",
        type=int,
        default=8,
        help="Number of recent history rows to display",
    )
    parser.add_argument(
        "--signal-rows",
        type=int,
        default=5,
        help="Number of non-HOLD signal events to display",
    )
    parser.add_argument(
        "--full-history",
        action="store_true",
        help="Print the full historical signal DataFrame",
    )
    parser.add_argument(
        "--local-only",
        action="store_true",
        help="Analyze existing local CSV only, without updating/downloading data",
    )
    args = parser.parse_args(argv)

    config = IndicatorConfig(rsi_period=14, sma_period=50)
    analyzer = StockDataAnalyzer(config=config, signal_model=args.model)

    symbol = args.symbol.upper()
    try:
        if args.local_only:
            df = analyzer.load_local_data(symbol, data_dir=DATA_DIR, interval="1d")
        else:
            df = analyzer.retrieve_data(symbol, data_dir=DATA_DIR, interval="1d")
    except FileNotFoundError as exc:
        print(f"Error: {exc}")
        return 1

    signal = analyzer.generate_signal(symbol, df)
    historical = analyzer.generate_historical_signals(symbol, df)

    print(
        render_analysis_report(
            symbol=symbol,
            model=args.model,
            signal=signal,
            historical=historical,
            adapter=analyzer.signal_generator,
            recent_rows=args.recent_rows,
            signal_rows=args.signal_rows,
            full_history=args.full_history,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
