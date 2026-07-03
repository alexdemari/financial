from __future__ import annotations

from pathlib import Path

import pytest

from btg_parser.account_detect import UnknownAccountError, detect_account


def test_detect_account_opcoes_from_filename():
    assert detect_account(Path("extrato_opcoes_jun2026.xlsx")) == "BTG-Opções"


def test_detect_account_geral_from_filename():
    assert detect_account(Path("009152487_geral.xlsx")) == "BTG-Geral"


def test_detect_account_unknown_raises():
    with pytest.raises(UnknownAccountError, match="Cannot detect account"):
        detect_account(Path("extrato_junho.xlsx"))
