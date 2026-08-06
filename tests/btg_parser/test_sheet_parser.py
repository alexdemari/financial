from __future__ import annotations

from btg_parser import sheet_parser
from btg_parser.sheet_parser import parse_workbook
from tests.btg_parser.fixtures import (
    build_xlsx,
    previdencia_rows,
    renda_fixa_rows,
    renda_variavel_rows,
)


def test_find_section_returns_correct_row():
    rows = [("a",), ("Posição > Ações",), ("b",)]

    assert sheet_parser._find_section(rows, "Posição > Ações") == 1


def test_find_section_returns_none_when_absent():
    rows = [("a",), ("b",)]

    assert sheet_parser._find_section(rows, "Posição > Ações") is None


def test_parse_acoes_positions_returns_correct_fields(tmp_path):
    path = build_xlsx(
        tmp_path / "extrato_opcoes.xlsx", {"Renda Variavel": renda_variavel_rows()}
    )

    data = parse_workbook(path, "BTG-Opções")

    stock_positions = [p for p in data.positions if p.asset_type == "ACAO"]
    assert len(stock_positions) == 1
    assert stock_positions[0].codigo == "TAEE11"
    assert stock_positions[0].quantidade == 251
    assert stock_positions[0].saldo_bruto == 9984.78


def test_parse_acoes_movimentacoes_maps_direction(tmp_path):
    path = build_xlsx(
        tmp_path / "extrato_opcoes.xlsx", {"Renda Variavel": renda_variavel_rows()}
    )

    data = parse_workbook(path, "BTG-Opções")

    stock_trades = {t.direction: t for t in data.trades if t.asset_type == "ACAO"}
    assert stock_trades["BUY"].symbol == "TAEE11"
    assert stock_trades["SELL"].quantity == 100


def test_parse_opcoes_movimentacoes_extracts_expiration(tmp_path):
    path = build_xlsx(
        tmp_path / "extrato_opcoes.xlsx", {"Renda Variavel": renda_variavel_rows()}
    )

    data = parse_workbook(path, "BTG-Opções")

    option_trade = next(t for t in data.trades if t.asset_type == "OPT")
    assert option_trade.expiration == "2026-06-19"
    assert option_trade.option_type == "Put"
    assert option_trade.direction == "SELL"


def test_parse_opcoes_positions_extracts_strike_and_expiration(tmp_path):
    path = build_xlsx(
        tmp_path / "extrato_opcoes.xlsx", {"Renda Variavel": renda_variavel_rows()}
    )

    data = parse_workbook(path, "BTG-Opções")

    option_position = next(p for p in data.positions if p.asset_type == "OPT")
    assert option_position.preco_exercicio == 20.9
    assert option_position.data_exercicio == "2026-08-21"


def test_missing_sheet_returns_empty_collections(tmp_path):
    path = build_xlsx(tmp_path / "empty.xlsx", {"Capa": [["placeholder"]]})

    data = parse_workbook(path, "BTG-Geral")

    assert data.positions == []
    assert data.trades == []


def test_parse_renda_fixa_reads_every_posicao_section_not_just_cdb(tmp_path):
    path = build_xlsx(
        tmp_path / "extrato_geral.xlsx", {"Renda Fixa": renda_fixa_rows()}
    )

    data = parse_workbook(path, "BTG-Geral")

    ativos = {entry.ativo for entry in data.fixed_income}
    assert ativos == {"CDB-CDBC25EUWI3", "LTN"}
    assert sum(entry.saldo_bruto for entry in data.fixed_income) == 331.12 + 1661.62


def test_parse_previdencia_positions_extracts_fund_holdings(tmp_path):
    path = build_xlsx(
        tmp_path / "extrato_geral.xlsx",
        {"Previdência Individual": previdencia_rows()},
    )

    data = parse_workbook(path, "BTG-Geral")

    prev_positions = [p for p in data.positions if p.asset_type == "PREVIDENCIA"]
    assert len(prev_positions) == 1
    assert prev_positions[0].codigo == "2597233/VGBL"
    assert prev_positions[0].nome == "EMPIRICUS FOF SUPERPREVIDÊNCIA ICATU FIM"
    assert prev_positions[0].saldo_bruto == 119551.68
