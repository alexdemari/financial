# Justfile - Cross-platform task runner (WSL/Linux first)

export PYTHONPATH := "src"

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

# Clean cache files (Linux compatible)
clean:
    rm -rf __pycache__
    find . -type d -name "__pycache__" -exec rm -rf {} +
    rm -rf build dist htmlcov .pytest_cache
    rm -f .coverage

clean-data:
    rm -rf data/stocks/*.csv
    rm -rf logs/*.log

# Build Docker image
docker-build:
    podman build -t stock_data_manager .

# Run with Docker
docker-run:
    podman run -v ${PWD}/data:/app/data stock_data_manager

# Update dependencies
update:
    uv sync --upgrade

# Security audit
audit:
    uv run pip-audit

# Pre-commit hooks
pre-commit:
    uv run pre-commit run --all-files

# Download commands
download symbol interval="1d":
    uv run python -m src.stock_data_manager.main -s {{symbol}} -i {{interval}}

download-many symbols interval="1d":
    uv run python -m src.stock_data_manager.main -s {{symbols}} -i {{interval}}

download-from-file file interval="1d":
    uv run python -m src.stock_data_manager.main -f {{file}} -i {{interval}}

download--from-file-full file interval="1d":
    uv run python -m src.stock_data_manager.main -f {{file}} --full -i {{interval}}

download-br interval="1d":
    uv run python -m src.stock_data_manager.main -s PETR4.SA VALE3.SA BBDC4.SA ITUB4.SA ABEV3.SA -i {{interval}}

download-us interval="1d":
    uv run python -m src.stock_data_manager.main -s AAPL MSFT GOOGL AMZN META -i {{interval}}

download-all-us interval="1d" base_dir=justfile_directory():
    uv run python -m src.stock_data_manager.main -a {{base_dir}}/data/us_symbols.json -i {{interval}}

analyzer symbol="AAPL":
    uv run python -m src.stock_analyzer.main -s {{symbol}}

ibkr-option-chain symbol expiration max_strikes="10" option-type="BOTH" strike-step="5":
    uv run python -m src.ibkr.main --symbol {{symbol}} --expiration {{expiration}} --max-strikes {{max_strikes}} --option-type {{option-type}} --strike-step {{strike-step}}

options-analyzer:
    uv run python -m src.options_tech_scanner.options_analyzer

options-tech-scanner data_dir=justfile_directory() mode="core":
    uv run python -m src.options_tech_scanner.main --data-dir {{data_dir}} --mode {{mode}} --scan --verbose

options-tech-scanner-backtest data_dir=justfile_directory():
    uv run python -m src.options_tech_scanner.main --data-dir {{data_dir}} --backtest

options-tech-scanner-backtest-relaxed data_dir=justfile_directory():
    uv run python -m src.options_tech_scanner.main --data-dir {{data_dir}} --backtest --mode relaxed

options-tech-scanner-backtest-45 data_dir=justfile_directory():
    uv run python -m src.options_tech_scanner.main --data-dir {{data_dir}} --backtest --lookahead 45

options-tech-scanner-full data_dir=justfile_directory():
    uv run python -m src.options_tech_scanner.main --data-dir {{data_dir}} --scan --backtest

clean-cache:
    rm -rf ./cache/joblib/*

profile-backtest:
    uv run python -m src.options_tech_scanner.profile_backtest
