# Justfile - Cross-platform task runner
# Install: cargo install just
# Usage: just <command>

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

# Run all tests
test:
    uv run pytest

# Run tests with coverage
test-coverage:
    uv run pytest --cov=src/trading_system --cov-report=html --cov-report=term-missing

# Run specific test file
test-file FILE:
    uv run pytest {{FILE}} -v

# Lint code
lint:
    uv run ruff check src tests
    uv run mypy src

# Format code
format:
    uv run ruff format src tests
    uv run ruff check --fix src tests

# Check code quality
check: format lint test

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

# Run example
run-example FILE="data/raw/sample_stocks.csv":
    uv run python -m src.trading_system.main --file {{FILE}}

# Start development server/CLI
dev:
    uv run python -m src.trading_system.cli.commands

# Build Docker image
docker-build:
    docker build -t trading-system .

# Run with Docker
docker-run:
    docker run -v ${PWD}/data:/app/data trading-system

# Generate documentation
docs:
    uv run mkdocs serve

# Update dependencies
update:
    uv sync --upgrade

# Security audit
audit:
    uv run pip-audit

# Pre-commit hooks
pre-commit:
    uv run pre-commit run --all-files
