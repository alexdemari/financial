# Task T24: Crédito Privado — config e reader próprios (integra ao T15)

**Status:** Completed (2026-08-16)
**Skill:** add-feature
**Scope:** `config/credito_privado.yaml` (novo), `src/web/readers/credito_privado_reader.py` (novo), `src/web/routers/patrimonio.py` (modificar), `frontend/src/components/PatrimonioView.jsx` (modificar), `justfile` (modificar)
**Effort:** S
**Depends on:** T15 (patrimônio consolidado — completo), T19 (cash — completo, mesmo padrão de reader a seguir)

---

## Contexto

O usuário tem crédito privado (CDB/RDB de emissores diversos) hoje registrado
manualmente dentro de `config/cash_accounts.yaml` (T19). Isso mistura duas
classes de patrimônio com formas de dado incompatíveis:

| Campo | Cash (T19) | Crédito Privado |
|---|---|---|
| Saldo único | ✅ suficiente | ❌ — precisa de valor investido + valor atual (podem divergir) |
| Vencimento | não existe | essencial |
| Indexador/taxa | não existe | essencial (CDI%, IPCA+, prefixado) |
| Liquidez | assumida imediata | variável, precisa ser campo explícito |
| Emissor/risco de crédito | não existe | é o ponto central da classe |

Forçar os dois no mesmo arquivo deixa o schema de cash poluído com campos
nulos, ou sub-representa o crédito privado (só um número, sem a informação
que mais importa pra decidir se resgata ou segura até o vencimento).

O T15 já consolida por classe de ativo (`config/patrimonio_targets.yaml` —
`renda_fixa_br`, `acoes_br`, `bdr`, `acoes_usd`, `etf_usd`, `opcoes_br`,
`opcoes_usd`, `caixa`). Crédito privado é Renda Fixa BR por definição — o
lugar certo é essa categoria já existente, não uma nova ao lado de "caixa".

---

## Objetivo

Criar `config/credito_privado.yaml` (arquivo próprio, mesmo padrão de
edição manual do `cash_accounts.yaml`), um `credito_privado_reader.py`
espelhando exatamente o `cash_reader.py` do T19 (leitura pura, degrada pra
`[]` se o arquivo não existir), e integrar a soma dentro da categoria
`renda_fixa_br` do T15 — não como categoria nova no gráfico de alocação.

---

## Outcome spec

1. `config/credito_privado.yaml` criado com uma entrada template (valores
   zerados) seguindo o schema abaixo.
2. `credito_privado_reader.py`:
   - `read_credito_privado() -> list[CreditoPrivadoItem]` — `[]` se o
     arquivo não existir, mesmo padrão de `read_cash_accounts()`.
   - `total_credito_privado_brl(items) -> float` — soma `valor_atual`
     quando presente, senão `valor_investido` (ver regra de estimativa
     abaixo).
3. **Regra de valor atual:** se `valor_atual` não for preenchido no YAML
   (usuário não atualiza isso manualmente com frequência), usar
   `valor_investido` como estimativa conservadora — **não projetar
   rendimento via CDI/IPCA histórico** (fora de escopo, mesmo espírito do
   `dividend_tracker`: sem modelo, o dado que existe é usado como está).
   Cada item retornado expõe `valor_estimado: bool` indicando se o valor
   usado é uma estimativa (por `valor_investido`) ou o valor real
   informado.
4. **Regra de vencimento:** se `vencimento < hoje`, o item é marcado
   `status: "vencido"` e **excluído da soma de `total_credito_privado_brl`**
   (o dinheiro presumivelmente já foi resgatado e deveria estar em
   `cash_accounts.yaml` agora) — mas continua aparecendo na lista retornada
   pela API com esse status, para o usuário perceber e limpar/atualizar o
   registro em vez de o valor sumir silenciosamente do total.
5. `GET /api/patrimonio` (T15) passa a incluir:
   ```json
   {
     "credito_privado": {
       "items": [ /* CreditoPrivadoItem[] */ ],
       "total_brl": 45000.00,
       "has_vencido_pending_cleanup": true
     }
   }
   ```
   E `total_credito_privado_brl` entra na soma de `renda_fixa_br` da
   alocação — junto com o que já vier de `_read_renda_fixa` (BTG).
6. Frontend (`PatrimonioView.jsx`):
   - Nova seção colapsável "Crédito Privado" ao lado das seções de contas
     já existentes (mesmo padrão visual do T15) — tabela: Emissor | Produto
     | Indexador | Taxa | Valor Investido | Valor Atual | Vencimento |
     Status.
   - Itens com `status: "vencido"` aparecem com destaque (mesmo padrão do
     badge "⚠ desatualizado" do T19) e uma nota "excluído do total —
     atualize o registro".
   - O card de alocação (donut) **não ganha uma fatia nova** — o valor
     entra dentro da fatia já existente `renda_fixa_br`.
7. `config/credito_privado.yaml` adicionado ao `.gitignore` (dado
   financeiro pessoal, mesmo tratamento do `cash_accounts.yaml`).
8. Recipe `just credito-privado-summary` no justfile, espelhando o
   `just cash-summary` do T19.
9. `uv run pytest tests/web/test_credito_privado_reader.py` passa
   (≥ 6 testes).
10. **Migração:** qualquer entrada de crédito privado hoje dentro de
    `config/cash_accounts.yaml` deve ser identificada e apontada nos
    resultados da task (não migrar automaticamente sem o usuário
    conferir — listar o que foi encontrado e pedir confirmação antes de
    remover do `cash_accounts.yaml`).

---

## Constraints

- Mesmo padrão de degradação do `cash_reader.py`: arquivo ausente → `[]`,
  sem erro. Campo `valor_investido` ausente/nulo → tratar como 0.0, não
  quebrar a leitura dos outros itens.
- Não introduzir cálculo de rentabilidade projetada (CDI% futuro, IPCA
  futuro) — isso é decisão de projeto explícita, não esquecimento. Se um
  dia isso for necessário, é um task separado, com fonte de dado de CDI
  histórico definida (provavelmente BCB, como o `irpf_report.ptax` já faz
  para câmbio).
- Reusar exatamente a mesma convenção de categoria de risco do resto do
  projeto: este task não introduz rating de crédito nem score de risco —
  só os campos que o usuário já tem em mãos ao abrir o extrato.
- `credito_privado_reader.py` não deve importar nada de `cash_reader.py`
  nem vice-versa — são módulos irmãos, mesmo padrão, sem acoplamento.

---

## Schema: `config/credito_privado.yaml`

```yaml
# Crédito privado (CDB/RDB/debêntures etc.) — atualizar manualmente após extrato.
# valor_atual é opcional: se ausente, o valor_investido é usado como estimativa
# (sem projeção de rendimento). Datas no formato YYYY-MM-DD.
items:
  - id: btg_cdb_xp_2027
    emissor: "Banco XP"
    produto: "CDB"
    indexador: "CDI"          # CDI | IPCA | PREFIXADO
    taxa_pct: 118.0            # 118% do CDI, ou "IPCA+6.5" como texto se prefixado/IPCA+
    valor_investido: 0.00
    valor_atual: null          # opcional — null usa valor_investido como estimativa
    data_aplicacao: "2025-03-15"
    vencimento: "2027-03-15"
    liquidez_diaria: false
    data_liquidez: null        # data de janela de resgate antecipado, se houver
    conta: "BTG-Geral"         # conta onde está custodiado
```

---

## Key design

### Reader: `src/web/readers/credito_privado_reader.py`

```python
from pathlib import Path
from datetime import date
from dataclasses import dataclass
import yaml

CONFIG_PATH = Path("config/credito_privado.yaml")


@dataclass
class CreditoPrivadoItem:
    id: str
    emissor: str
    produto: str
    indexador: str
    taxa_pct: float | str
    valor_investido: float
    valor_atual: float
    valor_estimado: bool          # True se valor_atual veio de valor_investido (fallback)
    data_aplicacao: str
    vencimento: str
    liquidez_diaria: bool
    data_liquidez: str | None
    conta: str
    status: str                   # "ativo" | "vencido"


def read_credito_privado() -> list[CreditoPrivadoItem]:
    """Lê config/credito_privado.yaml. Retorna [] se o arquivo não existir."""
    if not CONFIG_PATH.exists():
        return []
    raw = yaml.safe_load(CONFIG_PATH.read_text()) or {}
    today = date.today().isoformat()
    items = []
    for entry in raw.get("items", []):
        valor_investido = float(entry.get("valor_investido") or 0.0)
        valor_atual_raw = entry.get("valor_atual")
        valor_estimado = valor_atual_raw is None
        valor_atual = float(valor_atual_raw) if valor_atual_raw is not None else valor_investido
        vencimento = str(entry.get("vencimento", ""))
        status = "vencido" if vencimento and vencimento < today else "ativo"
        items.append(CreditoPrivadoItem(
            id=str(entry.get("id", "")),
            emissor=str(entry.get("emissor", "")),
            produto=str(entry.get("produto", "")),
            indexador=str(entry.get("indexador", "")),
            taxa_pct=entry.get("taxa_pct", ""),
            valor_investido=valor_investido,
            valor_atual=valor_atual,
            valor_estimado=valor_estimado,
            data_aplicacao=str(entry.get("data_aplicacao", "")),
            vencimento=vencimento,
            liquidez_diaria=bool(entry.get("liquidez_diaria", False)),
            data_liquidez=entry.get("data_liquidez"),
            conta=str(entry.get("conta", "")),
            status=status,
        ))
    return items


def total_credito_privado_brl(items: list[CreditoPrivadoItem]) -> float:
    """Soma valor_atual (ou estimativa) apenas dos itens não vencidos."""
    return sum(item.valor_atual for item in items if item.status == "ativo")
```

### Integração no `patrimonio_reader.py` (T15) — adicionar, não substituir

```python
from web.readers.credito_privado_reader import (
    read_credito_privado, total_credito_privado_brl,
)

def read_patrimonio() -> dict:
    ...
    credito_privado_items = read_credito_privado()
    credito_privado_total = total_credito_privado_brl(credito_privado_items)

    # renda_fixa_br da alocação passa a incluir isso:
    # allocation["renda_fixa_br"] += credito_privado_total
    # (ajustar _compute_allocation existente para receber esse valor)

    total_brl = (
        (ibkr["nlv_usd"] or 0) * (ptax or 1)
        + (btg_op["total_brl"] or 0)
        + (btg_ge["total_brl"] or 0)
        + (rf["total_brl"] or 0)
        + cash_total_brl               # já existe desde T19
        + credito_privado_total        # NOVO
    )

    return {
        ...,
        "credito_privado": {
            "items": [asdict(i) for i in credito_privado_items],
            "total_brl": credito_privado_total,
            "has_vencido_pending_cleanup": any(
                i.status == "vencido" for i in credito_privado_items
            ),
        },
    }
```

Confirmar o formato exato de `_compute_allocation` antes de editar — este
task assume que existe um jeito de somar um valor extra na categoria
`renda_fixa_br` sem duplicar lógica; se `_compute_allocation` só sabe ler
direto dos readers de posição (IBKR/BTG), pode ser necessário passar
`credito_privado_total` como parâmetro extra em vez de reconstruir a
função — usar o que já existir de mais simples.

---

## Migração do `cash_accounts.yaml`

Antes de finalizar, rodar:

```bash
grep -n "cdb\|CDB\|credito\|crédito\|rdb\|RDB" config/cash_accounts.yaml
```

Se houver entradas de crédito privado hoje classificadas como
`renda_fixa_liquidez` dentro do cash, **listar essas entradas no resultado
da task** (nome, saldo, categoria atual) para o usuário confirmar antes de
mover para `credito_privado.yaml` e remover do `cash_accounts.yaml` — não
fazer a migração de dado real sem essa confirmação explícita.

---

## Tests (mínimo 6)

```python
def test_read_credito_privado_returns_empty_when_file_missing(monkeypatch)

def test_valor_atual_falls_back_to_valor_investido_when_null(tmp_path, monkeypatch)
# valor_atual: null no YAML → valor_atual == valor_investido, valor_estimado=True

def test_valor_atual_used_directly_when_present(tmp_path, monkeypatch)
# valor_atual preenchido → usado como está, valor_estimado=False

def test_item_marked_vencido_when_vencimento_in_past(tmp_path, monkeypatch)

def test_total_excludes_vencido_items(tmp_path, monkeypatch)
# 1 item ativo (R$10k) + 1 vencido (R$5k) → total == 10000, não 15000

def test_missing_valor_investido_treated_as_zero(tmp_path, monkeypatch)
# entry sem valor_investido → 0.0, não quebra leitura dos outros itens
```

---

## Verification

```bash
# 1. Tests
uv run pytest tests/web/test_credito_privado_reader.py -v
uv run pytest tests/web/test_patrimonio_reader.py -v   # garantir que T15 não quebrou

# 2. Migração — checar se há dado hoje mal-classificado no cash
grep -n "cdb\|CDB\|credito\|crédito\|rdb\|RDB" config/cash_accounts.yaml

# 3. Dashboard
just web
# Aba Patrimônio → nova seção "Crédito Privado" com tabela de itens
# Fatia "Renda Fixa BR" no donut deve refletir o valor somado

# 4. just credito-privado-summary
just credito-privado-summary
# Lista os itens ativos + total, mesmo formato do just cash-summary

# 5. Lint
uv run ruff check src/web/readers/credito_privado_reader.py \
  src/web/routers/patrimonio.py tests/web/test_credito_privado_reader.py
```

### Implementação

- Reader, template de configuração e integração no consolidado implementados.
- A seção "Crédito Privado" foi adicionada ao dashboard sem criar nova fatia
  no gráfico: os itens ativos entram em `renda_fixa_br`.
- Foram adicionados 6 testes do reader e 1 teste de integração do patrimônio;
  o conjunto focado passou com 17 testes.
- `npm run build`, Ruff e `just credito-privado-summary` passaram.
- A busca de migração em `config/cash_accounts.yaml` não encontrou entradas
  com CDB, RDB ou crédito privado.
- A suíte completa chegou a 365 testes aprovados antes de falhar em um teste
  preexistente de stale data (`tests/market_scanner/test_eligibility.py`),
  cuja fixture histórica agora é rejeitada antes da verificação de volume.

---

## Known limitations / follow-up

- **Sem projeção de rendimento.** `valor_atual` é só o que o usuário
  digitar manualmente; sem isso, usa o valor investido (subestima
  sistematicamente o valor real de itens indexados a CDI/IPCA que estão
  rendendo). Se isso importar o suficiente, um task futuro de "projeção
  via CDI histórico" é o caminho — precisa de fonte de dado de CDI diário
  (BCB SGS, mesma família de API que o `irpf_report.ptax` já usa para
  câmbio).
- **Itens vencidos não são removidos automaticamente.** Ficam visíveis com
  status `vencido` até o usuário limpar o YAML manualmente — decisão
  deliberada (evita sumiço silencioso de patrimônio do histórico, mesmo
  que também signifique manutenção manual recorrente).
- **Sem rating/score de risco de crédito.** Fora de escopo — o task só
  organiza o dado que o usuário já tem no extrato.
