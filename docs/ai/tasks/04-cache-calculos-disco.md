# Task: Cache de cálculos Lux/SMC em disco

**Status:** Completed
**Scope:** `src/market_scanner/cache.py` (novo), `src/market_scanner/scan.py`, `backtest.py`
**Effort:** S
**Depende de:** Task 02 (SQLite) recomendado — SQLite resolve parte da necessidade; avaliar sobreposição antes de implementar

---

## Goal

Evitar recomputação de Lux/SMC a cada run persistindo os resultados em disco, invalidando automaticamente quando o CSV de origem muda.

---

## Outcome spec

Quando terminar, o seguinte deve ser verdade:

1. Segundo run de scanner para os mesmos símbolos é visivelmente mais rápido que o primeiro
2. Cache é invalidado automaticamente quando o CSV do símbolo é atualizado (mtime changed)
3. Sem cache (`--no-cache`) o comportamento é idêntico ao atual
4. Cache corrompido ou ausente não quebra o run — fallback silencioso para recomputação
5. Tests passam: `uv run pytest tests/market_scanner`
6. Arquivos de cache não são commitados no git

---

## Constraints

- Sem dependências novas — usar `pickle` ou `parquet` (já disponível via pandas)
- Chave de cache: `(symbol, csv_mtime)` — hash do mtime do CSV de origem
- Localização: `data/cache/lux/<symbol>_<hash>.pkl` e `data/cache/smc/<symbol>_<hash>.pkl`
- `--no-cache` flag desabilita completamente — default é cache habilitado
- Não modificar `trading_indicators`, `stock_analyzer`, ou a interface de `build_scanner_row`
- `data/cache/` no `.gitignore`

---

## Design

```python
# market_scanner/cache.py
def cache_key(symbol: str, csv_path: Path) -> str:
    mtime = csv_path.stat().st_mtime
    return f"{symbol}_{int(mtime)}"

def load_cached(symbol, csv_path, cache_dir) -> pd.DataFrame | None:
    key = cache_key(symbol, csv_path)
    path = cache_dir / f"{symbol}_{key}.pkl"
    if path.exists():
        return pd.read_pickle(path)
    return None

def save_cache(symbol, csv_path, df, cache_dir) -> None:
    key = cache_key(symbol, csv_path)
    path = cache_dir / f"{symbol}_{key}.pkl"
    df.to_pickle(path)
```

---

## Verification

```bash
# Primeiro run — sem cache
time just market-scanner

# Segundo run — deve ser mais rápido
time just market-scanner

# Forçar recomputação
just market-scanner no-cache=true

# Invalidação automática: atualizar CSV de um símbolo e rodar novamente
touch data/stocks/1D/AAPL.csv
time just market-scanner   # deve recomputar AAPL, usar cache para os demais

uv run pytest tests/market_scanner
```
