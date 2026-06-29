# financial

Personal family office system — local-first, CLI-driven, file-based.

Combines market scanning, dividend strategy, options management, IBKR portfolio
tracking, macro context, LLM-assisted analysis, and Brazilian IRPF tax reporting
into a single modular monolith.

---

## What this system does

| Capability | Module | Key command |
|---|---|---|
| Download and maintain local OHLC data | `stock_data_manager` | `just download` |
| Single-symbol signal analysis (Lux / SMC) | `stock_analyzer` | `just analyzer` |
| Multi-symbol scanner with backtest-qualified rankings | `market_scanner` | `just daily` |
| Weekly backtest to qualify entry rules | `market_scanner.backtest_execution` | `just weekly` |
| LLM-narrated daily report with macro context | `market_scanner.daily_report` | `just daily-report-llm` |
| Dividend portfolio: buy / overpriced decisions | `dividend_tracker` | `just dividends` |
| Live IBKR portfolio: positions, risk, P&L | `ibkr_positions` | `just ibkr-positions` |
| IBKR trade history: auto-derive `options_tracker.csv` | `ibkr_trades` | `just ibkr-trades-daily` |
| Open options exit monitor (DTE, signals) | `market_scanner.exit_monitor` | `just positions` |
| Brazilian IRPF annual report (USD → BRL via PTAX) | `irpf_report` | `just irpf` |

---

## Architecture

```
stock_data_manager      → local OHLC CSVs
stock_analyzer          → per-symbol Lux / SMC signals
market_scanner          → Scanner V3 decisions, rankings, daily report
  macro_context         → Selic, USD/BRL, S&P 500, Ibovespa (live)
  macro_calendar        → upcoming US macro events
  exit_monitor          → EXIT / WATCH / HOLD for open options positions
  options_filter        → live options liquidity (yfinance)
dividend_tracker        → dividend yield ceiling decisions (BUY / OVERPRICED)
ibkr_positions          → live portfolio state, risk metrics, HTML/CSV/MD report
ibkr_trades             → trade history store, options_tracker.csv auto-generation
irpf_report             → annual IRPF report with BCB PTAX conversion
```

All modules are synchronous, read-only with respect to IBKR, and require no
cloud infrastructure or always-on services.

---

## Prerequisites

- Python + [`uv`](https://docs.astral.sh/uv/) + Git
- WSL2 / Ubuntu (recommended; native Windows works for editing, not for tooling)
- IB Gateway running on Windows at port 7496 (for IBKR commands only)
- `.env` file at project root (see `.env.example`)

```bash
uv sync --dev          # install all dependencies
cp .env.example .env   # then fill in your keys
```

---

## Environment variables (`.env`)

```bash
# IBKR Connection — auto-detected from WSL2; leave blank
IBKR_HOST=
IBKR_PORT=7496

# IBKR Flex Web Service — required for just ibkr-trades-daily
# Client Portal → Settings → Account Settings → Flex Web Service
IBKR_FLEX_TOKEN=
# Client Portal → Performance & Reports → Flex Queries → ℹ️ → Query ID
IBKR_FLEX_QUERY_ID=

# LLM providers — required for just daily-report-llm
ANTHROPIC_API_KEY=
OPENAI_API_KEY=
```

---

## Daily workflow

### Market scanner (US equities)

```bash
# Full routine: update data → scan → report (with macro context + open positions)
just daily

# Same + LLM narration (requires ANTHROPIC_API_KEY or OPENAI_API_KEY)
just daily-report-llm

# LLM report portfolio-aware (uses live IBKR positions to filter recommendations)
just ibkr-positions
just daily-report-llm ibkr_snapshot="reports/output/ibkr_positions_$(date +%Y-%m-%d).csv"

# Report only (skip data download and scan — reuses last scan)
just report
```

### IBKR portfolio

```bash
# Live positions report + trade sync + options_tracker.csv rebuild
just ibkr-positions

# Open options exit signals from live IBKR snapshot
just positions-live

# Open options exit signals from local options_tracker.csv
just positions

# Account performance history (last N days)
just ibkr-history days=30

# Reconcile options_tracker.csv against live IBKR positions (diff report)
just ibkr-reconcile
```

### Dividend portfolio

```bash
# Update data + generate dividend report
just dividends budget=8000

# Dividend report enriched with live IBKR share counts and USD income projection
just dividends-ibkr budget=8000

# Report only (no data download)
just dividends-local
```

### Weekly maintenance

```bash
# Regenerate backtest-qualified entry rules (run after universe changes or weekly)
just weekly

# Same, optimized for SMC/DUAL strategy only
just weekly-smc
```

### IRPF (annual, Brazilian tax)

```bash
# Generate BRL IRPF report for a year (auto-selects trades_history.csv or legacy CSV)
just irpf year=2025
```

---

## Module reference

### `stock_data_manager`

Downloads and maintains local OHLC data in `data/stocks/1D/<SYMBOL>.csv`.

```bash
just download "AAPL MSFT NVDA"
just download-file data/scanner_universe_filtered.csv
```

---

### `stock_analyzer`

Single-symbol signal generation. Supports `lux`, `smc`, and `rsi-sma` models.

```bash
just analyzer symbol=AAPL model=lux
```

---

### `market_scanner`

Multi-symbol orchestration. Builds Scanner V3 rows with `market_state`,
`adjusted_alignment`, `action_bucket`, and per-strategy rankings (LUX / SMC / DUAL).

Crosses fresh signals with `execution_recommended_rules.csv` (backtest-qualified
entry rules, regenerated weekly with `just weekly`).

The daily report includes:

1. Open options positions — EXIT ⚠ / WATCH ~ / HOLD per position
2. Fresh signals — all symbols with a recent Lux or SMC event
3. Top N — LUX (ranked by `lux_days` asc)
4. Top N — SMC (ranked by `smc_days` asc)
5. Top N — DUAL (both signals fresh)
6. SMC High Conviction watchlist (`profit_factor > 5`, awaiting trigger)
7. Viable options (optional `--options-filter`, live liquidity data)
8. Bucket summary + stats

**Macro context** (injected into report header and LLM prompt):

| Indicator | Source |
|---|---|
| Selic meta rate | BCB API |
| USD/BRL PTAX | BCB Olinda API |
| S&P 500 close + 1d% | yfinance |
| Ibovespa close + 1d% | yfinance |
| Upcoming macro events | Public economic calendar |

```bash
just daily                              # macro on by default
just daily-report-llm no_macro=true    # disable macro fetch (offline)
```

---

### `dividend_tracker`

Evaluates a dividend portfolio defined in `config/dividend_portfolio.yaml`.

Core decision: **BUY** (current price ≤ dividend yield ceiling) or **OVERPRICED**.

Price ceiling methods per asset:
- `average_6y` — six-year average annual dividends ÷ `min_dy` (BR assets, excludes current incomplete year)
- `trailing_ttm` — trailing twelve-month dividends ÷ `min_dy` (rapidly growing payers)

Covered universes: BR (BEST sectors: Bancos, Energia, Saneamento, Seguros, Telecom)
and US dividend ETFs / individual names (SCHD, DGRO, VYM, PEP, etc.).

```bash
just dividends budget=8000             # update data + report
just dividends-ibkr budget=8000        # + IBKR share counts + USD income projection
just dividends-local                   # report only (cached data)
```

---

### `ibkr_positions`

Connects to IB Gateway (read-only) and generates a portfolio risk report as
HTML, CSV, and Markdown.

**Report includes:**
- Net liquidation, cash, invested capital, unrealized P&L, margin utilization
- Per-position performance table (STK + OPT)
- Open options detail (strike, expiration, DTE, premium received, current value)
- Portfolio allocation by asset type
- Risk analysis: concentration flags, margin metrics, cash coverage for short puts
- Approximate net portfolio delta (Black-Scholes, IV=30%, RF=5%)
- Cash shortfall resolution suggestions (ranked by impact)
- Daily account snapshot appended to `data/ibkr/history.jsonl`

`just ibkr-positions` automatically runs `ibkr-sync` + `ibkr-generate-tracker`
before the report so `options_tracker.csv` is always current.

**IB Gateway setup (WSL2 → Windows):**

1. IB Gateway running on Windows, port 7496 (live) or 4002 (paper)
2. Configure → Settings → API → uncheck "Permitir conexões somente do host local"
3. Add WSL2 IP to trusted IPs: `ip addr show eth0 | grep 'inet '`
4. Restart Gateway after IP changes (WSL2 IP changes on reboot)

```bash
just ibkr-positions                    # full report + trade sync
just ibkr-positions port=4002          # paper account
just ibkr-history days=30             # account performance history
just ibkr-reconcile                    # diff options_tracker.csv vs live IBKR
```

---

### `ibkr_trades`

Maintains `data/ibkr/trades_history.csv` — an append-only canonical store of
all IBKR executions — and derives `options_tracker.csv` automatically.

**Data flow:**

```
IBKR Flex Query XML   → one-time backfill (full history since account inception)
IBKR Client Portal API → daily incremental sync (new executions via ib_insync)
        ↓
data/ibkr/trades_history.csv   ← canonical store (append-only, deduplicated by trade_id)
        ↓
options_tracker.csv            ← derived: net open option legs only
        ↓
exit_monitor / daily_report    ← unchanged consumers
```

**Roll detection:** same-day close + open on same underlying / option type but
different expiration → both legs tagged with a shared `roll_id` UUID.

**Strategy tagging:** `covered_call`, `csp`, `long_call`, `long_put`, `roll`, `other`.

**First-time setup:**

```bash
# 1. Export Flex Query from IBKR:
#    Client Portal → Performance & Reports → Flex Queries → Run → Download
#    Save as: data/ibkr/flex_export.xml

# 2. One-time backfill
just ibkr-backfill flex=data/ibkr/flex_export.xml

# 3. Rebuild options_tracker.csv
just ibkr-generate-tracker

# After setup, just ibkr-positions handles everything automatically
```

**Daily automation (after setup):**

```bash
just ibkr-trades-daily     # fetch Flex XML + backfill + sync + rebuild tracker
# or just run:
just ibkr-positions        # ibkr-trades-daily runs automatically as a pre-step
```

**Flex Web Service (programmatic download — requires `.env` credentials):**

```bash
just ibkr-flex-fetch       # download latest Flex XML without portal login
```

Requires `IBKR_FLEX_TOKEN` and `IBKR_FLEX_QUERY_ID` in `.env`.
Setup: Client Portal → Settings → Account Settings → Flex Web Service.

---

### `irpf_report`

Generates an annual IRPF report for foreign-source income from IBKR closed trades.
Converts USD realized P&L to BRL using the official BCB PTAX selling rate for
each trade date (with local disk cache).

**No monthly DARF** for foreign investments — only annual IRPF declaration.

PTAX is fetched from the BCB Olinda API and cached in `data/ibkr/ptax_cache/`.
Falls back up to 3 prior business days for weekends and holidays.

```bash
just irpf year=2025
# Auto-selects trades_history.csv if available; falls back to data/ibkr/trades_2025.csv
```

Output: `reports/irpf/irpf_2025.md` — per-trade detail, monthly summary,
asset-type breakdown (STK / OPT / ETF), and annual totals in USD and BRL.

---

## Output files

| Path | Description |
|---|---|
| `reports/market_scanner/daily_report.md` | Daily scanner report (latest) |
| `reports/market_scanner/daily/` | Archived dated copies |
| `reports/market_scanner/scan_daily.csv` | Raw scanner output (latest) |
| `reports/market_scanner/execution_recommended_rules.csv` | Backtest-qualified entry rules |
| `reports/output/ibkr_positions_YYYY-MM-DD.html` | IBKR positions report (HTML) |
| `reports/output/ibkr_positions_YYYY-MM-DD.csv` | IBKR positions snapshot (CSV) |
| `reports/output/options_tracker_live.csv` | Live IBKR options snapshot |
| `reports/output/reconciliation_YYYY-MM-DD.md` | options_tracker diff report |
| `reports/dividend_tracker/dividend_daily_report.md` | Dividend buy / overpriced report |
| `reports/irpf/irpf_YYYY.md` | Annual IRPF BRL report |
| `data/ibkr/trades_history.csv` | Canonical trade history (gitignored) |
| `data/ibkr/history.jsonl` | Daily account snapshots (gitignored) |
| `data/ibkr/ptax_cache/` | BCB PTAX rate cache (gitignored) |
| `options_tracker.csv` | Open options log — auto-derived by ibkr_trades (gitignored) |

---

## Project structure

```
src/
├── stock_data_manager/     OHLC data download and persistence
├── stock_analyzer/         Single-symbol Lux / SMC signal generation
├── trading_indicators/     Low-level technical indicator implementations
├── market_scanner/         Scanner V3, rankings, daily report, exit monitor
│   ├── macro_context.py    Live macro indicators (Selic, PTAX, S&P, Ibov)
│   ├── macro_calendar.py   Upcoming US macro events
│   ├── exit_monitor.py     Open positions EXIT / WATCH / HOLD
│   ├── options_filter.py   Live options liquidity (yfinance)
│   └── llm/                LLM explainer + portfolio context injector
├── dividend_tracker/       Dividend yield ceiling decisions + IBKR enrichment
├── ibkr_positions/         Live IBKR portfolio report (read-only)
│   ├── risk.py             Delta proxy, cash coverage, concentration analysis
│   ├── snapshot_store.py   Append-only daily account history (JSONL)
│   ├── reconciler.py       Diff options_tracker.csv vs live IBKR
│   └── options_export.py   Export live option legs to options_tracker_live.csv
├── ibkr_trades/            Trade history store + options_tracker.csv derivation
│   ├── flex_fetcher.py     Programmatic Flex Query XML download
│   ├── flex_parser.py      Flex XML → list[TradeRecord]
│   ├── api_fetcher.py      ib_insync reqExecutions → incremental sync
│   ├── store.py            Append-only CSV with deduplication
│   ├── roll_detector.py    Same-day roll detection
│   ├── strategy_tagger.py  Infer covered_call / csp / roll etc.
│   └── tracker_builder.py  Derive options_tracker.csv from net open legs
└── irpf_report/            Annual IRPF BRL report with BCB PTAX conversion

config/
├── dividend_portfolio.yaml BR + US dividend assets with min_dy and ceiling_method

data/
├── stocks/1D/              Local OHLC CSVs per symbol
├── ibkr/                   Trade history, Flex exports, PTAX cache (gitignored)
└── dividends/              Dividend data cache (24h TTL)

docs/
├── architecture/           Per-module architecture docs
├── ai/tasks/               Agent task files (T01–T11)
├── ai/skills/              Reusable agent skill definitions
├── ai/prompts/             Session bootstrap and workflow prompts
└── runbooks/               Operational runbooks

reports/                    All generated output (gitignored)
options_tracker.csv         Open options log, auto-derived (gitignored)
justfile                    All CLI recipes
.env                        Credentials and config (gitignored)
.env.example                Template for .env
```

---

## Testing

```bash
just test                           # all tests (parallel)
just test-module ibkr_trades        # single module
just test-cov                       # with HTML coverage report
just lint                           # ruff
just check                          # format + lint + type-check + test
```

---

## Key design principles

- **Local-first**: no cloud required; all data in local CSV / JSONL files
- **Read-only IBKR**: never submits or modifies orders
- **Synchronous**: no async, no message queues
- **Graceful degradation**: all modules handle API unavailability without hard failures
- **Derived artifacts**: `options_tracker.csv` is generated from `trades_history.csv` — never edited manually
- **Append-only history**: `trades_history.csv` and `history.jsonl` are never modified after write; deduplication by `trade_id`
- **LLM as optional layer**: LLM narration is explanatory only — it does not affect scanner rankings or CSV outputs

---

## Documentation

| Doc | Location |
|---|---|
| Architecture overview | `docs/architecture/overview.md` |
| Module boundaries | `docs/architecture/module-boundaries.md` |
| IBKR positions module | `docs/architecture/ibkr-positions.md` |
| IBKR trades module | `docs/architecture/ibkr-trades.md` |
| Dividend tracker | `docs/architecture/dividend-tracker.md` |
| IRPF report | `docs/architecture/irpf-report.md` |
| Daily report runbook | `docs/runbooks/daily-market-report.md` |
| Local setup | `docs/runbooks/local-setup.md` |
| Agent tasks (T01–T11) | `docs/ai/tasks/` |
| Flex Query setup guide | `docs/ai/tasks/GUIDE-flex-query-setup.md` |
