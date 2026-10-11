# Task T28: Posições B3 e reconciliação com fontes brasileiras

**Status:** Planned
**Scope:** `src/b3_importer/`, `src/web/readers/`, `src/web/routers/`, `justfile`, testes web
**Effort:** L
**Depends on:** T27

---

## Context

Movimentações de 12 meses não permitem determinar todas as posições atuais:
ativos adquiridos antes da janela continuam em carteira sem aparecer no
histórico. A B3 deve fornecer uma segunda entrada: extrato de posições.

BTG continua fornecendo detalhes operacionais enquanto a B3 passa a ser a
referência consolidada para custódia brasileira.

## Goal

Importar um extrato de posições B3, expor seu valor e data de referência no
dashboard e gerar uma reconciliação auditável contra as posições BTG.

## Outcome spec

1. `just b3-positions-import file=...` grava um snapshot datado e imutável em
   `data/b3/positions/`.
2. O snapshot mais recente é exposto como fonte separada no Patrimônio, com
   data de referência e aviso de desatualização.
3. `just b3-reconcile` compara B3 e BTG por instituição, produto e quantidade
   normalizados; gera um relatório de ausentes, excedentes e divergências.
4. Uma divergência nunca altera posição, caixa ou total automaticamente.
5. O dashboard mostra o status da reconciliação e um link/caminho para o
   relatório local, sem exibir dados sensíveis em logs.
6. O total de patrimônio só usa B3 como fonte principal depois de uma regra de
   precedência explícita que evita dupla contagem com BTG.

## Decision gates

Antes de implementar o parser, registrar o esquema real de um extrato de
posições B3 (somente cabeçalhos e metadados). Não inferir layout a partir do
extrato de movimentações.

Antes de incluir valores B3 no Patrimônio, escolher uma das políticas:

1. **B3 prevalece para posições brasileiras**; BTG permanece para caixa e
   detalhes operacionais. Recomendado após reconciliação estável.
2. **BTG prevalece**; B3 é somente auditoria. Recomendado na primeira versão.

## Constraints

- Snapshots são write-once; correções entram como novo snapshot datado.
- Sem chamadas à API B3 nesta task.
- Não tentar reconstruir posições a partir de T27.
- Testes usam dados sintéticos e cobrem dupla contagem, ausência de arquivo,
  divergência de quantidade e data desatualizada.

## Definition of done

- O usuário consegue importar posição B3 e ver claramente a data e cobertura.
- O relatório de reconciliação identifica divergências sem modificar fontes.
- Não existe cenário em que B3 e BTG sejam somados para o mesmo ativo.
