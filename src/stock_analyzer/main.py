from pathlib import Path
from time import sleep
from typing import List

from src.stock_data_manager.cli import PROJECT_ROOT
from stock_analyzer.analyzer import StockDataAnalyzer
from stock_analyzer.config import IndicatorConfig
from stock_data_manager.implementations.trading_view_tickers_download import (
    TradingViewDownloader,
)
from stock_data_manager.implementations.trading_view_tickers_reader import (
    TradingViewTickerExtractor,
)

PROJECT_ROOT = Path(__file__).parent.parent.parent
DATA_DIR = f"{PROJECT_ROOT}\\data\\stocks"


def update_tickers_list(tickers_file: str):
    tv_downloader = TradingViewDownloader()
    tv_downloader.download(output_file=tickers_file)


def update_tickers_data(tickers_file: str, symbols: List[str] = None, sleep_time: float = 0.05):
    tv_ticker_extrator = TradingViewTickerExtractor(tickers_file)
    tickers = tv_ticker_extrator.extract_tickers()

    symbols_to_update = symbols or tickers["symbol"].tolist()
    for symbol in symbols_to_update:
        sleep(sleep_time)
        analyzer.retrieve_data(symbol, data_dir=DATA_DIR, interval="1d")


if __name__ == "__main__":
    # ADD SUPPORT TO SYMBOL AS COMMAND INPUT
    import argparse

    parser = argparse.ArgumentParser(description="Stock Data Analyzer")
    parser.add_argument("-s", "--symbol", type=str, required=True, help="Stock symbol to analyze")
    args = parser.parse_args()

    config = IndicatorConfig(rsi_period=14, sma_period=50)
    analyzer = StockDataAnalyzer(config=config)

    symbol = args.symbol.upper()
    # Recuperar dados
    df = analyzer.retrieve_data(symbol, data_dir=DATA_DIR, interval="1d")

    # Sinal atual
    signal = analyzer.generate_signal(symbol, df)
    print(f"Signal: {signal.combined_signal}")

    # Histórico
    historical = analyzer.generate_historical_signals(symbol, df)
    print(historical)

