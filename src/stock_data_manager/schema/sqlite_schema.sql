CREATE TABLE IF NOT EXISTS ohlcv_daily (
    symbol TEXT NOT NULL,
    date TEXT NOT NULL,
    open REAL,
    high REAL,
    low REAL,
    close REAL,
    volume REAL,
    dividends REAL,
    stock_splits REAL,
    source TEXT,
    imported_at TEXT,
    PRIMARY KEY(symbol, date)
);

CREATE INDEX IF NOT EXISTS idx_ohlcv_symbol_date ON ohlcv_daily(symbol, date);
CREATE INDEX IF NOT EXISTS idx_ohlcv_date ON ohlcv_daily(date);
