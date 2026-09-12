# Task T20: `crypto_irpf` — Apuração IRPF Criptoativos (integrada ao relatório consolidado)

**Status:** Completed
**Skill:** add-feature
**Scope:** `src/crypto_irpf/` (new module), `src/irpf_report/main.py`, `justfile`
**Effort:** M
**Depends on:** T19 (trades_history.csv + earn_history.csv + cost_basis.json existentes)
**Depends on:** T04/T11 (irpf_report já consolidado para IBKR + BTG)

---

## Context

Após T19, temos o histórico completo de operações de cripto em BRL com PTAX
correto. O próximo passo é a apuração tributária.

### Regras IRPF para criptoativos (RFB — Instrução Normativa 1.888/2019)

Diferente de ações (IBKR/BTG), cripto tem regras específicas:

| Item | Regra |
|---|---|
| **Isenção mensal** | Vendas ≤ R$35.000 no mês → ganho isento |
| **Alíquota** | 15% sobre ganho até R$5M; 17,5% até R$10M; 20% até R$30M; 22,5% acima |
| **DARF mensal** | Obrigatório quando há ganho tributável (vendas > R$35k com lucro) |
| **Código DARF** | 4600 (ganho de capital em ativos no exterior/cripto) |
| **Custo médio** | CMM (custo médio ponderado móvel) — exigido pela RFB |
| **Rendimentos EARN** | Renda de aplicação financeira no exterior — alíquota 15–27,5% |
| **Swap cripto→cripto** | Evento tributável: SELL da moeda enviada realiza ganho/perda |

### O que este módulo produz

1. **Apuração mensal de ganho de capital** — mês a mês, para cada alienação
2. **Verificação do limite de isenção** — sinaliza meses isentos vs tributáveis
3. **DARF a recolher** — valor e prazo por mês com ganho tributável
4. **Rendimentos EARN** — total anual, agrupado por tipo
5. **Relatório IRPF** — seção cripto integrada ao `just irpf year=2026`

---

## Goal

Criar `crypto_irpf` que lê `trades_history.csv`, `earn_history.csv` e
`cost_basis.json` (produzidos por T19) e gera:
- Apuração mensal de ganho/perda em BRL para cada alienação
- Verificação do limite de isenção mensal (R$35.000 em vendas)
- DARF mensal quando aplicável
- Relatório de rendimentos EARN para declaração anual
- Seção cripto no relatório IRPF consolidado (`just irpf year=2026`)

---

## Outcome spec

1. `just irpf-crypto year=2026` gera `reports/irpf/irpf_crypto_2026.md`
   com apuração completa do ano.
2. `just irpf year=2026` (T11) passa a incluir a seção cripto no relatório
   consolidado — um único arquivo cobre IBKR + BTG + Binance.
3. Para cada mês com alienações:
   - Total de vendas em BRL
   - Custo total das posições alienadas (CMM × quantidade)
   - Ganho/perda líquido
   - Status: ISENTO (vendas ≤ R$35k) ou TRIBUTÁVEL
   - DARF: valor, código 4600, data de vencimento (último dia útil do mês seguinte)
4. Para rendimentos EARN: total anual em BRL, por tipo (Flexible, Locked, Staking).
5. Se você zerou tudo em 2026 (jan + fev): o relatório mostra os ganhos/perdas
   reais realizados naquelas vendas, usando custo médio calculado das compras de 2025.
6. `uv run pytest tests/crypto_irpf/` passa (≥ 6 testes).

---

## Constraints

- Não recalcular custo médio — ler `cost_basis.json` (produzido por T19).
  Custo médio no momento da venda = `avg_cost_brl_ptax` vigente antes da venda.
- T19 já garante que o custo médio é CMM e usa PTAX BCB. Este módulo apenas
  lê e usa.
- Para apurar ganho em cada SELL: `ganho = (price_ptax - avg_cost) × quantity`
  onde `price_ptax = value_brl_ptax / quantity`.
- DARF vence no **último dia útil do mês seguinte** à alienação. Calcular via
  `calendar` (stdlib) — sem dependência externa de calendário de feriados.
  Usar uma aproximação conservadora: último dia do mês seguinte se for útil,
  senão dia anterior.
- Rendimentos EARN: não são ganho de capital — são rendimentos de aplicação
  financeira no exterior. Alíquota de tabela progressiva (15–27,5%) sobre
  o total recebido no ano. Este módulo informa o valor; o cálculo do imposto
  exato depende da renda total do contribuinte (out of scope).
- Sem modificar a lógica de T11 (`parse_history_csv`) — apenas adicionar
  chamada ao bloco cripto no `main.py` da `irpf_report`.

---

## Algoritmo de apuração mensal

```python
# src/crypto_irpf/apuracao.py

from dataclasses import dataclass
from decimal import Decimal

ISENCAO_MENSAL_BRL = 35_000.0  # RFB: vendas até R$35k/mês → isento

ALIQUOTAS = [
    (5_000_000,  0.15),
    (10_000_000, 0.175),
    (30_000_000, 0.20),
    (float('inf'), 0.225),
]

@dataclass
class ApuracaoMensal:
    ano_mes: str           # "2026-01"
    total_vendas_brl: float
    total_custo_brl: float
    ganho_liquido_brl: float
    isento: bool           # True se total_vendas <= 35k
    darf_valor: float      # 0 se isento ou prejuízo
    darf_codigo: str       # "4600"
    darf_vencimento: str   # "YYYY-MM-DD"
    trades: list[dict]     # detalhes de cada alienação no mês


def apurar_mes(
    sells: list[CryptoTrade],
    cost_basis_snapshot: dict[str, float],  # asset → avg_cost_brl no momento da venda
) -> ApuracaoMensal:
    """
    Para um conjunto de SELLs do mesmo mês, calcula ganho e DARF.
    cost_basis_snapshot deve refletir o custo médio ANTES das vendas do mês.
    """
    total_vendas = sum(t.value_brl_ptax for t in sells)
    total_custo  = sum(
        cost_basis_snapshot.get(t.asset, 0) * t.quantity
        for t in sells
    )
    ganho = total_vendas - total_custo
    isento = total_vendas <= ISENCAO_MENSAL_BRL

    darf_valor = 0.0
    if not isento and ganho > 0:
        darf_valor = _calc_imposto(ganho)

    return ApuracaoMensal(
        ano_mes=sells[0].date[:7],
        total_vendas_brl=total_vendas,
        total_custo_brl=total_custo,
        ganho_liquido_brl=ganho,
        isento=isento,
        darf_valor=darf_valor,
        darf_codigo="4600",
        darf_vencimento=_last_business_day_of_next_month(sells[0].date[:7]),
        trades=[_trade_detail(t, cost_basis_snapshot) for t in sells],
    )


def _calc_imposto(ganho: float) -> float:
    imposto = 0.0
    acumulado = 0.0
    for limite, aliq in ALIQUOTAS:
        faixa = min(ganho - acumulado, limite - acumulado)
        if faixa <= 0:
            break
        imposto += faixa * aliq
        acumulado += faixa
        if acumulado >= ganho:
            break
    return round(imposto, 2)
```

**Atenção para a ordem de processamento:** o custo médio muda conforme as
compras ocorrem. A apuração deve processar os trades em ordem cronológica,
atualizando o custo médio após cada BUY e realizando o ganho com o custo
vigente no momento do SELL.

```python
def apurar_ano(trades: list[CryptoTrade], year: int) -> list[ApuracaoMensal]:
    """
    Processa todos os trades do ano em ordem cronológica.
    Mantém cost_basis running (estado vivo de custo médio).
    Agrupa SELLs por mês e calcula DARF.
    """
    # Inicializar cost_basis com estado ao final do ano anterior
    # (ler cost_basis.json filtrado até 31/12/year-1)
    running_basis: dict[str, RunningBasis] = _init_basis_from_prior_year(trades, year)

    sells_by_month: dict[str, list] = defaultdict(list)

    for trade in sorted(trades, key=lambda t: t.datetime):
        if trade.trade_type in ("BUY", "SWAP_BUY"):
            _update_basis_buy(running_basis, trade)
        elif trade.trade_type in ("SELL", "SWAP_SELL"):
            if trade.date[:4] == str(year):
                # Captura custo médio atual (antes de alterar)
                sells_by_month[trade.date[:7]].append(
                    (trade, running_basis[trade.asset].avg_cost_brl_ptax)
                )

    return [
        apurar_mes_com_custo(mes, sells)
        for mes, sells in sorted(sells_by_month.items())
    ]
```

---

## Relatório formato

```markdown
# IRPF 2027 — Criptoativos Binance (ano-base 2026)

## Resumo do Ano

| Mês | Total Vendas R$ | Custo R$ | Ganho/Perda R$ | Status | DARF |
|-----|----------------|----------|----------------|--------|------|
| Jan/2026 | R$XX.XXX | R$XX.XXX | -R$XX.XXX | ISENTO (< R$35k) | — |
| Fev/2026 | R$XX.XXX | R$XX.XXX | -R$XX.XXX | ISENTO (< R$35k) | — |

**Total alienações 2026:** R$XX.XXX
**Total ganho/perda:** -R$XX.XXX (prejuízo)
**DARF total gerado:** R$0,00

> Todas as vendas foram isentas por total mensal ≤ R$35.000 ou resultaram
> em prejuízo. Não há DARF a recolher.

---

## Detalhamento por Alienação

| Data | Ativo | Qtde | Preço PTAX R$ | Custo Médio R$ | Ganho/Perda R$ |
|------|-------|------|---------------|----------------|----------------|
| 2026-01-22 | ADA | 2429,1 | R$1,944 | R$4,797 | -R$6.929 |
| 2026-01-22 | ENA | 2938,85 | R$0,943 | R$2,772 | -R$5.372 |
...

---

## Rendimentos de Aplicação Financeira (Simple Earn / Staking)

Rendimentos recebidos da Binance em 2025 (base para retenção 2026):

| Tipo | Valor R$ (PTAX) |
|------|----------------|
| Flexible Earn (USDT/BNB/ETH) | R$XX.XXX |
| Total | R$XX.XXX |

*Tributação: tabela progressiva (15%–27,5%) sobre total de rendimentos
no exterior. Declarar na ficha "Rendimentos Recebidos de Fontes no Exterior".*

---

## Bens e Direitos em 31/12/2026

| Criptoativo | Quantidade | Custo de Aquisição R$ |
|-------------|-----------|----------------------|
| (nenhum — carteira zerada em fev/2026) | — | — |

*Declarar na ficha "Bens e Direitos" — Grupo 08 (Criptoativos), pelo custo
de aquisição (não pelo valor de mercado).*

---

*Relatório gerado em 2026-09-12. Consulte um contador para validação.*
```

---

## Integração com `just irpf year=2026` (T11)

Adicionar bloco cripto ao final do relatório consolidado:

```python
# src/irpf_report/main.py — adição ao final do pipeline existente

from pathlib import Path

def _include_crypto_section(year: int) -> str:
    """
    Gera seção cripto para incluir no relatório IRPF consolidado.
    Retorna string vazia se trades_history.csv não existir.
    """
    trades_path = Path("data/crypto/trades_history.csv")
    earn_path   = Path("data/crypto/earn_history.csv")
    if not trades_path.exists():
        return "\n\n---\n*Seção Cripto: sem dados (rode just crypto-import)*\n"
    from crypto_irpf.apuracao import apurar_ano, format_section
    from crypto_irpf.earn import summarize_earn
    # import lazy para não quebrar se crypto_irpf não instalado
    trades = load_crypto_trades(trades_path, year)
    earn   = load_earn_records(earn_path, year)
    apuracao = apurar_ano(trades, year)
    return format_section(apuracao, summarize_earn(earn), year)
```

---

## Justfile additions

```just
# Apuração IRPF de criptoativos para um ano
irpf-crypto year="2026":
    PYTHONPATH=src uv run python -m crypto_irpf.main \
        --trades   data/crypto/trades_history.csv \
        --earn     data/crypto/earn_history.csv \
        --year     {{year}} \
        --output   reports/irpf/irpf_crypto_{{year}}.md
    @echo "✓ Relatório: reports/irpf/irpf_crypto_{{year}}.md"
```

O `just irpf year=2026` existente (T11) inclui automaticamente a seção cripto
se `data/crypto/trades_history.csv` existir — sem flag adicional.

---

## Files to create/modify

```
src/crypto_irpf/__init__.py
src/crypto_irpf/apuracao.py       ← apuração mensal, CMM, DARF
src/crypto_irpf/earn.py           ← sumário de rendimentos EARN
src/crypto_irpf/report.py         ← renderização markdown
src/crypto_irpf/main.py           ← CLI
src/irpf_report/main.py           ← adicionar _include_crypto_section()
tests/crypto_irpf/test_apuracao.py
tests/crypto_irpf/test_earn.py
justfile                          ← adicionar irpf-crypto recipe
```

---

## Testes (mínimo 6)

```python
def test_venda_isenta_abaixo_35k()
# SELLs totalizando R$30.000 no mês → isento=True, darf_valor=0

def test_venda_tributavel_acima_35k()
# SELLs totalizando R$50.000, custo R$30.000 → ganho R$20.000
# darf_valor = R$20.000 × 15% = R$3.000

def test_prejuizo_nao_gera_darf()
# SELLs totalizando R$40.000, custo R$50.000 → ganho -R$10.000 → darf=0

def test_custo_medio_aplicado_corretamente()
# BUY 2 ADA a R$5, BUY 2 ADA a R$7 → avg=R$6. SELL 2 ADA → custo=R$12

def test_earn_summarized_by_type()
# 10 Flexible EARN rows R$100 cada → total_flexible=R$1.000

def test_carteira_zerada_em_bens_e_direitos()
# Após todos os SELLs: cost_basis.json com qty=0 → seção "Bens e Direitos" vazia

def test_darf_vencimento_ultimo_dia_util_mes_seguinte()
# Venda em janeiro → vencimento = último dia útil de fevereiro
```

---

## Verificação

```bash
# 1. Testes
uv run pytest tests/crypto_irpf/ -v

# 2. Pré-requisito: T19 executado
just crypto-import file=data/crypto/uploads/binance_2025.csv
just crypto-import file=data/crypto/uploads/binance_2026.csv

# 3. Relatório cripto isolado
just irpf-crypto year=2026
cat reports/irpf/irpf_crypto_2026.md

# Verificar:
# - Jan e Fev 2026 listados com valores que batem com seu arquivo manual
# - ADA: -R$6.929, ENA: -R$5.372, etc.
# - Status ISENTO para ambos os meses (vendas < R$35k por mês)
# - Seção "Bens e Direitos" vazia (carteira zerada)

# 4. Relatório consolidado (IBKR + BTG + Binance)
just irpf year=2026
# Verificar que seção cripto aparece ao final do relatório

# 5. Lint
uv run ruff check src/crypto_irpf/ tests/crypto_irpf/
```

---

## Verificação cruzada com arquivo manual

Seus dados de referência (arquivo original 2026):

| Ativo | Qtde | Resultado R$ |
|-------|------|-------------|
| ADA   | 2429,1 | -R$6.929,63 |
| ENA   | 2938,85 | -R$5.372,50 |
| UNI   | 4,981 | -R$404,70 |
| ETH   | 1,0907 | -R$11.837,33 |
| SOL   | 7,618 | -R$4.861,03 |
| LINK  | 67,2 | -R$4.971,41 |
| AAVE  | 5,181 | -R$4.737,36 |
| BTC   | 0,00276 | -R$39,69 |

**Total prejuízo 2026: -R$39.153,65**

O relatório gerado deve bater com esses números (pequenas diferenças possíveis
por PTAX BCB vs câmbio Binance — o correto para IRPF é o PTAX BCB).

---

## Known limitations / follow-up

- **Compensação de prejuízos entre meses:** a RFB permite compensar prejuízo
  de um mês com ganho de outro, dentro do mesmo ano e mesma categoria. Este
  módulo calcula mês a mês; a compensação intermensal é informada no relatório
  mas não automatizada (requer o saldo de prejuízos a compensar de anos anteriores).
- **Rendimentos EARN e alíquota:** a alíquota correta depende da renda total
  do contribuinte (tabela progressiva). Este módulo informa o valor bruto;
  o cálculo final do imposto sobre EARN deve ser feito no Programa IRPF.
- **Swap cripto→cripto em 2025:** se houver swaps no histórico de 2025, eles
  são eventos tributáveis mesmo que as moedas não tenham saído para BRL/USDT.
  O módulo os trata como SELL + BUY conforme orientação RFB. Verificar se há
  swaps no histórico importado.
- **Staking rewards como custo zero:** rendimentos EARN são recebidos com
  custo de aquisição = 0 para fins de ganho de capital futuro. Ao vender
  ativos recebidos como EARN, o custo de aquisição no CMM deve incluir esses
  recebimentos com custo zero. T19 já trata isso ao atualizar o CMM com
  `value_brl_ptax = 0` para os EARN BUYs implícitos.
- **Consulte um contador:** as regras de tributação de criptoativos no Brasil
  ainda têm pontos de interpretação (especialmente sobre stablecoins, DeFi
  e earn programs). Este relatório é um auxiliar para a declaração — a
  responsabilidade pela declaração correta é do contribuinte.
