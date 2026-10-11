from __future__ import annotations

import zipfile
from pathlib import Path

import openpyxl
import pytest

from b3_importer.parser import parse_movements_xlsx

HEADERS = [
    "Entrada/Saída",
    "Data",
    "Movimentação",
    "Produto",
    "Instituição",
    "Quantidade",
    "Preço unitário",
    "Valor da Operação",
]


def _workbook(path: Path, rows: list[list[object]]) -> Path:
    workbook = openpyxl.Workbook()
    worksheet = workbook.active
    worksheet.title = "Movimentação"
    worksheet.append(HEADERS)
    for row in rows:
        worksheet.append(row)
    workbook.save(path)
    return path


def _break_dimension(path: Path) -> None:
    entries: dict[str, bytes] = {}
    with zipfile.ZipFile(path) as archive:
        for entry in archive.infolist():
            content = archive.read(entry.filename)
            if entry.filename == "xl/worksheets/sheet1.xml":
                content = content.replace(
                    b'<dimension ref="A1"/>', b'<dimension ref="A1"/>'
                )
                start = content.find(b"<dimension")
                end = content.find(b"/>", start) + 2
                content = content[:start] + b'<dimension ref="A1"/>' + content[end:]
            entries[entry.filename] = content
    with zipfile.ZipFile(path, "w") as archive:
        for name, content in entries.items():
            archive.writestr(name, content)


def test_parser_reads_all_rows_when_workbook_declares_dimension_a1(tmp_path: Path):
    path = _workbook(
        tmp_path / "movements.xlsx",
        [
            [
                "Entrada",
                "11/10/2026",
                "Compra",
                "TAEE11",
                "BTG",
                "10",
                "40,50",
                "405,00",
            ],
            ["Saída", "2026-10-12", "Venda", "TAEE11", "BTG", 2, 42.0, 84.0],
        ],
    )
    _break_dimension(path)

    parsed = parse_movements_xlsx(path)

    assert len(parsed.movements) == 2
    assert parsed.movements[0].event_date == "2026-10-11"
    assert parsed.movements[0].operation_value_brl == 405.0
    assert parsed.rejected_rows == []


def test_parser_rejects_invalid_rows_without_losing_valid_movements(tmp_path: Path):
    path = _workbook(
        tmp_path / "movements.xlsx",
        [
            ["Entrada", "2026-10-11", "Compra", "TAEE11", "BTG", 10, 40.5, 405],
            ["Entrada", "not-a-date", "Compra", "TAEE11", "BTG", 10, 40.5, 405],
        ],
    )

    parsed = parse_movements_xlsx(path)

    assert len(parsed.movements) == 1
    assert [(row.row_number, row.reason) for row in parsed.rejected_rows] == [
        (3, "invalid event date")
    ]


def test_parser_requires_b3_movement_sheet(tmp_path: Path):
    path = tmp_path / "wrong-sheet.xlsx"
    workbook = openpyxl.Workbook()
    workbook.active.title = "Other"
    workbook.save(path)

    with pytest.raises(ValueError, match="Movimentação"):
        parse_movements_xlsx(path)
