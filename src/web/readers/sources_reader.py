"""Local-only metadata for dashboard data sources."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

from crypto_tracker.snapshot import SNAPSHOT_PATH
from web.readers.b3_positions_reader import read_b3_summary
from web.readers.cash_reader import CONFIG_PATH as CASH_CONFIG_PATH
from web.readers.common import PROJECT_ROOT, file_mtime
from web.readers.credito_privado_reader import CONFIG_PATH as CREDIT_CONFIG_PATH
from web.readers.history_jsonl import read_account_snapshot
from web.readers.ibkr_csv import latest_ibkr_csv, read_positions
from web.readers.patrimonio_reader import BTG_GERAL_POS, BTG_OPCOES_POS
from web.readers.scan_csv import SCAN_PATH

DIVIDEND_REPORT_PATH = (
    PROJECT_ROOT / "reports/dividend_tracker/dividend_daily_report.md"
)
HISTORY_STALE_DAYS = 7
DAILY_STALE_HOURS = 25


def read_sources() -> list[dict[str, Any]]:
    """Return safe source metadata; one unreadable source never hides the rest."""
    builders: list[tuple[str, Callable[[], dict[str, Any]]]] = [
        (
            "IBKR",
            lambda: _file_source("IBKR", latest_ibkr_csv(), "Run: just ibkr-positions"),
        ),
        (
            "Binance",
            lambda: _file_source(
                "Binance", SNAPSHOT_PATH, "Run: just crypto-snapshot", stale_hours=4
            ),
        ),
        (
            "BTG",
            lambda: _file_source(
                "BTG", _newest((BTG_OPCOES_POS, BTG_GERAL_POS)), "Run: just btg-parse"
            ),
        ),
        ("B3", _b3_source),
        (
            "Caixa manual",
            lambda: _file_source(
                "Caixa manual",
                CASH_CONFIG_PATH,
                "Edite: config/cash_accounts.yaml",
                status="estimated",
            ),
        ),
        (
            "Crédito privado",
            lambda: _file_source(
                "Crédito privado",
                CREDIT_CONFIG_PATH,
                "Edite: config/credito_privado.yaml",
                status="estimated",
            ),
        ),
        ("Histórico IBKR", _history_source),
        (
            "Scanner",
            lambda: _file_source(
                "Scanner",
                SCAN_PATH,
                "Run: just daily",
                stale_hours=DAILY_STALE_HOURS,
                coverage="mercado",
            ),
        ),
        (
            "Dividendos",
            lambda: _file_source(
                "Dividendos",
                DIVIDEND_REPORT_PATH,
                "Run: just dividends-local",
                stale_hours=DAILY_STALE_HOURS,
                coverage="mercado",
            ),
        ),
    ]
    sources = []
    for name, builder in builders:
        try:
            sources.append(builder())
        except Exception:  # noqa: BLE001 - keep the overview alive per source
            sources.append(
                _source(
                    name,
                    "partial",
                    hint="Erro ao ler a fonte local; verifique o arquivo",
                )
            )
    return sources


def read_alerts() -> dict[str, int | None]:
    """Count critical option expirations so the overview can surface them."""
    try:
        exit_options = sum(
            1
            for position in read_positions()
            if position.asset_type == "OPT" and position.risk_status == "EXIT"
        )
    except Exception:  # noqa: BLE001
        exit_options = None
    return {"exit_options": exit_options}


def _source(
    name: str,
    status: str,
    *,
    as_of: str | None = None,
    last_updated: str | None = None,
    coverage: str = "local",
    hint: str | None = None,
) -> dict[str, Any]:
    return {
        "name": name,
        "status": status,
        "as_of": as_of,
        "last_updated": last_updated,
        "coverage": coverage,
        "hint": hint,
    }


def _file_source(
    name: str,
    path: Path | None,
    hint: str,
    *,
    stale_hours: int = 24 * 7,
    status: str = "ok",
    coverage: str = "local",
) -> dict[str, Any]:
    try:
        modified = datetime.fromtimestamp(path.stat().st_mtime, UTC) if path else None
    except FileNotFoundError:
        modified = None
    if path is None or modified is None:
        return _source(name, "no_data", coverage=coverage, hint=hint)
    stale = (datetime.now(UTC) - modified).total_seconds() > stale_hours * 3600
    return _source(
        name,
        "stale" if stale else status,
        as_of=modified.date().isoformat(),
        last_updated=file_mtime(path),
        coverage=coverage,
        hint=hint if stale else None,
    )


def _history_source() -> dict[str, Any]:
    snapshot = read_account_snapshot()
    hint = "Run: just ibkr-positions"
    if snapshot is None:
        return _source("Histórico IBKR", "no_data", coverage="NLV e caixa", hint=hint)
    try:
        age_days = (datetime.now(UTC).date() - date.fromisoformat(snapshot.as_of)).days
    except ValueError:
        age_days = None
    stale = age_days is None or age_days > HISTORY_STALE_DAYS
    return _source(
        "Histórico IBKR",
        "stale" if stale else "ok",
        as_of=snapshot.as_of,
        last_updated=snapshot.last_updated,
        coverage="NLV e caixa",
        hint=hint if stale else None,
    )


def _b3_source() -> dict[str, Any]:
    b3 = read_b3_summary(datetime.now(UTC).date())
    coverage = "custódia brasileira"
    import_hint = "Run: just b3-positions-import"
    if b3["status"] == "no_data":
        return _source("B3", "no_data", coverage=coverage, hint=import_hint)
    common = {
        "as_of": b3["as_of"],
        "last_updated": file_mtime(b3["snapshot"]),
        "coverage": coverage,
    }
    if b3["stale"]:
        return _source("B3", "stale", hint=import_hint, **common)
    reconciliation = b3["reconciliation"]["status"]
    if reconciliation == "issues":
        return _source(
            "B3",
            "partial",
            hint="Divergências: veja reports/b3_reconciliation_latest.md",
            **common,
        )
    if reconciliation in {"not_run", "outdated"}:
        return _source("B3", "partial", hint="Run: just b3-reconcile", **common)
    return _source("B3", "ok", **common)


def _newest(paths: tuple[Path, ...]) -> Path | None:
    existing = [path for path in paths if path.exists()]
    return max(existing, key=lambda path: path.stat().st_mtime) if existing else None
