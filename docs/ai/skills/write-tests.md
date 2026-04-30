# Skill: Write Tests

## Principles

- test behavior, not implementation
- avoid network
- use DataFrames in memory
- mock only boundaries

---

## Must Cover

- happy path
- edge cases
- failure scenarios

---

## Avoid

- trivial assertions
- over-mocking
- too many dependencies
- code duplication

## Project-specific fixtures
- use `tests/fixtures/ohlc_sample.csv` for OHLC data
- build DataFrames with at least 50 bars (SMC needs history)
- mock yfinance at `stock_data_manager.downloader.yf`
