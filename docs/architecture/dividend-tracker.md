# Dividend Tracker

## Purpose

`dividend_tracker` evaluates a user-defined dividend portfolio by combining
fundamental dividend yield thresholds with the existing single-symbol technical
signals from `stock_analyzer`.

Its core question is:

**"Which dividend assets are inside their price ceiling and technically worth
buying or watching today?"**

---

## Architectural Role

`dividend_tracker` is a consumer of local OHLC data and single-symbol technical
analysis. It does not replace the scanner decision layer.

```text
config/dividend_portfolio.yaml
  ->
dividend_tracker
  -> yfinance dividend cache in data/dividends/
  -> stock_analyzer technical signal
  ->
reports/dividend_tracker/dividend_daily_report.md
```

Expanded flow:

```text
portfolio config
  ->
dividend_data
  ->
price_ceiling
  ->
stock_analyzer
  ->
decision
  ->
report
```

---

## Responsibilities

`dividend_tracker` owns:

- loading and validating the dividend portfolio YAML
- adding `.SA` for Brazilian tickers when fetching Yahoo Finance dividend data
- caching dividend data in `data/dividends/` with a 24-hour TTL
- calculating dividend price ceiling from trailing twelve-month dividends or
  six-year average annual dividends
- combining price ceiling state with a technical signal
- generating the dividend daily markdown report
- optional budget allocation across `BUY` and `WATCH` assets

---

## What It Does NOT Own

`dividend_tracker` should NOT own:

- OHLC download and CSV lifecycle
- Lux, SMC, or RSI/SMA indicator logic
- broad market scanner ranking
- Scanner V3 fields such as `alignment`, `market_state`, or `action_bucket`
- brokerage execution

Those belong to:

- data lifecycle -> `stock_data_manager`
- single-symbol technical signals -> `stock_analyzer`
- low-level indicators -> `trading_indicators`
- multi-symbol scanner decisions -> `market_scanner`

---

## Key Types

### `DividendPortfolioConfig`

Parsed representation of `config/dividend_portfolio.yaml`.

Includes:

- `settings`
- `br_assets`
- `us_assets`

### `DividendAssetConfig`

Per-asset portfolio entry.

Includes:

- `ticker`
- `sector`
- `name`
- `target_weight`
- `technical_model`
- `market`
- optional `min_dy` override
- optional `ceiling_method` override (`trailing` or `average_6y`)
- optional `notes` for monitored assets

### `DividendData`

Cached dividend and price snapshot.

Includes:

- current price
- trailing annual dividends
- trailing dividend yield
- distribution history

### `PriceCeilingResult`

Fundamental price-ceiling result.

Includes:

- price ceiling
- current dividend yield
- trailing annual dividends
- dividend base used in the numerator
- ceiling method used for the numerator
- current price
- margin to ceiling

### `AssetDecision`

Final dividend contribution decision.

Values:

- `BUY`
- `WATCH`
- `WAIT`
- `OVERPRICED`

---

## CLI Interface

```bash
PYTHONPATH=src uv run python -m dividend_tracker.main \
  --config config/dividend_portfolio.yaml \
  --data-dir data/stocks \
  --budget 8000 \
  --output reports/dividend_tracker/dividend_daily_report.md
```

Use local cached dividend data and local OHLC CSVs only:

```bash
PYTHONPATH=src uv run python -m dividend_tracker.main --local-only
```

Recipes:

```bash
just dividends budget=8000
just dividends-local budget=8000
```

---

## Lógica de preço teto

```
preço_teto = dividendo_base(ceiling_method) / min_dy_efetivo
```

Onde:

- `dividendo_base`
  - `trailing` -> dividendo TTM (últimos 12 meses)
  - `average_6y` -> média aritmética dos dividendos anuais dos últimos 6 anos
    calendário com pagamentos; anos sem pagamento dentro da janela entram como zero
- `min_dy_efetivo`
  - `asset.min_dy` se definido no YAML para o ativo
  - `settings.min_dy` caso contrário

`average_6y` segue a metodologia AGF para suavizar distribuições irregulares.
Ativos brasileiros podem ter anos com JCP alto, dividendos extraordinários ou
pagamentos fracos; usar só TTM pode superestimar ou subestimar o dividendo
sustentável.

### Tabela de referência atual

| Ativo | ceiling_method | min_dy | Racional |
|-------|----------------|--------|----------|
| EGIE3 | average_6y | 6.0% | Distribuições BR irregulares; média suaviza |
| ITSA4 | average_6y | 6.0% | Distribuições BR irregulares; média suaviza |
| BBSE3 | average_6y | 6.0% | Distribuições BR irregulares; média suaviza |
| VIVT3 | average_6y | 6.0% | Distribuições BR irregulares; média suaviza |
| SAPR4 | average_6y | 6.0% | Distribuições BR irregulares; média suaviza |
| SCHD | trailing | 6.0% | ETF com dividendo mais linear; TTM adequado |
| DGRO | trailing | 6.0% | ETF com dividendo mais linear; TTM adequado |
| VYM | trailing | 6.0% | ETF com dividendo mais linear; TTM adequado |
| PEP | trailing | 3.8% | Dividend King 54a; mercado precifica 2.5-4.5% |

This table is a snapshot — `config/dividend_portfolio.yaml` is authoritative.

## Seleção de modelo técnico por ativo

O campo `technical_model` em `dividend_portfolio.yaml` define qual modelo do
`stock_analyzer` gera o sinal técnico que complementa o critério fundamentalista
de preço teto.

### Filosofia

O modelo técnico não escolhe quais ativos pertencem à carteira. Essa decisão vem
dos critérios fundamentalistas: setores escolhidos, histórico de dividendos,
preço teto e DY mínimo.

O modelo técnico responde a uma pergunta mais estreita:

> "O preço teto foi atingido. Devo comprar hoje ou aguardar 2-3 dias?"

Por isso, a métrica relevante é a precisão de sinais de compra: percentual de
sinais BUY seguidos de alta de pelo menos 5% em 45 dias. O `stock_analyzer`
histórico expõe BUY/HOLD/SELL; WATCH é uma classificação do `dividend_tracker`
sobre sinal recente, então o backtest mede BUY como evento técnico base.

### Critério de atualização

O modelo por ativo é validado via backtest com janela mínima de 3 anos. O modelo
é atualizado quando um modelo alternativo supera o atual em mais de 5 pontos
percentuais de precisão e tem pelo menos 5 sinais avaliáveis. Diferenças menores
não justificam mudança.

### Resultado do último backtest

Ver: `reports/backtest/dividend_model_comparison.md`

Última execução: 2026-06-10

---

## Ativos monitorados (`target_weight = 0.0`)

Ativos com `target_weight: 0.0` são analisados e aparecem no relatório diário,
mas são excluídos do Guia de Aporte. Esse padrão é usado para ativos operados via
estratégias de opções, onde a entrada no ativo ocorre pelo exercício da opção e
não por aporte direto.

Ativos monitorados atualmente:

- PEP — operado via venda de puts recorrente na IBKR

---

## Integration Points

- Reads portfolio config from `config/dividend_portfolio.yaml`
- Reads and writes dividend cache under `data/dividends/`
- Calls `stock_analyzer.StockDataAnalyzer` directly for technical signals
- Reads OHLC through `stock_analyzer`, which delegates local data access to
  `stock_data_manager`
- Writes report to `reports/dividend_tracker/dividend_daily_report.md`
