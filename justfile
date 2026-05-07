# Justfile - Cross-platform task runner (WSL/Linux first)

export PYTHONPATH := "src"

# Default recipe
default:
    just --list


# ── Dev environment ───────────────────────────────────────────────────────────

install:
    uv sync --dev

setup: install
    uv run pre-commit install

update:
    uv sync --upgrade

audit:
    uv run pip-audit


# ── Code quality ──────────────────────────────────────────────────────────────

test:
    uv run pytest -n 2

# Run tests for a specific module: just test-module market_scanner
test-module module:
    uv run pytest tests/{{module}} -v -q

test-file FILE:
    uv run pytest {{FILE}} -v

test-cov:
    uv run pytest --cov=src --cov-report=html
    @echo "Coverage report: htmlcov/index.html"

lint:
    uv run ruff check src tests

lint-fix:
    uv run ruff check --fix src tests

format:
    uv run ruff format src tests

type-check:
    uv run mypy src tests

# Full local quality check before committing
check: format lint-fix type-check test

pre-commit:
    uv run pre-commit run --all-files


# ── Clean ─────────────────────────────────────────────────────────────────────

clean:
    find . -type d -name "__pycache__" -exec rm -rf {} +
    rm -rf build dist htmlcov .pytest_cache
    rm -f .coverage

clean-data:
    rm -rf data/stocks/*.csv
    rm -rf logs/*.log

clean-cache:
    rm -rf ./cache/joblib/*
    rm -rf data/cache/


# ── Docker ────────────────────────────────────────────────────────────────────

docker-build:
    podman build -t stock_data_manager .

docker-run:
    podman run -v ${PWD}/data:/app/data stock_data_manager


# ── Data download ─────────────────────────────────────────────────────────────

# Download one or more symbols: just download "AAPL MSFT GOOGL"
download symbols interval="1d":
    uv run python -m stock_data_manager.main -s {{symbols}} -i {{interval}}

# Download from universe file: just download-file data/scanner_universe_filtered.csv
download-file file interval="1d":
    uv run python -m stock_data_manager.main -f {{file}} -i {{interval}}

# Download full history from universe file
download-file-full file interval="1d":
    uv run python -m stock_data_manager.main -f {{file}} --full -i {{interval}}

# Download all US symbols from JSON index
download-all-us interval="1d" base_dir=justfile_directory():
    uv run python -m stock_data_manager.main -a {{base_dir}}/data/us_symbols.json -i {{interval}}


# ── Analysis ──────────────────────────────────────────────────────────────────

analyzer symbol="AAPL" model="lux":
    uv run python -m stock_analyzer.main -s {{symbol}} --model {{model}}


# ── Scanner ───────────────────────────────────────────────────────────────────

# Full universe scan — snapshot for exploration
scan universe="data/scanner_universe_sample.csv" data_dir="data/stocks/1D" \
     output="reports/market_scanner/scan.csv" ranking_mode="snapshot" workers="8":
    uv run python -m market_scanner.scan \
      --universe-file {{universe}} \
      --data-dir {{data_dir}} \
      --output {{output}} \
      --ranking-mode {{ranking_mode}} \
      --workers {{workers}}

# Daily scan — recent-event mode, filtered universe
scan-daily universe="data/scanner_universe_filtered.csv" data_dir="data/stocks/1D" workers="8":
    uv run python -m market_scanner.scan \
      --universe-file {{universe}} \
      --data-dir {{data_dir}} \
      --ranking-mode recent-event \
      --output reports/market_scanner/scan_daily.csv \
      --workers {{workers}}

# Daily report from existing scan + recommendations
# strategy: all | lux | smc | dual (default: all)
daily-report scan="reports/market_scanner/scan_daily.csv" \
             recommendations="reports/market_scanner/execution_recommended_rules.csv" \
             max_days="2" top="20" strategy="all" \
             output="reports/market_scanner/daily_report.md":
    uv run python -m market_scanner.daily_report \
      --scan {{scan}} \
      --recommendations {{recommendations}} \
      --max-days {{max_days}} \
      --top {{top}} \
      --strategy {{strategy}} \
      --output {{output}}


# ── Operational workflows ─────────────────────────────────────────────────────

# Rotina diária completa: atualiza dados → scan → daily report
# Salva report fixo + cópia datada em reports/market_scanner/daily/
daily universe="data/scanner_universe_filtered.csv" \
      data_dir="data/stocks/1D" \
      max_days="2" \
      top="20" \
      workers="8":
    uv run python -m stock_data_manager.main \
      -f {{universe}} -d {{data_dir}}
    uv run python -m market_scanner.scan \
      --universe-file {{universe}} \
      --data-dir {{data_dir}} \
      --ranking-mode recent-event \
      --output reports/market_scanner/scan_daily.csv \
      --workers {{workers}}
    uv run python -m market_scanner.daily_report \
      --scan reports/market_scanner/scan_daily.csv \
      --recommendations reports/market_scanner/execution_recommended_rules.csv \
      --max-days {{max_days}} \
      --top {{top}} \
      --output reports/market_scanner/daily_report.md \
      --output-candidates reports/market_scanner/daily_candidates.csv \
      --archive-dir reports/market_scanner/daily
    @echo "✓ Daily report: reports/market_scanner/daily_report.md"

# Regenera execution_recommended_rules.csv (rodar semanalmente ou após mudanças)
# exit_rule: all | alignment_break | opposite_signal | bucket_downgrade | bars_5 | bars_10 | bars_20 | late_state
weekly universe="data/scanner_universe_filtered.csv" \
       data_dir="data/stocks/1D" \
       exit_rule="all" \
       min_trades="20" \
       workers="8":
    uv run python -m market_scanner.backtest_execution \
      --universe-file {{universe}} \
      --data-dir {{data_dir}} \
      --ranking-mode recent-event \
      --exit-rule {{exit_rule}} \
      --min-trades {{min_trades}} \
      --min-price 5 \
      --workers {{workers}} \
      --output-trades reports/market_scanner/execution_trades.csv \
      --output-summary reports/market_scanner/execution_summary.csv \
      --output-comparison reports/market_scanner/execution_rule_comparison.csv \
      --output-symbol-comparison reports/market_scanner/execution_symbol_comparison.csv \
      --output-recommendations reports/market_scanner/execution_recommended_rules.csv \
      --output-worst-trades reports/market_scanner/execution_worst_trades.csv \
      --output-time-windows reports/market_scanner/execution_time_windows.csv
    @echo "✓ execution_recommended_rules.csv atualizado"


# ── Backtest ──────────────────────────────────────────────────────────────────

backtest universe="data/scanner_universe_sample.csv" data_dir="data/stocks/1D" \
          ranking_mode="recent-event" workers="1":
    uv run python -m market_scanner.backtest \
      --universe-file {{universe}} \
      --data-dir {{data_dir}} \
      --output-detailed-summary reports/market_scanner/backtest_detailed_summary.csv \
      --output-decision-summary reports/market_scanner/backtest_decision_summary.csv \
      --output-lux-summary reports/market_scanner/backtest_lux_summary.csv \
      --output-smc-summary reports/market_scanner/backtest_smc_summary.csv \
      --ranking-mode {{ranking_mode}} \
      --workers {{workers}}


# ── Benchmark & quality gate ──────────────────────────────────────────────────

# Write backtest output to /tmp/candidate.csv for comparison
bench-output config="config/bench.yaml":
    uv run python -m src.bench --config {{config}} --output /tmp/candidate.csv

# Time a single backtest run and emit JSON metrics to stdout
bench config="config/bench.yaml":
    uv run python -m src.bench --config {{config}} --json

# Compare current output to the golden baseline. Exits non-zero on divergence.
verify-identical:
    just bench-output
    uv run python -c "\
        import pandas as pd; \
        a=pd.read_csv('tests/baselines/golden.csv'); \
        b=pd.read_csv('/tmp/candidate.csv'); \
        pd.testing.assert_frame_equal(a, b, check_like=True)" \
    && echo "✓ bit-identical"

# Promote the current output to the new golden baseline.
# Use only after a deliberate semantic change.
update-baseline:
    uv run python -m src.bench --config config/bench.yaml \
        --output tests/baselines/golden.csv
    @echo "✓ baseline updated. Commit tests/baselines/golden.csv."

# Full quality gate: lint + test + verify-identical
gate: lint test verify-identical
    @echo "✓ all gates passed"


# ── IBKR ─────────────────────────────────────────────────────────────────────

ibkr-option-chain symbol expiration max_strikes="10" option-type="BOTH" strike-step="5":
    uv run python -m src.ibkr.main \
      --symbol {{symbol}} \
      --expiration {{expiration}} \
      --max-strikes {{max_strikes}} \
      --option-type {{option-type}} \
      --strike-step {{strike-step}}


# ── AI / Agent tooling ────────────────────────────────────────────────────────

# Sincroniza skills entre .claude/skills/ e .codex/skills/
sync-skills:
    @echo "Sincronizando skills: .claude/skills/ → .codex/skills/"
    @mkdir -p .codex/skills
    @cp .claude/skills/*.md .codex/skills/
    @echo "Pronto."
