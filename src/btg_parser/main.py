from __future__ import annotations

import argparse
from pathlib import Path

from btg_parser.account_detect import detect_account
from btg_parser.merger import write_merged_outputs
from btg_parser.sheet_parser import WorkbookData, parse_workbook
from btg_parser.writer import write_account_outputs


def _combine(workbooks: list[WorkbookData]) -> WorkbookData:
    return WorkbookData(
        positions=[p for wb in workbooks for p in wb.positions],
        trades=[t for wb in workbooks for t in wb.trades],
        fixed_income=[f for wb in workbooks for f in wb.fixed_income],
        proventos=[p for wb in workbooks for p in wb.proventos],
        conta_corrente=[c for wb in workbooks for c in wb.conta_corrente],
    )


def run(input_dir: Path, output_dir: Path) -> None:
    xlsx_files = sorted(input_dir.glob("*.xlsx"))
    if not xlsx_files:
        print(f"No XLSX files found in {input_dir}")
        return

    by_account: dict[str, list[WorkbookData]] = {}
    for filepath in xlsx_files:
        account = detect_account(filepath)
        data = parse_workbook(filepath, account)
        by_account.setdefault(account, []).append(data)
        print(
            f"Parsed {filepath.name} ({account}): "
            f"{len(data.positions)} positions, {len(data.trades)} trades"
        )

    all_workbooks: list[WorkbookData] = []
    for account, workbooks in by_account.items():
        combined = _combine(workbooks)
        write_account_outputs(combined, account, output_dir)
        all_workbooks.append(combined)

    write_merged_outputs(all_workbooks, output_dir)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Parse BTG extrato XLSX files into canonical CSVs"
    )
    parser.add_argument("--input-dir", type=Path, default=Path("data/btg/uploads"))
    parser.add_argument("--output-dir", type=Path, default=Path("data/btg"))
    args = parser.parse_args()
    run(args.input_dir, args.output_dir)


if __name__ == "__main__":
    main()
