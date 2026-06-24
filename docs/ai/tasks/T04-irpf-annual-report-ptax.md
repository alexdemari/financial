# Task: Annual IRPF Report — Foreign Operations Converted to BRL via PTAX

**Status:** Completed
**Skill:** add-feature
**Scope:** `src/irpf_report/` (new module), `justfile`
**Effort:** M
**Depends on:** none (standalone module; reads IBKR trade history export)

---

## Context

Brazilian tax law requires residents to declare foreign investment income in the
annual IRPF (Imposto de Renda Pessoa Física) return. There is **no monthly DARF**
for foreign equity/options income — the obligation is annual only.

Each realized gain or loss must be converted to BRL using the PTAX exchange rate
published by the Banco Central do Brasil (BCB) for the **exact date of each operation**.

The PTAX is available via the BCB public API (no authentication required):
```
https://olinda.bcb.gov.br/olinda/servico/PTAX/versao/v1/odata/
  CotacaoDolarDia(dataCotacao=@dataCotacao)?
  @dataCotacao='MM-DD-YYYY'&$format=json
```

IBKR provides a trade history export (CSV) via the web portal under:
Reports → Activity → Custom Date Range → Format: CSV → Section: Trades.

---

## Goal

Create `irpf_report` module that:
1. Reads an IBKR trades CSV export for a given calendar year.
2. Fetches the BCB PTAX rate for each trade date (with local cache to avoid
   repeated API calls).
3. Computes BRL-equivalent realized P&L per trade.
4. Aggregates by asset type (STK, OPT, ETF) and by month.
5. Generates a markdown report ready for manual transcription into the IRPF program
   (Programa IRPF da Receita Federal).

---

## Outcome spec

When done, the following must be true:

1. `just irpf year=2025` runs end-to-end given an IBKR trades CSV in
   `data/ibkr/trades_2025.csv`.
2. PTAX rates are fetched from BCB API and cached in `data/cache/ptax/YYYY-MM-DD.json`.
   Cached rates are reused without new API calls.
3. For each closed trade, the report contains:
   - date, symbol, asset_type, quantity, proceeds_usd, cost_usd, pnl_usd,
     ptax_rate, proceeds_brl, cost_brl, pnl_brl.
4. Summary section contains:
   - Total realized gains in BRL (only profitable trades).
   - Total realized losses in BRL (only loss trades).
   - Net result in BRL.
   - Monthly breakdown (month, gross_gain_brl, gross_loss_brl, net_brl).
5. Weekend / holiday dates: use the last available PTAX (BCB API returns empty
   for non-business days; module must walk back up to 3 days to find the prior
   business day rate).
6. Report is written to `reports/irpf/irpf_YYYY.md`.
7. `uv run pytest tests/irpf_report/` passes (≥7 tests).
8. Module is standalone — no dependency on `ibkr_positions` or `market_scanner`.

---

## Constraints

- No write operations to IBKR. Read IBKR CSV export only (offline file).
- Network calls only to BCB PTAX API. Fail gracefully with clear error if
  API is unreachable (print warning, leave ptax_rate as None).
- Cached PTAX files live in `data/cache/ptax/` (gitignored).
- IRPF rates: this module reports the numbers only. It does not compute tax owed
  (rates depend on individual profile and other income; out of scope).
- No dependency on `pandas` for the BCB API call — use `urllib.request` or
  `requests` (already in project deps). Pandas is fine for trade CSV processing.
- Options: treat each option trade as a separate closed position (open + close
  pair). Do not net options against stock positions.

---

## Key design

### Module structure

```
src/irpf_report/
    __init__.py
    ptax.py         ← BCB API fetch + disk cache
    trades.py       ← parse IBKR trades CSV, pair opens/closes
    calculator.py   ← BRL conversion + aggregation
    report.py       ← markdown renderer
    main.py         ← CLI entry point
tests/irpf_report/
    test_ptax.py
    test_trades.py
    test_calculator.py
```

### BCB PTAX fetcher

```python
# src/irpf_report/ptax.py

import json
import urllib.request
from datetime import date, timedelta
from pathlib import Path

CACHE_DIR = Path("data/cache/ptax")
BCB_URL = (
    "https://olinda.bcb.gov.br/olinda/servico/PTAX/versao/v1/odata/"
    "CotacaoDolarDia(dataCotacao=@dataCotacao)?"
    "@dataCotacao='{date}'&$format=json&$select=cotacaoVenda"
)

def get_ptax(trade_date: date, max_lookback: int = 3) -> float | None:
    """
    Returns the PTAX sell rate (cotacaoVenda) for a given date.
    Walks back up to max_lookback days for weekends/holidays.
    Uses disk cache to avoid duplicate API calls.
    """
    for delta in range(max_lookback + 1):
        d = trade_date - timedelta(days=delta)
        cached = _load_cache(d)
        if cached is not None:
            return cached
        rate = _fetch_bcb(d)
        if rate is not None:
            _save_cache(d, rate)
            return rate
    return None  # could not find rate

def _bcb_date_fmt(d: date) -> str:
    return d.strftime("%m-%d-%Y")  # BCB expects MM-DD-YYYY

def _cache_path(d: date) -> Path:
    return CACHE_DIR / f"{d.isoformat()}.json"

def _load_cache(d: date) -> float | None:
    p = _cache_path(d)
    if p.exists():
        data = json.loads(p.read_text())
        return data.get("cotacaoVenda")
    return None

def _save_cache(d: date, rate: float) -> None:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    _cache_path(d).write_text(json.dumps({"cotacaoVenda": rate}))

def _fetch_bcb(d: date) -> float | None:
    url = BCB_URL.format(date=_bcb_date_fmt(d))
    try:
        with urllib.request.urlopen(url, timeout=10) as r:
            data = json.loads(r.read())
        values = data.get("value", [])
        if values:
            return float(values[0]["cotacaoVenda"])
    except Exception:
        pass
    return None
```

### IBKR trades CSV parsing

IBKR CSV trade export columns (relevant fields):
`DataDiscriminator`, `Asset Category`, `Currency`, `Symbol`, `Date/Time`,
`Quantity`, `T. Price`, `Proceeds`, `Comm/Fee`, `Basis`, `Realized P/L`, `Code`

Filter rows where:
- `DataDiscriminator == "Trade"`
- `Code` contains `"C"` (closed trade) or `"O;C"` (open+close in same row)

```python
# src/irpf_report/trades.py

@dataclass
class Trade:
    date: date
    symbol: str
    asset_type: str   # STK | OPT | ETF
    quantity: float
    proceeds_usd: float
    cost_usd: float
    pnl_usd: float
    currency: str     # should be USD for IBKR USD account

def parse_ibkr_csv(path: Path) -> list[Trade]:
    ...
```

### CLI

```bash
just irpf year=2025
```

```just
irpf year="2025":
    PYTHONPATH=src uv run python -m irpf_report.main \
        --trades data/ibkr/trades_{{year}}.csv \
        --year {{year}} \
        --output reports/irpf/irpf_{{year}}.md
```

---

## Report format

```markdown
# IRPF 2026 — Rendimentos no Exterior (ano-base 2025)

Fonte: IBKR account UXXXXXXXX · Gerado em YYYY-MM-DD

## Operações Encerradas

| Data | Símbolo | Tipo | Qtd | Resultado USD | PTAX | Resultado BRL |
|------|---------|------|-----|---------------|------|---------------|
| 2025-03-15 | AAPL | STK | 50 | +$1,250.00 | 5.8342 | +R$7,292.75 |
| 2025-04-22 | PEP 250718P140 | OPT | -1 | +$182.00 | 5.9110 | +R$1,075.80 |

## Resumo Anual

| | USD | BRL |
|---|---|---|
| Ganhos totais | $X.XX | R$X.XX |
| Perdas totais | -$X.XX | -R$X.XX |
| **Resultado líquido** | **$X.XX** | **R$X.XX** |

## Breakdown Mensal

| Mês | Ganhos BRL | Perdas BRL | Líquido BRL |
|-----|-----------|-----------|-------------|
| Jan/2025 | R$... | R$... | R$... |

---
*Nota: este relatório tem finalidade informativa. A apuração do imposto devido
deve ser feita no Programa IRPF da Receita Federal, considerando todos os
rendimentos do ano-calendário. Consulte um contador.*
```

---

## Tests (minimum 7)

```python
def test_ptax_loads_from_cache_without_network(tmp_path)
# Write a fake cache file; get_ptax() returns cached value, no HTTP call

def test_ptax_walks_back_on_weekend()
# Saturday → returns Friday's rate (mock HTTP response)

def test_ptax_returns_none_when_api_unreachable()
# Mock HTTP failure → None returned, no crash

def test_parse_ibkr_csv_returns_only_closed_trades()
# CSV with open + closed rows → only closed trades returned

def test_trade_pnl_usd_is_correct()
# Proceeds=1500, Basis=1250 → pnl_usd=250 (after commissions)

def test_brl_conversion_multiplies_pnl_by_ptax()
# pnl_usd=100, ptax=5.80 → pnl_brl=580.00

def test_monthly_aggregation_groups_by_month()
# 3 trades in March, 2 in April → 2 rows in monthly summary
```

---

## Verification

```bash
# 1. Tests (no network required — mock PTAX responses)
uv run pytest tests/irpf_report/ -v

# 2. Live run with a real IBKR export
# Download: Reports → Activity → Custom Date Range 2025-01-01/2025-12-31 → CSV → Trades
cp ~/Downloads/ibkr_trades_2025.csv data/ibkr/trades_2025.csv
just irpf year=2025

# Expected: reports/irpf/irpf_2025.md with all trades converted to BRL
cat reports/irpf/irpf_2025.md

# 3. Verify PTAX cache populated
ls data/cache/ptax/

# 4. Lint
uv run ruff check src/irpf_report/ tests/irpf_report/
```

---

## Known limitations / follow-up

- Options bought-to-open and sold-to-close must be matched manually if
  IBKR export splits them across rows. The `Code` column (`O`, `C`, `O;C`)
  is used as the signal; partial fills may require manual review.
- Currency conversion for non-USD positions (e.g., EUR-denominated trades)
  is out of scope. Only USD trades are supported.
- Does not compute tax owed — only the raw BRL P&L figures for IRPF declaration.
- Does not handle isento/tributável distinctions (exempt foreign income rules).
  User must verify with a tax professional.
