from stock_analyzer.analyzer import StockDataAnalyzer


if __name__ == "__main__":
    symbol = "VZ"
    stock_analyzer = StockDataAnalyzer()
    df = stock_analyzer.retrieve_data(symbol)
    result = stock_analyzer.rsi_backtest(df)
    # result = stock_analyzer.sma_crossing_backtest(df)
    print(result)
