from __future__ import annotations

import pandas as pd

from btg_parser.main import run
from tests.btg_parser.fixtures import build_xlsx, renda_variavel_rows

_SUMARIO_HEADER = ["Ativo", "Saldo Bruto R$ {}"]


def _sumario_rows(period_end: str) -> list[list]:
    return [_SUMARIO_HEADER[:1] + [_SUMARIO_HEADER[1].format(period_end)]]


def _renda_variavel_no_stock() -> list[list]:
    rows = renda_variavel_rows()
    # Drop the TAEE11 position row, keep the section headers so the account
    # is reported as "no equity positions" for this statement.
    return [row for row in rows if not (row and row[0] == "TAEE11")]


def test_run_skips_unrecognized_filename_and_processes_the_rest(tmp_path, capsys):
    input_dir = tmp_path / "uploads"
    input_dir.mkdir()
    build_xlsx(
        input_dir / "extrato_opcoes_jun2026.xlsx",
        {"Renda Variavel": renda_variavel_rows()},
    )
    build_xlsx(
        input_dir / "extrato_junho2026.xlsx", {"Renda Variavel": renda_variavel_rows()}
    )
    output_dir = tmp_path / "out"

    run(input_dir, output_dir)

    assert "Skipping extrato_junho2026.xlsx" in capsys.readouterr().out
    assert (output_dir / "btg_opcoes_trades.csv").exists()
    assert not list(output_dir.glob("btg_unknown_*"))


def test_run_writes_nothing_when_no_file_is_recognized(tmp_path, capsys):
    input_dir = tmp_path / "uploads"
    input_dir.mkdir()
    build_xlsx(
        input_dir / "extrato_junho2026.xlsx", {"Renda Variavel": renda_variavel_rows()}
    )
    output_dir = tmp_path / "out"

    run(input_dir, output_dir)

    assert "Nothing written" in capsys.readouterr().out
    assert not output_dir.exists()


def test_run_second_account_still_processed_after_first_fails_detection(tmp_path):
    input_dir = tmp_path / "uploads"
    input_dir.mkdir()
    build_xlsx(
        input_dir / "extrato_junho2026.xlsx", {"Renda Variavel": renda_variavel_rows()}
    )
    build_xlsx(
        input_dir / "extrato_geral_jun2026.xlsx",
        {"Renda Variavel": renda_variavel_rows()},
    )
    output_dir = tmp_path / "out"

    run(input_dir, output_dir)

    trades = pd.read_csv(output_dir / "trades_all.csv")
    assert set(trades["account"]) == {"BTG-Geral"}


def test_positions_use_latest_statement_only_not_all_uploads_combined(tmp_path):
    """A stock sold since an older statement must not linger in the merged output."""
    input_dir = tmp_path / "uploads"
    input_dir.mkdir()
    build_xlsx(
        input_dir / "btg_geral_20230101_20231231.xlsx",
        {
            "Renda Variavel": renda_variavel_rows(),
            "Sumario": _sumario_rows("31/12/23"),
        },
    )
    build_xlsx(
        input_dir / "btg_geral_20260101_20260630.xlsx",
        {
            "Renda Variavel": _renda_variavel_no_stock(),
            "Sumario": _sumario_rows("30/06/26"),
        },
    )
    output_dir = tmp_path / "out"

    run(input_dir, output_dir)

    positions = pd.read_csv(output_dir / "btg_geral_positions.csv")
    assert "TAEE11" not in set(positions.get("codigo", []))
