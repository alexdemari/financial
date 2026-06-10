# Backtest — Comparativo de modelos técnicos para carteira de dividendos
Data de geração: 2026-06-10
Período solicitado: 2022-01-01 a 2026-05-31
Período coberto: 2022-01-03 a 2026-05-29

## Metodologia
- Sinal de compra: BUY gerado pelo modelo técnico
- Observação: WATCH é uma classificação do `dividend_tracker` sobre sinal recente; o `stock_analyzer` histórico expõe BUY/HOLD/SELL, então o backtest mede BUY
- Janela de avaliação: 45 dias após o sinal
- Critério de sucesso: alta ≥ 5% no período
- Critério de falso positivo: queda ≥ 5% no período
- Drawdown máximo: pior mínima dentro da janela de 45 dias contra o preço de entrada
- Critério de atualização: delta precisão > 5pp e modelo recomendado com pelo menos 5 sinais

## Resultados por ativo

### EGIE3.SA

| Modelo | Sinais | Precisão | Falsos+ | Drawdown máx | Recomendação |
|--------|--------|----------|---------|--------------|--------------|
| lux | 49 | 26.5% | 26.5% | -11.0% | - |
| smc | 4 | 50.0% | 25.0% | -8.0% | Atual / manter |
| rsi-sma | 0 | 0.0% | 0.0% | 0.0% | - |

**Modelo recomendado: smc — Current model is best**

### ITSA4.SA

| Modelo | Sinais | Precisão | Falsos+ | Drawdown máx | Recomendação |
|--------|--------|----------|---------|--------------|--------------|
| lux | 55 | 38.2% | 25.5% | -18.5% | Atual / manter |
| smc | 2 | 0.0% | 100.0% | -12.4% | - |
| rsi-sma | 0 | 0.0% | 0.0% | 0.0% | - |

**Modelo recomendado: lux — Current model is best**

### BBSE3.SA

| Modelo | Sinais | Precisão | Falsos+ | Drawdown máx | Recomendação |
|--------|--------|----------|---------|--------------|--------------|
| lux | 59 | 35.6% | 10.2% | -13.1% | Atual / manter |
| smc | 4 | 25.0% | 25.0% | -9.2% | - |
| rsi-sma | 0 | 0.0% | 0.0% | 0.0% | - |

**Modelo recomendado: lux — Current model is best**

### VIVT3.SA

| Modelo | Sinais | Precisão | Falsos+ | Drawdown máx | Recomendação |
|--------|--------|----------|---------|--------------|--------------|
| lux | 48 | 33.3% | 35.4% | -15.7% | - |
| smc | 3 | 66.7% | 33.3% | -8.0% | Atual / manter |
| rsi-sma | 0 | 0.0% | 0.0% | 0.0% | - |

**Modelo recomendado: smc — Current model is best**

### SAPR4.SA

| Modelo | Sinais | Precisão | Falsos+ | Drawdown máx | Recomendação |
|--------|--------|----------|---------|--------------|--------------|
| lux | 41 | 41.5% | 17.1% | -16.1% | - |
| smc | 4 | 50.0% | 25.0% | -9.8% | Atual / manter |
| rsi-sma | 0 | 0.0% | 0.0% | 0.0% | - |

**Modelo recomendado: smc — Current model is best**

### SCHD

| Modelo | Sinais | Precisão | Falsos+ | Drawdown máx | Recomendação |
|--------|--------|----------|---------|--------------|--------------|
| lux | 64 | 20.3% | 12.5% | -14.3% | Atual / manter |
| smc | 2 | 50.0% | 0.0% | -7.1% | - |
| rsi-sma | 0 | 0.0% | 0.0% | 0.0% | - |

**Modelo recomendado: lux — Too few signals (2 < 5)**

### DGRO

| Modelo | Sinais | Precisão | Falsos+ | Drawdown máx | Recomendação |
|--------|--------|----------|---------|--------------|--------------|
| lux | 66 | 25.8% | 7.6% | -13.0% | Atual / manter |
| smc | 2 | 0.0% | 0.0% | -5.3% | - |
| rsi-sma | 0 | 0.0% | 0.0% | 0.0% | - |

**Modelo recomendado: lux — Current model is best**

### VYM

| Modelo | Sinais | Precisão | Falsos+ | Drawdown máx | Recomendação |
|--------|--------|----------|---------|--------------|--------------|
| lux | 64 | 31.2% | 7.8% | -13.4% | Atual / manter |
| smc | 3 | 0.0% | 33.3% | -8.1% | - |
| rsi-sma | 0 | 0.0% | 0.0% | 0.0% | - |

**Modelo recomendado: lux — Current model is best**

### PEP

| Modelo | Sinais | Precisão | Falsos+ | Drawdown máx | Recomendação |
|--------|--------|----------|---------|--------------|--------------|
| lux | 61 | 19.7% | 19.7% | -14.7% | - |
| smc | 2 | 50.0% | 0.0% | -5.4% | Atual / manter |
| rsi-sma | 0 | 0.0% | 0.0% | 0.0% | - |

**Modelo recomendado: smc — Current model is best**

## Resumo consolidado

| Ativo | Modelo atual | Melhor modelo | Precisão atual | Precisão melhor | Mudar? |
|-------|--------------|---------------|----------------|-----------------|--------|
| EGIE3.SA | smc | smc | 50.0% | 50.0% | Não |
| ITSA4.SA | lux | lux | 38.2% | 38.2% | Não |
| BBSE3.SA | lux | lux | 35.6% | 35.6% | Não |
| VIVT3.SA | smc | smc | 66.7% | 66.7% | Não |
| SAPR4.SA | smc | smc | 50.0% | 50.0% | Não |
| SCHD | lux | smc | 20.3% | 50.0% | Não |
| DGRO | lux | lux | 25.8% | 25.8% | Não |
| VYM | lux | lux | 31.2% | 31.2% | Não |
| PEP | smc | smc | 50.0% | 50.0% | Não |

## Decisões

### Ativos onde o modelo atual é o melhor -> manter
- EGIE3.SA: `smc`
- ITSA4.SA: `lux`
- BBSE3.SA: `lux`
- VIVT3.SA: `smc`
- SAPR4.SA: `smc`
- DGRO: `lux`
- VYM: `lux`
- PEP: `smc`

### Ativos onde outro modelo é significativamente melhor -> atualizar YAML
- Nenhum

### Ativos sem diferença significativa (< 5pp) -> manter modelo atual por simplicidade
- Nenhum

### Ativos com melhor precisão bruta, mas sinais insuficientes
- SCHD: Too few signals (2 < 5)
