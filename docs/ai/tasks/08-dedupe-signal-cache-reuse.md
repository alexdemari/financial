# Task: Eliminar recomputação duplicada de sinal em `generate_signal`

**Status:** Not started
**Scope:** `src/stock_analyzer/signals/lux.py`, `src/stock_analyzer/signals/smc.py`, `src/stock_analyzer/analyzer.py`, `src/market_scanner/scanner_row.py`, `src/market_scanner/cache.py`
**Effort:** S
**Depende de:** Task 04 (cache disco) — já implementada, esta task fecha o gap deixado por ela

---

## Goal

`build_scanner_row` chama `generate_signal` e `generate_historical_signals` para o mesmo símbolo/modelo (`scanner_row.py:46-49`). `generate_current_signal`, usado internamente por `generate_signal`, já recomputa `generate_historical_signals` por conta própria. Resultado: `LuxSignalsOverlays.compute()` (ou equivalente SMC) roda até 2x por símbolo por modelo por run — e ainda 1x extra mesmo com `--use-cache` ligado, porque `CachedAnalyzer` (Task 04) só envolve `generate_historical_signals`, não `generate_signal`/`generate_current_signal`.

Eliminar a segunda computação: `generate_signal` deve reaproveitar o resultado de `generate_historical_signals` já calculado (ou já cacheado em disco), não recomputar do zero.

---

## Outcome spec

Quando terminar, o seguinte deve ser verdade:

1. Para um símbolo/modelo dado, `LuxSignalsOverlays.compute()` (e equivalente SMC) roda no máximo 1x por chamada a `build_scanner_row`, com ou sem `--use-cache`.
2. Com `--use-cache` ligado, a segunda chamada ao scanner para os mesmos símbolos não recomputa `generate_historical_signals` nem `generate_signal` — vem inteiramente do disco.
3. Saída de `build_scanner_row` (todos os campos de `scanner_row`) é bit-idêntica à saída atual — este é um refactor de performance, não de semântica.
4. `workers=1` (path sequencial) e `ProcessPoolExecutor` (path paralelo) continuam produzindo o mesmo resultado.
5. Tests passam: `uv run pytest tests/stock_analyzer tests/market_scanner -x -q`
6. `just verify-identical` (ou `/verify`) confirma saída idêntica ao baseline em `tests/baselines/golden.parquet`.

---

## Constraints

- Não mudar a interface pública de `build_scanner_row` nem os campos de `scanner_row` (ver AGENTS.md — Canonical scanner row fields).
- Não introduzir cache em memória entre processos — `ProcessPoolExecutor` usa processos separados; reuso só é válido dentro da mesma chamada/processo, ou via cache em disco já existente (Task 04).
- `generate_current_signal` não deve mudar de assinatura nem comportamento observável — só evitar redundância interna.
- Rastrear o parâmetro/model_name ponta a ponta (AGENTS.md — Strategy & Filter Plumbing) antes de implementar: confirmar que lux e smc passam pelo mesmo caminho de dedupe.

---

## Design (ponto de partida, ajustar durante implementação)

Opção mais simples: `generate_signal` recebe (ou calcula uma vez) o DataFrame de `generate_historical_signals` e extrai o sinal atual dele, ao invés de `generate_current_signal` chamar `generate_historical_signals` de novo internamente.

```python
# analyzer.py — antes
def generate_signal(self, df):
    historical = self.model.generate_current_signal(df)  # recomputa internamente
    ...

# depois — computa uma vez, reusa
def generate_signal(self, df):
    historical_df = self.model.generate_historical_signals(df)  # cacheado via CachedAnalyzer
    current = self.model.extract_current_from_historical(historical_df)
    ...
```

Avaliar se cabe em `analyzer.py` (nível `StockDataAnalyzer`) ou precisa mudar `lux.py`/`smc.py` (`generate_current_signal`) individualmente — os dois modelos têm implementações próprias.

---

## Verification

```bash
uv run pytest tests/stock_analyzer tests/market_scanner -x -q

# confirmar sem regressão de saída
uv run python -m market_scanner.scan --universe-file data/scanner_universe_filtered.csv \
  --data-dir data/stocks/1D --ranking-mode recent-event \
  --output /tmp/scan_before.csv --workers 1
# (após implementar)
uv run python -m market_scanner.scan --universe-file data/scanner_universe_filtered.csv \
  --data-dir data/stocks/1D --ranking-mode recent-event \
  --output /tmp/scan_after.csv --workers 1
diff /tmp/scan_before.csv /tmp/scan_after.csv   # deve ser vazio

just verify-identical
```
