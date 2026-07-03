from __future__ import annotations

from dataclasses import asdict
from pathlib import Path

import pandas as pd

from btg_parser.sheet_parser import WorkbookData


def write_merged_outputs(all_data: list[WorkbookData], output_dir: Path) -> None:
    """Combine parsed data from every account into *_all.csv files, overwriting existing ones."""
    output_dir.mkdir(parents=True, exist_ok=True)
    _write_records(
        [asdict(position) for data in all_data for position in data.positions],
        output_dir / "positions_all.csv",
    )
    _write_records(
        [asdict(trade) for data in all_data for trade in data.trades],
        output_dir / "trades_all.csv",
    )
    _write_records(
        [asdict(entry) for data in all_data for entry in data.fixed_income],
        output_dir / "renda_fixa_all.csv",
    )
    _write_records(
        [asdict(entry) for data in all_data for entry in data.proventos],
        output_dir / "proventos_futuros_all.csv",
    )
    _write_records(
        [asdict(entry) for data in all_data for entry in data.conta_corrente],
        output_dir / "conta_corrente_all.csv",
    )


def _write_records(records: list[dict], path: Path) -> None:
    pd.DataFrame(records).to_csv(path, index=False)
