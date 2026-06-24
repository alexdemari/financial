# Task: Macro Context Injector — Selic, USD/BRL, S&P 500, Ibovespa in Daily Report

**Status:** Planned
**Skill:** add-feature
**Scope:** `src/market_scanner/macro_context.py` (new), `src/market_scanner/daily_report.py`
**Effort:** S
**Depends on:** task 07-daily-operational-report (completed), task 05-llm-explainer (completed)

---

## Context

`just daily-report-llm` sends scanner rows to the LLM with no macro context.
The LLM analysis is disconnected from the actual market environment: it cannot
know whether the Selic is at 10.5% or 14.75%, whether USD/BRL is at 5.20 or
6.10, or whether Ibovespa just fell 3%.

This context materially changes how scanner candidates should be interpreted:
- High Selic → RF competing harder with equities → higher dividend bar
- USD/BRL spike → dolarização thesis reinforced, domestic importers under pressure
- S&P 500 in correction → US covered calls less attractive at ATM strikes

---

## Goal

Add a `macro_context` module that fetches a compact macro snapshot from public
APIs and injects it into the LLM prompt and the daily markdown report header.

---

## Outcome spec

When done, the following must be true:

1. `just daily` and `just daily-report-llm` automatically include a macro
   context block at the top of the daily report.
2. The macro block contains (all fetched from public APIs, no auth required):
   - Selic meta (current target rate) — BCB API
   - USD/BRL exchange rate (PTAX sell, last available) — BCB PTAX API (reuse T04 cache)
   - S&P 500 last close and 1-day % change — Yahoo Finance (yfinance)
   - Ibovespa (^BVSP) last close and 1-day % change — yfinance
3. All fields degrade gracefully: if an API call fails, the field shows
   `N/A` rather than crashing the report.
4. When `--llm-explain` is active, the macro block is prepended to the LLM
   prompt (compact text, ≤150 tokens).
5. `just daily-report-llm --no-macro` skips macro fetching (for offline use).
6. Macro data is not cached between runs (always fresh, unlike PTAX which is
   cached by date in T04).
7. `uv run pytest tests/market_scanner/test_macro_context.py` passes (≥5 tests).

---

## Constraints

- No new pip dependencies: use `yfinance` (already in project) for S&P 500 and
  Ibovespa; use `urllib.request` for BCB APIs (standard library).
- All API calls have a 5-second timeout and are wrapped in try/except.
- Macro context is informational only — it does not affect scanner ranking,
  scoring, or CSV output.
- Do not modify `scan.py`, `ranking.py`, or any model file.
- `--no-macro` flag is the escape hatch; default is to always attempt macro fetch.

---

## Key design

### APIs

| Field | Source | Endpoint |
|---|---|---|
| Selic target | BCB | `https://api.bcb.gov.br/dados/serie/bcdata.sgs.432/dados/ultimos/1?formato=json` |
| USD/BRL PTAX | BCB PTAX | reuse `irpf_report.ptax.get_ptax(date.today())` (T04) or inline same logic |
| S&P 500 | yfinance | `yf.Ticker("^GSPC").fast_info` |
| Ibovespa | yfinance | `yf.Ticker("^BVSP").fast_info` |

### Module

```python
# src/market_scanner/macro_context.py

from dataclasses import dataclass

@dataclass
class MacroSnapshot:
    selic_pct: float | None        # e.g. 14.75
    usd_brl: float | None          # e.g. 5.89
    sp500_close: float | None
    sp500_change_pct: float | None
    ibov_close: float | None
    ibov_change_pct: float | None
    fetched_at: str                # ISO datetime

def fetch_macro() -> MacroSnapshot:
    """
    Fetches all macro indicators. All failures are caught and return None
    for the affected field. Never raises.
    """
    ...

def format_macro_block(snap: MacroSnapshot) -> str:
    """
    Returns a compact text block for the daily report header and LLM prompt.
    """
    def fmt(v, fmt_str, suffix=""):
        return f"{v:{fmt_str}}{suffix}" if v is not None else "N/A"

    return f"""## Macro Context — {snap.fetched_at[:10]}

| Indicator | Value |
|-----------|-------|
| Selic (meta) | {fmt(snap.selic_pct, '.2f', '%')} |
| USD/BRL (PTAX) | {fmt(snap.usd_brl, '.4f')} |
| S&P 500 | {fmt(snap.sp500_close, ',.0f')} ({fmt(snap.sp500_change_pct, '+.2f', '%')}) |
| Ibovespa | {fmt(snap.ibov_close, ',.0f')} ({fmt(snap.ibov_change_pct, '+.2f', '%')}) |
"""

def format_macro_prompt_block(snap: MacroSnapshot) -> str:
    """Compact single-line version for LLM prompt injection (≤150 tokens)."""
    ...
```

Files to create/modify:
```
src/market_scanner/macro_context.py              ← NEW
src/market_scanner/daily_report.py               ← call fetch_macro(), inject block
tests/market_scanner/test_macro_context.py       ← NEW
justfile                                         ← add --no-macro passthrough
```

---

## Report header injection

```markdown
# Daily Report — 2026-06-23

## Macro Context — 2026-06-23

| Indicator    | Value            |
|-------------|-----------------|
| Selic (meta) | 14.75%          |
| USD/BRL (PTAX) | 5.8901        |
| S&P 500      | 5,473 (+0.43%) |
| Ibovespa     | 137,420 (-0.22%) |

---

## 1. Fresh Signals (last 2 days)
...
```

---

## Tests (minimum 5)

```python
def test_fetch_macro_returns_snapshot_on_success(monkeypatch)
# Mock all 3 API calls to return valid data → all fields populated

def test_fetch_macro_degrades_when_bcb_api_fails(monkeypatch)
# Mock BCB Selic call to raise → selic_pct=None, rest populated

def test_fetch_macro_degrades_when_yfinance_fails(monkeypatch)
# Mock yfinance to raise → sp500_close=None, ibov_close=None

def test_format_macro_block_shows_na_for_missing_fields()
# MacroSnapshot with all None fields → table shows N/A throughout, no crash

def test_format_macro_prompt_block_under_150_tokens()
# len(format_macro_prompt_block(snap).split()) < 150
```

---

## Verification

```bash
# 1. Tests
uv run pytest tests/market_scanner/test_macro_context.py -v

# 2. Live daily report with macro header
just daily-report-llm

# Check report starts with macro context table
head -25 reports/market_scanner/daily_report.md

# 3. Offline mode
just daily-report-llm --no-macro
# Confirm report generated without macro section, no crash

# 4. Lint
uv run ruff check src/market_scanner/macro_context.py \
  tests/market_scanner/test_macro_context.py
```

---

## Known limitations / follow-up

- Selic meta rate from `bcdata.sgs.432` is the COPOM target — it updates only
  on COPOM meeting dates (~8x/year). This is the correct series for the displayed
  rate.
- S&P 500 and Ibovespa 1-day % change uses `fast_info` which may return the
  prior close if markets are pre-open. Acceptable for daily context.
- Does not include EUR/BRL, commodity prices, or VIX. These can be added as
  optional fields in a follow-up task.
