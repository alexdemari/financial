# Daily Market Report

## Purpose

Generate an actionable daily report crossing fresh scanner signals with
backtest-qualified setups, ranked separately per strategy.

Output: `reports/market_scanner/daily_report.md` — sections:

1. **Posições Abertas** _(optional, `--portfolio-path`)_ — open options positions evaluated against today's scan. EXIT ⚠️ → WATCH ~ → HOLD.
2. **Sinais Frescos** — all symbols with a Lux or SMC event within N days
3. **Top N — LUX** — ranked by `lux_days` asc, filtered by lux-qualified backtest recs
4. **Top N — SMC** — ranked by `smc_days` asc, filtered by smc-qualified backtest recs
5. **Top N — DUAL** — requires both signals fresh, ranked by `lux_days + smc_days` asc
6. **SMC High Conviction — Aguardando Trigger** — `needs_review` with SMC ≤ 10 days and `profit_factor > 5`, symbol-scoped recs only, sorted by `profit_factor` desc
7. **Opções Viáveis** _(optional, `--options-filter`)_ — top candidates with sufficient options liquidity (live yfinance data). Shows `strategy` origin column, sorted GOOD→OK then OI desc. SMC signals take priority when a symbol appears in multiple strategies.
8. **Sumário por Bucket** — count per action bucket for today's scan
9. **Stats** — fresh counts per strategy

Section 1 is omitted when `--portfolio-path` is not provided; all other numbers remain sequential.

Pool for rankings is **all action buckets** (not just `candidate`). `action_bucket`
is visible as a column in each ranking table.

---

## Quick Commands

```bash
# Rotina completa recomendada (dados + scan + report + LLM + posições abertas)
just daily && just daily-report-llm

# LLM portfolio-aware using the read-only IBKR positions snapshot
just ibkr-positions
just daily-report-llm \
  ibkr_snapshot="reports/output/ibkr_positions_YYYY-MM-DD.csv"

# Sem LLM (mais rápido)
just daily                          # inclui options_tracker.csv por padrão
just daily portfolio=""             # sem seção de posições

# ⚠️  NÃO rodar `just daily-report` depois de `just daily` — sobrescreve sem portfolio
# Scanner + report only (skip data download)
PYTHONPATH=src uv run python -m market_scanner.scan \
  --universe-file data/scanner_universe_filtered.csv \
  --data-dir data/stocks/1D \
  --ranking-mode recent-event \
  --output reports/market_scanner/scan_daily.csv \
  --workers 8
just daily-report

# Single strategy report
PYTHONPATH=src uv run python -m market_scanner.daily_report \
  --scan reports/market_scanner/scan_daily.csv \
  --recommendations reports/market_scanner/execution_recommended_rules.csv \
  --strategy lux \
  --output reports/market_scanner/daily_report_lux.md

# With options liquidity filter (live yfinance — adds ~10-30s)
just daily-report options_filter=true
# or directly:
PYTHONPATH=src uv run python -m market_scanner.daily_report \
  --scan reports/market_scanner/scan_daily.csv \
  --recommendations reports/market_scanner/execution_recommended_rules.csv \
  --options-filter \
  --output reports/market_scanner/daily_report.md

# With open positions exit signals (já incluído por padrão em `just daily`)
just daily-report portfolio_path=options_tracker.csv
# or directly:
PYTHONPATH=src uv run python -m market_scanner.daily_report \
  --scan reports/market_scanner/scan_daily.csv \
  --recommendations reports/market_scanner/execution_recommended_rules.csv \
  --portfolio-path options_tracker.csv \
  --output reports/market_scanner/daily_report.md

# Standalone exit monitor (positions only, no full report)
just positions

# Standalone exit monitor using live IBKR snapshot
just ibkr-positions
just positions-live
# Custom ibkr-positions output directory:
just positions-live reports/my/options_tracker_live.csv
```

---

## Full Daily Routine (manual)

```bash
# 1. Update data
PYTHONPATH=src uv run python -m stock_data_manager.main \
  -f data/scanner_universe_filtered.csv -d data/stocks/1D

# 2. Run scanner
PYTHONPATH=src uv run python -m market_scanner.scan \
  --universe-file data/scanner_universe_filtered.csv \
  --data-dir data/stocks/1D \
  --ranking-mode recent-event \
  --output reports/market_scanner/scan_daily.csv \
  --workers 8

# 3. Generate report (all strategies)
PYTHONPATH=src uv run python -m market_scanner.daily_report \
  --scan reports/market_scanner/scan_daily.csv \
  --recommendations reports/market_scanner/execution_recommended_rules.csv \
  --max-days 2 \
  --top 20 \
  --output reports/market_scanner/daily_report.md
```

---

## Key Parameters

| Flag | Default | When to change |
|------|---------|----------------|
| `--max-days` | `2` | Use `1` for tighter filter. Use `5` for wider window. |
| `--top` | `20` | Use `10` for shorter list. |
| `--strategy` | `all` | `lux`, `smc`, `dual`, or `all` (renders all 3 sections). |
| `--recommendations` | optional | Omit to list fresh signals without backtest filter. |
| `--smc-watchlist-days` | `10` | Max SMC signal age for high conviction watchlist. |
| `--smc-min-pf` | `5.0` | Min profit_factor threshold for SMC watchlist. |
| `--options-filter` | off | Add live options liquidity section (requires internet, ~10-30s). |
| `--portfolio-path` | optional | Path to `options_tracker.csv` for open positions exit signals. |
| `--ibkr-snapshot` | optional | CSV/JSON IBKR snapshot injected only into the LLM prompt; ignored unless `--llm-explain` is set. |

---

## How Rankings Work Per Strategy

**LUX**: pool = all symbols where `lux_days_since_active_event <= max_days`.
Sort: `lux_days` asc, then `consistency_score` desc.

**SMC**: pool = all symbols where `smc_days_since_active_event <= max_days`.
Sort: `smc_days` asc, then `consistency_score` desc.

**DUAL**: pool = symbols where **both** `lux_days <= max_days` AND `smc_days <= max_days`.
Sort: `lux_days + smc_days` asc, then `consistency_score` desc.

### Backtest filter (when `--recommendations` provided)

A symbol is shown only when `(symbol, side)` is qualified:
- prefers `scope=symbol` recommendation
- falls back to `scope=global` for the inferred side

Recommendations are filtered by `strategy` column when present:
- `strategy=lux` rec qualifies lux and dual sections
- `strategy=dual` rec qualifies lux, smc, and dual sections
- No `strategy` column (old format): applies to all sections (backward compat)

Side inferred from `adjusted_alignment`:
- `bullish_aligned` → `bullish`
- `bearish_aligned` → `bearish`
- anything else → excluded

---

## Recommendation File Cadence

`execution_recommended_rules.csv` is generated by `market_scanner.backtest_execution`.
Regenerate weekly or after universe changes. The file now includes a `strategy` column
(lux/smc/dual) — regenerate with `just weekly` to activate per-strategy filtering.

```bash
just weekly
```

Until regenerated, backward compat applies: old files without `strategy` column
pass through without strategy-based filtering.

---

## Without Recommendations

```bash
PYTHONPATH=src uv run python -m market_scanner.daily_report \
  --scan reports/market_scanner/scan_daily.csv \
  --max-days 2 --top 20 \
  --output reports/market_scanner/daily_report.md
```

Rankings show all fresh symbols sorted by signal recency + consistency, no backtest filter.

---

## Related Files

| File | Description |
|------|-------------|
| `src/market_scanner/daily_report.py` | Report orchestration and rendering |
| `src/market_scanner/options_filter.py` | Options liquidity fetch + classification (yfinance) |
| `src/ibkr_positions/options_export.py` | Export live IBKR option positions to `reports/output/options_tracker_live.csv` |
| `src/market_scanner/portfolio.py` | Parse `options_tracker.csv` or the live IBKR snapshot, return open positions |
| `src/market_scanner/exit_monitor.py` | Evaluate open positions against scan; EXIT/WATCH/HOLD |
| `src/market_scanner/exits.py` | Exit rule functions (reused by exit_monitor) |
| `options_tracker.csv` | Personal options trade log (gitignored). Semicolon-delimited, European decimals, DD/MM/YYYY. Col 25 = `signal_source` (lux/smc/dual/—). Open rows have empty Close Date (col 18). |
| `reports/output/options_tracker_live.csv` | Point-in-time live IBKR option snapshot written by `just ibkr-positions`; consumed by `just positions-live`. |
| `reports/market_scanner/scan_daily.csv` | Input: today's scan |
| `reports/market_scanner/execution_recommended_rules.csv` | Input: backtest qualification (weekly) |
| `reports/market_scanner/daily_report.md` | Output: daily report |
