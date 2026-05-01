# Task: Paralelização do scanner e backtest

**Status:** Completed
**Scope:** `src/market_scanner/scan.py`, `backtest.py`, `backtest_execution.py`
**Effort:** M
**Depende de:** Task 02 (SQLite) recomendado para I/O seguro; pode rodar sem se CSV for read-only

---

## Goal

Processar símbolos em paralelo no scanner e backtest usando `ProcessPoolExecutor`, com flag `--workers N` opt-in e comportamento idêntico ao atual quando `--workers 1`.

---

## Outcome spec

Quando terminar, o seguinte deve ser verdade:

1. `just market-scanner` e `just market-scanner-backtest` aceitam `--workers N` (default `1`)
2. Com `--workers 1` o output é bit-a-bit idêntico ao atual — nenhuma regressão
3. Com `--workers 4` o tempo de run cai proporcionalmente ao número de workers para universos grandes
4. Workers recebem dados já carregados em memória — nenhum worker faz I/O de CSV
5. Sem shared state entre workers — cada processo é isolado
6. Tests passam: `uv run pytest tests/market_scanner`
7. `README.md` atualizado com a flag `--workers`

---

## Constraints

- `ProcessPoolExecutor` apenas — não introduzir `asyncio`, `threading`, ou filas
- Caller permanece síncrono — paralelismo é interno ao scanner, invisível para quem chama
- Carregamento de CSV acontece no processo principal antes do pool — workers recebem DataFrame já em memória
- `--workers 1` é o default — retrocompatível com todos os comandos existentes no `justfile`
- Não modificar `trading_indicators` ou `stock_analyzer`

---

## Design

```
# Hoje — scan.py
for symbol in symbols:
    row = build_scanner_row(symbol, df_map[symbol], ...)

# Depois
def _worker(args):
    symbol, df, config = args
    return build_scanner_row(symbol, df, config)

# carrega tudo antes
df_map = {s: load_symbol_csv(data_dir, s) for s in symbols}

with ProcessPoolExecutor(max_workers=workers) as pool:
    rows = list(pool.map(_worker, [(s, df_map[s], config) for s in symbols]))
```

Aplicar o mesmo padrão em `backtest.py` e `backtest_execution.py`.

---

## Verification

```bash
# Comportamento idêntico com 1 worker
just market-scanner
just market-scanner workers=1   # deve produzir output igual

# Performance com N workers
time just market-scanner workers=4

uv run pytest tests/market_scanner
```
