# Bugfix: `tracker_builder.py` — FSLY não removida após fechamento + linhas duplicadas no tracker

## Contexto

Hoje é 2026-07-09. A posição FSLY (PUT $15 jul/17) foi encerrada há alguns dias.
Após rodar `just ibkr-positions` e `just ibkr-trades-daily`, `options_tracker.csv`
ainda mostra FSLY como posição aberta. Adicionalmente, AAPL aparece em duas linhas
com schemas diferentes — uma com campos `nan`, outra preenchida corretamente.

Este é um bug de implementação no `tracker_builder.py` — a spec do T09 está correta.

---

## Leia antes de qualquer coisa

1. `docs/architecture/ibkr-trades.md`
2. `docs/ai/tasks/T09-ibkr-trade-history-auto-tracker.md` — seção "tracker_builder"
3. `src/ibkr_trades/tracker_builder.py`
4. `src/ibkr_trades/store.py`
5. `options_tracker.csv` — estado atual com o bug
6. `data/ibkr/trades_history.csv` — fonte de verdade (confira as linhas de FSLY)

---

## Sintomas observados

**`options_tracker.csv` atual (estado com bug):**

```
# AAPL aparece DUAS vezes — schemas diferentes
nan;IBKR;nan;AAPL;AAPL;C;V;2026-07-17;325.00;nan;1;...       ← sem entry_date, sem trade_id
2026-07-06;IBKR;USD;AAPL;AAPL;CALL;V;2026-07-17;325.00;150.00;1;...  ← correto

# FSLY ainda aparece — deveria ter sido removida
nan;IBKR;nan;FSLY;FSLY;P;C;2026-07-17;15.00;nan;5;...        ← open_close=C mas está no tracker
```

**Daily report (2026-07-09):** confirma FSLY como posição aberta com `DTE=8`, `exit_status=WATCH ~`.

---

## Diagnóstico esperado

Antes de corrigir qualquer coisa, inspecione `data/ibkr/trades_history.csv`
e responda:

1. Quantas linhas existem para FSLY? Quais são os valores de `open_close`,
   `quantity` e `trade_id` de cada uma?

2. Para AAPL, quantas linhas existem? Há linhas com `trade_id` vazio/nan?
   Se sim, qual é a `source` dessas linhas (`flex` ou `api`)?

3. O net quantity calculado pelo `tracker_builder` para FSLY está correto
   (deveria ser 0)? Adicione um print de debug temporário e rode
   `just ibkr-generate-tracker` para ver o que está sendo calculado.

---

## Bugs prováveis a investigar

### Bug A — Sinal invertido no net quantity (causa do FSLY)

A spec do T09 define:

```python
opts["signed_qty"] = opts.apply(
    lambda r: r["quantity"] if "O" in str(r["open_close"])
              else -r["quantity"],
    axis=1,
)
net = opts.groupby(match_key)["signed_qty"].sum()
open_legs = net[net["signed_qty"].abs() > 0.001]
```

**Possíveis implementações erradas:**

```python
# ❌ Errado: soma quantity diretamente sem inverter sinal de fechamento
net = opts.groupby(match_key)["quantity"].sum()

# ❌ Errado: condição invertida — inverte sinal dos opens em vez dos closes
lambda r: -r["quantity"] if "O" in str(r["open_close"]) else r["quantity"]

# ❌ Errado: match_key não inclui expiration — contratos de expirations
# diferentes do mesmo underlying colapsam em um único grupo
match_key = ["underlying", "option_type", "strike"]  # sem "expiration"
```

Verifique qual das três (ou outra variação) está na implementação atual.

### Bug B — Duas fontes alimentando o tracker (causa das linhas duplicadas de AAPL)

O `tracker_builder.py` deve ser a **única** fonte do `options_tracker.csv`.
Ele deve sobrescrever o arquivo completamente a cada execução.

Possíveis causas das linhas duplicadas:
- O arquivo não está sendo sobrescrito — está sendo feito append.
- Uma segunda lógica em `ibkr_positions` ou `options_export.py` (T01) também
  escreve no `options_tracker.csv` sem limpar o conteúdo anterior.
- O arquivo antigo (manual backup) está sendo mergeado com o novo output.

Verifique se `tracker_builder.py` abre o arquivo com `mode='w'` (sobrescreve)
ou `mode='a'` (append). Também verifique se algum outro módulo escreve nesse arquivo.

### Bug C — Linhas com `trade_id = nan` no histórico

As linhas `nan;IBKR;nan;...` no tracker sugerem que existem entradas em
`trades_history.csv` com `trade_id` vazio. Isso pode ocorrer quando:
- O `api_fetcher.py` retorna execuções sem `execId` (IBKR às vezes omite esse
  campo para execuções muito antigas).
- O `flex_parser.py` não mapeia corretamente o campo `TradeID` do XML.

Linhas com `trade_id` vazio não são deduplicadas corretamente e podem causar
duplicação no histórico e, consequentemente, no tracker.

---

## Correções esperadas

### Fix 1 — `tracker_builder.py`: net quantity com sinal correto

```python
# src/ibkr_trades/tracker_builder.py

match_key = ["underlying", "option_type", "strike", "expiration"]  # todos os 4 campos

def _compute_net_quantity(df: pd.DataFrame) -> pd.DataFrame:
    """
    Computes net open quantity per contract.
    Opening legs (open_close contains 'O') contribute their quantity as-is.
    Closing legs (open_close contains 'C' but NOT 'O') invert the sign.

    IBKR convention for short options:
    - Open short: quantity = -N (sell to open)
    - Close short: quantity = +N (buy to close)
    Net for closed position: -N + N = 0  ✓
    """
    opts = df[df["asset_type"] == "OPT"].copy()

    def signed(row):
        oc = str(row["open_close"])
        if "O" in oc and "C" not in oc:
            return row["quantity"]          # pure open: use as-is
        elif "C" in oc and "O" not in oc:
            return row["quantity"]          # pure close: also use as-is
            # NOTE: for short options, close is a BUY (+N), open is SELL (-N)
            # So summing quantity directly IS correct — no sign inversion needed
            # as long as quantity signs are correct in trades_history.csv
        else:  # "O;C" — same-trade open+close: net 0 contribution
            return 0.0

    opts["signed_qty"] = opts.apply(signed, axis=1)
    net = opts.groupby(match_key, as_index=False)["signed_qty"].sum()
    return net[net["signed_qty"].abs() > 0.001]
```

**Atenção**: o sinal de `quantity` em `trades_history.csv` deve ser verificado.
O IBKR usa:
- Sell to open (short option): `quantity < 0`
- Buy to close (short option): `quantity > 0`

Se isso estiver correto, a soma direta sem inversão de sinal resulta no net
correto: `-5 (open) + 5 (close) = 0`. Confirme com os dados reais de FSLY.

### Fix 2 — `tracker_builder.py`: sobrescrever, não fazer append

```python
# Correto: sempre sobrescreve
output.to_csv(tracker_path, index=False, sep=';', mode='w')

# Errado: faz append
output.to_csv(tracker_path, index=False, sep=';', mode='a')
```

O arquivo deve ser completamente regenerado a cada `just ibkr-generate-tracker`.
Antes de escrever, não leia o conteúdo existente — ignore-o completamente.

### Fix 3 — Deduplicar `trades_history.csv` por `trade_id` (se existirem nan)

Se existirem linhas com `trade_id` vazio/nan em `trades_history.csv`:

```python
# src/ibkr_trades/store.py — em append_trades()
# Após carregar o existing DataFrame:
existing = existing.dropna(subset=["trade_id"])           # remove linhas sem trade_id
existing = existing[existing["trade_id"].str.strip() != ""]  # remove strings vazias
```

E no `tracker_builder`, filtrar linhas com `trade_id` inválido antes de processar:

```python
df = pd.read_csv(history_path, dtype={"trade_id": str})
df = df[df["trade_id"].notna() & (df["trade_id"].str.strip() != "") & (df["trade_id"] != "nan")]
```

---

## Como verificar a correção

```bash
# 1. Confirmar estado atual do histórico para FSLY
python3 -c "
import pandas as pd
df = pd.read_csv('data/ibkr/trades_history.csv', dtype={'trade_id': str})
fsly = df[df['underlying'] == 'FSLY']
print(fsly[['date','underlying','option_type','strike','expiration','quantity','open_close','trade_id']].to_string())
print('Net quantity FSLY:', fsly['quantity'].sum())
"

# 2. Após aplicar correções, regerar o tracker
just ibkr-generate-tracker

# 3. Verificar resultado
cat options_tracker.csv

# Esperado:
# - FSLY NÃO aparece (net qty = 0)
# - AAPL aparece UMA vez com todos os campos preenchidos
# - NVDA, PEP aparecem corretamente
# - Nenhuma linha com campos nan onde não deveria haver

# 4. Verificar no daily report
just daily
# Seção "Posições Abertas" não deve mais listar FSLY

# 5. Rodar testes
uv run pytest tests/ibkr_trades/ -v

# 6. Teste específico de regressão (adicionar se não existir)
# Confirmar que posição completamente fechada não aparece no tracker
```

---

## Teste de regressão a adicionar

```python
# tests/ibkr_trades/test_tracker_builder.py

def test_closed_position_not_in_tracker(tmp_path):
    """
    FSLY short put: open -5 + close +5 → net 0 → NOT in tracker.
    """
    history = pd.DataFrame([
        {
            "trade_id": "A001", "date": "2026-06-20", "datetime": "2026-06-20T10:00:00",
            "symbol": "FSLY  260717P00015000", "underlying": "FSLY",
            "asset_type": "OPT", "option_type": "PUT",
            "strike": 15.0, "expiration": "2026-07-17",
            "quantity": -5.0,   # sell to open
            "open_close": "O", "source": "flex",
            "price": 0.70, "proceeds": 350.0, "commission": -1.0,
            "pnl_realized": None, "currency": "USD",
            "roll_id": None, "strategy": "csp",
        },
        {
            "trade_id": "A002", "date": "2026-07-05", "datetime": "2026-07-05T11:00:00",
            "symbol": "FSLY  260717P00015000", "underlying": "FSLY",
            "asset_type": "OPT", "option_type": "PUT",
            "strike": 15.0, "expiration": "2026-07-17",
            "quantity": 5.0,    # buy to close
            "open_close": "C", "source": "flex",
            "price": 0.05, "proceeds": -25.0, "commission": -1.0,
            "pnl_realized": 325.0, "currency": "USD",
            "roll_id": None, "strategy": None,
        },
    ])
    history_path  = tmp_path / "trades_history.csv"
    tracker_path  = tmp_path / "options_tracker.csv"
    history.to_csv(history_path, index=False)

    from ibkr_trades.tracker_builder import build_options_tracker
    count = build_options_tracker(history_path, tracker_path)

    assert count == 0, "Closed FSLY position must not appear in tracker"
    result = pd.read_csv(tracker_path, sep=';')
    assert len(result) == 0 or "FSLY" not in result["underlying"].values
```

---

## Entregável esperado

1. `src/ibkr_trades/tracker_builder.py` corrigido
2. `src/ibkr_trades/store.py` com deduplicação de `trade_id` nan (se necessário)
3. Teste de regressão adicionado em `tests/ibkr_trades/test_tracker_builder.py`
4. `options_tracker.csv` regenerado sem FSLY e sem duplicatas de AAPL
5. `just daily` mostrando apenas 4 posições abertas (AAPL CC, NVDA PUT, PEP PUT + qualquer nova)
