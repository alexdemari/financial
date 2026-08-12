Implementar T19: Módulo de Caixa e Liquidez BRL para fechar o patrimônio consolidado.

**Status:** Completed (2026-08-12)

## Contexto
O dashboard já consolida IBKR (USD) + BTG-Opções + BTG-Geral via T15.
Falta o caixa em BRL: conta corrente Neon, BTG pós-fixado/CDB liquidez diária,
reserva de emergência. Sem isso, o patrimônio total em T15 está sistematicamente
subavaliado em ~15%.

## Arquivos a criar/modificar

**Criar:** `config/cash_accounts.yaml`
**Criar:** `src/web/readers/cash_reader.py`
**Modificar:** `src/web/routers/patrimonio.py` — incluir caixa no consolidado
**Modificar:** `frontend/src/components/PatrimonioView.jsx` — exibir caixa
**Criar:** `tests/web/test_cash_reader.py` (≥ 4 testes)

## Spec de `config/cash_accounts.yaml`

```yaml
# Saldos de caixa e liquidez imediata em BRL
# Atualizar manualmente após extrato. Data no formato YYYY-MM-DD.
accounts:
  - id: neon_cc
    name: "Neon — Conta Corrente"
    institution: Neon
    currency: BRL
    category: caixa          # caixa | renda_fixa_liquidez | reserva
    balance: 0.00
    as_of: "2026-01-01"

  - id: btg_pos_fixado
    name: "BTG — Pós-fixado / CDB"
    institution: BTG
    currency: BRL
    category: renda_fixa_liquidez
    balance: 0.00
    as_of: "2026-01-01"

  - id: reserva_emergencia
    name: "Reserva de Emergência"
    institution: ""
    currency: BRL
    category: reserva
    balance: 0.00
    as_of: "2026-01-01"
```

Regras do YAML:
- `category` determina a classe de ativo no gráfico de alocação do T15
- `as_of` é a data do último extrato — mostrado no dashboard como "atualizado em X"
- Campos `balance` e `as_of` são os únicos que o usuário edita no dia a dia
- Adicionar `config/cash_accounts.yaml` ao `.gitignore` (dados financeiros pessoais)

## Spec de `cash_reader.py`

```python
from pathlib import Path
import yaml
from dataclasses import dataclass

CONFIG_PATH = Path("config/cash_accounts.yaml")

@dataclass
class CashAccount:
    id: str
    name: str
    institution: str
    currency: str        # sempre BRL nesta versão
    category: str        # caixa | renda_fixa_liquidez | reserva
    balance: float
    as_of: str           # YYYY-MM-DD string

def read_cash_accounts() -> list[CashAccount]:
    """Lê config/cash_accounts.yaml. Retorna [] se o arquivo não existir."""
    if not CONFIG_PATH.exists():
        return []
    ...

def total_cash_brl(accounts: list[CashAccount]) -> float:
    """Soma todos os saldos em BRL."""
    ...
```

Degradação: se `cash_accounts.yaml` não existe, retornar lista vazia sem erro.
Se um entry tiver `balance` ausente ou nulo, tratar como 0.0.

## Integração com T15 (patrimonio.py)

`GET /api/patrimonio` já retorna o consolidado. Estender para incluir:

```json
{
  "cash_accounts": [
    {
      "id": "neon_cc",
      "name": "Neon — Conta Corrente",
      "category": "caixa",
      "balance_brl": 12500.00,
      "as_of": "2026-08-01"
    }
  ],
  "cash_total_brl": 15000.00,
  "total_brl": "<soma de tudo incluindo caixa>",
  "cash_stale": true   // true se qualquer as_of > 7 dias atrás
}
```

O campo `cash_stale: true` deve acionar um badge de aviso no frontend
("⚠ Caixa desatualizado — edite config/cash_accounts.yaml").

## Frontend (PatrimonioView.jsx)

Adicionar à seção de summary cards:
- Card "Caixa BRL" com total e badge "⚠ desatualizado" se `cash_stale == true`
- Expandir o gráfico de alocação para incluir as categories:
  caixa (slate), renda_fixa_liquidez (blue), reserva (green-700)
- Linha na tabela de target comparison:
  "Caixa total: atual XX% | target ≤ 20% | status ✓/⚠"

## Justfile

Adicionar recipe de conveniência:

```just
# Mostra saldo atual de caixa (lê config/cash_accounts.yaml)
cash-summary:
    PYTHONPATH=src uv run python -c "
    from web.readers.cash_reader import read_cash_accounts, total_cash_brl
    accounts = read_cash_accounts()
    for a in accounts:
        print(f'{a.name}: R$ {a.balance:,.2f} (em {a.as_of})')
    print(f'Total: R$ {total_cash_brl(accounts):,.2f}')
    "
```

## Definition of Done
1. `config/cash_accounts.yaml` criado com as 3 contas template (saldos zerados)
2. `uv run pytest tests/web/test_cash_reader.py -q` — todos passando
3. `uv run pytest tests/web/ -q` — nenhum teste existente quebrado
4. `GET /api/patrimonio` inclui `cash_accounts`, `cash_total_brl`, `cash_stale`
5. `npm run build` sem erros
6. `config/cash_accounts.yaml` adicionado ao `.gitignore`
7. Reportar arquivos criados/modificados
