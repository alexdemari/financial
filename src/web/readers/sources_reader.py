"""Local-only metadata for dashboard data sources."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from crypto_tracker.snapshot import SNAPSHOT_PATH
from web.readers.b3_positions_reader import read_b3_positions
from web.readers.cash_reader import CONFIG_PATH as CASH_CONFIG_PATH
from web.readers.common import PROJECT_ROOT, file_mtime
from web.readers.credito_privado_reader import CONFIG_PATH as CREDIT_CONFIG_PATH
from web.readers.history_jsonl import read_account_snapshot
from web.readers.ibkr_csv import latest_ibkr_csv

BTG_PATHS = (
    PROJECT_ROOT / "data/btg/btg_opcoes_positions.csv",
    PROJECT_ROOT / "data/btg/btg_geral_positions.csv",
)


def read_sources() -> list[dict[str, Any]]:
    """Return safe source metadata without reading or exposing financial rows."""
    ibkr_snapshot = read_account_snapshot()
    b3 = read_b3_positions(datetime.now(UTC).date())
    return [
        _file_source("IBKR", latest_ibkr_csv(), "Run: just ibkr-positions"),
        _file_source(
            "Binance", SNAPSHOT_PATH, "Run: just crypto-snapshot", stale_hours=4
        ),
        _file_source("BTG", _newest(BTG_PATHS), "Run: just btg-parse"),
        {
            "name": "B3",
            "status": _b3_status(b3),
            "as_of": b3["as_of"],
            "last_updated": b3.get("snapshot_path"),
            "coverage": "custódia brasileira",
            "hint": b3["hint"] or "Run: just b3-reconcile",
        },
        _file_source(
            "Caixa manual",
            CASH_CONFIG_PATH,
            "Edite: config/cash_accounts.yaml",
            status="estimated",
        ),
        _file_source(
            "Crédito privado",
            CREDIT_CONFIG_PATH,
            "Edite: config/credito_privado.yaml",
            status="estimated",
        ),
        {
            "name": "Histórico IBKR",
            "status": "ok" if ibkr_snapshot else "no_data",
            "as_of": ibkr_snapshot.as_of if ibkr_snapshot else None,
            "last_updated": ibkr_snapshot.last_updated if ibkr_snapshot else None,
            "coverage": "NLV e caixa",
            "hint": None if ibkr_snapshot else "Run: just ibkr-positions",
        },
    ]


def _file_source(
    name: str,
    path: Path | None,
    hint: str,
    *,
    stale_hours: int = 24 * 7,
    status: str = "ok",
) -> dict[str, Any]:
    if path is None or not path.exists():
        return {
            "name": name,
            "status": "no_data",
            "as_of": None,
            "last_updated": None,
            "coverage": "local",
            "hint": hint,
        }
    modified = datetime.fromtimestamp(path.stat().st_mtime, UTC)
    stale = (datetime.now(UTC) - modified).total_seconds() > stale_hours * 3600
    return {
        "name": name,
        "status": "stale" if stale else status,
        "as_of": modified.date().isoformat(),
        "last_updated": file_mtime(path),
        "coverage": "local",
        "hint": hint if stale else None,
    }


def _newest(paths: tuple[Path, ...]) -> Path | None:
    existing = [path for path in paths if path.exists()]
    return max(existing, key=lambda path: path.stat().st_mtime) if existing else None


def _b3_status(b3: dict[str, Any]) -> str:
    if b3["status"] != "ok":
        return "no_data" if b3["status"] == "no_data" else "partial"
    return "stale" if b3["stale"] else "ok"
