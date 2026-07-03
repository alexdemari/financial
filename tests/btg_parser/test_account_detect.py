from __future__ import annotations

from pathlib import Path

from btg_parser.account_detect import detect_account


def test_detect_account_opcoes_from_filename():
    assert detect_account(Path("extrato_opcoes_jun2026.xlsx")) == "BTG-Opções"


def test_detect_account_geral_from_filename():
    assert detect_account(Path("009152487_geral.xlsx")) == "BTG-Geral"


def test_detect_account_unknown_warns(capsys):
    account = detect_account(Path("extrato_junho.xlsx"))

    assert account == "BTG-Unknown"
    assert "Cannot detect account" in capsys.readouterr().out
