# Daily Workflow Runbook

## Rotina diária completa (ordem correta)

```bash
# 1. IBKR primeiro — sincroniza trades, reconstrói options_tracker.csv, gera relatório de risco
just ibkr-positions

# 2. Scanner — atualiza dados + scan + relatório (options_tracker.csv já atualizado pelo passo 1)
just daily

# 3. Relatório LLM com contexto de portfólio (passa o snapshot IBKR de hoje)
just daily-report-llm \
  ibkr_snapshot="reports/output/ibkr_positions_$(date +%Y-%m-%d).csv"
```

O passo 1 é obrigatório porque `just ibkr-positions` reconstrói automaticamente
`options_tracker.csv` a partir do histórico de trades antes de gerar o relatório.
O passo 2 usa esse arquivo para a seção de posições abertas do relatório diário.

---

## Comandos por situação

### Sem IB Gateway (offline / fim de semana)

```bash
# Scanner sem IBKR — usa options_tracker.csv do último ibkr-positions
just daily

# Relatório LLM sem snapshot IBKR
just daily-report-llm

# Posições abertas (offline, usa CSV local da última sincronização)
just positions
```

### Só quero atualizar o relatório (dados e scan já rodaram hoje)

```bash
just report           # reusa scan_daily.csv existente, inclui options_tracker.csv
```

### Só quero ver as posições abertas agora

```bash
# Com IB Gateway aberta — snapshot ao vivo
just ibkr-positions
just positions-live

# Sem IB Gateway — usa último CSV local
just positions
```

### Semana — manutenção das regras de backtest

```bash
just weekly           # regenera execution_recommended_rules.csv (rodar semanalmente)
just weekly-smc       # versão otimizada para entradas SMC/DUAL
```

---

## O que cada comando faz (cadeia completa)

### `just ibkr-positions`

```
ibkr-flex-fetch              → baixa XML do Flex Query via API (sem login no portal)
ibkr-backfill                → atualiza trades_history.csv com novas operações
ibkr-sync                    → sync incremental via ib_insync (últimos 7 dias)
ibkr-generate-tracker        → reconstrói options_tracker.csv a partir do histórico
ibkr_positions.main          → gera reports/output/ibkr_positions_YYYY-MM-DD.{html,csv,md}
```

Outputs gerados:
- `reports/output/ibkr_positions_YYYY-MM-DD.html` — relatório visual completo
- `reports/output/ibkr_positions_YYYY-MM-DD.csv` — snapshot de posições
- `reports/output/options_tracker_live.csv` — posições de opções ao vivo
- `data/ibkr/history.jsonl` — snapshot diário da conta (append)
- `options_tracker.csv` — reconstituído automaticamente

### `just daily`

```
stock_data_manager.main      → atualiza data/stocks/1D/*.csv
market_scanner.scan          → gera reports/market_scanner/scan_daily.csv
market_scanner.daily_report  → gera reports/market_scanner/daily_report.md
  macro_context              → Selic, USD/BRL, S&P 500, Ibovespa (live)
  exit_monitor               → avalia options_tracker.csv vs scan (EXIT/WATCH/HOLD)
```

### `just daily-report-llm`

Igual ao `just daily` (sem download de dados), mais:

```
  macro_context + macro_calendar → header do relatório e contexto do prompt
  llm.explainer                 → narração LLM dos top candidatos
  llm.portfolio_context         → injeta snapshot IBKR no prompt (se --ibkr-snapshot)
```

---

## `just positions` vs `just positions-live` — quando usar cada um

| Situação | Comando | Fonte dos dados |
|---|---|---|
| IB Gateway aberta, quer dados ao vivo | `just ibkr-positions` + `just positions-live` | `options_tracker_live.csv` (snapshot live) |
| IB Gateway fechada, quer checar posições | `just positions` | `options_tracker.csv` (último sync) |
| Quer só o EXIT/WATCH/HOLD sem relatório completo | `just positions` ou `just positions-live` | depende do contexto acima |

**Nota**: `just ibkr-positions` já inclui a análise de posições no seu relatório HTML/MD.
`just positions` e `just positions-live` são atalhos standalone úteis quando não é necessário
rodar o relatório completo de risco.

---

## Relatório diário — seções

1. **Posições Abertas** — EXIT ⚠️ / WATCH ~ / HOLD por posição vs scan de hoje
2. **Sinais Frescos** — todos os símbolos com evento Lux ou SMC nos últimos N dias
3. **Top N — LUX** — rankeados por `lux_days` asc, filtrados por backtest recs
4. **Top N — SMC** — rankeados por `smc_days` asc, filtrados por backtest recs
5. **Top N — DUAL** — ambos os sinais frescos, rankeados por `lux_days + smc_days` asc
6. **SMC High Conviction — Aguardando Trigger** — `needs_review`, SMC ≤ 10 dias, `profit_factor > 5`
7. **Opções Viáveis** — liquidez ao vivo via yfinance (opcional, `--options-filter`)
8. **Contexto Macro** — Selic, USD/BRL, S&P 500, Ibovespa, calendário macro EUA
9. **Sumário por Bucket** + Stats

---

## Parâmetros úteis

| Flag | Default | Quando mudar |
|---|---|---|
| `--max-days` | `2` | `1` para filtro mais apertado; `5` para janela maior |
| `--top` | `20` | `10` para lista mais curta |
| `--strategy` | `all` | `lux`, `smc`, `dual` para relatório focado |
| `--options-filter` | off | Adiciona seção de liquidez de opções (requer internet, +10–30s) |
| `--no-macro` | off | Desativa busca de indicadores macro (uso offline) |
| `ibkr_snapshot` | vazio | Caminho do CSV IBKR para contexto portfolio-aware no LLM |

---

## Dividend tracker

```bash
# Atualiza dados + relatório de dividendos
just dividends budget=8000

# Com enriquecimento IBKR (contagens de ações + projeção de renda em USD)
# Requer que just ibkr-positions tenha rodado antes
just dividends-ibkr budget=8000

# Só relatório (dados já baixados)
just dividends-local
```

---

## IRPF (anual)

```bash
# Gera relatório BRL com PTAX do BCB para cada operação
# Usa trades_history.csv automaticamente se disponível
just irpf year=2025
```

Output: `reports/irpf/irpf_2025.md`
Inclui: detalhe por operação, resumo mensal, breakdown por tipo de ativo, total anual em USD e BRL.

---

## Arquivos de referência

| Arquivo | Descrição |
|---|---|
| `options_tracker.csv` | Posições abertas — auto-gerado pelo `ibkr_trades`, nunca editar manualmente |
| `reports/output/options_tracker_live.csv` | Snapshot ao vivo das opções IBKR |
| `reports/market_scanner/daily_report.md` | Relatório diário (latest) |
| `reports/market_scanner/scan_daily.csv` | Output bruto do scanner |
| `reports/market_scanner/execution_recommended_rules.csv` | Regras de entrada qualificadas pelo backtest |
| `data/ibkr/trades_history.csv` | Histórico canônico de trades (gitignored) |
| `data/ibkr/history.jsonl` | Snapshots diários da conta (gitignored) |
