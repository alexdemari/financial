# Task T15: Dashboard — Aba "Patrimônio" (Visão Consolidada BR + USD)

**Status:** Planned
**Skill:** add-feature
**Scope:** `src/web/readers/patrimonio_reader.py` (new), `src/web/routers/patrimonio.py` (new), `frontend/src/components/PatrimonioView.jsx` (new)
**Effort:** M
**Depends on:** T12 (dashboard), T13 (trades tab), T14 (BTG parser — positions data)

---

## Context

After T14, the system has three position sources:
- **IBKR**: `reports/output/ibkr_positions_*.csv` — USD stocks, ETFs, options
- **BTG-Opções**: `data/btg/btg_opcoes_positions.csv` — BR stocks, BDRs, B3 options, aluguel
- **BTG-Geral**: `data/btg/btg_geral_positions.csv` — general BR investments + Renda Fixa

No single view shows the total patrimônio across all three. The user must
mentally sum up NLV from the IBKR HTML report + BTG Sumário + Renda Fixa.

This task adds a "Patrimônio" tab that consolidates everything into one screen,
converting USD → BRL via the latest PTAX from the BCB cache, and showing
allocation vs targets defined in `config/patrimonio_targets.yaml` (new file).

---

## Goal

A "Patrimônio" tab that shows:
1. Total patrimônio in BRL (all accounts summed, USD converted via PTAX)
2. BR vs USD split with target comparison
3. Per-account breakdown cards
4. Asset class allocation: RF / RV-BR / RV-USD / Opções / Caixa
5. Pending income (Valores em Trânsito: JCP, dividendos futuros)
6. All data read from files already written by T12/T14 — no new network calls

---

## Outcome spec

When done, the following must be true:

1. "Patrimônio" tab appears in the dashboard as the **first tab** (most
   frequently used after the main dashboard card).
2. Top section — summary cards:
   - Total BRL (all accounts, USD converted at latest PTAX)
   - IBKR NLV in USD + BRL equivalent
   - BTG-Opções total líquido BRL
   - BTG-Geral total líquido BRL
   - USD/BRL PTAX rate used (with date)
3. Allocation section — donut chart + table:
   - Asset classes: Renda Fixa BR, Ações BR, BDR, Opções BR, Caixa BR,
     Ações USD, ETF USD, Opções USD, Caixa USD
   - Shown as % of total BRL patrimônio
   - Color-coded vs targets (green = within range, amber = ±5%, red = outside)
4. Target comparison table (from `config/patrimonio_targets.yaml`):
   - RF: target 40–50% | atual XX% | status ✓/↑/↓
   - RV BR: target 20–30% | atual XX% | status
   - RV USD: target 20–30% | atual XX% | status
   - Caixa: target ≤10% | atual XX% | status
5. Pending income section (Valores em Trânsito from BTG):
   - Table: Data Liquidação | Descrição | Valor R$ | Conta
   - Total pending BRL
6. Per-account position tables (collapsible):
   - IBKR: full positions table (reuses T12 data)
   - BTG-Opções: ações + opções + BDR
   - BTG-Geral: ações + renda fixa
7. `GET /api/patrimonio` returns all consolidated data in one call.
8. PTAX is read from `data/ibkr/ptax_cache/` (BCB cache from `irpf_report`).
   If no cache exists, falls back to live BCB API call (reuses
   `irpf_report.ptax.get_ptax`).
9. If any source file is missing, that account shows as "No data —
   run: just btg-parse" rather than crashing.
10. `uv run pytest tests/web/test_patrimonio_reader.py` passes (≥ 6 tests).

---

## Constraints

- USD → BRL conversion uses PTAX only. No other exchange rate sources.
  PTAX is fetched from BCB cache first (disk), then live BCB API if needed.
- `config/patrimonio_targets.yaml` is a new file created by this task.
  The user can edit it to adjust targets. Default values based on the
  Family Office Advisor Pro guidelines (RF 40–50%, RV BR 20–30%, etc.).
- `patrimonio_reader.py` may import from `irpf_report.ptax` for PTAX fetch.
  This is an acceptable dependency (irpf_report is a peer module, not a parent).
- No modification to T14's output files.
- Allocation chart uses Recharts (already in frontend deps from T12).
- Read-only. No writes except PTAX cache (handled by irpf_report.ptax).

---

## New config file: `config/patrimonio_targets.yaml`

```yaml
# Patrimônio allocation targets (Family Office Advisor Pro guidelines)
# Ranges are inclusive (min, max) as percentage of total BRL patrimônio

currency_mix:
  brl_pct:
    target_min: 60
    target_max: 75
    label: "BRL (BR)"
  usd_pct:
    target_min: 25
    target_max: 40
    label: "USD (Exterior)"

asset_classes:
  renda_fixa_br:
    target_min: 35
    target_max: 50
    label: "Renda Fixa BR"
    color: "#3b82f6"
  acoes_br:
    target_min: 15
    target_max: 25
    label: "Ações BR"
    color: "#10b981"
  bdr:
    target_min: 0
    target_max: 5
    label: "BDR"
    color: "#6366f1"
  opcoes_br:
    target_min: 0
    target_max: 5
    label: "Opções BR"
    color: "#f59e0b"
  acoes_usd:
    target_min: 15
    target_max: 30
    label: "Ações USD"
    color: "#0ea5e9"
  etf_usd:
    target_min: 5
    target_max: 15
    label: "ETF USD"
    color: "#8b5cf6"
  opcoes_usd:
    target_min: 0
    target_max: 5
    label: "Opções USD"
    color: "#ec4899"
  caixa:
    target_min: 5
    target_max: 15
    label: "Caixa (BR + USD)"
    color: "#94a3b8"
```

---

## Key design

### Reader: `src/web/readers/patrimonio_reader.py`

```python
from pathlib import Path
from datetime import date
import yaml
import pandas as pd

# Import PTAX from irpf_report (peer module)
from irpf_report.ptax import get_ptax

IBKR_REPORTS    = Path("reports/output")
BTG_OPCOES_POS  = Path("data/btg/btg_opcoes_positions.csv")
BTG_GERAL_POS   = Path("data/btg/btg_geral_positions.csv")
BTG_RF          = Path("data/btg/renda_fixa_all.csv")
BTG_PROVENTOS   = Path("data/btg/proventos_futuros_all.csv")
TARGETS_PATH    = Path("config/patrimonio_targets.yaml")

def read_patrimonio() -> dict:
    """
    Consolidates all account data and returns patrimônio summary.
    """
    ptax = get_ptax(date.today()) or _last_cached_ptax()

    ibkr   = _read_ibkr_summary(ptax)
    btg_op = _read_btg_positions(BTG_OPCOES_POS, "BTG-Opções", ptax)
    btg_ge = _read_btg_positions(BTG_GERAL_POS,  "BTG-Geral",  ptax)
    rf     = _read_renda_fixa(ptax)
    prov   = _read_proventos()
    targets = yaml.safe_load(TARGETS_PATH.read_text())

    total_brl = (
        (ibkr["nlv_usd"] or 0) * (ptax or 1) +
        (btg_op["total_brl"] or 0) +
        (btg_ge["total_brl"] or 0) +
        (rf["total_brl"] or 0)
    )

    allocation = _compute_allocation(ibkr, btg_op, btg_ge, rf, total_brl, ptax)
    allocation_vs_targets = _compare_to_targets(allocation, targets)

    return {
        "total_brl": total_brl,
        "ptax": ptax,
        "ptax_date": date.today().isoformat(),
        "accounts": {
            "ibkr":       ibkr,
            "btg_opcoes": btg_op,
            "btg_geral":  btg_ge,
        },
        "renda_fixa": rf,
        "allocation": allocation,
        "allocation_vs_targets": allocation_vs_targets,
        "proventos_futuros": prov,
    }

def _compute_allocation(ibkr, btg_op, btg_ge, rf, total_brl, ptax) -> dict:
    """
    Returns dict of asset_class → {value_brl, pct_of_total}.
    """
    ...
```

### Asset class mapping

| Source | Asset type | Class |
|---|---|---|
| IBKR STK | asset_type=STK | acoes_usd |
| IBKR ETF | asset_type=ETF | etf_usd |
| IBKR OPT | asset_type=OPT | opcoes_usd |
| IBKR Cash | — | caixa |
| BTG ACAO | asset_type=ACAO | acoes_br |
| BTG BDR | asset_type=BDR | bdr |
| BTG OPT | asset_type=OPT | opcoes_br |
| BTG ALUGUEL | (excluded from total — already counted in ACAO position) | — |
| BTG Renda Fixa | CDB etc. | renda_fixa_br |
| BTG Caixa | Conta Corrente saldo | caixa |

### Router: `src/web/routers/patrimonio.py`

```python
from fastapi import APIRouter
from web.readers.patrimonio_reader import read_patrimonio

router = APIRouter(prefix="/api")

@router.get("/patrimonio")
def get_patrimonio():
    return read_patrimonio()
```

Register in `src/web/server.py`.

### Frontend: `frontend/src/components/PatrimonioView.jsx`

Three sub-sections:

**1. Summary cards row**
```
┌──────────────┬──────────────┬──────────────┬──────────────┐
│ Total        │ IBKR         │ BTG-Opções   │ BTG-Geral    │
│ R$XXX.XXX    │ US$XX.XXX    │ R$XX.XXX     │ R$XX.XXX     │
│              │ R$XX.XXX     │              │              │
│ USD/BRL 5.89 │              │              │              │
└──────────────┴──────────────┴──────────────┴──────────────┘
```

**2. Allocation chart + target table**
- Recharts `PieChart` (donut) with asset class colors from config
- Table below: Class | Valor R$ | % Atual | Meta | Status (✓/↑/↓)

**3. Accounts detail (collapsible)**
- IBKR positions table (from T12 reader)
- BTG-Opções positions table
- BTG-Geral positions table
- Renda Fixa table (CDB details)
- Valores em Trânsito table

---

## Files to create/modify

```
config/patrimonio_targets.yaml                  ← NEW
src/web/readers/patrimonio_reader.py            ← NEW
src/web/routers/patrimonio.py                   ← NEW
src/web/server.py                               ← register patrimonio router
frontend/src/App.jsx                            ← add "Patrimônio" as first tab
frontend/src/components/PatrimonioView.jsx      ← NEW
tests/web/test_patrimonio_reader.py             ← NEW
```

---

## Tests (minimum 6)

```python
def test_patrimonio_returns_zero_when_no_files(monkeypatch)
# No IBKR or BTG files → total_brl=0, no crash, accounts show "no_data"

def test_usd_converted_to_brl_via_ptax(monkeypatch)
# IBKR NLV=$62,406, PTAX=5.89 → ibkr.nlv_brl ≈ 367,591

def test_allocation_sums_to_100_pct(monkeypatch, tmp_path)
# All source files present → sum of allocation pct == 100 ± 0.1

def test_allocation_vs_targets_flags_outside_range(monkeypatch, tmp_path)
# acoes_br at 35% with target 15–25% → status="above"

def test_proventos_futuros_parsed_from_btg_file(tmp_path, monkeypatch)
# BTG proventos CSV with 2 rows → proventos_futuros list has 2 entries

def test_ptax_fallback_to_cache_when_api_unavailable(monkeypatch, tmp_path)
# BCB API unavailable → uses most recent cached PTAX, no crash
```

---

## Verification

```bash
# 1. Tests
uv run pytest tests/web/test_patrimonio_reader.py -v

# 2. Prerequisites
just ibkr-positions    # IBKR data fresh
just btg-parse         # BTG data parsed (both accounts)

# 3. Start dashboard
just web
# Navigate to "Patrimônio" tab (first tab)

# Expected:
# - Total BRL card shows sum of all accounts converted at today's PTAX
# - Donut chart shows allocation split: RF, Ações BR, BDR, USD...
# - Target table shows ✓/↑/↓ per class
# - Valores em Trânsito shows ITSA4 JCP (ago/26) and VIVT3 JCP (abr/27)
# - Collapsible IBKR section shows AAPL, SGOV, 4 options

# 4. Verify PTAX used
# Check the "USD/BRL PTAX" card — should match BCB rate for today

# 5. Edit targets
# Modify config/patrimonio_targets.yaml, refresh dashboard
# Verify status indicators update accordingly

# 6. Lint
uv run ruff check src/web/readers/patrimonio_reader.py \
  src/web/routers/patrimonio.py \
  tests/web/test_patrimonio_reader.py
```

---

## Known limitations / follow-up

- **Aluguel de ações** (TAEE11, VIVT3 doador no BTG): the loaned shares
  still appear in the ACAO position section with full quantity. The aluguel
  section shows the lending contract separately. This means total ações BR
  is correct (you still own the shares), and aluguel income appears in
  `conta_corrente` movimentações rather than as a position value.
- **Renda Fixa BRL in PTAX conversion**: CDB values are already in BRL —
  no conversion needed. Only IBKR NLV (USD) is converted.
- **Options notional value**: OPT positions show market value (prêmio × qty),
  not notional exposure. This is consistent with how IBKR reports options.
- **Target config is not validated** — if the user edits `patrimonio_targets.yaml`
  to non-sensical values, the dashboard may show odd results. A validation
  step is out of scope.
- **Historical patrimônio**: the History tab (T12) shows IBKR NLV only.
  A consolidated BRL history including BTG would require daily snapshots
  from BTG too — currently BTG data is point-in-time (one file per period).
  This is a future task post T15.
