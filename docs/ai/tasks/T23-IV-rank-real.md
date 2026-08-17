# Task T23: IV Rank real (fecha o gap deixado pelo T22)

**Status:** Planned
**Skill:** add-feature
**Scope:** `market_scanner/options_screener.py` (modificar), possivelmente `market_scanner/daily_report.py` e `src/web/` se consumirem `ivr_approx`
**Effort:** S
**Depends on:** T22 (implementado — `fetch_ibkr_underlying_iv_history` e `compute_iv_percentiles` já existem e funcionam)

---

## Contexto

O T22 implementou IV Percentile real (`compute_iv_percentiles`, janelas 13w/26w/52w)
a partir de `iv_history` — a série de IV do underlying buscada uma vez por símbolo
via `fetch_ibkr_underlying_iv_history`. Isso funcionou bem.

O que não aconteceu: **IV Rank continua vindo de `compute_ivr` (proxy via HV,
herdado do T17)**. `ivr_approx` é usado hoje:

- Como filtro de elegibilidade (`LAYER1_FILTERS["ivr_min"] = 30`, em
  `_candidate_from_contract`)
- Como componente do score, em **ambos** os conjuntos de pesos
  (`WEIGHTS_WITH_REAL_IVP["ivr_approx"] = 0.20`, `WEIGHTS_LEGACY["ivr_approx"] = 0.40`)
- Como **chave primária de ordenação** dos candidatos finais:
  ```python
  candidates.sort(
      key=lambda candidate: (
          candidate.ivr_approx if candidate.ivr_approx is not None else -1.0,
          candidate.score,
      ),
      reverse=True,
  )
  ```

A série `iv_history` já buscada pelo T22 tem tudo que é preciso pra calcular
IV Rank real (`(atual - min) / (max - min) × 100` sobre a mesma janela de
52 semanas que `compute_iv_percentiles` já usa) — só falta a função. Não é
preciso nenhuma chamada nova à IBKR.

---

## Objetivo

Adicionar `compute_iv_rank(iv_history) -> float | None`, calcular
`ivr_real` junto com `iv_percentile_*` (mesmo ponto de chamada, mesma
série), e trocar `ivr_approx` por `ivr_real` no score e na ordenação —
mantendo `ivr_approx` só como fallback de última instância, para quando
nem `iv_history` estiver disponível (Gateway fora do ar, símbolo sem
histórico suficiente).

---

## Outcome spec

1. `compute_iv_rank(iv_history: list[float]) -> float | None` — mesma
   assinatura e mesmo critério de suficiência de dado que
   `compute_iv_percentiles` (window de 250 dias / 52w; `None` se
   `len(iv_history) < 250`, não aproximar com janela menor).
2. `OptionsCandidate` ganha `ivr_real: float | None`. **Não remover
   `ivr_approx`** — ele continua existindo como fallback e para
   comparação/auditoria (útil enquanto o dado real ainda não tem histórico
   longo o bastante em símbolos novos).
3. `fetch_ibkr_iv_data` passa a retornar também `ivr_real` (calculado a
   partir do mesmo `iv_history` já recebido — não é uma chamada nova).
4. Filtro de elegibilidade (`ivr_min = 30`) passa a usar `ivr_real` quando
   disponível, `ivr_approx` como fallback quando não — mesma lógica de
   "prefira o real, caia pro proxy" já usada em `iv_percentile_52w` vs.
   score.
5. `score_candidate` reponderado:
   - Quando `ivr_real` e `iv_percentile_52w` **ambos** disponíveis: dado
     100% real, sem HV proxy nenhum no cálculo.
   - Quando só um dos dois está disponível: usa o disponível, redistribui
     o peso do outro entre `return`/`spread` (não preencher silenciosamente
     com `ivr_approx` misturado a dado real no mesmo score — ou é dado
     real ou é fallback total, não uma mistura opaca).
   - Quando nenhum dos dois está disponível: fallback total pro
     `WEIGHTS_LEGACY` já existente (`ivr_approx` + return + spread) — esse
     caminho não muda.
6. `classify_iv_quadrant` passa a receber `ivr_real` (com fallback pra
   `ivr_approx` só se `ivr_real` for `None`) em vez de sempre receber
   `ivr_approx`.
7. Ordenação final troca `candidate.ivr_approx` por
   `candidate.ivr_real if candidate.ivr_real is not None else candidate.ivr_approx`
   como chave primária.
8. **Antes de tocar em `daily_report.py` e no dashboard (`src/web/`),
   rodar `grep -rn "ivr_approx"` no repo inteiro** — se a coluna "IVR
   (aprox)" do relatório ou algum reader do dashboard depender do nome ou
   da posição desse campo, atualizar para mostrar `ivr_real` (com label
   "IVR" sem "aprox") quando disponível, e "IVR (aprox)" só quando for de
   fato o fallback. Não presumir que só o `options_screener.py` usa esse
   campo — confirmar antes de editar os outros arquivos.
9. `uv run pytest tests/market_scanner/test_options_screener.py` passa,
   incluindo os testes já existentes (não quebrar nada do T22), mais
   ≥ 5 testes novos para esta task.

---

## Constraints

- **Não é uma chamada nova à IBKR.** `iv_history` já é buscado uma vez por
  símbolo; `compute_iv_rank` e `compute_iv_percentiles` são as duas
  leituras da mesma série, chamadas juntas no mesmo lugar
  (`fetch_ibkr_iv_data`). Se a implementação acabar fazendo uma segunda
  requisição à IBKR para o Rank, isso é um erro de design — pare e revise.
- **Não misturar dado real com proxy no mesmo score sem rótulo.** Se um
  candidato usa `ivr_approx` em vez de `ivr_real` (porque a série era
  curta demais), isso precisa ficar visível em algum lugar — no mínimo via
  `iv_source` (que já existe: `"ibkr"` vs `"unavailable"`) refletindo
  corretamente qual dos dois foi de fato usado no score daquele candidato,
  não só se a IBKR respondeu.
- **`ivr_approx` não é removido nesta task.** Continua existindo,
  continua sendo calculado (é barato, usa dado do yfinance que já está
  sendo buscado de qualquer forma) — só deixa de ser a fonte primária.
- Seguir o padrão de threshold já estabelecido pelo T22 para
  `IV_PERCENTILE_WINDOWS["52w"] = 250` (dias de pregão) — usar a mesma
  constante para o Rank, não duplicar o número mágico.

---

## Key design

```python
def compute_iv_rank(iv_history: list[float]) -> float | None:
    """Real IV Rank: (current - 52w_low) / (52w_high - 52w_low) × 100.

    Mirrors compute_iv_percentiles' sufficiency rule — withholds the
    result (None) rather than computing over a window shorter than 52w,
    for the same reason: a Rank computed from 40 days of history looks
    precise while being close to meaningless.
    """
    window_size = IV_PERCENTILE_WINDOWS["52w"]
    if len(iv_history) < window_size:
        return None
    window = iv_history[-window_size:]
    current = window[-1]
    low, high = min(window), max(window)
    if high <= low:
        return None
    rank = (current - low) / (high - low) * 100.0
    return round(max(0.0, min(100.0, rank)), 1)
```

`fetch_ibkr_iv_data` — adicionar ao dict de retorno:

```python
percentiles = compute_iv_percentiles(iv_history or [])
ivr_real = compute_iv_rank(iv_history or [])
result = {
    "iv_underlying_pct": iv_underlying_pct,
    "iv_contract_pct": iv_contract_pct,
    "iv_percentile_13w": percentiles["13w"],
    "iv_percentile_26w": percentiles["26w"],
    "iv_percentile_52w": percentiles["52w"],
    "ivr_real": ivr_real,
    "iv_source": (
        "ibkr" if iv_underlying_pct is not None or iv_contract_pct is not None
        else "unavailable"
    ),
}
```

Score reponderado — ilustrativo, ajustar os splits exatos durante a
implementação, mas a estrutura de decisão deve ser:

```python
WEIGHTS_FULLY_REAL = {"ivr_real": 0.25, "ivp_real": 0.25, "return": 0.35, "spread": 0.15}
WEIGHTS_PARTIAL_REAL_IVP_ONLY = {"ivp_real": 0.30, "return": 0.45, "spread": 0.25}
WEIGHTS_PARTIAL_REAL_IVR_ONLY = {"ivr_real": 0.30, "return": 0.45, "spread": 0.25}
WEIGHTS_LEGACY = {"ivr_approx": 0.40, "return": 0.40, "spread": 0.20}  # já existe, sem mudança


def score_candidate(candidate: OptionsCandidate) -> float:
    return_score = min(candidate.monthly_return_pct / 2.0, 1.0)
    spread_score = 1.0 - min(candidate.spread_pct / 10.0, 1.0)
    has_ivr_real = candidate.ivr_real is not None
    has_ivp_real = candidate.iv_percentile_52w is not None

    if has_ivr_real and has_ivp_real:
        w = WEIGHTS_FULLY_REAL
        return round(
            (candidate.ivr_real / 100.0) * w["ivr_real"]
            + (candidate.iv_percentile_52w / 100.0) * w["ivp_real"]
            + return_score * w["return"]
            + spread_score * w["spread"], 4,
        )
    if has_ivp_real:
        w = WEIGHTS_PARTIAL_REAL_IVP_ONLY
        return round(
            (candidate.iv_percentile_52w / 100.0) * w["ivp_real"]
            + return_score * w["return"]
            + spread_score * w["spread"], 4,
        )
    if has_ivr_real:
        w = WEIGHTS_PARTIAL_REAL_IVR_ONLY
        return round(
            (candidate.ivr_real / 100.0) * w["ivr_real"]
            + return_score * w["return"]
            + spread_score * w["spread"], 4,
        )
    w = WEIGHTS_LEGACY
    return round(
        ((candidate.ivr_approx or 0.0) / 100.0) * w["ivr_approx"]
        + return_score * w["return"]
        + spread_score * w["spread"], 4,
    )
```

Ordenação:

```python
candidates.sort(
    key=lambda c: (
        c.ivr_real if c.ivr_real is not None
        else (c.ivr_approx if c.ivr_approx is not None else -1.0),
        c.score,
    ),
    reverse=True,
)
```

---

## Tests (mínimo 5 novos)

```python
def test_compute_iv_rank_known_series()
# série sintética com min/max conhecidos, 250+ pontos → rank bate com cálculo manual

def test_compute_iv_rank_none_when_history_short()
# 100 pontos (< 250) → None, mesmo comportamento de compute_iv_percentiles

def test_score_uses_fully_real_weights_when_both_available()
def test_score_falls_back_to_ivp_only_weights_when_ivr_real_missing()
def test_score_falls_back_to_legacy_when_nothing_real_available()
# cada um comparado com cálculo manual esperado, não só "roda sem erro"

def test_sort_prefers_ivr_real_over_ivr_approx_as_primary_key()
# dois candidatos com ivr_approx igual mas ivr_real diferente → ordem
# reflete ivr_real, não ivr_approx
```

---

## Verification

```bash
# 1. Confirmar quem mais usa ivr_approx antes de editar report/dashboard
grep -rn "ivr_approx" --include="*.py" .

# 2. Tests
uv run pytest tests/market_scanner/test_options_screener.py -v

# 3. Rodar com Gateway ativo, conferir a seção 7 do relatório
just daily-options
# Esperado: candidatos com histórico de IV suficiente mostram IVR sem "(aprox)";
# candidatos sem histórico suficiente (símbolo novo) continuam mostrando IVR (aprox)

# 4. Lint
uv run ruff check market_scanner/options_screener.py
```

---

## Known limitations / follow-up

- Symbols com menos de 250 dias de `iv_history` (IPOs recentes, opções
  novas) continuam limitados ao `ivr_approx` — isso é esperado e não é bug,
  mas vale monitorar quantos candidatos caem nesse caminho na prática ao
  longo de algumas execuções, pra saber se o proxy ainda pesa muito no
  ranking final ou se já é caso raro.
- Não mexi na constante de `ivr_min` (filtro de elegibilidade, hoje 30)
  nem nos limiares do quadrante (`IVR_THRESHOLD`/`IVP_THRESHOLD` = 50) —
  eles foram calibrados olhando o proxy; vale reavaliar depois de rodar
  algumas semanas com o dado real se os limiares ainda fazem sentido.
