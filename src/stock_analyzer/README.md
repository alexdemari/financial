# Stock Analyzer

`stock_analyzer` analyzes OHLC market data (usually downloaded by `stock_data_manager`) and generates technical signals and backtest metrics.

## What This Package Does

- Calculates core indicators (RSI, SMA, CCI)
- Generates current and historical RSI/SMA-based signals
- Contains simple strategy backtests (RSI, SMA crossover, CCI mean reversion)
- Integrates with `stock_data_manager` to fetch/update symbol data

## Current State

`stock_analyzer` is an early local/manual analysis module. It is usable as a
single-symbol CLI and as a programmatic wrapper around signal generation.

Current execution model:

```text
CLI / Python caller
  -> StockDataAnalyzer
      -> stock_data_manager retrieves or updates local CSV data
      -> SignalGenerator
          -> IndicatorCalculator
      -> current signal and historical signal DataFrame
```

The current analyzer is not event-driven, not a scanner, and not an options
strategy engine. Its practical job is to take OHLC data and produce simple
technical signals for one stock at a time.

There are currently no dedicated tests for this package under `tests/`.

## Package Structure

- `analyzer.py`: high-level orchestrator (`StockDataAnalyzer`)
- `signals.py`: signal generation (`SignalGenerator`, `SignalResult`)
- `indicators.py`: indicator calculations (`IndicatorCalculator`)
- `backtest.py`: backtesting implementations (`RSIBacktesting`, `SMAPairBacktesting`, `CCIBacktesting`)
- `config.py`: config dataclasses for indicators/backtests
- `enums.py`: normalized signal enum values
- `main.py`: CLI entry point for single-symbol analysis

## Available Indicators

### RSI (Relative Strength Index)

- Implemented in: `IndicatorCalculator.calculate_rsi`
- Default period: `14`
- Signal thresholds (from `IndicatorConfig`):
- Buy when RSI `< 30`
- Sell when RSI `> 70`
- Else Hold

### SMA (Simple Moving Average)

- Implemented in: `IndicatorCalculator.calculate_sma`
- Default period: `50`
- Signal logic:
- Buy when `Close > SMA`
- Sell when `Close < SMA`
- Else Hold

### CCI (Commodity Channel Index)

- Implemented in: `IndicatorCalculator.calculate_cci`
- Default period: `14`
- Used by CCI backtesting strategy (not part of combined live signal in `signals.py`)

## Signal Model

Signal values are normalized in `enums.Signal`:

- `BUY = 1`
- `SELL = -1`
- `HOLD = 0`

The combined signal in `SignalGenerator` is conservative:

- Combined Buy only if RSI and SMA are both Buy
- Combined Sell only if RSI and SMA are both Sell
- Otherwise Hold

## Data Requirements

For RSI/SMA signal generation:

- Required column: `Close`

For CCI/backtests that need full OHLC:

- Required columns: `High`, `Low`, `Close`

Input data should be a `pandas.DataFrame` indexed or sortable by date.

## CLI Usage

From project root:

```bash
just analyzer AAPL
```

Equivalent direct command:

```bash
PYTHONPATH=src uv run python -m stock_analyzer.main -s AAPL
```

What it does:

1. Updates/retrieves data for the symbol (`1d` interval)
2. Prints the current combined signal
3. Prints the historical signal DataFrame

## Programmatic Usage

### Generate Current and Historical Signals

```python
from stock_analyzer.analyzer import StockDataAnalyzer
from stock_analyzer.config import IndicatorConfig

config = IndicatorConfig(
    rsi_period=14,
    rsi_buy_threshold=30.0,
    rsi_sell_threshold=70.0,
    sma_period=50,
)

analyzer = StockDataAnalyzer(config=config)

# Data retrieval via stock_data_manager integration
df = analyzer.retrieve_data(symbol="AAPL", data_dir="./data/stocks", interval="1d")

current = analyzer.generate_signal("AAPL", df)
historical = analyzer.generate_historical_signals("AAPL", df)

print(current)
print(historical.tail())
```

### Use IndicatorCalculator Directly

```python
from stock_analyzer.indicators import IndicatorCalculator

rsi = IndicatorCalculator.calculate_rsi(df["Close"], period=14)
sma = IndicatorCalculator.calculate_sma(df["Close"], period=50)
cci = IndicatorCalculator.calculate_cci(df["High"], df["Low"], df["Close"], period=14)
```

### Run Backtests

```python
from stock_analyzer.backtest import RSIBacktesting, SMAPairBacktesting, CCIBacktesting

rsi_results = RSIBacktesting().backtest(df.copy(), column="Close", period=14, lower_limit=30, upper_limit=70)
sma_results = SMAPairBacktesting().backtest(df.copy(), column="Close", short=20, long=50, capital_inicial=10000)
cci_results = CCIBacktesting().backtest(
    df.copy(),
    close_column="Close",
    cci_period=14,
    low_th=-100,
    high_th=100,
    initial_capital=10000,
    risked_money=500,
    commission_rate=0.001,
)
```

## Configuration Objects

- `IndicatorConfig`: periods and RSI/SMA thresholds for signal generation
- `BacktestConfig`: generic backtest defaults (capital, commission, CCI params)
- `RSIBacktestConfig`: RSI-specific backtest defaults

## Notes

- `main.py` currently analyzes one symbol at a time (`-s/--symbol` required).
- Data retrieval in `StockDataAnalyzer.retrieve_data` writes/reads under `data_dir/<INTERVAL>` (for example `./data/stocks/1D`).
- If there are not enough rows for a configured indicator period, methods return empty/hold-like outputs and log warnings.

## Known Gaps

- The CLI is minimal and only supports one symbol at a time.
- The CLI always retrieves/updates data through `stock_data_manager`; there is no
  read-only mode for analyzing already downloaded CSV files.
- There are no analyzer-specific tests yet.
- Backtesting code is less mature than signal generation and should be reviewed
  before treating results as reliable.
- `CCIBacktesting` appears to have result-shape inconsistencies that need tests
  and cleanup before regular use.

## Planned Changes

Near-term changes should keep the module local, manual, and synchronous:

1. Add analyzer tests using in-memory DataFrames, with no network calls.
2. Separate "analyze existing CSV" from "download/update then analyze".
3. Improve CLI output into a compact table with symbol, date, close, RSI, SMA,
   RSI signal, SMA signal, and combined signal.
4. Add multi-symbol CLI support after single-symbol behavior is covered.
5. Review and fix backtests separately from signal generation.
