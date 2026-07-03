from __future__ import annotations

import pandas as pd

from btg_parser.main import run
from tests.btg_parser.fixtures import build_xlsx, renda_variavel_rows


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
