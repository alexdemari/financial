# Task T14: BTG Extrato XLSX Parser — Duas Contas com Merge

**Status:** Planned
**Skill:** add-feature
**Scope:** `src/btg_parser/` (new module), `justfile`
**Effort:** M
**Depends on:** T13 (trades reader already expects BTG canonical CSV at data/btg/)

---

## Context

Two BTG accounts exist:
- **BTG-Opções**: dividend portfolio + options on BR stocks (TAEE11, VIVT3, ITSA4,
  BBSE3, AURA33 BDR) and B3 options (BBASH212, EGIER324, PETRR417)
- **BTG-Geral**: general investment account (separate portfolio, same XLSX format)

Both accounts export monthly extracts in the same XLSX format with 6 sheets:
`Capa`, `Sumario`, `Renda Fixa`, `Renda Variavel`, `Conta Corrente`,
`Valores em Trânsito`.

The user uploads one or two XLSX files manually (monthly or on demand).
The parser reads both, tags each row with its account alias, and writes
canonical CSV files under `data/btg/` for consumption by the dashboard
(T13, T15) and future IRPF support.

### Confirmed XLSX structure (from template analysis)

**Sheet: Renda Variável**

Positions section — Ações:
```
Código | Ação | Qtde. | Preço Fechamento R$ | Preço Médio R$ | Saldo Bruto R$
BBSE3  | BBSEGURIDADEON NM | ... | ... | ... | ...
ITSA4  | ITAUSA PN EJ N1   | ... | ... | ... | ...
TAEE11 | TAESA UNT N2      | ... | ... | ... | ...
VIVT3  | TELEF BRASILON EJ  | ... | ... | ... | ...
```

Movimentação — Ações:
```
Data | Transação | Código | Qtde. | Preço R$ | Valor Bruto R$ | Corretagem e Emolumentos R$ | Valor Líquido R$
2026-06-12 | COMPRA | ITSA4  | ... | ... | ... | ... | ...
2026-06-12 | COMPRA | VIVT3  | ... | ... | ... | ... | ...
2026-06-12 | COMPRA | BBSE3  | ... | ... | ... | ... | ...
2026-06-12 | COMPRA | TAEE11 | ... | ... | ... | ... | ...
```

Positions — Opções:
```
Código | Ativo Ref. | Qtde. | Preço Exercício R$ | Data Exercício | Tipo | Posição | Prêmio Mercado R$ | Valor de Mercado R$ | Preço de Prêmio R$
BBASH212 | BB ON | ... | ... | ... | ... | ... | ... | ... | ...
```

Movimentação — Opções:
```
Data | Transação | Tipo | Código | Data Exercício | Prêmio de Mercado R$ | Qtde. de Contratos | Prêmio Pago/Recebido R$ | Valor Financeiro Bruto R$ | Corretagem e Emolumentos R$
2026-06-12 | COMPRA | Put | EGIER324 | 2026-06-19 | ... | ... | ... | ... | ...
2026-06-12 | VENDA  | Put | EGIER324 | 2026-06-19 | ... | ... | ... | ... | ...
2026-06-18 | COMPRA | Put | PETRR417 | 2026-06-19 | ... | ... | ... | ... | ...
```

Positions — Aluguel:
```
Código | Qtde. | Posição | Preço de Referência R$ | Valor Contratado R$ | Data Operação | Data Vencimento | Taxa Ano % | IR R$ | Valor Repasse R$ | Result. Acum. Líq. R$
TAEE11 | 251.0 | Doador  | ... | ... | ... | ... | ... | ... | ... | ...
VIVT3  | 294.0 | Doador  | ... | ... | ... | ... | ... | ... | ... | ...
```

Positions — BDR:
```
Código | Ativo | Qtde. | Preço Fechamento R$ | Preço Médio R$ | Saldo Bruto R$
AURA33 | AURA 360 DR3 | ... | ... | ... | ...
```

Movimentação — BDR (includes dividends):
```
Data | Transação | Código | Qtde. | Preço R$ | Valor Bruto R$ | Corretagem e Emolumentos R$ | Valor Líquido R$
2026-06-05 | RECEBIMENTO DIVIDENDOS | AURA33 | 45.0 | - | ... | ... | ...
```

**Sheet: Renda Fixa**

Positions — CDB:
```
Emissor | Ativo | Emissão | Vencimento | Liquidez | Dias de carência | Data inicial de liquidez | Taxa Média Ponderada | Quantidade | Preço R$ | Saldo Bruto R$ | IR R$ | IOF R$ | Saldo Líquido R$
BANCO BTG PACTUAL S A | ... | ... | ... | ... | ... | ... | ... | ... | ... | ... | ... | ... | ...
```

**Sheet: Sumário**
```
Mercados | Saldo Bruto R$ 31/05/26 | Saldo Líquido R$ 31/05/26 | Saldo Bruto R$ 30/06/26 | Saldo Líquido R$ 30/06/26
Renda Fixa       | ... | ... | ... | ...
Renda Variável   | ... | ... | ... | ...
Conta Corrente   | ... | ... | ... | ...
Derivativos      | ... | ... | ... | ...
```

**Sheet: Valores em Trânsito**
```
Data Liquidação | Descrição | Valor R$
2026-08-31 | JUROS S/ CAPITAL - ITAUSA PN EJ N1    | ...
2027-04-30 | JUROS S/ CAPITAL - TELEF BRASILON EJ  | ...
```

**Sheet: Conta Corrente**

Movimentações:
```
Data | Descrição | Movimentação R$ | Saldo conta investimentos R$
2026-06-01 | Saldo Anterior | ... | ...
2026-06-05 | DIVIDENDOS - À VISTA s/ AURA 360 DR3 - AURA33 | ... | ...
2026-06-12 | LIQ BOLSA (Operacoes)- Pregão:12/06/2026 | ... | ...
2026-06-15 | VENDA - CDB BANCO BTG PACTUAL S.A. | ... | ...
```

---

## Goal

Create `btg_parser` module that:
1. Parses one or two BTG XLSX files and extracts all sections above.
2. Tags each record with `account` ("BTG-Opções" or "BTG-Geral").
3. Writes canonical CSV files under `data/btg/` — one per data type,
   with merged data from both accounts.
4. The canonical trade schema matches what T13's `trades_reader.py`
   expects at `data/btg/btg_opcoes_trades.csv` and `data/btg/btg_geral_trades.csv`.

---

## Outcome spec

When done, the following must be true:

1. `just btg-parse` processes all XLSX files found in `data/btg/uploads/`
   and writes canonical CSV outputs to `data/btg/`.
2. Account is detected by filename convention:
   - Files containing `opcoes` or matching the BTG-Opções account number → `BTG-Opções`
   - Files containing `geral` or matching the BTG-Geral account number → `BTG-Geral`
   - Fallback: prompt user to rename file with `_opcoes` or `_geral` suffix.
3. Per-account canonical outputs:
   - `data/btg/btg_opcoes_positions.csv` — current stock + BDR + options positions
   - `data/btg/btg_geral_positions.csv`
   - `data/btg/btg_opcoes_trades.csv` — stock + BDR + options movimentações
   - `data/btg/btg_geral_trades.csv`
4. Merged outputs (both accounts combined):
   - `data/btg/positions_all.csv` — all positions with `account` column
   - `data/btg/trades_all.csv` — all trades with `account` column
   - `data/btg/renda_fixa_all.csv` — CDB positions with `account` column
   - `data/btg/proventos_futuros_all.csv` — Valores em Trânsito
   - `data/btg/conta_corrente_all.csv` — movimentações CC
5. Running `just btg-parse` twice with the same file is idempotent
   (overwrites existing outputs — no duplication).
6. `data/btg/uploads/` and all outputs are gitignored.
7. `uv run pytest tests/btg_parser/` passes (≥ 8 tests).
8. After running, `just web` shows BTG trades in the Trades tab (T13)
   and BTG positions in the Brasil tab (T15, when implemented).

---

## Constraints

- **Read-only inputs.** The XLSX is never modified.
- Openpyxl `read_only=True` — always. The sheets are wide (26 columns)
  but sparse; most data is in column B onward, column A is always None.
- **Section detection by header string**, not by fixed row number.
  Sheet layouts may shift between export periods. Use `iter_rows()` and
  detect section starts by scanning for known header strings:
  `"Posição > Ações"`, `"Movimentação > Ações"`, `"Posição > Opções"`, etc.
- All monetary values are floats or None. Empty cells from anonymized
  template are None — handle gracefully.
- Dates from openpyxl are `datetime.datetime` objects — convert to
  `date.isoformat()` strings for CSV output.
- No pandas required for parsing (openpyxl only) — pandas used only
  for CSV output and merging.
- `data/btg/uploads/` must be added to `.gitignore`.

---

## Module structure

```
src/btg_parser/
    __init__.py
    models.py         ← BTGPosition, BTGTrade, BTGFixedIncome, BTGProvento dataclasses
    sheet_parser.py   ← parse each sheet section by header detection
    account_detect.py ← detect account alias from filename
    writer.py         ← write canonical CSVs to data/btg/
    merger.py         ← merge two account outputs into *_all.csv files
    main.py           ← CLI: just btg-parse
tests/btg_parser/
    test_sheet_parser.py
    test_account_detect.py
    test_writer.py
    fixtures/         ← minimal XLSX fixtures for testing
```

---

## Canonical positions schema (`btg_*_positions.csv`)

```
account        str   "BTG-Opções" | "BTG-Geral"
codigo         str   e.g. "TAEE11", "BBASH212"
nome           str   full name from XLSX e.g. "TAESA UNT N2"
asset_type     str   ACAO | OPT | BDR | ALUGUEL
quantidade     float
preco_fechamento float | None
preco_medio    float | None
saldo_bruto    float | None
currency       str   BRL
# Options only
tipo_opcao     str | None   CALL | PUT
preco_exercicio float | None
data_exercicio str | None
posicao        str | None   COMPRADOR | VENDEDOR (Doador for aluguel)
# Aluguel only
taxa_ano_pct   float | None
valor_repasse  float | None
# Source metadata
source_file    str   original XLSX filename
period_end     str   YYYY-MM-DD (end date parsed from Sumário header)
```

---

## Canonical trades schema (`btg_*_trades.csv`)

Matches what `trades_reader.py` (T13) expects:

```
date           str   YYYY-MM-DD
account        str   "BTG-Opções" | "BTG-Geral"
symbol         str   e.g. "TAEE11" or "EGIER324"
asset_type     str   ACAO | OPT | BDR
direction      str   BUY | SELL | DIVIDEND | EMPRESTIMO
quantity       float
price          float | None
proceeds       float | None   valor_bruto
commission     float | None   corretagem_emolumentos (negative)
net_value      float | None   valor_liquido
pnl_realized   float | None   (null — BTG does not report per-trade P&L directly)
currency       str   BRL
# Options only
option_type    str | None   PUT | CALL
expiration     str | None   YYYY-MM-DD
source_file    str
```

Note: `pnl_realized` is null for BTG trades — BTG exports gross proceeds only,
not per-trade P&L. Future enhancement: compute FIFO P&L from trade sequence.

---

## Section detection algorithm

```python
def _find_section(ws, header_text: str) -> int | None:
    """
    Scans sheet rows for a cell containing header_text (partial match).
    Returns the row index (0-based) of the header row, or None if not found.
    """
    for i, row in enumerate(ws.iter_rows(values_only=True)):
        if any(isinstance(c, str) and header_text in c for c in row):
            return i
    return None

def _read_table(ws, start_row: int, col_headers: list[str]) -> list[dict]:
    """
    Reads rows after start_row until a row where all data cells are None
    or a new section header is encountered.
    Maps columns by position to col_headers.
    """
    ...
```

Known section headers to detect:

| Section | Header string |
|---|---|
| Posição Ações | `"Posição > Ações"` |
| Movimentação Ações | `"Movimentação > Ações"` |
| Posição Opções | `"Posição > Opções"` |
| Movimentação Opções | `"Movimentação > Opções"` |
| Posição Aluguel | `"Posição > Ações \| Aluguel"` |
| Movimentação Aluguel | `"Movimentação > Ações \| Aluguel"` |
| Posição BDR | `"Posição > BDR"` |
| Movimentação BDR | `"Movimentação > BDR"` |
| Posição CDB | `"Posição > CDB"` |
| Sumário header | `"Saldo Bruto R$"` (in Sumário sheet) |
| Valores em Trânsito header | `"Data Liquidação"` |
| Conta Corrente movimentos | `"Movimentações"` (in CC sheet) |

---

## Account detection (`account_detect.py`)

```python
KNOWN_ALIASES = {
    "opcoes": "BTG-Opções",
    "opções": "BTG-Opções",
    "geral":  "BTG-Geral",
}

def detect_account(filepath: Path) -> str:
    """
    Detects account alias from filename.
    e.g. "extrato_opcoes_junho_2026.xlsx" → "BTG-Opções"
         "009152487_geral.xlsx"           → "BTG-Geral"
    Falls back to "BTG-Unknown" with a warning if no keyword matches.
    """
    stem = filepath.stem.lower()
    for keyword, alias in KNOWN_ALIASES.items():
        if keyword in stem:
            return alias
    print(
        f"⚠ Cannot detect account for '{filepath.name}'.\n"
        f"  Rename to include '_opcoes' or '_geral' in the filename.\n"
        f"  Defaulting to 'BTG-Unknown'."
    )
    return "BTG-Unknown"
```

---

## Justfile additions

```just
# Parse BTG XLSX export(s) and write canonical CSVs to data/btg/
# Place XLSX files in data/btg/uploads/ with _opcoes or _geral in filename.
# Example: extrato_opcoes_jun2026.xlsx, extrato_geral_jun2026.xlsx
btg-parse input-dir="data/btg/uploads":
    #!/usr/bin/env bash
    set -euo pipefail
    if [ -z "$(ls {{input-dir}}/*.xlsx 2>/dev/null)" ]; then
        echo "No XLSX files found in {{input-dir}}"
        echo "Place your BTG extracts there with '_opcoes' or '_geral' in the filename."
        exit 1
    fi
    PYTHONPATH=src uv run python -m btg_parser.main \
        --input-dir {{input-dir}} \
        --output-dir data/btg
    echo "✓ BTG data written to data/btg/"
    echo "  Run 'just web' to see BTG trades and positions in the dashboard."
```

Add `data/btg/` to `.gitignore`.

---

## Files to create/modify

```
src/btg_parser/__init__.py
src/btg_parser/models.py
src/btg_parser/sheet_parser.py
src/btg_parser/account_detect.py
src/btg_parser/writer.py
src/btg_parser/merger.py
src/btg_parser/main.py
tests/btg_parser/test_sheet_parser.py
tests/btg_parser/test_account_detect.py
tests/btg_parser/test_writer.py
tests/btg_parser/fixtures/           ← minimal XLSX for tests (openpyxl generated)
.gitignore                           ← add data/btg/
justfile                             ← add btg-parse recipe
```

---

## Tests (minimum 8)

```python
def test_detect_account_opcoes_from_filename()
# "extrato_opcoes_jun2026.xlsx" → "BTG-Opções"

def test_detect_account_geral_from_filename()
# "009152487_geral.xlsx" → "BTG-Geral"

def test_detect_account_unknown_warns(capsys)
# "extrato_junho.xlsx" → "BTG-Unknown" + warning printed

def test_find_section_returns_correct_row(fixture_ws)
# Sheet with "Posição > Ações" at row 5 → returns 5

def test_parse_acoes_positions_returns_correct_fields(fixture_xlsx)
# XLSX with 2 stock rows → 2 BTGPosition with codigo, quantidade, saldo_bruto

def test_parse_acoes_movimentacoes_maps_direction(fixture_xlsx)
# "COMPRA" row → direction="BUY"; "VENDA" row → direction="SELL"

def test_parse_opcoes_movimentacoes_extracts_expiration(fixture_xlsx)
# Options movimentação row with "Data Exercício" → expiration="2026-06-19"

def test_merger_combines_two_accounts(tmp_path)
# Two CSVs with different account tags → merged file has both, account column preserved

def test_idempotent_parse_overwrites_not_duplicates(tmp_path)
# Parse same file twice → output CSV has same row count both times
```

---

## Verification

```bash
# 1. Tests (uses fixture XLSX, no real file needed)
uv run pytest tests/btg_parser/ -v

# 2. Place real XLSX files
mkdir -p data/btg/uploads
cp ~/Downloads/extrato_jun2026.xlsx data/btg/uploads/extrato_opcoes_jun2026.xlsx
# (second account if available)
cp ~/Downloads/extrato_geral_jun2026.xlsx data/btg/uploads/extrato_geral_jun2026.xlsx

# 3. Run parser
just btg-parse

# 4. Verify outputs
ls -lh data/btg/
head -5 data/btg/btg_opcoes_positions.csv
head -5 data/btg/trades_all.csv

# Expected positions: BBSE3, ITSA4, TAEE11, VIVT3 (ações) + BBASH212 (opção) + AURA33 (BDR)
# Expected trades: COMPRA ITSA4/VIVT3/BBSE3/TAEE11 on 2026-06-12 + options EGIER324/PETRR417

# 5. Open dashboard — Trades tab should now show BTG trades
just web

# 6. Lint
uv run ruff check src/btg_parser/ tests/btg_parser/
```

---

## Known limitations / follow-up

- `pnl_realized` is null for all BTG trades — the XLSX does not export
  per-trade P&L. Computing FIFO P&L from trade sequence is a future task
  (needed for DARF calculation on B3 operations).
- Renda Fixa (CDB) positions are parsed and written to `renda_fixa_all.csv`
  but not shown in T13 (trades tab) or T15 (patrimônio) yet — those tasks
  will consume the file when ready.
- The `Conta Corrente` movimentações are parsed and archived to
  `conta_corrente_all.csv` for auditing but not surfaced in the dashboard yet.
- Multi-month history: running `btg-parse` monthly adds new data. A future
  merge/dedup step is needed if the same trade appears in two monthly exports
  (e.g., a position carried over appears in positions of both months).
  For now, each parse run overwrites the output files.
- SAPR4 appears in `config/dividend_portfolio.yaml` but not in the BTG extrato
  template — it may be in the BTG-Geral account or not currently held.
  The parser handles missing assets gracefully.
