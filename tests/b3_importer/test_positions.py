from datetime import date
from pathlib import Path

import openpyxl

from b3_importer.positions import POSITION_SHEETS, parse_positions_xlsx
from b3_importer.positions_store import write_snapshot
from b3_importer.reconcile import reconcile


def _workbook(path: Path) -> Path:
    workbook = openpyxl.Workbook()
    workbook.remove(workbook.active)
    for sheet_name, (
        _asset_class,
        code,
        _price,
        value,
        _included,
    ) in POSITION_SHEETS.items():
        sheet = workbook.create_sheet(sheet_name)
        headers = ["Produto", "Instituição", "Quantidade", value]
        if code:
            headers.append(code)
        sheet.append(headers)
        row = ["Produto Teste", "BTG Pactual", 10, 1000]
        if code:
            row.append("TEST3")
        sheet.append(row)
    workbook.save(path)
    return path


def test_position_parser_uses_registered_schema_and_excludes_lending(tmp_path: Path):
    positions = parse_positions_xlsx(
        _workbook(tmp_path / "posicao-2026-10-12.xlsx"), date(2026, 10, 12)
    )

    assert len(positions) == len(POSITION_SHEETS)
    assert {position.asset_class for position in positions} == {
        "acoes_br",
        "bdr",
        "emprestimos",
        "renda_fixa_br",
    }
    assert (
        next(
            position for position in positions if position.source_sheet == "Empréstimos"
        ).included_in_total
        is False
    )


def test_position_parser_ignores_b3_total_rows_without_custody_identity(tmp_path: Path):
    path = _workbook(tmp_path / "posicao-2026-10-12.xlsx")
    workbook = openpyxl.load_workbook(path)
    workbook["Acoes"].append([None, None, None, 9999])
    workbook.save(path)

    positions = parse_positions_xlsx(path, date(2026, 10, 12))

    assert len(positions) == len(POSITION_SHEETS)


def test_snapshot_is_immutable_and_idempotent(tmp_path: Path):
    positions = parse_positions_xlsx(
        _workbook(tmp_path / "posicao-2026-10-12.xlsx"), date(2026, 10, 12)
    )

    first = write_snapshot(tmp_path / "snapshots", positions)
    second = write_snapshot(tmp_path / "snapshots", positions)

    assert first == second
    assert len(list((tmp_path / "snapshots").glob("*.csv"))) == 1


def test_reconciliation_reports_quantity_mismatch_without_writing_sources(
    tmp_path: Path
):
    snapshot = tmp_path / "snapshot.csv"
    snapshot.write_text(
        "as_of,source_sheet,asset_class,product,institution,trading_code,quantity,value_brl,included_in_total,source_file_hash\n"
        "2026-10-12,Acoes,acoes_br,Produto,BTG Pactual,TEST3,10,1000,True,hash\n",
        encoding="utf-8",
    )
    btg = tmp_path / "btg.csv"
    original = "codigo,asset_type,quantidade\nTEST3,ACAO,8\n"
    btg.write_text(original, encoding="utf-8")

    rows = reconcile(snapshot, [btg])

    assert [(row.product, row.status) for row in rows] == [
        ("TEST3", "quantity_mismatch")
    ]
    assert btg.read_text(encoding="utf-8") == original
