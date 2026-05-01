# Task: Profiling de escala real

**Status:** Completed
**Scope:** `src/market_scanner/` — read-only, sem mudanças de código
**Effort:** 1h
**Depende de:** —

---

## Goal

Medir onde o tempo é gasto num run de scanner + backtest com 5–10 símbolos e 260 bars, para confirmar se I/O de CSV ou cálculo Lux/SMC é o bottleneck dominante antes de investir em paralelização ou cache.

---

## Outcome spec

Quando terminar, o seguinte deve ser verdade:

1. Existe um relatório com breakdown de tempo por fase: carregamento CSV, cálculo Lux, cálculo SMC, build_scanner_row, output
2. O relatório identifica claramente qual fase consome > 50% do tempo
3. Nenhum código de produção foi modificado — apenas scripts de profiling
4. O relatório está salvo em `reports/profiling/scanner_profile_<date>.txt`

---

## Constraints

- Não modificar nenhum módulo de produção
- Usar apenas stdlib: `cProfile`, `pstats`, `time` — sem dependências novas
- Rodar com símbolos reais já presentes em `data/stocks/1D/`
- 5 símbolos mínimo, 260 bars máximo

---

## Verification

```bash
# Rodar o profiling
PYTHONPATH=src uv run python -m cProfile -o /tmp/scanner.prof \
  -m market_scanner.scan \
  --universe-file data/scanner_universe_sample.csv \
  --data-dir data/stocks/1D \
  --max-bars 260 \
  --ranking-mode recent-event \
  --output /tmp/scan_profile_output.csv

# Ver top 20 funções por tempo cumulativo
PYTHONPATH=src uv run python -c "
import pstats, io
p = pstats.Stats('/tmp/scanner.prof')
p.sort_stats('cumulative')
p.print_stats(20)
"
```

---

## O que registrar no relatório

- Tempo total do run
- Top 5 funções por tempo cumulativo
- Resposta para: "I/O ou CPU é o bottleneck?"
- Recomendação: SQLite primeiro, paralelização primeiro, ou ambos juntos
