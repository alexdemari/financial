# Task T19: `crypto_trades` — Histórico Canônico de Operações Binance + Sync Incremental

**Status:** Planned
**Skill:** add-feature
**Scope:** `src/crypto_trades/` (new module), `justfile`
**Effort:** M
**Depends on:** T18 (crypto_tracker já existente com BinanceReadOnlyClient)

---

## Context

T18 implementou `crypto_tracker` com snapshot de saldos (Spot + Simple Earn)
para o patrimônio consolidado. Mas não existe registro histórico de operações —
apenas o saldo atual.

Para IRPF e controle patrimonial, precisamos de:
1. **Histórico completo de trades** (compras, vendas, conversões) desde o início
2. **Rendimentos do Simple Earn** (staking, flexible savings) — tratados como
   rendimento de aplicação financeira no exterior, não ganho de capital
3. **Custo médio ponderado por ativo** em BRL — obrigatório para apuração de ganho

O export manual da Binance (Transaction History → CSV) já entrega os campos
necessários incluindo `sent_value_BRL` e `received_value_BRL`. O PTAX oficial
do BCB é buscado para cada data para gerar o campo canônico `ptax_bcb` —
necessário para a declaração IRPF (a Binance usa câmbio próprio, não o PTAX).

### Formato do export Binance (confirmado na análise do arquivo real)

```
id, datetime_tz_GMT-03:00, type, label, market_model_type, order_type,
sent_amount, sent_currency, sent_value_BRL, sent_address,
received_amount, received_currency, received_value_BRL, received_address,
fee_amount, fee_currency, fee_value_BRL
```

**Tipos relevantes:**
- `Trade` (SPOT LIMIT/MARKET) — compras e vendas principais
- `Buy` / `Sell` (CONVERT) — conversões rápidas
- `Receive` com `market_model_type=EARN` — rendimentos Simple Earn/Staking
- `Deposit` (FIAT) — aportes em BRL — registrar, não tributar como ganho
- `Send` / `Receive` (CRYPTO_DEPOSIT) — transferências externas — registrar

**Lógica de classificação de direção:**
- `sent_currency = USDT` (ou BRL) → **BUY** (comprou cripto com USDT/BRL)
- `received_currency = USDT` (ou BRL) e `sent_currency = <cripto>` → **SELL**
- `sent_currency = <cripto A>` e `received_currency = <cripto B>` → **SWAP**
  (tratado como SELL de A + BUY de B para fins de custo médio)

---

## Goal

Criar `crypto_trades` que:
1. Parseia o export CSV da Binance e popula `data/crypto/trades_history.csv`
2. Enriquece cada operação com PTAX do BCB (reusa `irpf_report.ptax`)
3. Calcula custo médio ponderado em BRL por ativo após cada ingestão
4. Faz sync incremental via API Binance para novos trades desde o último ID
5. Classifica rendimentos EARN separadamente de trades para IRPF correto

---

## Outcome spec

1. `just crypto-import file=data/crypto/uploads/binance_2025.csv` parseia o
   export e popula `data/crypto/trades_history.csv`. Idempotente por `trade_id`.
2. `just crypto-sync` busca trades novos via API Binance desde o último
   `trade_id` por par, para os pares em `config/crypto_pairs.yaml`.
3. `just crypto-cost-basis` recalcula custo médio ponderado BRL por ativo
   e salva em `data/crypto/cost_basis.json`.
4. `just crypto-import` executa automaticamente `crypto-cost-basis` ao final.
5. `data/crypto/trades_history.csv` contém **apenas operações de trading**
   (Trade, Buy, Sell, Swap). Rendimentos EARN vão para arquivo separado.
6. `data/crypto/earn_history.csv` contém todos os `Receive/EARN` com valor
   em BRL e PTAX — insumo direto para a seção de rendimentos no IRPF.
7. `uv run pytest tests/crypto_trades/` passa (≥ 8 testes).
8. `data/crypto/` está no `.gitignore`.

---

## Constraints

- Reutilizar `irpf_report.ptax.get_ptax()` para busca de PTAX — não reimplementar.
- Reutilizar `crypto_tracker.binance_client.BinanceReadOnlyClient` para sync API.
- Sem novas dependências além das já existentes.
- PTAX é buscada e cacheada automaticamente (cache em `data/ibkr/ptax_cache/`
  já existente de T04). Não criar segundo cache — reutilizar o mesmo diretório.
- Linhas com `fee_currency = BNB`: converter `fee_value_BRL` usando o campo
  já presente no export (não buscar preço BNB separado).
- Swap (cripto→cripto): registrar como duas linhas — SELL da moeda enviada
  e BUY da moeda recebida — usando o mesmo `trade_id` com sufixo `_A` e `_B`.
- `sent_value_BRL` e `received_value_BRL` do export Binance são usados como
  referência de `value_brl_binance`. O campo `value_brl_ptax` é calculado
  separadamente: `amount_usdt × ptax_bcb`. Ambos são armazenados — o IRPF
  usa `value_brl_ptax`.

---

## Schema canônico — `data/crypto/trades_history.csv`

```
trade_id         str   id do export ou execId da API (dedup key)
date             str   YYYY-MM-DD (GMT-3)
datetime         str   ISO datetime (GMT-3)
trade_type       str   BUY | SELL | SWAP_SELL | SWAP_BUY | DEPOSIT_FIAT | SEND | RECEIVE_EXTERNAL
asset            str   e.g. BTC, ETH, ADA (o ativo cripto — não USDT)
quantity         float quantidade do ativo
price_usdt       float preço do ativo em USDT na operação
total_usdt       float quantity × price_usdt
fee_amount       float
fee_currency     str
fee_value_brl    float
value_brl_binance float  sent/received_value_BRL do export (câmbio Binance)
ptax_bcb         float   PTAX BCB da data (cotacaoVenda)
value_brl_ptax   float   total_usdt × ptax_bcb (para IRPF)
source           str   export | api
order_type       str   LIMIT | MARKET | CONVERT | etc
```

## Schema — `data/crypto/earn_history.csv`

```
trade_id         str
date             str   YYYY-MM-DD
asset            str   e.g. USDT, BNB, ETH
quantity         float
value_brl_binance float  received_value_BRL do export
ptax_bcb         float
value_brl_ptax   float
earn_type        str   FLEXIBLE | LOCKED | STAKING (do market_model_type)
source           str   export | api
```

## Schema — `data/crypto/cost_basis.json`

```json
{
  "updated_at": "2026-09-12T07:00:00",
  "assets": {
    "BTC": {
      "quantity": 0.05,
      "avg_cost_usdt": 67000.0,
      "avg_cost_brl_ptax": 392000.0,
      "total_invested_brl": 19600.0,
      "trades_count": 10
    },
    "ETH": { ... }
  }
}
```

---

## Módulo estrutura

```
src/crypto_trades/
    __init__.py
    models.py           ← CryptoTrade, EarnRecord dataclasses
    parser.py           ← parse export CSV Binance → list[CryptoTrade | EarnRecord]
    classifier.py       ← classifica type/direction por sent/received currency
    ptax_enricher.py    ← enriquece com PTAX BCB (reusa irpf_report.ptax)
    store.py            ← trades_history.csv e earn_history.csv: append + dedup
    cost_basis.py       ← calcula custo médio ponderado FIFO/ponderado por ativo
    sync.py             ← sync incremental via BinanceReadOnlyClient
    main.py             ← CLI: import | sync | cost-basis
tests/crypto_trades/
    test_parser.py
    test_classifier.py
    test_cost_basis.py
    test_store.py
```

---

## Classificador de operações

```python
# src/crypto_trades/classifier.py

FIAT_CURRENCIES = {"BRL", "USD", "EUR"}
STABLE_COINS    = {"USDT", "USDC", "BUSD", "TUSD"}
IGNORE_TYPES    = {"Deposit", "Send", "Receive"}  # tratar separado

def classify(row: dict) -> str:
    """
    Determina trade_type a partir dos campos do export Binance.
    """
    t    = row["type"]
    sent = row["sent_currency"]
    recv = row["received_currency"]
    mm   = row["market_model_type"]

    if t == "Receive" and mm == "EARN":
        return "EARN"
    if t == "Deposit" and mm == "FIAT":
        return "DEPOSIT_FIAT"
    if t in ("Send",):
        return "SEND"
    if t == "Receive" and mm == "CRYPTO_DEPOSIT":
        return "RECEIVE_EXTERNAL"

    # Trades reais
    if sent in STABLE_COINS | FIAT_CURRENCIES:
        return "BUY"
    if recv in STABLE_COINS | FIAT_CURRENCIES:
        return "SELL"
    # Cripto → Cripto
    if sent and recv and sent not in STABLE_COINS and recv not in STABLE_COINS:
        return "SWAP"  # gera SWAP_SELL + SWAP_BUY

    return "UNKNOWN"


def get_asset(row: dict, trade_type: str) -> str:
    """Retorna o ativo principal (não USDT/BRL)."""
    if trade_type == "BUY":
        return row["received_currency"]
    if trade_type == "SELL":
        return row["sent_currency"]
    if trade_type in ("SWAP_SELL",):
        return row["sent_currency"]
    if trade_type in ("SWAP_BUY",):
        return row["received_currency"]
    return row["received_currency"] or row["sent_currency"]
```

---

## Custo médio ponderado

Método: **custo médio ponderado móvel** (CMM) — exigido pela RFB para criptoativos.

```python
# src/crypto_trades/cost_basis.py

def compute_cost_basis(trades: list[CryptoTrade]) -> dict[str, AssetCostBasis]:
    """
    Calcula custo médio ponderado em BRL (PTAX) por ativo.
    Método CMM: ao comprar, recalcula preço médio.
    Ao vender, mantém custo médio atual (não altera).
    """
    basis: dict[str, AssetCostBasis] = {}

    for trade in sorted(trades, key=lambda t: t.datetime):
        asset = trade.asset
        if asset not in basis:
            basis[asset] = AssetCostBasis(asset=asset)

        b = basis[asset]

        if trade.trade_type in ("BUY", "SWAP_BUY"):
            # CMM: novo preço médio = (qty_atual * custo_médio + qty_nova * custo_nova) / qty_total
            total_qty  = b.quantity + trade.quantity
            total_cost = (b.quantity * b.avg_cost_brl_ptax) + trade.value_brl_ptax
            b.avg_cost_brl_ptax = total_cost / total_qty if total_qty > 0 else 0
            b.quantity = total_qty
            b.total_invested_brl += trade.value_brl_ptax
            b.trades_count += 1

        elif trade.trade_type in ("SELL", "SWAP_SELL"):
            b.quantity = max(0, b.quantity - trade.quantity)
            b.trades_count += 1
            # avg_cost_brl_ptax mantém o mesmo após venda (CMM)

    return basis
```

---

## config/crypto_pairs.yaml (novo)

Lista de pares para sync incremental via API:

```yaml
# Pares negociados na Binance — usados pelo crypto-sync para buscar novos trades
# Formato: BASE + QUOTE. Adicionar novo par quando iniciar operações nele.
pairs:
  - BTCUSDT
  - ETHUSDT
  - SOLUSDT
  - ADAUSDT
  - XRPUSDT
  - AAVEUSDT
  - LINKUSDT
  - ENAAUSDT
  - PENDLEUSDT
  - ETHFIUSDT
  - BNBUSDT
  - UNIUSDT
  - AVAXUSDT
  - SUIUSDT
  - CRVUSDT
# Adicionar outros pares se necessário
```

---

## Justfile additions

```just
# Importa export CSV da Binance para trades_history.csv + earn_history.csv
# Idempotente — pode rodar múltiplas vezes com o mesmo arquivo
crypto-import file="data/crypto/uploads/binance_export.csv":
    PYTHONPATH=src uv run python -m crypto_trades.main import \
        --file {{file}} \
        --trades-output data/crypto/trades_history.csv \
        --earn-output   data/crypto/earn_history.csv
    just crypto-cost-basis
    @echo "✓ Import concluído. Cost basis atualizado."

# Sync incremental via API Binance (novos trades desde o último ID por par)
# Requer BINANCE_API_KEY e BINANCE_API_SECRET no .env
crypto-sync:
    PYTHONPATH=src uv run python -m crypto_trades.main sync \
        --pairs-config config/crypto_pairs.yaml \
        --trades-output data/crypto/trades_history.csv
    just crypto-cost-basis
    @echo "✓ Sync concluído. Cost basis atualizado."

# Recalcula custo médio ponderado BRL por ativo
crypto-cost-basis:
    PYTHONPATH=src uv run python -m crypto_trades.main cost-basis \
        --trades data/crypto/trades_history.csv \
        --output data/crypto/cost_basis.json

# Exibe cost basis atual por ativo
crypto-status:
    PYTHONPATH=src uv run python -c "
import json
from pathlib import Path
cb = Path('data/crypto/cost_basis.json')
if not cb.exists():
    print('Nenhum cost basis. Rode: just crypto-import')
else:
    data = json.loads(cb.read_text())
    print(f'Atualizado: {data[\"updated_at\"]}')
    for asset, info in data['assets'].items():
        if info['quantity'] > 0.0001:
            print(f'{asset:8} qty={info[\"quantity\"]:.6f}  '
                  f'preço_médio=R\${info[\"avg_cost_brl_ptax\"]:,.2f}  '
                  f'custo_total=R\${info[\"total_invested_brl\"]:,.2f}')
    "
```

---

## Fluxo de primeiro uso

```bash
# 1. Criar diretório e colocar o export
mkdir -p data/crypto/uploads
cp ~/Downloads/binance_2025.csv data/crypto/uploads/

# 2. Importar histórico 2025
just crypto-import file=data/crypto/uploads/binance_2025.csv

# 3. Verificar resultado
just crypto-status

# 4. Importar histórico 2026 (vendas de jan/fev)
# Exportar do portal Binance: Transaction History → Jan 2026 → Fev 2026
just crypto-import file=data/crypto/uploads/binance_2026.csv

# 5. Verificar — após vender tudo em 2026, quantity deve ser 0 para todos
just crypto-status

# 6. Rotina diária (se voltar a operar)
just crypto-sync
```

---

## Testes (mínimo 8)

```python
def test_classifier_usdt_sent_is_buy()
# sent_currency=USDT, received_currency=ADA → BUY, asset=ADA

def test_classifier_usdt_received_is_sell()
# sent_currency=ETH, received_currency=USDT → SELL, asset=ETH

def test_classifier_cripto_to_cripto_is_swap()
# sent_currency=BTC, received_currency=ETH → SWAP → gera SWAP_SELL + SWAP_BUY

def test_classifier_earn_receive_classified_separately()
# type=Receive, market_model_type=EARN → EARN (não vai para trades_history)

def test_parser_returns_correct_count_from_sample(tmp_path)
# CSV com 10 rows (5 Trade, 3 Receive/EARN, 2 Deposit) → 5 trades, 3 earn records

def test_store_deduplicates_by_trade_id(tmp_path)
# Importar mesmo CSV duas vezes → trades_history.csv com mesma quantidade de linhas

def test_cost_basis_cmm_after_two_buys()
# BUY 1 BTC a R$300k, BUY 0.5 BTC a R$330k → avg = R$310k

def test_cost_basis_unchanged_after_sell()
# BUY 2 ETH a R$10k → SELL 1 ETH → avg_cost permanece R$10k (CMM)

def test_ptax_enricher_populates_value_brl_ptax(monkeypatch)
# Mock get_ptax retorna 5.89 → value_brl_ptax = total_usdt × 5.89

def test_earn_records_go_to_earn_history_not_trades(tmp_path)
# 3 Receive/EARN rows → earn_history.csv tem 3 linhas, trades_history.csv tem 0
```

---

## Verificação

```bash
# 1. Testes
uv run pytest tests/crypto_trades/ -v

# 2. Import do arquivo real 2025
just crypto-import file=data/crypto/uploads/controle_cripto_2026_xlsx_-_Orders_SPOT_Binance_2025.csv

# 3. Verificar contagens esperadas
python3 -c "
import pandas as pd
trades = pd.read_csv('data/crypto/trades_history.csv')
earn   = pd.read_csv('data/crypto/earn_history.csv')
print(f'Trades: {len(trades)} linhas')
print(f'Earn:   {len(earn)} linhas')
print(f'Trade types: {trades.trade_type.value_counts().to_dict()}')
print(f'Ativos únicos: {trades.asset.nunique()}')
"
# Esperado: ~316 trades (BUY+SELL+SWAP), ~3780 earn records

# 4. Cost basis
just crypto-status
# Após importar 2025: vários ativos com quantity > 0
# Após importar 2026 (vendas): todos com quantity ≈ 0

# 5. Lint
uv run ruff check src/crypto_trades/ tests/crypto_trades/
```

---

## Known limitations / follow-up

- **PTAX para earn records:** rendimentos EARN em USDT recebidos diariamente
  (3.780 linhas) exigem 365+ chamadas BCB distintas. O cache em disco evita
  rechamadas mas o primeiro import pode demorar 2–3 minutos. Aceitável.
- **Swap cripto→cripto:** para fins de custo médio, SWAP é tratado como SELL
  da moeda enviada (realiza ganho) + BUY da recebida (novo custo). Esta é a
  interpretação correta pela RFB (Solução de Consulta COSIT 214/2021).
- **Preço de referência para SWAP:** `total_usdt` é derivado de
  `received_value_BRL / ptax_bcb` quando não há campo USDT direto — pode
  haver pequena imprecisão em swaps cripto→cripto onde o preço de mercado
  momentâneo não está no export.
- **Sync incremental:** `GET /api/v3/myTrades` exige um `symbol` por chamada
  (ex: BTCUSDT). Para 15 pares em `crypto_pairs.yaml`, são 15 chamadas por
  sync — dentro do rate limit. Novos pares devem ser adicionados manualmente
  ao YAML antes de operar.
- **2026: você zerou tudo.** Cost basis resultante deve ser ≈ 0 em quantidade
  para todos os ativos após importar os dois arquivos (2025 + 2026). Verificar
  se há resíduos (poeira/dust) que ficaram na conta.