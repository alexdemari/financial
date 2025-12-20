# Justfile - Cross-platform task runner
# Install: cargo install just
# Usage: just <command>

export PYTHONPATH := "src"

# Set shell for Windows compatibility
set shell := ["cmd", "/c"]

# Default recipe
default:
    just --list

# Setup development environment
setup:
    uv sync --dev
    uv run pre-commit install

# Install project in development mode
install:
    uv sync --dev

# Run tests
test:
    uv run pytest

test-cov:
    uv run pytest --cov=src/stock_data_manager --cov-report=html
    @echo "Relatório de cobertura: htmlcov/index.html"

# Run specific test file
test-file FILE:
    uv run pytest {{FILE}} -v

# Lint code
lint:
    uv run ruff check src tests

lint-fix:
    uv run ruff check --fix src tests

# Format code
format:
    uv run ruff format src tests

type-check:
    uv run mypy src tests

# Check code quality
check: format lint type-check test

# Clean cache files
clean:
    @echo "Cleaning cache files..."
    @if exist "__pycache__" rmdir /s /q __pycache__
    @for /d /r . %%d in (__pycache__) do @if exist "%%d" rmdir /s /q "%%d"
    @if exist "build" rmdir /s /q build
    @if exist "dist" rmdir /s /q dist
    @if exist ".coverage" del .coverage
    @if exist "htmlcov" rmdir /s /q htmlcov
    @if exist ".pytest_cache" rmdir /s /q .pytest_cache

clean-data:
    rm -rf data/stocks/*.csv
    rm -rf logs/*.log

# Build Docker image
docker-build:
    docker build -t stock_data_manager .

# Run with Docker
docker-run:
    docker run -v ${PWD}/data:/app/data stock_data_manager

# Update dependencies
update:
    uv sync --upgrade

# Security audit
audit:
    uv run pip-audit

# Pre-commit hooks
pre-commit:
    uv run pre-commit run --all-files

# Baixa dados de uma ação específica
download symbol interval="1d":
    uv run python -m src.stock_data_manager.main -s {{symbol}} -i {{interval}}

# Baixa dados de múltiplas ações (símbolos separados por espaço)
download-many symbols interval="1d":
    uv run python -m src.stock_data_manager.main -s {{symbols}} -i {{interval}}

# Baixa símbolos de um arquivo
download-file file interval="1d":
    uv run python -m src.stock_data_manager.main -f {{file}} -i {{interval}}

# Download completo (força re-download)
download-full file interval="1d":
    uv run python -m src.stock_data_manager.main -f {{file}} --full -i {{interval}}

# Baixa dados de ações brasileiras (predefinidas)
download-br interval="1d":
    uv run python -m src.stock_data_manager.main -s PETR4.SA VALE3.SA BBDC4.SA ITUB4.SA ABEV3.SA -i {{interval}}

# Baixa dados de ações americanas (predefinidas)
download-us interval="1d":
    uv run python -m src.stock_data_manager.main -s AAPL MSFT GOOGL AMZN META -i {{interval}}

download-all-us interval="1d" base_dir=justfile_directory():
    uv run python -m src.stock_data_manager.main -a {{base_dir}}\data\us_symbols.json -i {{interval}}

analyzer symbol="AAPL":
    uv run python -m src.stock_analyzer.main -s {{symbol}}

ibkr-option-chain symbol expiration max_strikes="10" option-type="BOTH" strike-step="5":
    uv run python -m src.ibkr.main --symbol {{symbol}} --expiration {{expiration}} --max-strikes {{max_strikes}} --option-type {{option-type}} --strike-step {{strike-step}}

options-analyzer: 
    uv run python -m src.stock_analyzer.options_analyzer

options-tech-scanner data_dir=justfile_directory() mode="core":
    uv run python -m src.options_tech_scanner.main --data-dir {{data_dir}} --mode {{mode}} --scan

options-tech-scanner-backtest data_dir=justfile_directory():
    uv run python -m src.options_tech_scanner.main --data-dir {{data_dir}} --backtest

options-tech-scanner-backtest-relaxed data_dir=justfile_directory():
    uv run python -m src.options_tech_scanner.main --data-dir data\stocks\1D --backtest --mode relaxed

options-tech-scanner-backtest-45 data_dir=justfile_directory():
    uv run python -m src.options_tech_scanner.main --data-dir {{data_dir}} --backtest --lookahead 45

options-tech-scanner-full data_dir=justfile_directory():
    uv run python -m src.options_tech_scanner.main --data-dir {{data_dir}} --scan --backtest

options-tech-scanner-bench:
    uv run python -m src.options_tech_scanner.main --data-dir data\stocks\1D --backtest
    uv run python -m src.options_tech_scanner.main --data-dir data\stocks\1D --backtest

clean-cache:
    del .\\cache\\joblib\\*

profile-backtest:
    uv run python -m src.options_tech_scanner.profile_backtest