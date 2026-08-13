import json
from datetime import date

import pandas as pd
import pytest

from web.readers import cash_reader
from web.readers import patrimonio_reader
from web.readers.history_jsonl import AccountSnapshot
from web.readers.ibkr_csv import Position
from crypto_tracker.snapshot import CryptoPosition, CryptoSnapshot


def _configure_paths(monkeypatch, tmp_path):
    monkeypatch.setattr(
        patrimonio_reader, "BTG_OPCOES_POS", tmp_path / "btg_opcoes.csv"
    )
    monkeypatch.setattr(patrimonio_reader, "BTG_GERAL_POS", tmp_path / "btg_geral.csv")
    monkeypatch.setattr(patrimonio_reader, "BTG_RF", tmp_path / "rf.csv")
    monkeypatch.setattr(patrimonio_reader, "BTG_PROVENTOS", tmp_path / "proventos.csv")
    monkeypatch.setattr(patrimonio_reader, "BTG_CASH", tmp_path / "cash.csv")
    monkeypatch.setattr(patrimonio_reader, "PTAX_CACHE_DIR", tmp_path / "ptax")
    monkeypatch.setattr(patrimonio_reader, "get_ptax", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(cash_reader, "CONFIG_PATH", tmp_path / "cash_accounts.yaml")
    monkeypatch.setattr(patrimonio_reader, "read_crypto_snapshot", lambda: None)


def _snapshot(nlv=100.0, cash=20.0):
    return AccountSnapshot(
        nlv=nlv,
        cash=cash,
        invested=nlv - cash,
        unrealized_pnl=0,
        unrealized_pnl_pct=0,
        margin_utilization=0,
        net_delta_approx=0,
        as_of="2026-07-02",
        last_updated="2026-07-02T12:00:00+00:00",
    )


def _position(symbol="AAPL", asset_type="STK", market_value=80.0):
    return Position(
        symbol=symbol,
        asset_type=asset_type,
        quantity=1,
        cost_basis=market_value,
        market_value=market_value,
        unrealized_pnl=0,
        return_pct=0,
        weight=0,
        option_type=None,
        strike=None,
        expiration=None,
        dte=None,
        risk_status=None,
    )


def test_patrimonio_returns_zero_when_no_files(monkeypatch, tmp_path):
    _configure_paths(monkeypatch, tmp_path)
    monkeypatch.setattr(patrimonio_reader, "read_account_snapshot", lambda: None)
    monkeypatch.setattr(patrimonio_reader, "read_positions", lambda: [])

    result = patrimonio_reader.read_patrimonio(date(2026, 7, 3))

    assert result["total_brl"] == 0
    assert result["accounts"]["ibkr"]["status"] == "no_data"
    assert result["accounts"]["btg_opcoes"]["hint"] == "Run: just btg-parse"


def test_usd_converted_to_brl_via_ptax(monkeypatch, tmp_path):
    _configure_paths(monkeypatch, tmp_path)
    monkeypatch.setattr(
        patrimonio_reader,
        "_resolve_ptax",
        lambda _today: (5.89, "2026-07-02"),
    )
    monkeypatch.setattr(
        patrimonio_reader, "read_account_snapshot", lambda: _snapshot(62_406, 0)
    )
    monkeypatch.setattr(patrimonio_reader, "read_positions", lambda: [])

    result = patrimonio_reader.read_patrimonio()

    assert result["accounts"]["ibkr"]["nlv_brl"] == pytest.approx(367_571.34)
    assert result["total_brl"] == pytest.approx(367_571.34)


def test_allocation_sums_to_100_pct(monkeypatch, tmp_path):
    _configure_paths(monkeypatch, tmp_path)
    monkeypatch.setattr(
        patrimonio_reader, "_resolve_ptax", lambda _today: (5.0, "2026-07-02")
    )
    monkeypatch.setattr(patrimonio_reader, "read_account_snapshot", lambda: _snapshot())
    monkeypatch.setattr(patrimonio_reader, "read_positions", lambda: [_position()])
    pd.DataFrame(
        [
            {
                "account": "BTG-Opções",
                "codigo": "BRAS3",
                "asset_type": "ACAO",
                "saldo_bruto": 500,
            }
        ]
    ).to_csv(patrimonio_reader.BTG_OPCOES_POS, index=False)

    result = patrimonio_reader.read_patrimonio()

    assert sum(
        item["pct_of_total"] for item in result["allocation"].values()
    ) == pytest.approx(100)


def test_allocation_vs_targets_flags_outside_range(monkeypatch, tmp_path):
    _configure_paths(monkeypatch, tmp_path)
    monkeypatch.setattr(
        patrimonio_reader, "_resolve_ptax", lambda _today: (5.0, "2026-07-02")
    )
    monkeypatch.setattr(patrimonio_reader, "read_account_snapshot", lambda: None)
    monkeypatch.setattr(patrimonio_reader, "read_positions", lambda: [])
    pd.DataFrame(
        [
            {
                "account": "BTG-Opções",
                "codigo": "BRAS3",
                "asset_type": "ACAO",
                "saldo_bruto": 70,
            }
        ]
    ).to_csv(patrimonio_reader.BTG_OPCOES_POS, index=False)
    pd.DataFrame([{"account": "BTG-Geral", "saldo_liquido": 30}]).to_csv(
        patrimonio_reader.BTG_RF, index=False
    )

    result = patrimonio_reader.read_patrimonio()

    assert result["allocation"]["acoes_br"]["pct_of_total"] == 70
    assert result["allocation"]["acoes_br"]["status"] == "above"


def test_proventos_futuros_parsed_from_btg_file(monkeypatch, tmp_path):
    _configure_paths(monkeypatch, tmp_path)
    monkeypatch.setattr(patrimonio_reader, "read_account_snapshot", lambda: None)
    monkeypatch.setattr(patrimonio_reader, "read_positions", lambda: [])
    pd.DataFrame(
        [
            {
                "account": "BTG-Opções",
                "data_liquidacao": "2026-08-01",
                "descricao": "Provento A",
                "valor": 12.5,
            },
            {
                "account": "BTG-Geral",
                "data_liquidacao": "2026-09-01",
                "descricao": "Provento B",
                "valor": 7.5,
            },
        ]
    ).to_csv(patrimonio_reader.BTG_PROVENTOS, index=False)

    result = patrimonio_reader.read_patrimonio()

    assert len(result["proventos_futuros"]) == 2
    assert result["proventos_total_brl"] == 20


def test_ptax_uses_latest_cache_without_live_call(monkeypatch, tmp_path):
    _configure_paths(monkeypatch, tmp_path)
    patrimonio_reader.PTAX_CACHE_DIR.mkdir()
    (patrimonio_reader.PTAX_CACHE_DIR / "2026-07-01.json").write_text(
        json.dumps({"cotacaoVenda": 5.45})
    )
    live_calls = []
    monkeypatch.setattr(
        patrimonio_reader,
        "get_ptax",
        lambda *_args, **_kwargs: live_calls.append(True) or None,
    )

    rate, rate_date = patrimonio_reader._resolve_ptax(date(2026, 7, 3))

    assert (rate, rate_date) == (5.45, "2026-07-01")
    assert live_calls == []


def test_btg_aluguel_is_not_double_counted(monkeypatch, tmp_path):
    _configure_paths(monkeypatch, tmp_path)
    monkeypatch.setattr(patrimonio_reader, "read_account_snapshot", lambda: None)
    monkeypatch.setattr(patrimonio_reader, "read_positions", lambda: [])
    pd.DataFrame(
        [
            {"asset_type": "ACAO", "saldo_bruto": 100},
            {"asset_type": "ALUGUEL", "saldo_bruto": 100},
        ]
    ).to_csv(patrimonio_reader.BTG_GERAL_POS, index=False)

    result = patrimonio_reader.read_patrimonio()

    assert result["accounts"]["btg_geral"]["total_brl"] == 100


def test_empty_btg_output_does_not_crash(monkeypatch, tmp_path):
    _configure_paths(monkeypatch, tmp_path)
    monkeypatch.setattr(patrimonio_reader, "read_account_snapshot", lambda: None)
    monkeypatch.setattr(patrimonio_reader, "read_positions", lambda: [])
    patrimonio_reader.BTG_OPCOES_POS.write_text("")

    result = patrimonio_reader.read_patrimonio()

    assert result["accounts"]["btg_opcoes"]["total_brl"] == 0


def test_cash_accounts_are_included_in_patrimonio_total(monkeypatch, tmp_path):
    _configure_paths(monkeypatch, tmp_path)
    monkeypatch.setattr(
        patrimonio_reader, "_resolve_ptax", lambda _today: (5.0, "2026-08-11")
    )
    monkeypatch.setattr(patrimonio_reader, "read_account_snapshot", lambda: None)
    monkeypatch.setattr(patrimonio_reader, "read_positions", lambda: [])
    (tmp_path / "cash.csv").write_text(
        """
account,date,descricao,movimentacao,saldo,currency,source_file
BTG-Geral,2026-08-09,Saldo,200.00,200.00,BRL,btg.xlsx
""".strip(),
        encoding="utf-8",
    )
    (tmp_path / "cash_accounts.yaml").write_text(
        """
accounts:
  - id: neon_cc
    name: Neon
    institution: Neon
    currency: BRL
    category: caixa
    balance: 1250.00
    as_of: "2026-08-01"
  - id: btg_liquidez
    name: BTG Liquidez
    institution: BTG
    currency: BRL
    category: renda_fixa_liquidez
    balance: 3750.00
    as_of: "2026-08-01"
""".strip(),
        encoding="utf-8",
    )

    result = patrimonio_reader.read_patrimonio(date(2026, 8, 11))

    assert result["cash_total_brl"] == pytest.approx(5200)
    assert result["cash_stale"] is True
    assert result["cash_accounts"] == [
        {
            "id": "neon_cc",
            "name": "Neon",
            "category": "caixa",
            "balance_brl": 1250.0,
            "as_of": "2026-08-01",
        },
        {
            "id": "btg_liquidez",
            "name": "BTG Liquidez",
            "category": "renda_fixa_liquidez",
            "balance_brl": 3750.0,
            "as_of": "2026-08-01",
        },
        {
            "id": "btg_geral_cash",
            "name": "BTG — BTG-Geral",
            "category": "caixa",
            "balance_brl": 200.0,
            "as_of": "2026-08-09",
        },
    ]
    assert result["cash_summary"]["target_max"] == 20
    assert result["cash_summary"]["value_brl"] == pytest.approx(5200)
    assert result["total_brl"] == pytest.approx(5200)


def test_crypto_snapshot_is_included_in_total_and_allocation(monkeypatch, tmp_path):
    _configure_paths(monkeypatch, tmp_path)
    monkeypatch.setattr(patrimonio_reader, "read_account_snapshot", lambda: None)
    monkeypatch.setattr(patrimonio_reader, "read_positions", lambda: [])
    monkeypatch.setattr(
        patrimonio_reader,
        "read_crypto_snapshot",
        lambda: CryptoSnapshot(
            positions=[CryptoPosition("BTC", 0.1, 10_000, 1_000, 5_000)],
            total_usdt=1_000,
            total_brl=5_000,
            ptax_used=5.0,
            fetched_at="2020-01-01T00:00:00+00:00",
        ),
    )

    result = patrimonio_reader.read_patrimonio(date(2026, 8, 11))

    assert result["total_brl"] == pytest.approx(5_000)
    assert result["crypto"]["total_brl"] == 5_000
    assert result["crypto"]["stale"] is True
    assert result["allocation"]["cripto"]["pct_of_total"] == pytest.approx(100)
    assert result["allocation"]["cripto"]["target_min"] is None
