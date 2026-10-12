# Task T27: Importação canônica de movimentações B3

**Status:** Completed
**Scope:** novo `src/b3_importer/`, `justfile`, `README.md`, `tests/b3_importer/`
**Effort:** M
**Depends on:** none

---

## Context

O dashboard recebe dados brasileiros de extratos BTG e configurações manuais.
Um extrato B3 de movimentações consolida eventos de investimentos brasileiros
de diferentes instituições e deve se tornar a fonte histórica complementar.

O arquivo real de referência é um XLSX com a aba `Movimentação` e colunas:

```text
Entrada/Saída | Data | Movimentação | Produto | Instituição |
Quantidade | Preço unitário | Valor da Operação
```

O XLSX declara incorretamente a dimensão `A1`, embora contenha múltiplas linhas
e colunas. O parser não pode confiar na dimensão declarada pelo workbook.

## Goal

Importar extratos XLSX de movimentações B3 para um histórico canônico local,
append-only e idempotente, começando pelo extrato de 12 meses e aceitando
importações mensais sobrepostas.

## Outcome spec

1. `just b3-import data/b3/uploads/movimentacao.xlsx` lê a aba
   `Movimentação` e produz/atualiza `data/b3/movements_history.csv`.
2. A primeira carga de 12 meses e cargas mensais posteriores são idempotentes.
3. A importação nunca reescreve registros históricos; somente acrescenta
   eventos novos e registra a origem da carga.
4. O comando mostra total lido, total novo, duplicados e linhas ambíguas.
5. Uma linha inválida aborta a carga antes de qualquer escrita e informa seu
   número e motivo, sem valores financeiros expostos no terminal.
6. O XLSX com dimensão incorreta é lido integralmente.
7. `data/b3/` fica no `.gitignore`.
8. `uv run pytest tests/b3_importer -x -q` passa.

## Modelo canônico

```text
event_id             str   identificador local estável
event_date           str   YYYY-MM-DD
direction            str   entrada | saida
movement_type        str   texto normalizado da B3
product              str
institution          str
quantity             float | null
unit_price_brl       float | null
operation_value_brl  float | null
source_file_hash     str   SHA-256 do XLSX importado
source_row_number    int
imported_at          str   ISO-8601 UTC
```

### Deduplicação e ambiguidade

O extrato não fornece um ID de evento. A chave candidata é o hash dos campos
econômicos normalizados (`date`, `direction`, `movement_type`, `product`,
`institution`, `quantity`, `unit_price_brl`, `operation_value_brl`).

Se a mesma chave aparecer mais de uma vez, o importador não pode assumir que
as linhas são duplicadas: podem ser eventos legítimos idênticos. Ele deve
preservar a multiplicidade, registrar a colisão e apresentá-la no resumo para
revisão. Nunca deduplicar silenciosamente colisões.

## Estrutura proposta

```text
src/b3_importer/
    __init__.py
    models.py       # B3Movement e ImportSummary
    parser.py       # leitura XLSX tolerante à dimensão incorreta
    store.py        # append-only, dedup e relatório de colisões
    main.py         # CLI import
tests/b3_importer/
    test_parser.py
    test_store.py
```

## Constraints

- Não automatizar login, scraping ou browser da Área do Investidor B3.
- Não alterar nem copiar o XLSX original; ele permanece em `data/b3/uploads/`.
- Não tratar movimentações como posições atuais.
- Testes usam workbooks sintéticos em `tmp_path`, nunca o extrato real.
- Não imprimir conteúdo de operações ou PII em logs/testes.

## Definition of done

- Uma carga inicial de 12 meses seguida da mesma carga resulta em zero novos
  eventos na segunda execução.
- Uma carga mensal sobreposta acrescenta somente eventos comprovadamente novos.
- O resumo destaca colisões que exigem revisão humana.
- Uma carga com linha inválida não altera o histórico existente.
- Documentação descreve a rotina inicial e mensal.
