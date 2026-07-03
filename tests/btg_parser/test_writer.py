from __future__ import annotations

import pandas as pd

from btg_parser.merger import write_merged_outputs
from btg_parser.sheet_parser import parse_workbook
from btg_parser.writer import write_account_outputs
from tests.btg_parser.fixtures import build_xlsx, renda_variavel_rows


def test_writer_produces_positions_and_trades_csv(tmp_path):
    xlsx_path = build_xlsx(
        tmp_path / "extrato_opcoes.xlsx", {"Renda Variavel": renda_variavel_rows()}
    )
    data = parse_workbook(xlsx_path, "BTG-Opções")
    output_dir = tmp_path / "out"

    write_account_outputs(data, "BTG-Opções", output_dir)

    positions = pd.read_csv(output_dir / "btg_opcoes_positions.csv")
    trades = pd.read_csv(output_dir / "btg_opcoes_trades.csv")
    assert len(positions) == len(data.positions)
    assert len(trades) == len(data.trades)


def test_merger_combines_two_accounts(tmp_path):
    opcoes_path = build_xlsx(
        tmp_path / "extrato_opcoes.xlsx", {"Renda Variavel": renda_variavel_rows()}
    )
    geral_path = build_xlsx(
        tmp_path / "extrato_geral.xlsx", {"Renda Variavel": renda_variavel_rows()}
    )
    opcoes_data = parse_workbook(opcoes_path, "BTG-Opções")
    geral_data = parse_workbook(geral_path, "BTG-Geral")
    output_dir = tmp_path / "out"

    write_merged_outputs([opcoes_data, geral_data], output_dir)

    merged_trades = pd.read_csv(output_dir / "trades_all.csv")
    assert set(merged_trades["account"]) == {"BTG-Opções", "BTG-Geral"}
    assert len(merged_trades) == len(opcoes_data.trades) + len(geral_data.trades)


def test_idempotent_parse_overwrites_not_duplicates(tmp_path):
    xlsx_path = build_xlsx(
        tmp_path / "extrato_opcoes.xlsx", {"Renda Variavel": renda_variavel_rows()}
    )
    data = parse_workbook(xlsx_path, "BTG-Opções")
    output_dir = tmp_path / "out"

    write_account_outputs(data, "BTG-Opções", output_dir)
    first_run_row_count = len(pd.read_csv(output_dir / "btg_opcoes_trades.csv"))
    write_account_outputs(data, "BTG-Opções", output_dir)
    second_run_row_count = len(pd.read_csv(output_dir / "btg_opcoes_trades.csv"))

    assert first_run_row_count == second_run_row_count
