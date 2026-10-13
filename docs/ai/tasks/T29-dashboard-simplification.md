# Task T29: Simplificação do dashboard local

**Status:** Implemented
**Scope:** `frontend/src/`, `src/web/`, `tests/web/`, `README.md`
**Effort:** M
**Depends on:** none; deve acomodar T27/T28 quando disponíveis

---

## Context

O dashboard é corretamente read-only e local, mas carrega todos os endpoints
independentemente da aba aberta. A navegação atual expõe sete módulos técnicos
e exige que o usuário descubra qual fonte está ausente ou desatualizada.

## Goal

Organizar a experiência pelas decisões do usuário: patrimônio atual, ações
pendentes e detalhe de investimentos; carregar somente os dados necessários.

## Design alvo

```text
Visão geral       patrimônio, metas, alertas, atualização das fontes
Investimentos     posições, operações e fluxo de caixa
Análise           scanner, dividendos, macro e histórico
```

O backend continua exclusivamente leitor: o dashboard não dispara comandos
nem integrações externas nesta task.

## Outcome spec

1. A abertura inicial busca somente o endpoint de visão geral e status das
   fontes; endpoints de detalhes são carregados ao abrir sua área.
2. A visão geral mostra, para IBKR, Binance, BTG, B3 quando disponível, caixa
   manual e crédito privado: estado, data de referência e comando/manual de
   atualização adequado.
3. A UI distingue `sem dados`, `desatualizado`, `parcial`, `estimado` e `ok`.
4. Patrimônio, alocação e alertas continuam visíveis sem navegação adicional.
5. Operações incluem a proveniência (`IBKR`, `BTG`, `Binance`, `B3`) sem
   misturar moedas ou inventar P&L inexistente.
6. Nenhum endpoint atualmente público muda de semântica sem teste de
   compatibilidade.
7. O dashboard continua funcional quando qualquer uma das fontes não existe.

## Arquitetura proposta

- Criar um contrato comum de metadados de fonte:
  `name`, `status`, `as_of`, `last_updated`, `coverage`, `hint`.
- Adicionar `/api/sources` como leitura agregada destes metadados.
- Fazer `useApi` aceitar carregamento condicional e refetch explícito.
- Separar componentes por área em vez de concentrar todas as consultas em
  `App.jsx`.

## Constraints

- Preservar o princípio local/read-only; T16 (botões de ação) continua uma
  decisão independente e não deve ser incorporada automaticamente.
- Não converter valores entre moedas na tela de operações.
- Não ocultar alerta de fonte desatualizada apenas porque existe dado antigo.
- Não acoplar componentes React diretamente a caminhos de arquivos.

## Definition of done

- A primeira carga de rede do dashboard é menor e não busca relatórios de abas
  invisíveis.
- Um usuário identifica as fontes vencidas e o próximo passo em uma única tela.
- Testes cobrem fonte ausente, fonte desatualizada e carregamento condicional.
- README descreve a nova navegação e o comportamento read-only.
