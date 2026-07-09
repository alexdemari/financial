# Task T17: Options Candidate Filter — IVR, Spread, Earnings, Delta e Retorno sobre Colateral

**Status:** Completed
**Skill:** add-feature
**Scope:** `src/market_scanner/options_screener.py` (new), `src/market_scanner/daily_report.py`, `justfile`
**Effort:** M
**Depends on:** task 07-daily-operational-report (completed), T08 (macro context)

---

## Context

The existing `--options-filter` flag in `daily-report` performs only a basic
liquidity check (volume and open interest threshold) via yfinance. It does not:

- Calculate IV Rank (IVR) — the most critical signal for premium selling
- Check bid-ask spread quality
- Detect earnings within the DTE window (position killer)
- Score contracts by delta target and return on collateral
- Distinguish CSP candidates (bullish setup) from CC candidates (extended/resistance)

The result: "Viable Options" in the daily report is a flat list with no
prioritization, no strategy context, and no prêmio quality assessment.

This task replaces the stub with a full options screener that produces a
ranked "Candidatos para Opções" section in the daily report, driven by the
three-layer filter framework designed for 30–45 DTE premium selling
(CSP + Covered Call).

---

## Goal

For each scanner candidate with `action_bucket` in (`candidate`, `watchlist`),
fetch options chain data from yfinance, apply the three-layer filter, score
each contract, and output a ranked table in the daily report with:
strategy type (CSP/CC), strike, expiration, delta, IVR, bid-ask spread,
premium, and estimated monthly return on collateral.

---

## Outcome spec

When done, the following must be true:

1. `just daily options_filter=true` (or the new `just daily-options`) generates
   a daily report that includes a new section **"7. Candidatos para Opções"**
   after the existing sections.
2. The section contains a ranked table with one row per viable contract found,
   with columns defined below.
3. Assets are filtered and scored through three layers in sequence:
   - **Layer 1 — Asset filters**: liquidity, IV range, IVR, no earnings
   - **Layer 2 — Technical filters**: `market_state` + `adjusted_alignment`
     mapped to CSP or CC strategy
   - **Layer 3 — Contract filters**: DTE 30–45, delta 0.20–0.30, spread < 10%,
     minimum return on collateral ≥ 0.5%/month
4. Rows are ranked by `ivr_rank DESC` (highest IVR = richest premium first).
5. If no viable contracts are found, the section prints:
   `"Nenhum candidato encontrado com os filtros atuais."`
6. Earnings detection: if a known earnings date falls within the DTE window
   of the contract, the contract is excluded. An excluded asset shows a note:
   `"NVDA — excluído: earnings 2026-08-20 dentro do vencimento"`
7. The screener respects the existing `--top N` flag: only the top N scanner
   candidates (by existing ranking) are evaluated for options viability.
   This limits yfinance API calls.
8. Results are also written to
   `reports/market_scanner/options_candidates_YYYY-MM-DD.csv`
   for consumption by the dashboard (future T18).
9. `just daily` (without `options_filter=true`) is **unchanged** — the screener
   is opt-in only. No performance regression on the standard daily flow.
10. `uv run pytest tests/market_scanner/test_options_screener.py` passes (≥ 8 tests).

---

## Constraints

- yfinance only — no paid options data API. All options chain data via
  `yf.Ticker(symbol).option_chain(expiration)`.
- No new pip dependencies beyond `yfinance` (already in project) and
  `numpy` (already in project).
- IVR is computed from historical IV: `(current_IV - IV_52w_low) / (IV_52w_high - IV_52w_low) × 100`.
  yfinance does not provide IV history directly — use `impliedVolatility` from
  the options chain as current IV, and approximate 52-week range from
  `yf.Ticker.history_metadata` or from the ATM option IV over 52 weekly
  expirations. See implementation note below.
- All yfinance calls are wrapped in try/except with a 10-second timeout.
  Network failures for a single symbol are logged and skipped — they never
  crash the screener.
- The screener must complete in < 90 seconds for up to 20 symbols
  (existing `--top` default). Use `concurrent.futures.ThreadPoolExecutor`
  with max_workers=4 for parallel yfinance fetches.
- Do NOT modify `scan.py`, `ranking.py`, `market_state.py`, or any existing
  scanner model. The screener reads scanner rows as input only.
- The existing `--options-filter` flag behavior is preserved for backward
  compatibility. The new screener is triggered by `--options-screener` flag
  (or `options_filter=true` in justfile, which maps to this new flag).

---

## Three-layer filter implementation

### Layer 1 — Asset filters

```python
LAYER1_FILTERS = {
    "min_option_volume":    500,    # avg daily options volume (20d)
    "min_open_interest":    1_000,  # OI at target expiration
    "min_stock_volume":     1_000_000,  # avg daily stock volume
    "min_market_cap_b":     5,      # $5B minimum market cap
    "iv_min_pct":           20,     # IV < 20% → prêmio não compensa
    "iv_max_pct":           60,     # IV > 60% → risco desproporcional
    "ivr_min":              30,     # IVR < 30 → não é momento de vender
    "earnings_buffer_days": 5,      # exclude if earnings within DTE + 5 days
    "min_price":            10.0,   # price < $10 → spreads ruins
}
```

### Layer 2 — Technical → strategy mapping

```python
# Maps scanner output to options strategy
# Returns "CSP", "CC", or None (no options trade)

STRATEGY_MAP = {
    # CSP candidates: bullish setup, pullback or range
    ("pullback",    "bullish_aligned"):   "CSP",
    ("pullback",    "early_bullish"):     "CSP",
    ("pullback",    "bullish_watch"):     "CSP",
    ("range",       "bullish_aligned"):   "CSP",
    ("range",       "range_watchlist"):   "CSP",
    ("early_trend", "early_bullish"):     "CSP",

    # CC candidates: extended or resistance zone
    ("extended",    "bullish_aligned"):   "CC",
    ("extended",    "bullish_trend"):     "CC",
    ("exhaustion",  "bullish_aligned"):   "CC",
    ("exhaustion",  "bearish_aligned"):   "CC",  # own stock, sell call into weakness

    # Explicitly excluded
    ("extended",    "conflicted"):        None,
    ("unknown",     "*"):                 None,
}

def map_strategy(market_state: str, adjusted_alignment: str) -> str | None:
    key = (market_state, adjusted_alignment)
    if key in STRATEGY_MAP:
        return STRATEGY_MAP[key]
    # Fallback: any bullish_* → CSP if not extended
    if "bullish" in adjusted_alignment and market_state != "extended":
        return "CSP"
    return None
```

### Layer 3 — Contract filters

```python
LAYER3_FILTERS = {
    "dte_min":              30,
    "dte_max":              45,
    "delta_min":            0.18,   # allow slight buffer below 0.20
    "delta_max":            0.32,   # allow slight buffer above 0.30
    "spread_max_pct":       10.0,   # (ask - bid) / mid × 100
    "min_premium":          0.50,   # absolute minimum per contract
    "min_monthly_return":   0.005,  # 0.5% / month on collateral
}
```

---

## IVR calculation

yfinance does not provide a direct IV history series. Use this approach:

```python
def compute_ivr(ticker: yf.Ticker, current_iv: float) -> float | None:
    """
    Approximates IV Rank using ATM implied volatility from weekly
    option expirations over the past 52 weeks.

    Falls back to a simplified estimate using historical price volatility
    if options history is unavailable.
    """
    try:
        # Method 1: use HV as IV proxy for 52-week range
        hist = ticker.history(period="1y")
        if hist.empty:
            return None
        returns = hist["Close"].pct_change().dropna()
        hv_series = returns.rolling(20).std() * (252 ** 0.5) * 100
        hv_52w_low  = hv_series.min()
        hv_52w_high = hv_series.max()
        if hv_52w_high <= hv_52w_low:
            return None
        # Use current IV vs HV range as IVR proxy
        ivr = (current_iv - hv_52w_low) / (hv_52w_high - hv_52w_low) * 100
        return round(max(0.0, min(100.0, ivr)), 1)
    except Exception:
        return None
```

Note: this is an approximation (IV vs HV range, not IV vs IV range). It is
labeled as "IVR (aprox)" in the report output. True IVR requires IV history
which yfinance does not provide. This is documented clearly in the output.

---

## Contract scoring

```python
@dataclass
class OptionsCandidate:
    symbol: str
    strategy: str            # CSP | CC
    expiration: str          # YYYY-MM-DD
    dte: int
    strike: float
    option_type: str         # PUT (CSP) | CALL (CC)
    delta: float
    iv_pct: float
    ivr_approx: float | None
    bid: float
    ask: float
    mid: float
    spread_pct: float
    premium: float           # mid price
    collateral: float        # strike × 100 (CSP) | stock_price × 100 (CC)
    monthly_return_pct: float  # (premium / collateral) × (30 / dte) × 100
    market_state: str
    adjusted_alignment: str
    earnings_date: str | None
    score: float             # composite ranking score

def score_candidate(c: OptionsCandidate) -> float:
    """
    Composite score for ranking. Higher = better.
    Weights: IVR (40%) + monthly_return (40%) + spread quality (20%)
    """
    ivr_score     = (c.ivr_approx or 0) / 100          # 0–1
    return_score  = min(c.monthly_return_pct / 2.0, 1)  # 0–1, cap at 2%/month
    spread_score  = 1 - min(c.spread_pct / 10.0, 1)    # 0–1, best=0% spread

    return (ivr_score * 0.40) + (return_score * 0.40) + (spread_score * 0.20)
```

---

## Module structure

```
src/market_scanner/
    options_screener.py     ← NEW: full three-layer screener
    options_filter.py       ← EXISTING: preserve as legacy stub (no changes)

tests/market_scanner/
    test_options_screener.py  ← NEW
```

```python
# src/market_scanner/options_screener.py

def screen_options_candidates(
    scanner_rows: list[dict],
    *,
    top_n: int = 20,
    dte_min: int = 30,
    dte_max: int = 45,
) -> tuple[list[OptionsCandidate], list[dict]]:
    """
    Main entry point. Reads scanner rows, applies three-layer filter,
    returns (candidates_ranked, exclusion_log).

    exclusion_log: list of {symbol, reason} for assets that failed
    a filter — used for the "excluded" notes in the report.
    """
    rows = scanner_rows[:top_n]

    # Layer 2 first (no network) — discard no-strategy rows early
    eligible = [(row, map_strategy(row["market_state"], row["adjusted_alignment"]))
                for row in rows]
    eligible = [(row, strat) for row, strat in eligible if strat is not None]

    # Layer 1 + 3 in parallel (network calls)
    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = {pool.submit(_evaluate_symbol, row, strat, dte_min, dte_max): (row, strat)
                   for row, strat in eligible}
        results = [f.result() for f in as_completed(futures)]

    candidates = [c for c in results if isinstance(c, OptionsCandidate)]
    exclusions  = [c for c in results if isinstance(c, dict)]  # {symbol, reason}

    candidates.sort(key=lambda c: c.score, reverse=True)
    return candidates, exclusions
```

---

## Report section format

```markdown
## 7. Candidatos para Opções (30–45 DTE)

*IVR aproximado — baseado em IV atual vs range de HV 52 semanas. Não substitui IVR real.*

| # | Símbolo | Estratégia | Strike | Exp | DTE | Delta | IVR (aprox) | Prêmio | Ret/Mês | Spread% | Setup |
|---|---------|-----------|--------|-----|-----|-------|-------------|--------|---------|---------|-------|
| 1 | NVDA | CSP PUT | $180 | 15 Ago | 37d | 0.24 | 68 | $2.85 | 1.6%/mês | 4.2% | pullback / bullish_aligned |
| 2 | PEP  | CSP PUT | $135 | 15 Ago | 37d | 0.22 | 55 | $1.20 | 0.9%/mês | 3.1% | pullback / bullish_watch   |
| 3 | AAPL | CC  CALL | $340 | 15 Ago | 37d | 0.21 | 42 | $3.10 | 1.5%/mês | 2.8% | extended / bullish_aligned |

**Excluídos:**
- NVDA *(ciclo anterior)* — já em posição aberta (strike $185, exp 17 Jul)
- META — earnings 2026-07-30 dentro do vencimento (DTE=22)
- AMZN — IVR 18 (abaixo de 30)
```

The "already in position" check reads `options_tracker.csv` — if the symbol
already has an open position, it is excluded from new candidates to avoid
doubling up.

---

## Justfile changes

```just
# Daily flow with options screener (opt-in, adds ~60-90s for yfinance calls)
daily-options universe="data/scanner_universe_filtered.csv" \
               dte_min="30" dte_max="45":
    just download-file {{universe}}
    just scan-daily universe={{universe}}
    PYTHONPATH=src uv run python -m market_scanner.daily_report \
      --scan reports/market_scanner/scan_daily.csv \
      --recommendations reports/market_scanner/execution_recommended_rules.csv \
      $([ -f reports/market_scanner/execution_recommended_rules_smc.csv ] \
        && echo "--recommendations-smc reports/market_scanner/execution_recommended_rules_smc.csv" \
        || true) \
      $([ -f options_tracker.csv ] && echo "--portfolio-path options_tracker.csv" || true) \
      --max-days 2 --top 20 --strategy all \
      --options-screener \
      --dte-min {{dte_min}} --dte-max {{dte_max}} \
      --output reports/market_scanner/daily_report.md \
      --output-candidates reports/market_scanner/daily_candidates.csv
    @echo "✓ Relatório com candidatos de opções: reports/market_scanner/daily_report.md"
```

---

## Files to create/modify

```
src/market_scanner/options_screener.py            ← NEW
src/market_scanner/daily_report.py                ← add --options-screener flag + section 7
tests/market_scanner/test_options_screener.py     ← NEW
justfile                                          ← add daily-options recipe
```

---

## Tests (minimum 8)

```python
def test_map_strategy_pullback_bullish_returns_csp()
# market_state="pullback", adjusted_alignment="bullish_aligned" → "CSP"

def test_map_strategy_extended_bullish_returns_cc()
# market_state="extended", adjusted_alignment="bullish_aligned" → "CC"

def test_map_strategy_conflicted_returns_none()
# market_state="extended", adjusted_alignment="conflicted" → None

def test_layer1_excludes_low_ivr(monkeypatch)
# Mock yfinance: IV=25%, IVR=18 → excluded with reason "IVR 18 < 30"

def test_layer1_excludes_earnings_within_dte(monkeypatch)
# Mock yfinance: earnings in 35 days, DTE target=37 → excluded

def test_layer3_excludes_wide_spread(monkeypatch)
# bid=0.50, ask=1.50 → spread_pct=100% → excluded

def test_layer3_excludes_low_monthly_return(monkeypatch)
# premium=0.30, collateral=10000, DTE=37 → return=0.024%/month < 0.5% → excluded

def test_score_ranking_ivr_weight(monkeypatch)
# Candidate A: IVR=80, return=0.8%  vs Candidate B: IVR=40, return=1.2%
# A scores higher (IVR weight=40% dominates)

def test_existing_position_excluded(monkeypatch, tmp_path)
# options_tracker.csv has open NVDA PUT → NVDA excluded from candidates

def test_screen_completes_without_crash_on_network_error(monkeypatch)
# yfinance raises exception for all symbols → returns ([], exclusion_log), no crash
```

---

## Verification

```bash
# 1. Tests (all mocked — no network)
uv run pytest tests/market_scanner/test_options_screener.py -v

# 2. Live run (requires internet, ~60-90s)
just daily-options

# 3. Check section 7 in report
grep -A 30 "Candidatos para Opções" reports/market_scanner/daily_report.md

# Expected: table with 1–5 candidates ranked by IVR
# Exclusions listed below table

# 4. Check CSV output
cat reports/market_scanner/options_candidates_$(date +%Y-%m-%d).csv

# 5. Verify existing positions excluded
# If NVDA PUT $185 is open in options_tracker.csv:
# NVDA should appear in exclusions section, not candidates

# 6. Verify standard daily is unchanged (no regression)
just daily
# Must complete without --options-screener behavior

# 7. Lint
uv run ruff check src/market_scanner/options_screener.py \
  tests/market_scanner/test_options_screener.py
```

---

## Known limitations / follow-up

- **IVR is approximate.** True IVR compares current IV against 52 weeks of
  IV history, not HV. This requires a paid data source (e.g. IBKR market
  data subscription, Tradier, or Polygon.io). The approximation using
  `IV_current vs HV_52w_range` directionally correct but overstates IVR
  in low-vol environments. Labeled as "IVR (aprox)" throughout.
- **Delta from yfinance** is computed by yfinance internally and may differ
  slightly from broker-displayed delta (different pricing model or IV surface
  point). Treat as directional estimate.
- **CC strategy** requires the user to actually hold the stock. The screener
  cannot verify this automatically unless `ibkr_positions` data is passed in.
  Future enhancement: cross-reference IBKR positions to only suggest CC for
  stocks actually held.
- **Spread data** from yfinance reflects last market close, not live bid/ask.
  During market hours, run `just ibkr-option-chain SYMBOL EXPIRATION` for
  live data on specific candidates.
- **Performance**: 20 symbols × ~3 yfinance calls each = ~60 calls total.
  With `max_workers=4` and typical yfinance latency of 0.5–2s per call,
  expect 30–90 seconds. This is why `just daily-options` is a separate
  recipe from `just daily`.
- **B3 options** (BTG portfolio) are not covered by this task. yfinance
  does not provide reliable options chain data for Brazilian underlyings.
  B3 options analysis is a future task requiring a dedicated data source.
