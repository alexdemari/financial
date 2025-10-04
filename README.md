# 📈 Stock Data Manager

Sistema robusto e profissional para download e gerenciamento de dados históricos de ações do mercado financeiro. Desenvolvido seguindo os princípios SOLID e utilizando Design Patterns consagrados.

## 🎯 Objetivos do Projeto

### Objetivos Principais
- **Download Incremental**: Baixar apenas dados novos, evitando downloads desnecessários
- **Persistência**: Armazenar dados históricos em arquivos CSV para reutilização
- **Flexibilidade**: Suportar múltiplas fontes de símbolos (linha de comando ou arquivo)
- **Manutenibilidade**: Código organizado, testável e fácil de estender
- **Automação**: Facilitar a atualização periódica de dados via scripts

### Objetivos Técnicos
- Implementar **princípios SOLID** para código limpo e manutenível
- Utilizar **Design Patterns** (Strategy, Factory, Dependency Injection)
- Separação clara de responsabilidades entre componentes
- Interface de linha de comando (CLI) intuitiva e poderosa
- Sistema extensível para novos formatos de dados e fontes

## 🏗️ Arquitetura

O projeto segue uma arquitetura modular baseada em interfaces:

```
┌─────────────────────────────────────────────┐
│          CLI / Scripts                      │
└─────────────────┬───────────────────────────┘
                  │
┌─────────────────▼───────────────────────────┐
│      StockDataManager (Orchestrator)        │
└─────┬───────────┬───────────┬───────────────┘
      │           │           │
┌─────▼─────┐ ┌──▼──────┐ ┌──▼──────────┐
│  IReader  │ │ IWriter │ │ IDownloader │
└───────────┘ └─────────┘ └─────────────┘
      │           │           │
┌─────▼─────┐ ┌──▼──────┐ ┌──▼──────────┐
│CSVReader  │ │CSVWriter│ │YFinance     │
└───────────┘ └─────────┘ └─────────────┘
```

### Princípios SOLID Aplicados

- ✅ **S**ingle Responsibility: Cada classe tem uma única responsabilidade
- ✅ **O**pen/Closed: Aberto para extensão, fechado para modificação
- ✅ **L**iskov Substitution: Interfaces podem ser substituídas
- ✅ **I**nterface Segregation: Interfaces específicas e focadas
- ✅ **D**ependency Inversion: Depende de abstrações, não implementações

## 🚀 Setup do Ambiente

### Pré-requisitos

- **Python 3.11+**
- **uv** - Gerenciador de pacotes ultra-rápido
- **just** - Command runner (opcional, mas recomendado)

### Instalação das Ferramentas

#### Instalar uv (recomendado)

**Linux/macOS:**
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

**Windows:**
```powershell
powershell -c "irm https://astral.sh/uv/install.ps1 | iex"
```

**Via pip:**
```bash
pip install uv
```

#### Instalar just (opcional)

**Linux/macOS:**
```bash
# Via Homebrew
brew install just

# Via cargo
cargo install just
```

**Windows:**
```powershell
# Via Scoop
scoop install just

# Via cargo
cargo install just
```

### Setup do Projeto

#### 1. Clone o Repositório
```bash
git clone https://github.com/seu-usuario/stock-data-manager.git
cd stock-data-manager
```

#### 2. Crie a Estrutura de Diretórios
```bash
# Com just
just setup

# Ou manualmente
mkdir -p data/stocks logs
```

#### 3. Instale as Dependências
```bash
# Com just
just install-dev

# Ou com uv diretamente
uv sync --all-extras
```

#### 4. Verifique a Instalação
```bash
# Com just
just check

# Ou manualmente
uv run pytest
uv run ruff check src/
uv run mypy src/
```

## 🧪 Como Testar

### Executar Todos os Testes
```bash
# Com just
just test

# Com coverage
just test-cov

# Manualmente
uv run pytest
uv run pytest --cov=src/stock_data_manager --cov-report=html
```

### Executar Testes Específicos
```bash
# Testes unitários
uv run pytest tests/unit/

# Testes de integração
uv run pytest tests/integration/

# Teste específico
uv run pytest tests/unit/test_csv_reader.py

# Teste com padrão
uv run pytest -k "test_download"
```

### Verificações de Qualidade

```bash
# Linting
just lint

# Type checking
just type-check

# Formatação
just format

# Todos os checks
just check
```

## 📖 Como Executar

### Interface de Linha de Comando (CLI)

#### Uso Básico

```bash
# Ver ajuda completa
uv run python -m stock_data_manager --help

# Baixar ações específicas
uv run python -m stock_data_manager -s AAPL MSFT GOOGL

# Baixar ações brasileiras
uv run python -m stock_data_manager -s PETR4.SA VALE3.SA BBDC4.SA
```

#### Usando Arquivo de Símbolos

**Criar arquivo `symbols.txt`:**
```txt
# Ações Americanas
AAPL
MSFT
GOOGL
AMZN
META

# Ações Brasileiras
PETR4.SA
VALE3.SA
BBDC4.SA
ITUB4.SA
ABEV3.SA
```

**Executar:**
```bash
uv run python -m stock_data_manager -f symbols.txt
```

#### Especificar Diretório de Saída

```bash
# Diretório específico
uv run python -m stock_data_manager -s AAPL -d ./meus_dados

# Diretório absoluto
uv run python -m stock_data_manager -s AAPL -d /home/user/stocks

# Com arquivo
uv run python -m stock_data_manager -f symbols.txt -d ~/Documents/stocks
```

#### Opções Avançadas

```bash
# Download completo (força re-download de todo histórico)
uv run python -m stock_data_manager -s AAPL --full

# Estratégia de atualização (em vez de append)
uv run python -m stock_data_manager -s AAPL --strategy update

# Modo verboso
uv run python -m stock_data_manager -s AAPL -v

# Modo silencioso (apenas erros)
uv run python -m stock_data_manager -s AAPL -q

# Combinando opções
uv run python -m stock_data_manager -f symbols.txt -d ./data --full -v
```

### Usando Just (Recomendado)

```bash
# Listar todos os comandos
just

# Download de ações específicas
just download AAPL
just download PETR4.SA

# Download de arquivo
just download-file symbols.txt

# Download com diretório específico
just download-file symbols.txt ~/meus_dados

# Atualizar todos os dados existentes
just update-all

# Baixar ações brasileiras (predefinido)
just download-br

# Baixar ações americanas (predefinido)
just download-us
```

## 📝 Exemplos Práticos

### Exemplo 1: Setup Inicial e Primeiro Download

```bash
# 1. Setup
just setup
just install-dev

# 2. Criar arquivo de símbolos
cat > symbols.txt << EOF
AAPL
MSFT
GOOGL
PETR4.SA
VALE3.SA
EOF

# 3. Baixar dados
just download-file symbols.txt

# 4. Verificar arquivos
ls -lh data/stocks/
```

### Exemplo 2: Atualização Diária Automatizada

**Script `scripts/update_all.py`:**
```python
#!/usr/bin/env python3
from stock_data_manager.factories import StockDataManagerFactory
from stock_data_manager.cli import SymbolsLoader

# Carrega símbolos do arquivo
symbols = SymbolsLoader.from_file('symbols.txt')

# Cria manager
manager = StockDataManagerFactory.create_default()

# Atualiza todos
print(f"Atualizando {len(symbols)} símbolos...")
results = manager.download_multiple(symbols)

# Resumo
success = sum(1 for d in results.values() if d is not None)
print(f"✅ Sucesso: {success}/{len(symbols)}")
```

**Executar:**
```bash
just update-all
```

### Exemplo 3: Uso Programático

```python
from stock_data_manager.factories import StockDataManagerFactory

# Criar manager
manager = StockDataManagerFactory.create_default(data_dir='./meus_dados')

# Baixar uma ação
data = manager.download_and_save('AAPL')
print(f"Baixados {len(data)} registros de AAPL")

# Baixar múltiplas
symbols = ['MSFT', 'GOOGL', 'PETR4.SA']
results = manager.download_multiple(symbols)

# Ler dados salvos
aapl_data = manager.get_data('AAPL')
print(aapl_data.tail())
```

### Exemplo 4: CSV com Múltiplas Colunas

**stocks.csv:**
```csv
symbol,name,sector
AAPL,Apple Inc,Technology
MSFT,Microsoft Corp,Technology
JPM,JPMorgan Chase,Financial
PETR4.SA,Petrobras,Energy
VALE3.SA,Vale,Materials
```

**Executar:**
```bash
uv run python -m stock_data_manager -f stocks.csv -d ./data/setores
```

### Exemplo 5: Agendamento com Cron

```bash
# Editar crontab
crontab -e

# Adicionar linha para atualização diária às 18h
0 18 * * * cd /path/to/stock-data-manager && just update-all >> logs/cron.log 2>&1
```

## 📊 Formato dos Dados

Os dados são salvos em arquivos CSV com a seguinte estrutura:

```csv
Date,Open,High,Low,Close,Volume,Dividends,Stock Splits
2024-01-02,185.64,186.95,184.15,185.63,54153800,0.0,0.0
2024-01-03,184.35,185.40,183.43,184.25,58414400,0.0,0.0
...
```

### Colunas Disponíveis
- **Date**: Data (índice)
- **Open**: Preço de abertura
- **High**: Preço máximo
- **Low**: Preço mínimo
- **Close**: Preço de fechamento
- **Volume**: Volume negociado
- **Dividends**: Dividendos pagos
- **Stock Splits**: Desdobramentos

## 🔧 Configuração Avançada

### Mudando a Estratégia de Merge

```python
# Estratégia Append (padrão) - adiciona novos dados
manager = StockDataManagerFactory.create_default()

# Estratégia Update - atualiza dados existentes
manager = StockDataManagerFactory.create_with_update_strategy()
```

### Criando Reader/Writer Personalizado

```python
from stock_data_manager.interfaces import IDataReader, IDataWriter

class ParquetWriter(IDataWriter):
    def write(self, data, filepath):
        data.to_parquet(filepath)

class ParquetReader(IDataReader):
    def read(self, filepath):
        return pd.read_parquet(filepath)

# Usar
manager = StockDataManager(
    reader=ParquetReader(),
    writer=ParquetWriter(),
    downloader=YFinanceDownloader(),
    merge_strategy=AppendMergeStrategy(),
    data_dir='data/parquet'
)
```

## 🐛 Solução de Problemas

### Erro: "No module named 'yfinance'"
```bash
just install-dev
```

### Erro: Símbolos não encontrados
- Verifique a formatação: ações brasileiras precisam do sufixo `.SA`
- Exemplos: `PETR4.SA`, `VALE3.SA`, `ITUB4.SA`

### Dados desatualizados
```bash
# Force download completo
uv run python -m stock_data_manager -s AAPL --full
```

### Permissões de escrita
```bash
# Verifique permissões do diretório
chmod -R u+w data/
```

## 🤝 Contribuindo

1. Fork o projeto
2. Crie uma branch para sua feature (`git checkout -b feature/MinhaFeature`)
3. Commit suas mudanças (`git commit -m 'Adiciona MinhaFeature'`)
4. Push para a branch (`git push origin feature/MinhaFeature`)
5. Abra um Pull Request

### Diretrizes de Contribuição
- Siga os princípios SOLID
- Adicione testes para novas funcionalidades
- Mantenha cobertura de testes acima de 80%
- Use type hints em todas as funções
- Documente código complexo

## 📄 Licença

Este projeto está sob a licença MIT. Veja o arquivo `LICENSE` para mais detalhes.

## 🔗 Links Úteis

- [Documentação do yfinance](https://github.com/ranaroussi/yfinance)
- [Documentação do pandas](https://pandas.pydata.org/docs/)
- [Guia do uv](https://github.com/astral-sh/uv)
- [Documentação do just](https://just.systems/)

## 📧 Contato

- **Autor**: Seu Nome
- **Email**: seu.email@example.com
- **GitHub**: [@seu-usuario](https://github.com/seu-usuario)

---
