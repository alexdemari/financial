# Task: Daily Operational Report (Fase 1)

**Status:** Planned
**Scope:** `src/market_scanner/daily_report.py` (novo), `tests/market_scanner/test_daily_report.py` (novo), `README.md` (atualizar)
**Effort:** M
**Depende de:** `execution_recommended_rules.csv` gerado pelo backtest (já existe)

---

## Context

O scanner já gera 51 colunas por símbolo incluindo `lux_days_since_active_event`,
`smc_days_since_active_event`, `market_state`, `action_bucket`, `adjusted_alignment`.
O backtest já gera `execution_recommended_rules.csv` com `symbol`, `side`, `qualified`,
`recommended_exit_rule`, `expectancy`, `profit_factor`, `avg_mae`, `total_trades`.

O que falta é o módulo que cruza os dois e gera o relatório diário.

---

## Goal

Criar `market_scanner.daily_report` que recebe scan CSV + recommendations CSV
e gera um relatório markdown acionável com sinais frescos, top 20 qualificados,
sumário por bucket e stats — sem rodar o scanner, sem alterar nenhum módulo existente.

---

## Rotina diária (fluxo completo)

```bash
# 1. Atualizar dados
PYTHONPATH=src uv run python -m stock_data_manager.main -s <universe>

# 2. Rodar scanner (com cache ativo)
PYTHONPATH=src uv run python -m market_scanner.scan \
  --universe-file data/scanner_universe_filtered.csv \
  --data-dir data/stocks/1D \
  --ranking-mode recent-event \
  --output reports/market_scanner/scan_daily.csv

# 3. Gerar relatório (NOVO — este módulo)
PYTHONPATH=src uv run python -m market_scanner.daily_report \
  --scan reports/market_scanner/scan_daily.csv \
  --recommendations reports/market_scanner/execution_recommended_rules.csv \
  --max-days 2 \
  --top 20 \
  --output reports/market_scanner/daily_report.md
```

`execution_recommended_rules.csv` é regenerado periodicamente (ex: semanal),
não a cada run diário.

---

## Outcome spec

Quando terminar, o seguinte deve ser verdade:

1. `python -m market_scanner.daily_report` roda com os flags acima sem erro
2. Gera markdown com 4 seções: Sinais Frescos, Top 20, Sumário por Bucket, Stats
3. Top 20 contém apenas `action_bucket == candidate` com sinal fresco E qualificado pelo backtest
4. Colunas do Top 20 incluem: `recommended_exit_rule`, `expectancy`, `profit_factor`, `avg_mae`, `total_trades`
5. Símbolo sem recomendação `scope=symbol` usa recomendação `scope=global` para o side inferido
6. Sem `--recommendations`: Top 20 lista candidatos frescos sem cruzamento de backtest
7. 7 testes passam: `uv run pytest tests/market_scanner/test_daily_report.py -v`
8. `README.md` atualizado com o comando do daily report em "Common Commands"
9. Nenhum módulo existente foi modificado

---

## CLI

```
--scan PATH              scan CSV gerado por scan.py
--recommendations PATH   execution_recommended_rules.csv do backtest (opcional)
--max-days INT           janela de recência (default 2)
--top INT                tamanho do top ranking (default 20)
--output PATH            markdown de saída
```

---

## Lógica interna

```python
# 1. Carrega scan_df do CSV
# 2. Carrega recommendations_df, filtra qualified == True
# 3. Constrói set de (symbol, side) qualificados:
#    - preferência: scope=symbol
#    - fallback: scope=global para o side inferido
# 4. Filtra sinais frescos:
fresh_mask = (
    (scan_df["lux_days_since_active_event"] <= max_days) |
    (scan_df["smc_days_since_active_event"] <= max_days)
)
# 5. Top 20 = fresco AND candidate AND (symbol, side) in qualified_set
# 6. Ordena por consistency_score desc
# 7. Join com recommendations para anexar métricas
# 8. Renderiza markdown

def infer_side(adjusted_alignment: str) -> str | None:
    if adjusted_alignment == "bullish_aligned":  return "bullish"
    if adjusted_alignment == "bearish_aligned":  return "bearish"
    return None  # no_trade, mixed → não opera
```

---

## Formato markdown

```markdown
# Daily Report — 2026-05-01

## 1. Sinais Frescos (últimos 2 dias)

| symbol | action_bucket | market_state | lux_days | lux_event | smc_days | smc_event |
|--------|--------------|--------------|----------|-----------|----------|-----------|
| NVDA   | candidate    | pullback     | 1        | BUY       | 3        | —         |

## 2. Top 20 Operacional

| rank | symbol | side    | market_state | consistency_score | recommended_exit_rule | expectancy | profit_factor | avg_mae | total_trades |
|------|--------|---------|--------------|-------------------|-----------------------|------------|---------------|---------|-------------|
| 1    | NVDA   | bullish | pullback     | 3                 | alignment_break       | 2.1%       | 1.8           | -1.2%   | 47          |

## 3. Sumário por Bucket

| bucket       | count |
|-------------|-------|
| candidate    | 12    |
| watchlist    | 34    |
| needs_review | 8     |
| avoid        | 21    |

## 4. Stats

- Total símbolos no scan: 75
- Com sinal fresco (≤ 2 dias): 18
- Qualificados pelo backtest: 12
- No Top 20: 12
```

---

## Reuse — não reimplementar

```python
from market_scanner.report_writer import sort_scanner_results  # ordenação
# padrão de markdown e formatadores: ver operational_report.py
# campos do scanner row: ver models.py
```

Não alterar `scan.py` — filtragem por recência fica isolada em `daily_report.py`.

---

## Arquivos

```
src/market_scanner/daily_report.py        ← criar
tests/market_scanner/test_daily_report.py ← criar
README.md                                 ← atualizar seção Common Commands
```

Leitura obrigatória antes de implementar:
```
src/market_scanner/operational_report.py  ← padrão markdown existente
src/market_scanner/report_writer.py       ← sort_scanner_results
src/market_scanner/models.py              ← campos canônicos
```

---

## 7 testes obrigatórios

```python
def test_filter_fresh_signals_keeps_only_recent_events()
# max_days=2 — símbolos com lux_days=5 e smc_days=5 são excluídos

def test_top_20_requires_candidate_action_bucket()
# watchlist não entra no top 20 mesmo com sinal fresco e qualificado

def test_top_20_cross_references_backtest_qualified()
# (symbol, side) não qualificado é excluído do top 20

def test_top_20_uses_symbol_recommendation_when_available()
# scope=symbol tem prioridade sobre scope=global

def test_top_20_falls_back_to_global_recommendation()
# sem recomendação scope=symbol, usa scope=global para o side inferido

def test_infer_side_from_adjusted_alignment()
# bullish_aligned → "bullish"
# bearish_aligned → "bearish"
# no_trade → None
# mixed → None

def test_render_markdown_contains_required_sections()
# output contém as 4 seções: Sinais Frescos, Top 20, Sumário, Stats
```

Usar DataFrames em memória — sem leitura de CSV real nos testes.

---

## Constraints

- `daily_report.py` é post-processing puro — não roda scanner, não baixa dados
- Não modificar `scan.py`, `operational_report.py`, `report_writer.py`, `scanner_row`, ou `cache`
- Sem portfolio tracking nesta fase (Fase 2 futura)
- Sem LLM, sem rede, sem async
- `--recommendations` é opcional — sem ele o Top 20 lista candidatos frescos sem cruzamento

---

## Out of scope (fases futuras)

- Fase 2: exit triggers em holdings (alignment_break, bucket_downgrade)
- Fase 3: portfolio tracking (CSV manual ou IBKR)
- Fase 4: alertas automáticos (email, Telegram)
- LLM Explainer (task 05) — independente, roda sobre output do daily_report

---

## Verification

```bash
# 1. Testes
uv run pytest tests/market_scanner/test_daily_report.py -v

# 2. Lint
uv run ruff check src/market_scanner/daily_report.py \
  tests/market_scanner/test_daily_report.py

# 3. End-to-end
PYTHONPATH=src uv run python -m market_scanner.scan \
  --universe-file data/scanner_universe_filtered.csv \
  --data-dir data/stocks/1D \
  --ranking-mode recent-event \
  --output /tmp/scan_test.csv

PYTHONPATH=src uv run python -m market_scanner.daily_report \
  --scan /tmp/scan_test.csv \
  --recommendations reports/market_scanner/execution_recommended_rules.csv \
  --max-days 2 --top 20 \
  --output /tmp/daily_report_test.md

# 4. Inspeção manual — confirmar:
# - Sinais frescos listados corretamente
# - Top 20 só tem candidates qualificados
# - recommended_exit_rule + métricas históricas presentes
cat /tmp/daily_report_test.md
```
