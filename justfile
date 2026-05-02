# Justfile - Cross-platform task runner (WSL/Linux first)

export PYTHONPATH := "src"

# Default recipe
default:
    just --list

# Install project in development mode
install:
    uv sync --dev

# Setup development environment
setup: install
    uv run pre-commit install

# Run tests
test:
    uv run pytest -n 2

test-stock-data-manager:
    .venv/bin/python -m pytest tests/stock_data_manager -q

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

pre-commit-ready:
    uv run ruff format src tests
    uv run ruff check src tests
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

analyzer symbol="AAPL" model="rsi-sma":
    uv run python -m stock_analyzer.main -s {{symbol}} --model {{model}}

market-scanner universe_file="data/scanner_universe_sample.csv" data_dir="data/stocks/1D" output="reports/market_scanner/scan.csv" ranking_mode="snapshot" top="10" workers="1":
    uv run python -m market_scanner.scan --universe-file {{universe_file}} --data-dir {{data_dir}} --output {{output}} --ranking-mode {{ranking_mode}} --top {{top}} --workers {{workers}}

market-scanner-backtest universe_file="data/scanner_universe_sample.csv" data_dir="data/stocks/1D" output_detailed_summary="reports/market_scanner/backtest_detailed_summary.csv" output_decision_summary="reports/market_scanner/backtest_decision_summary.csv" output_lux_summary="reports/market_scanner/backtest_lux_summary.csv" output_smc_summary="reports/market_scanner/backtest_smc_summary.csv" ranking_mode="recent-event" workers="1":
    uv run python -m market_scanner.backtest --universe-file {{universe_file}} --data-dir {{data_dir}} --output-detailed-summary {{output_detailed_summary}} --output-decision-summary {{output_decision_summary}} --output-lux-summary {{output_lux_summary}} --output-smc-summary {{output_smc_summary}} --ranking-mode {{ranking_mode}} --workers {{workers}}

market-scanner-execution-backtest universe_file="data/scanner_universe_sample.csv" data_dir="data/stocks/1D" output_trades="reports/market_scanner/execution_trades.csv" output_summary="reports/market_scanner/execution_summary.csv" output_comparison="reports/market_scanner/execution_rule_comparison.csv" ranking_mode="recent-event" exit_rule="bucket_downgrade" min_trades="20" workers="1":
    uv run python -m market_scanner.backtest_execution --universe-file {{universe_file}} --data-dir {{data_dir}} --output-trades {{output_trades}} --output-summary {{output_summary}} --output-comparison {{output_comparison}} --ranking-mode {{ranking_mode}} --exit-rule {{exit_rule}} --min-trades {{min_trades}} --workers {{workers}}

market-scanner-execution-backtest-all universe_file="data/scanner_universe_sample.csv" data_dir="data/stocks/1D" output_trades="reports/market_scanner/execution_trades.csv" output_summary="reports/market_scanner/execution_summary.csv" output_comparison="reports/market_scanner/execution_rule_comparison.csv" ranking_mode="recent-event" min_trades="20" workers="1":
    uv run python -m market_scanner.backtest_execution --universe-file {{universe_file}} --data-dir {{data_dir}} --output-trades {{output_trades}} --output-summary {{output_summary}} --output-comparison {{output_comparison}} --ranking-mode {{ranking_mode}} --exit-rule all --min-trades {{min_trades}} --workers {{workers}}

market-scanner-execution-backtest-bucket-downgrade universe_file="data/scanner_universe_sample.csv" data_dir="data/stocks/1D" output_trades="reports/market_scanner/execution_trades_bucket_downgrade.csv" output_summary="reports/market_scanner/execution_summary_bucket_downgrade.csv" output_comparison="reports/market_scanner/execution_rule_comparison_bucket_downgrade.csv" ranking_mode="recent-event" min_trades="20" workers="1":
    uv run python -m market_scanner.backtest_execution --universe-file {{universe_file}} --data-dir {{data_dir}} --output-trades {{output_trades}} --output-summary {{output_summary}} --output-comparison {{output_comparison}} --ranking-mode {{ranking_mode}} --exit-rule bucket_downgrade --min-trades {{min_trades}} --workers {{workers}}

market-scanner-execution-backtest-bars-5 universe_file="data/scanner_universe_sample.csv" data_dir="data/stocks/1D" output_trades="reports/market_scanner/execution_trades_bars_5.csv" output_summary="reports/market_scanner/execution_summary_bars_5.csv" output_comparison="reports/market_scanner/execution_rule_comparison_bars_5.csv" ranking_mode="recent-event" min_trades="20" workers="1":
    uv run python -m market_scanner.backtest_execution --universe-file {{universe_file}} --data-dir {{data_dir}} --output-trades {{output_trades}} --output-summary {{output_summary}} --output-comparison {{output_comparison}} --ranking-mode {{ranking_mode}} --exit-rule bars_5 --min-trades {{min_trades}} --workers {{workers}}

market-scanner-execution-backtest-bars-10 universe_file="data/scanner_universe_sample.csv" data_dir="data/stocks/1D" output_trades="reports/market_scanner/execution_trades_bars_10.csv" output_summary="reports/market_scanner/execution_summary_bars_10.csv" output_comparison="reports/market_scanner/execution_rule_comparison_bars_10.csv" ranking_mode="recent-event" min_trades="20" workers="1":
    uv run python -m market_scanner.backtest_execution --universe-file {{universe_file}} --data-dir {{data_dir}} --output-trades {{output_trades}} --output-summary {{output_summary}} --output-comparison {{output_comparison}} --ranking-mode {{ranking_mode}} --exit-rule bars_10 --min-trades {{min_trades}} --workers {{workers}}

market-scanner-execution-backtest-bars-20 universe_file="data/scanner_universe_sample.csv" data_dir="data/stocks/1D" output_trades="reports/market_scanner/execution_trades_bars_20.csv" output_summary="reports/market_scanner/execution_summary_bars_20.csv" output_comparison="reports/market_scanner/execution_rule_comparison_bars_20.csv" ranking_mode="recent-event" min_trades="20" workers="1":
    uv run python -m market_scanner.backtest_execution --universe-file {{universe_file}} --data-dir {{data_dir}} --output-trades {{output_trades}} --output-summary {{output_summary}} --output-comparison {{output_comparison}} --ranking-mode {{ranking_mode}} --exit-rule bars_20 --min-trades {{min_trades}} --workers {{workers}}

market-scanner-execution-backtest-alignment-break universe_file="data/scanner_universe_sample.csv" data_dir="data/stocks/1D" output_trades="reports/market_scanner/execution_trades_alignment_break.csv" output_summary="reports/market_scanner/execution_summary_alignment_break.csv" output_comparison="reports/market_scanner/execution_rule_comparison_alignment_break.csv" ranking_mode="recent-event" min_trades="20" workers="1":
    uv run python -m market_scanner.backtest_execution --universe-file {{universe_file}} --data-dir {{data_dir}} --output-trades {{output_trades}} --output-summary {{output_summary}} --output-comparison {{output_comparison}} --ranking-mode {{ranking_mode}} --exit-rule alignment_break --min-trades {{min_trades}} --workers {{workers}}

market-scanner-execution-backtest-late-state universe_file="data/scanner_universe_sample.csv" data_dir="data/stocks/1D" output_trades="reports/market_scanner/execution_trades_late_state.csv" output_summary="reports/market_scanner/execution_summary_late_state.csv" output_comparison="reports/market_scanner/execution_rule_comparison_late_state.csv" ranking_mode="recent-event" min_trades="20" workers="1":
    uv run python -m market_scanner.backtest_execution --universe-file {{universe_file}} --data-dir {{data_dir}} --output-trades {{output_trades}} --output-summary {{output_summary}} --output-comparison {{output_comparison}} --ranking-mode {{ranking_mode}} --exit-rule late_state --min-trades {{min_trades}} --workers {{workers}}

market-scanner-execution-backtest-opposite-signal universe_file="data/scanner_universe_sample.csv" data_dir="data/stocks/1D" output_trades="reports/market_scanner/execution_trades_opposite_signal.csv" output_summary="reports/market_scanner/execution_summary_opposite_signal.csv" output_comparison="reports/market_scanner/execution_rule_comparison_opposite_signal.csv" ranking_mode="recent-event" min_trades="20" workers="1":
    uv run python -m market_scanner.backtest_execution --universe-file {{universe_file}} --data-dir {{data_dir}} --output-trades {{output_trades}} --output-summary {{output_summary}} --output-comparison {{output_comparison}} --ranking-mode {{ranking_mode}} --exit-rule opposite_signal --min-trades {{min_trades}} --workers {{workers}}

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

# Produce the canonical backtest output to stdout (or a file via redirection).
# Used by /verify to compare against the golden baseline.
bench-output:
    uv run python -m src.backtest --config config/bench.yaml --output -

# Time a single backtest run and emit JSON metrics to stdout.
# /bench appends this to bench/history.jsonl.
bench:
    uv run python -m src.bench --config config/bench.yaml --json

# Compare current output to the golden baseline. Exits non-zero on divergence.
verify-identical:
    uv run python -m src.tools.diff_outputs \
        --baseline tests/baselines/golden.parquet \
        --candidate <(just bench-output)

# Promote the current output to the new golden baseline.
# Use only after a deliberate semantic change.
update-baseline:
    just bench-output > tests/baselines/golden.parquet
    @echo "✓ baseline updated. Commit tests/baselines/golden.parquet."

# Full quality gate, no commit.
gate: lint test verify-identical
    @echo "✓ all gates passed"

# ── AI / Agent tooling ────────────────────────────────────────────────────────

# Sincroniza skills entre .claude/skills/ e .codex/skills/
# Skills usam o mesmo formato (YAML frontmatter) nos dois ambientes
sync-skills:
    @echo "Sincronizando skills: .claude/skills/ → .codex/skills/"
    @mkdir -p .codex/skills
    @cp .claude/skills/*.md .codex/skills/
    @echo "Pronto."
