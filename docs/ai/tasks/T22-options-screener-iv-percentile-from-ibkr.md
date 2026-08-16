# Task T22: Options Screener — IV Percentile real via IBKR (substitui proxy HV do T17)

**Status:** Implemented
**Skill:** add-feature
**Scope:** `src/market_scanner/options_screener.py` (modificar), `src/market_scanner/daily_report.py` (modificar), `justfile` (modificar)
**Effort:** M
**Depends on:** T17 (options screener — completo, esta task substitui parte da lógica dele, não recria do zero)

---

## Contexto

O T17 implementou o screener de opções com um IVR aproximado (`ivr_approx`),
calculado usando volatilidade histórica (HV) do preço como proxy do range de
IV, porque yfinance não expõe histórico de IV. Isso está documentado no
próprio T17 como limitação conhecida.

Validei diretamente contra a API da IBKR (via snapshot de market data) que
esse proxy não é mais necessário para IV Percentile — a IBKR calcula e serve
isso nativamente, com dado real, em três janelas:

```json
// AAPL (contract_id 265598), sábado — mercado fechado, dado ainda válido
"implied-vol-underlying": { "annual_iv": 0.2227, "is_valid": true }
"historical-vol":         { "annual_pct": 0.3597 }
"implied-volatility-percentile": {
  "high_13w": 0.2063,
  "high_26w": 0.1032,
  "high_52w": 0.2151
}
```

Por contrato específico (não só o underlying), o IV real também está
disponível:

```json
// AAPL 305 PUT, venc. 18/set/26 (contract_id 838696736)
"implied-vol": { "annual_iv": 0.2253, "is_valid": true }
```

**Achado importante:** o campo de IV por *midpoint* (`option_midpoint_iv`)
retornou inválido (`isValid: false`, valor negativo) no teste com mercado
fechado — provavelmente porque o cálculo de midpoint IV depende de NBBO ao
vivo. O campo `implied_vol` (não-midpoint) funcionou normalmente e bateu com
o IV do underlying. **Usar `implied_vol`, não `option_midpoint_iv`**, e
tratar `is_valid: false` como "sem dado" (fallback), nunca como zero.

Não existe um campo nativo equivalente a **IV Rank** (`(atual-min)/(max-min)`
de IV) — só Percentile. O `ivr_approx` do T17 continua existindo como
aproximação complementar, agora rotulado como tal ao lado do dado real.

---

## Objetivo

Substituir a fonte de IV/IVR no `options_screener.py` por dados reais da
IBKR (IV do underlying, IV por contrato, IV Percentile em 3 janelas),
mantendo o `ivr_approx` do T17 como campo secundário (não remover — ainda é
o único proxy disponível para "Rank"). Adicionar classificação por quadrante
IVR×IVP ao ranking, seguindo a lógica de "IV Rank vs IV Percentile" descrita
no guia usado como referência para esta task.

yfinance continua sendo usado **apenas** para o que ele já fazia bem e que a
IBKR não resolve aqui: earnings date e fundamentals (market cap, volume
médio). Não trocar essa parte.

---

## Outcome spec

Quando pronto, tudo isso deve ser verdade:

1. `OptionsCandidate` ganha os campos: `iv_underlying_pct`,
   `iv_contract_pct`, `iv_percentile_13w`, `iv_percentile_26w`,
   `iv_percentile_52w`, `iv_quadrant`. O campo `ivr_approx` do T17
   permanece, sem remoção.
2. A busca de IV usa a mesma camada de acesso à IBKR já usada pelo resto do
   projeto (verificar se `ibkr` / `ibkr_trades` já tem um cliente
   HTTP/SDK reutilizável antes de criar um novo — não duplicar transporte).
3. Se `is_valid` vier `false` (ou o campo vier ausente) para qualquer uma
   dessas métricas, o candidato usa `None` nesses campos, mantém
   `ivr_approx` como fallback, e uma nota é registrada no exclusion/warning
   log — **nunca** um valor de IV negativo ou zero é usado silenciosamente
   no score.
4. `iv_quadrant` classifica cada candidato com base em `ivr_approx` e
   `iv_percentile_52w`, ambos vs. limiar 50 (ajustável), em uma das quatro
   categorias:
   - `venda_confiante` — IVR alto + IVP alto
   - `spike_pontual` — IVR alto + IVP baixo (cautela: pode reverter rápido)
   - `ambiente_comprimido` — IVR baixo + IVP alto (evitar venda de prêmio)
   - `compra_premio` — IVR baixo + IVP baixo
   - `indefinido` — se qualquer um dos dois inputs for `None`
5. `score_candidate` é reponderado para incorporar o dado real quando
   disponível:
   - Com `iv_percentile_52w` disponível: IVP real (30%) + IVR aprox (20%) +
     retorno mensal (35%) + qualidade de spread (15%)
   - Sem `iv_percentile_52w` (fallback total pro T17 antigo): mantém os
     pesos originais do T17 (IVR aprox 40% + retorno 40% + spread 20%)
   - Os dois casos e seus pesos devem ficar explícitos em constantes
     nomeadas no código, não number mágico inline.
6. A seção 7 do relatório diário ganha colunas `IVP (52w)` e `Quadrante`,
   mantendo `IVR (aprox)` como já existe.
7. `just daily-options` passa a exigir Gateway da IBKR ativo (documentar
   isso claramente no `justfile` e no `README`/runbook — hoje o comentário
   do recipe diz que o daily scanner não precisa de Gateway; isso deixa de
   ser verdade só para esta variante `--options-screener`).
8. yfinance continua sendo a fonte de earnings date e fundamentals — nenhuma
   mudança nessa parte do Layer 1.
9. `uv run pytest tests/market_scanner/test_options_screener.py` passa,
   incluindo os testes já existentes do T17 (não quebrar nenhum) mais os
   novos testes desta task (≥ 6 adicionais).
10. Testes seguem a regra dura do `AGENTS.md`: sem rede real — mockar o
    cliente IBKR com fixtures baseadas nos payloads reais validados acima.

---

## Constraints

- **Confirmar os identificadores de campo reais antes de codar.** Os nomes
  usados aqui (`implied_vol`, `implied_vol_underlying`,
  `implied_volatility_percentile`, `historical_vol`) vieram de uma
  ferramenta de MCP de mercado, não necessariamente do endpoint que o
  módulo `ibkr`/`ibkr_trades` do projeto já usa (Client Portal REST API ou
  `ib_insync`, dependendo de como foi implementado). **Não assumir os
  mesmos nomes de campo/field codes na API real sem checar** — inspecionar
  primeiro como o `ibkr` module existente já autentica e busca market data,
  e usar essa mesma camada. Se for a Client Portal Web API
  (`/iserver/marketdata/snapshot`), os campos são resolvidos por *field
  code* numérico (referência:
  `https://interactivebrokers.github.io/cpwebapi/`), não por nome — mapear
  os nomes usados aqui pros field codes corretos e documentar o mapeamento
  num único lugar (`options_screener.py` ou um `ibkr_market_data.py` novo,
  o que fizer mais sentido dado o código existente).
- **Fallback obrigatório.** Falha de rede, Gateway fora do ar, ou
  `is_valid: false` em qualquer contrato nunca derruba o screener inteiro —
  mesmo padrão de resiliência que o T17 já usa pra yfinance (try/except por
  símbolo, log de exclusão, segue pro próximo).
- **Não remover `ivr_approx`.** Ele é o único proxy disponível pra "Rank"
  hoje; a mudança é aditiva, não substitutiva, exceto na fonte do que hoje
  é chamado de "IV atual" (isso sim passa a vir da IBKR em vez do
  yfinance, quando disponível — com fallback pro valor de yfinance se a
  IBKR não responder).
- **Rate limit / custo de market data.** Snapshot de IV por contrato
  significa uma chamada por candidato (não por símbolo) — com `top_n=20` e
  ~2-3 contratos avaliados por símbolo (deltas próximos do alvo), isso pode
  ser 40-60 chamadas por execução do screener. Verificar se isso estoura
  algum limite de market data lines simultâneas da assinatura da IBKR do
  usuário; se sim, deve ficar batched/sequencial com um pequeno intervalo,
  não paralelizado sem limite.
- yfinance permanece exatamente como está para earnings/fundamentals — zero
  mudança nessa parte do Layer 1.

---

## Data model (adições)

```python
@dataclass
class OptionsCandidate:
    # ... campos existentes do T17 sem alteração ...
    ivr_approx: float | None          # já existe (T17) — mantido

    # novos campos (T22)
    iv_underlying_pct: float | None   # implied_vol_underlying.annual_iv × 100
    iv_contract_pct: float | None     # implied_vol do contrato específico × 100
    iv_percentile_13w: float | None   # × 100 (fração → %)
    iv_percentile_26w: float | None
    iv_percentile_52w: float | None
    iv_quadrant: str                  # venda_confiante | spike_pontual |
                                       # ambiente_comprimido | compra_premio | indefinido
    iv_source: str                    # "ibkr" | "yfinance_proxy" | "unavailable"
```

## Classificação de quadrante

```python
IVR_THRESHOLD = 50.0
IVP_THRESHOLD = 50.0

def classify_iv_quadrant(ivr_approx: float | None, ivp_52w: float | None) -> str:
    if ivr_approx is None or ivp_52w is None:
        return "indefinido"
    ivr_high = ivr_approx >= IVR_THRESHOLD
    ivp_high = ivp_52w >= IVP_THRESHOLD
    if ivr_high and ivp_high:
        return "venda_confiante"
    if ivr_high and not ivp_high:
        return "spike_pontual"
    if not ivr_high and ivp_high:
        return "ambiente_comprimido"
    return "compra_premio"
```

## Scoring (reponderado)

```python
# Pesos usados quando iv_percentile_52w está disponível (dado real da IBKR)
WEIGHTS_WITH_REAL_IVP = {"ivp_real": 0.30, "ivr_approx": 0.20, "return": 0.35, "spread": 0.15}

# Pesos originais do T17 — fallback quando não há dado real de IVP
WEIGHTS_LEGACY = {"ivr_approx": 0.40, "return": 0.40, "spread": 0.20}


def score_candidate(c: OptionsCandidate) -> float:
    return_score = min(c.monthly_return_pct / 2.0, 1)
    spread_score = 1 - min(c.spread_pct / 10.0, 1)
    ivr_score = (c.ivr_approx or 0) / 100

    if c.iv_percentile_52w is not None:
        ivp_score = c.iv_percentile_52w / 100
        w = WEIGHTS_WITH_REAL_IVP
        return (
            ivp_score * w["ivp_real"]
            + ivr_score * w["ivr_approx"]
            + return_score * w["return"]
            + spread_score * w["spread"]
        )

    w = WEIGHTS_LEGACY
    return ivr_score * w["ivr_approx"] + return_score * w["return"] + spread_score * w["spread"]
```

---

## Fallback / resiliência

```python
def fetch_ibkr_iv_data(contract_id: int, exchange: str = "SMART") -> dict:
    """
    Busca IV do underlying, IV percentile e IV do contrato via IBKR.
    Nunca levanta exceção para o caller — retorna dict com campos None
    e iv_source="unavailable" em caso de falha, timeout, ou is_valid=false.
    """
    try:
        # usar a MESMA camada de acesso IBKR já existente no projeto —
        # ver ibkr/ibkr_trades para o cliente já configurado (auth,
        # base URL, retry) antes de escrever um novo
        ...
    except Exception:
        return {
            "iv_underlying_pct": None,
            "iv_percentile_13w": None,
            "iv_percentile_26w": None,
            "iv_percentile_52w": None,
            "iv_source": "unavailable",
        }
```

Se `fetch_ibkr_iv_data` retornar `iv_source="unavailable"` para um símbolo,
o candidato ainda é avaliado — só cai automaticamente nos pesos
`WEIGHTS_LEGACY` (mesmo comportamento do T17 hoje) em vez de ser excluído.

---

## Report section format (atualizado)

```markdown
## 7. Candidatos para Opções (30–45 DTE)

*IVP = IV Percentile real (IBKR, janela 52w). IVR (aprox) = proxy via HV, ver T17.*

| # | Símbolo | Estratégia | Strike | Exp | DTE | Delta | IVR (aprox) | IVP (52w) | Quadrante | Prêmio | Ret/Mês | Spread% |
|---|---------|-----------|--------|-----|-----|-------|-------------|-----------|-----------|--------|---------|---------|
| 1 | NVDA | CSP PUT | $180 | 15 Ago | 37d | 0.24 | 68 | 71% | venda_confiante | $2.85 | 1.6%/mês | 4.2% |
| 2 | PEP  | CSP PUT | $135 | 15 Ago | 37d | 0.22 | 55 | 22% | spike_pontual   | $1.20 | 0.9%/mês | 3.1% |
```

---

## Arquivos a criar/modificar

```
src/market_scanner/options_screener.py       ← modificar: novos campos, fetch IBKR, scoring, quadrante
src/market_scanner/daily_report.py           ← modificar: colunas IVP + Quadrante na seção 7
justfile                                     ← modificar: comentário de daily-options exigindo Gateway
tests/market_scanner/test_options_screener.py ← modificar/estender
```

---

## Tests (mínimo 6 novos, além dos existentes do T17 que devem continuar passando)

```python
def test_classify_quadrant_venda_confiante()
# ivr=70, ivp=80 → "venda_confiante"

def test_classify_quadrant_spike_pontual()
# ivr=75, ivp=20 → "spike_pontual"

def test_classify_quadrant_indefinido_when_ivp_missing()
# ivr=70, ivp=None → "indefinido"

def test_fetch_ibkr_iv_data_handles_invalid_flag(monkeypatch)
# mock resposta com is_valid=False → todos os campos None, iv_source="unavailable"

def test_score_uses_real_weights_when_ivp_available()
# candidato com iv_percentile_52w=80 → usa WEIGHTS_WITH_REAL_IVP (checar via
# comparação com cálculo manual esperado)

def test_score_falls_back_to_legacy_weights_when_ivp_missing()
# candidato com iv_percentile_52w=None → score idêntico ao cálculo do T17 original

def test_screen_completes_without_crash_on_ibkr_error(monkeypatch)
# cliente IBKR levanta exceção para todos os símbolos → candidatos ainda
# gerados via fallback yfinance-only, sem crash
```

---

## Verification

```bash
# 1. Tests (mockados, sem rede real)
uv run pytest tests/market_scanner/test_options_screener.py -v

# 2. Rodar com Gateway ativo
just daily-options
# Esperado: seção 7 do relatório com colunas IVP (52w) e Quadrante preenchidas
# para os símbolos com dado válido; IVR (aprox) preenchido para todos

# 3. Simular Gateway fora do ar (parar IB Gateway) e rodar de novo
just daily-options
# Esperado: relatório ainda gerado, todos os candidatos com iv_source=unavailable,
# score calculado via WEIGHTS_LEGACY, sem crash

# 4. Lint
uv run ruff check src/market_scanner/options_screener.py \
  src/market_scanner/daily_report.py tests/market_scanner/test_options_screener.py
```

---

## Known limitations / follow-up

- **IV Rank real ainda não existe.** `ivr_approx` continua sendo proxy via
  HV. Construir uma série histórica própria de `iv_underlying_pct` (gravada
  diariamente) é o caminho natural para calcular IVR real no futuro — fica
  como task separado depois que este estiver validado em produção por
  algumas semanas.
- **Field codes não confirmados contra a API real do projeto.** Os nomes
  usados neste task vieram de uma ferramenta de mercado usada só para
  validação exploratória — o Claude Code deve confirmar contra o cliente
  IBKR que o `financial` já usa antes de fechar a implementação.
- **Dependência de Gateway ativo** muda o perfil operacional de
  `daily-options` — deixa de ser "roda em qualquer hora" e passa a exigir
  IB Gateway rodando, igual `ibkr-positions`. Vale considerar um aviso no
  início da execução (`daily-options`) se o Gateway não responder, em vez
  de deixar o erro aparecer só nos logs por símbolo.
