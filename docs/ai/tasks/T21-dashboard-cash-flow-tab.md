# Task T21: Dashboard — Fluxo de Caixa (aportes/retiradas via ibkr_cash)

**Status:** Planned
**Skill:** add-feature
**Scope:** `src/web/readers/cash_flow_reader.py` (new), `src/web/routers/cash_flow.py` (new),
`frontend/src/components/CashFlowPanel.jsx` (new), `frontend/src/components/HistoryChart.jsx` (modificar)
**Effort:** M
**Depends on:** T20 (ibkr_cash — `data/ibkr/cash_transactions.csv` e `data/ibkr/nav_changes.csv` já sendo gerados), T12 (dashboard rodando)

---

## Contexto

T20 implementou `ibkr_cash`, que roda via `just ibkr-flex-sync` e popula:

```
data/ibkr/cash_transactions.csv   ← deposit/withdrawal, interest, fees, dividends
data/ibkr/nav_changes.csv          ← starting_value, ending_value, deposits_withdrawals, net_trades por período
```

Isso substitui a estimativa manual de aportes (inferida a partir de saltos no NAV
diário) por dado exato vindo direto da IBKR. O dashboard hoje não sabe que esses
arquivos existem — a aba History (T12) mostra só a curva de NLV, sem separar
"quanto é aporte" de "quanto é retorno real".

Este task fecha esse gap: mostra os aportes/retiradas como eventos, e sobrepõe uma
curva de "capital aportado acumulado" na curva de NLV, deixando visualmente óbvio
quanto do crescimento do patrimônio veio de dinheiro novo vs. performance.

---

## Goal

Uma seção "Fluxo de Caixa" — dentro da aba History existente, não uma aba nova —
mostrando:
1. Tabela de transações (aportes, saques, juros, taxas) com filtro de período.
2. Um resumo: total aportado, total retirado, líquido, no período selecionado.
3. Uma segunda linha no gráfico de NLV (History tab) com o "capital aportado
   acumulado", pra comparar visualmente NLV vs. dinheiro que entrou.
4. Reconciliação: para cada linha de `nav_changes.csv`, expor se
   `starting_value + deposits_withdrawals + net_trades == ending_value` bate
   (dentro de tolerância) — se não bater, mostrar um aviso discreto, não um erro.

---

## Outcome spec

Quando pronto, tudo isso deve ser verdade:

1. A aba **History** existente ganha uma subseção "Fluxo de Caixa" abaixo do
   gráfico de NLV (não é uma aba nova no menu principal).
2. O gráfico de NLV (`HistoryChart.jsx`) ganha uma segunda série (linha
   tracejada) com o capital aportado acumulado, na mesma escala do eixo Y.
3. Tabela de transações: Data | Tipo | Valor | Moeda | Descrição, ordenada por
   data decrescente, com filtro de período (30d / 90d / 6m / 1y / Tudo —
   mesmo padrão de filtro client-side já usado em `TradesTable.jsx`).
4. Cards de resumo acima da tabela: Total Aportado, Total Retirado, Líquido,
   no período filtrado.
5. Se `data/ibkr/cash_transactions.csv` ou `data/ibkr/nav_changes.csv` não
   existirem, a seção mostra `"Sem dados ainda — rode: just ibkr-flex-sync"`
   em vez de quebrar (mesmo padrão do EmptyState do T12).
6. `GET /api/cash-flow` retorna transações + reconciliação num único payload.
7. Reconciliação exposta no payload; discrepância acima de tolerância gera um
   badge de aviso no frontend, não um erro bloqueante.
8. `uv run pytest tests/web/test_cash_flow_reader.py` passa (≥ 5 testes).
9. Nenhum arquivo do `ibkr_cash` é modificado — este task só lê os CSVs que
   T20 já produz.

---

## Constraints

- **Read-only.** Sem escrita, sem chamada de rede, sem subprocess. Se o dado
  estiver desatualizado, o botão "▶ Atualizar IBKR" / equivalente de cash já
  cabe no escopo do T16 (action buttons) — não duplicar isso aqui.
- Segue o padrão de reader puro (sem dependência de FastAPI) + router fino,
  igual `trades_reader.py` / `patrimonio_reader.py` / `cash_reader.py`.
- **Não confundir com `cash_reader.py` do T19** — aquele lê
  `config/cash_accounts.yaml` (saldos manuais BRL: Neon, BTG pós-fixado,
  reserva). Este task lê `data/ibkr/cash_transactions.csv` (histórico de
  movimentações USD vindas da IBKR via Flex Query). São conceitos
  diferentes — nomear o novo módulo `cash_flow_reader.py` (não
  `cash_reader.py`) para evitar colisão de nome e de conceito.
- Filtro client-side apenas (mesmo padrão do T13) — `/api/cash-flow` retorna
  tudo, o frontend filtra.
- Sem conversão de moeda — os valores da IBKR já vêm em USD; mostrar a moeda
  por linha (a maioria será USD, mas não assumir isso no código).
- Tolerância de reconciliação: usar `abs(diff) > 1.0` (USD) como limiar de
  aviso — pequenas diferenças de arredondamento/timing são esperadas e não
  devem gerar ruído visual.

---

## Canonical shape da API

```python
@dataclass
class CashTransactionRow:
    date: str            # YYYY-MM-DD
    type: str             # "Deposits/Withdrawals" | "Broker Interest Paid" | etc.
    amount: float
    currency: str
    description: str

@dataclass
class NavReconciliation:
    from_date: str
    to_date: str
    starting_value: float
    ending_value: float
    deposits_withdrawals: float
    net_trades: float
    reconciles: bool      # abs(starting + deposits_withdrawals + net_trades - ending) <= 1.0
    diff: float
```

`GET /api/cash-flow` response:

```json
{
  "transactions": [ /* CashTransactionRow[] */ ],
  "reconciliation": [ /* NavReconciliation[] */ ],
  "cumulative_contributed": [
    { "date": "2025-11-18", "contributed": 24997.92 },
    { "date": "2025-11-19", "contributed": 31283.17 }
  ],
  "source": {
    "cash_transactions": "data/ibkr/cash_transactions.csv",
    "nav_changes": "data/ibkr/nav_changes.csv",
    "last_updated": "2026-08-15T10:03:00"
  }
}
```

`cumulative_contributed` é a série usada para a segunda linha do gráfico:
soma corrida de `amount` para transações do tipo `"Deposits/Withdrawals"`
(saques entram como valor negativo, então a soma corrida já reflete líquido).

---

## Key design

### Reader: `src/web/readers/cash_flow_reader.py`

```python
from pathlib import Path
from dataclasses import dataclass
import pandas as pd

CASH_TRANSACTIONS = Path("data/ibkr/cash_transactions.csv")
NAV_CHANGES = Path("data/ibkr/nav_changes.csv")
RECONCILIATION_TOLERANCE_USD = 1.0


def read_cash_transactions() -> list[dict]:
    """Lê data/ibkr/cash_transactions.csv. Retorna [] se o arquivo não existir."""
    if not CASH_TRANSACTIONS.exists():
        return []
    df = pd.read_csv(CASH_TRANSACTIONS)
    df = df.sort_values("date", ascending=False)
    return df.to_dict(orient="records")


def read_nav_reconciliation() -> list[dict]:
    """Lê data/ibkr/nav_changes.csv e calcula reconciliação por período."""
    if not NAV_CHANGES.exists():
        return []
    df = pd.read_csv(NAV_CHANGES)
    rows = []
    for _, r in df.iterrows():
        expected = r["starting_value"] + r["deposits_withdrawals"] + r["net_trades"]
        diff = expected - r["ending_value"]
        rows.append({
            **r.to_dict(),
            "reconciles": abs(diff) <= RECONCILIATION_TOLERANCE_USD,
            "diff": round(diff, 2),
        })
    return rows


def read_cumulative_contributed() -> list[dict]:
    """
    Soma corrida (por data) dos valores tipo 'Deposits/Withdrawals'.
    Usada para a linha de capital aportado sobreposta ao gráfico de NLV.
    """
    if not CASH_TRANSACTIONS.exists():
        return []
    df = pd.read_csv(CASH_TRANSACTIONS)
    deposits = df[df["type"] == "Deposits/Withdrawals"].copy()
    deposits = deposits.sort_values("date")
    deposits["contributed"] = deposits["amount"].cumsum()
    return deposits[["date", "contributed"]].to_dict(orient="records")
```

Confirmar as colunas exatas de `cash_transactions.csv` / `nav_changes.csv`
lendo os arquivos reais gerados por `just ibkr-flex-sync` antes de fechar o
parsing — os nomes acima seguem o `dataclass` definido em T20, mas o CSV
pode ter serializado com nomes ligeiramente diferentes (checar o `to_csv` /
schema real usado em `ibkr_cash`).

### Router: `src/web/routers/cash_flow.py`

```python
from fastapi import APIRouter
from web.readers.cash_flow_reader import (
    read_cash_transactions, read_nav_reconciliation, read_cumulative_contributed,
    CASH_TRANSACTIONS, NAV_CHANGES,
)

router = APIRouter(prefix="/api")

@router.get("/cash-flow")
def get_cash_flow():
    return {
        "transactions": read_cash_transactions(),
        "reconciliation": read_nav_reconciliation(),
        "cumulative_contributed": read_cumulative_contributed(),
        "source": {
            "cash_transactions": str(CASH_TRANSACTIONS) if CASH_TRANSACTIONS.exists() else None,
            "nav_changes": str(NAV_CHANGES) if NAV_CHANGES.exists() else None,
        },
    }
```

Registrar em `src/web/server.py`:
```python
from web.routers import cash_flow
app.include_router(cash_flow.router)
```

### Frontend: `HistoryChart.jsx` (modificar)

Adicionar a segunda série ao `LineChart` do Recharts já existente:

```jsx
<Line type="monotone" dataKey="nlv" stroke="var(--color-primary)" name="NLV" />
<Line
  type="stepAfter"
  dataKey="contributed"
  stroke="var(--color-muted)"
  strokeDasharray="4 4"
  name="Capital aportado"
  dot={false}
/>
```

Os dois datasets (`/api/history` e `/api/cash-flow`) têm eixos de data
diferentes — fazer o merge por data no frontend (join simples por string
`YYYY-MM-DD`) antes de passar pro `LineChart`, preenchendo `contributed` com
o último valor conhecido nos dias sem aporte (forward-fill).

### Frontend: `CashFlowPanel.jsx` (novo)

```jsx
// Renderizado abaixo do HistoryChart na aba History
// Reusa o padrão de filtro de período do TradesTable.jsx

function CashFlowPanel() {
  const { data, loading } = useApi("/api/cash-flow");
  const [period, setPeriod] = useState(90);

  if (loading) return <Spinner />;
  if (!data?.source?.cash_transactions) {
    return <EmptyState command="ibkr-flex-sync" />;
  }

  const filtered = filterByPeriod(data.transactions, period);
  const totals = summarize(filtered); // { deposited, withdrawn, net }

  return (
    <section>
      <h3>Fluxo de Caixa</h3>
      <PeriodFilter value={period} onChange={setPeriod} />
      <SummaryCards deposited={totals.deposited} withdrawn={totals.withdrawn} net={totals.net} />
      {data.reconciliation.some(r => !r.reconciles) && (
        <ReconciliationWarning rows={data.reconciliation.filter(r => !r.reconciles)} />
      )}
      <TransactionsTable rows={filtered} />
    </section>
  );
}
```

---

## Arquivos a criar/modificar

```
src/web/readers/cash_flow_reader.py         ← NOVO
src/web/routers/cash_flow.py                ← NOVO
src/web/server.py                           ← registrar cash_flow router
frontend/src/components/CashFlowPanel.jsx   ← NOVO
frontend/src/components/HistoryChart.jsx    ← modificar (segunda série)
frontend/src/App.jsx                        ← montar CashFlowPanel na aba History
tests/web/test_cash_flow_reader.py          ← NOVO
```

---

## Tests (mínimo 5)

```python
def test_read_cash_transactions_returns_empty_when_file_missing(monkeypatch)
# CSV ausente → [] retornado, sem crash

def test_read_cash_transactions_sorted_descending(tmp_path, monkeypatch)
# CSV com datas fora de ordem → retornado ordenado desc

def test_reconciliation_flags_mismatch_beyond_tolerance(tmp_path, monkeypatch)
# starting + deposits + net_trades difere de ending por > 1.0 → reconciles=False

def test_reconciliation_passes_within_tolerance(tmp_path, monkeypatch)
# diferença de arredondamento (< 1.0) → reconciles=True

def test_cumulative_contributed_is_running_sum(tmp_path, monkeypatch)
# 3 depósitos em sequência → contributed é soma corrida, não soma total repetida

def test_cash_flow_endpoint_returns_hint_when_no_data(client)
# GET /api/cash-flow sem CSVs → source com valores None, sem erro 500
```

---

## Verification

```bash
# 1. Gerar os dados de origem primeiro (se ainda não rodou)
just ibkr-flex-sync

# 2. Tests
uv run pytest tests/web/test_cash_flow_reader.py -v

# 3. Dashboard
just web
# Abrir http://localhost:8000 → aba History
# Esperado: gráfico de NLV com a linha tracejada de capital aportado,
# seção "Fluxo de Caixa" abaixo com cards de resumo + tabela

# 4. Testar sem dados (renomear os CSVs temporariamente)
# Esperado: seção mostra "Sem dados ainda — rode: just ibkr-flex-sync"

# 5. Lint
uv run ruff check src/web/readers/cash_flow_reader.py \
  src/web/routers/cash_flow.py tests/web/test_cash_flow_reader.py
```

---

## Known limitations / follow-up

- **Sem MWR/XIRR calculado.** Este task só expõe os dados brutos e a
  reconciliação; um cálculo de retorno money-weighted a partir de
  `cash_transactions.csv` fica como task futuro (`irpf_report` ou um novo
  módulo `performance_report` seriam os candidatos naturais).
- **`cumulative_contributed` não distingue moeda.** Se algum dia a conta
  tiver cash transactions em outra moeda além de USD, a soma corrida vai
  misturar — hoje isso não acontece na conta IBKR do usuário, mas vale um
  guard explícito (`assert currency == "USD"` com mensagem clara) em vez de
  somar silenciosamente errado.
- **Sem botão de refresh na UI.** Rodar `just ibkr-flex-sync` continua sendo
  manual/terminal até o T16 (action buttons) cobrir isso — não duplicar
  esse trabalho aqui.
