from __future__ import annotations

from dataclasses import asdict
from pathlib import Path

import pandas as pd

from btg_parser.sheet_parser import WorkbookData

ACCOUNT_SLUGS = {
    "BTG-Opções": "opcoes",
    "BTG-Geral": "geral",
}


def _account_slug(account: str) -> str:
    return ACCOUNT_SLUGS.get(account, account.lower().replace("btg-", ""))


def write_account_outputs(data: WorkbookData, account: str, output_dir: Path) -> None:
    """Write per-account canonical positions and trades CSVs, overwriting existing files."""
    slug = _account_slug(account)
    output_dir.mkdir(parents=True, exist_ok=True)
    _write_records(
        [asdict(position) for position in data.positions],
        output_dir / f"btg_{slug}_positions.csv",
    )
    _write_records(
        [asdict(trade) for trade in data.trades],
        output_dir / f"btg_{slug}_trades.csv",
    )


def _write_records(records: list[dict], path: Path) -> None:
    pd.DataFrame(records).to_csv(path, index=False)
