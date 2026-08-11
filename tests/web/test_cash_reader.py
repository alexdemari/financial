from datetime import date

import pytest

from web.readers import cash_reader


def test_read_cash_accounts_returns_empty_list_when_file_is_missing(
    monkeypatch, tmp_path
):
    monkeypatch.setattr(cash_reader, "CONFIG_PATH", tmp_path / "cash_accounts.yaml")

    assert cash_reader.read_cash_accounts() == []


def test_read_cash_accounts_parses_accounts_and_totals(monkeypatch, tmp_path):
    config_path = tmp_path / "cash_accounts.yaml"
    config_path.write_text(
        """
accounts:
  - id: neon_cc
    name: Neon
    institution: Neon
    currency: BRL
    category: caixa
    balance: 1250.50
    as_of: "2026-08-01"
  - id: btg_liquidez
    name: BTG Liquidez
    institution: BTG
    currency: BRL
    category: renda_fixa_liquidez
    balance: 3749.50
    as_of: "2026-08-01"
""".strip(),
        encoding="utf-8",
    )
    monkeypatch.setattr(cash_reader, "CONFIG_PATH", config_path)

    accounts = cash_reader.read_cash_accounts()

    assert [account.id for account in accounts] == ["neon_cc", "btg_liquidez"]
    assert cash_reader.total_cash_brl(accounts) == pytest.approx(5000.0)


def test_missing_or_null_balance_defaults_to_zero(monkeypatch, tmp_path):
    config_path = tmp_path / "cash_accounts.yaml"
    config_path.write_text(
        """
accounts:
  - id: emergency
    name: Reserva
    institution: ""
    currency: BRL
    category: reserva
    as_of: "2026-08-01"
  - id: btg_cc
    name: BTG CC
    institution: BTG
    currency: BRL
    category: caixa
    balance: null
    as_of: "2026-08-01"
""".strip(),
        encoding="utf-8",
    )
    monkeypatch.setattr(cash_reader, "CONFIG_PATH", config_path)

    accounts = cash_reader.read_cash_accounts()

    assert [account.balance for account in accounts] == [0.0, 0.0]


def test_cash_accounts_are_stale_when_any_account_is_old():
    accounts = [
        cash_reader.CashAccount(
            id="fresh",
            name="Fresh",
            institution="",
            currency="BRL",
            category="caixa",
            balance=100.0,
            as_of="2026-08-05",
        ),
        cash_reader.CashAccount(
            id="old",
            name="Old",
            institution="",
            currency="BRL",
            category="reserva",
            balance=200.0,
            as_of="2026-07-20",
        ),
    ]

    assert cash_reader.cash_accounts_are_stale(accounts, date(2026, 8, 11)) is True


def test_cash_accounts_are_fresh_when_all_accounts_are_recent():
    accounts = [
        cash_reader.CashAccount(
            id="fresh",
            name="Fresh",
            institution="",
            currency="BRL",
            category="caixa",
            balance=100.0,
            as_of="2026-08-08",
        )
    ]

    assert cash_reader.cash_accounts_are_stale(accounts, date(2026, 8, 11)) is False


def test_read_btg_cash_accounts_uses_latest_balance_per_account(tmp_path):
    csv_path = tmp_path / "conta_corrente_all.csv"
    csv_path.write_text(
        """
account,date,descricao,movimentacao,saldo,currency,source_file
BTG-Geral,2026-08-01,Entrada,100,100,BRL,one.xlsx
BTG-Geral,2026-08-05,Saida,-20,80,BRL,two.xlsx
BTG-Opções,2026-08-03,Saldo,50,50,BRL,one.xlsx
""".strip(),
        encoding="utf-8",
    )

    accounts = cash_reader.read_btg_cash_accounts(csv_path)

    assert [account.id for account in accounts] == [
        "btg_geral_cash",
        "btg_opcoes_cash",
    ]
    assert [account.balance for account in accounts] == [80.0, 50.0]
    assert [account.as_of for account in accounts] == ["2026-08-05", "2026-08-03"]
