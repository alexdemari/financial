Implementar T18: Binance Read-Only Tracker para incluir cripto (~2% patrimônio)
no consolidado patrimonial, incluindo Spot e Simple Earn.

**Status:** Completed (2026-08-12)

## Contexto
Patrimônio consolidado (T15) já cobre IBKR + BTG + Caixa (T19).
Falta a fatia de cripto (Binance Spot e Simple Earn). A integração é read-only via REST API
pública da Binance — sem WebSocket, sem trading, sem chave de saque.

## Arquivos a criar/modificar

**Criar:** `src/crypto_tracker/__init__.py`
**Criar:** `src/crypto_tracker/binance_client.py`
**Criar:** `src/crypto_tracker/snapshot.py`
**Criar:** `src/web/readers/crypto_reader.py`
**Modificar:** `src/web/routers/patrimonio.py` — incluir cripto no consolidado
**Modificar:** `frontend/src/components/PatrimonioView.jsx`
**Criar:** `tests/crypto_tracker/test_snapshot.py` (≥ 5 testes)
**Criar:** `tests/web/test_crypto_reader.py` (≥ 3 testes)

## Configuração de credenciais

Chave API via `.env` (já carregado pelo justfile via `set dotenv-load`):

BINANCE_API_KEY=sua_chave_read_only
BINANCE_API_SECRET=seu_secret_read_only


Adicionar ao `.env.example`:

BINANCE_API_KEY=
BINANCE_API_SECRET=


Se as variáveis não estiverem definidas: retornar snapshot vazio sem crash,
logar warning. Nunca lançar exceção não tratada por credenciais ausentes.

## Spec de `binance_client.py`

```python
import hashlib, hmac, time, os
from urllib.parse import urlencode
import urllib.request
import json

BASE_URL = "https://api.binance.com"

class BinanceReadOnlyClient:
    """
    Cliente mínimo read-only para Binance Spot.
    Usa apenas urllib (sem httpx/requests) para não adicionar dependências.
    Endpoints usados:
      GET /api/v3/account          → saldos Spot
      GET /api/v3/ticker/price     → preços atuais (sem autenticação)
    """

    def __init__(self, api_key: str, api_secret: str): ...

    def get_spot_balances(self) -> list[dict]:
        """Retorna apenas assets com free + locked > 0.01 (filtrar dust)."""
        ...

    def get_prices(self, symbols: list[str]) -> dict[str, float]:
        """
        Retorna {symbol: price_usdt} para a lista dada.
        Ex: get_prices(["BTCUSDT", "ETHUSDT"]) → {"BTCUSDT": 67000.0, ...}
        Usa GET /api/v3/ticker/price (público, sem auth).
        """
        ...
```

Timeout de 10s em todas as chamadas. Se a API retornar erro ou timeout:
lançar exceção específica `BinanceAPIError(message, status_code)`.

## Spec de `snapshot.py`

```python
from pathlib import Path
from dataclasses import dataclass
import json
from datetime import datetime

SNAPSHOT_PATH = Path("data/crypto/snapshot.json")

@dataclass
class CryptoPosition:
    asset: str           # "BTC", "ETH", "USDT"
    quantity: float
    price_usdt: float    # preço spot atual
    value_usdt: float    # quantity * price_usdt
    value_brl: float     # value_usdt * ptax

@dataclass
class CryptoSnapshot:
    positions: list[CryptoPosition]
    total_usdt: float
    total_brl: float
    ptax_used: float
    fetched_at: str      # ISO datetime

def fetch_and_save(ptax: float) -> CryptoSnapshot:
    """
    Busca saldos e preços na Binance, calcula total em BRL via ptax,
    salva em data/crypto/snapshot.json, retorna snapshot.
    Criar data/crypto/ se não existir.
    """
    ...

def load_last_snapshot() -> CryptoSnapshot | None:
    """Lê snapshot.json do disco. Retorna None se não existir."""
    ...
```

USDT é tratado como 1:1 com USD para conversão BRL (USDT * ptax).
Filtrar assets com `value_usdt < 1.0` (dust) antes de salvar.

## Justfile

```just
# Busca saldos Spot e Simple Earn da Binance e salva em data/crypto/snapshot.json
crypto-snapshot:
    PYTHONPATH=src uv run python -m crypto_tracker.snapshot

# Mostra último snapshot salvo sem nova chamada à API
crypto-summary:
    PYTHONPATH=src uv run python -c "
    from crypto_tracker.snapshot import load_last_snapshot
    s = load_last_snapshot()
    if not s:
        print('Nenhum snapshot. Rode: just crypto-snapshot')
    else:
        for p in s.positions:
            print(f'{p.asset}: {p.quantity:.6f} = USD {p.value_usdt:,.2f} / BRL {p.value_brl:,.2f}')
        print(f'Total: USD {s.total_usdt:,.2f} / BRL {s.total_brl:,.2f}')
        print(f'Snapshot de: {s.fetched_at}')
    "
```

## `crypto_reader.py` (web reader)

```python
from crypto_tracker.snapshot import load_last_snapshot, CryptoSnapshot

def read_crypto_snapshot() -> CryptoSnapshot | None:
    """Lê snapshot do disco. Nunca chama a API — apenas lê arquivo local."""
    return load_last_snapshot()
```

O dashboard lê sempre do arquivo local (offline-first).
Para atualizar, o usuário roda `just crypto-snapshot` no terminal
(ou futuramente via action button T16).

## Integração com T15 (patrimonio.py)

Estender `GET /api/patrimonio` para incluir:

```json
{
  "crypto": {
    "positions": [
      {"asset": "BTC", "quantity": 0.05, "value_usdt": 3350.0, "value_brl": 19950.0},
      {"asset": "ETH", "quantity": 0.8,  "value_usdt": 2400.0, "value_brl": 14280.0}
    ],
    "total_usdt": 5750.0,
    "total_brl": 34230.0,
    "fetched_at": "2026-08-10T07:30:00",
    "stale": false     // true se fetched_at > 4h atrás
  },
  "total_brl": "<soma de tudo incluindo cripto>"
}
```

`stale: true` aciona badge "⚠ Cripto desatualizado — rode: just crypto-snapshot".

## Frontend (PatrimonioView.jsx)

- Card "Cripto" com total BRL e badge stale se aplicável
- Incluir "Cripto" como fatia no gráfico de alocação (cor: amber-500)
- Linha na tabela: "Cripto: atual 2.1% | sem target definido"

## Testes

`test_snapshot.py`:
- `test_fetch_filters_dust` — assets < $1 não aparecem no snapshot
- `test_usdt_treated_as_one_to_one` — USDT price = 1.0 sem chamada de preço
- `test_total_calculated_correctly` — soma de value_usdt bate com total_usdt
- `test_save_and_load_roundtrip` — salvar e carregar snapshot preserva valores
- `test_load_returns_none_when_no_file` — sem snapshot.json → None, sem crash

`test_crypto_reader.py`:
- `test_returns_none_when_no_snapshot` — degradação silenciosa
- `test_returns_snapshot_when_file_exists` — integração com load_last_snapshot
- `test_stale_flag_when_old_snapshot` — fetched_at > 4h → stale = true

## Constraints

- Sem dependências externas além da stdlib (urllib, json, hmac, hashlib)
- `binance_client.py` nunca é chamado diretamente pelo web server —
  apenas `crypto_reader.py` (que lê arquivo local)
- `data/crypto/` adicionado ao `.gitignore`
- Chaves nunca aparecem em logs ou outputs
- Mock de `BinanceReadOnlyClient` nos testes — zero chamadas reais à API

## Definition of Done
1. `just crypto-snapshot` busca saldos reais e salva `data/crypto/snapshot.json`
2. `just crypto-summary` exibe posições do último snapshot
3. `uv run pytest tests/crypto_tracker/ tests/web/test_crypto_reader.py -q` — todos passando
4. `uv run pytest tests/web/ -q` — nenhum teste existente quebrado
5. `GET /api/patrimonio` inclui bloco `crypto` com `stale` calculado
6. `npm run build` sem erros
7. `.env.example` atualizado com as variáveis Binance
8. `data/crypto/` e credenciais no `.gitignore`
9. Reportar arquivos criados/modificados
