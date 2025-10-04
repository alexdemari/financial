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
download symbol dir="data/stocks":
    uv run python -m src.stock_data_manager.main -s {{symbol}} -d {{dir}}

# Baixa dados de múltiplas ações (símbolos separados por espaço)
download-many symbols dir="data/stocks":
    uv run python -m src.stock_data_manager.main -s {{symbols}} -d {{dir}}

# Baixa símbolos de um arquivo
download-file file dir="data/stocks":
    uv run python -m src.stock_data_manager.main -f {{file}} -d {{dir}}

# Download completo (força re-download)
download-full file:
    uv run python -m src.stock_data_manager.main -f {{file}} --full

# Baixa dados de ações brasileiras (predefinidas)
download-br:
    uv run python -m src.stock_data_manager.main -s PETR4.SA VALE3.SA BBDC4.SA ITUB4.SA ABEV3.SA

# Baixa dados de ações americanas (predefinidas)
download-us:
    uv run python -m src.stock_data_manager.main -s AAPL MSFT GOOGL AMZN META
