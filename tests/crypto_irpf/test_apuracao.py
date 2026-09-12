import pytest

from crypto_irpf.apuracao import apurar_ano
from crypto_trades.cost_basis import compute_cost_basis_with_history
from crypto_trades.models import CryptoTrade


def _trade(
    trade_type: str,
    quantity: float,
    value_brl_ptax: float,
    date: str,
    asset: str = "BTC",
) -> CryptoTrade:
    return CryptoTrade(
        trade_id=f"{trade_type}-{date}-{quantity}",
        datetime=f"{date}T10:00:00-03:00",
        date=date,
        trade_type=trade_type,
        asset=asset,
        quantity=quantity,
        price_usdt=0,
        total_usdt=0,
        fee_amount=0,
        fee_currency="",
        fee_value_brl=0,
        value_brl_binance=value_brl_ptax,
        ptax_bcb=5,
        value_brl_ptax=value_brl_ptax,
    )


def _history(trades: list[CryptoTrade]) -> dict[str, dict[str, dict[str, object]]]:
    _, snapshots = compute_cost_basis_with_history(trades)
    return {str(snapshot["trade_id"]): snapshot["assets"] for snapshot in snapshots}


def test_venda_isenta_abaixo_35k():
    trades = [
        _trade("BUY", 1, 20_000, "2025-01-01"),
        _trade("SELL", 1, 30_000, "2026-01-15"),
    ]
    monthly = apurar_ano(trades, 2026, _history(trades))
    assert monthly[0].isento is True
    assert monthly[0].darf_valor == 0


def test_venda_tributavel_acima_35k():
    trades = [
        _trade("BUY", 1, 30_000, "2025-01-01"),
        _trade("SELL", 1, 50_000, "2026-01-15"),
    ]
    monthly = apurar_ano(trades, 2026, _history(trades))
    assert monthly[0].ganho_liquido_brl == 20_000
    assert monthly[0].darf_valor == 3_000


def test_prejuizo_nao_gera_darf():
    trades = [
        _trade("BUY", 1, 50_000, "2025-01-01"),
        _trade("SELL", 1, 40_000, "2026-01-15"),
    ]
    monthly = apurar_ano(trades, 2026, _history(trades))
    assert monthly[0].ganho_liquido_brl == -10_000
    assert monthly[0].darf_valor == 0


def test_custo_medio_vigente_na_venda():
    trades = [
        _trade("BUY", 2, 10, "2026-01-01", "ADA"),
        _trade("BUY", 2, 14, "2026-01-02", "ADA"),
        _trade("SELL", 2, 20, "2026-01-03", "ADA"),
    ]
    monthly = apurar_ano(trades, 2026, _history(trades))
    assert monthly[0].trades[0].average_cost_brl == 6
    assert monthly[0].trades[0].cost_brl == 12


def test_darf_vencimento_ultimo_dia_util_mes_seguinte():
    trades = [
        _trade("BUY", 1, 30_000, "2025-01-01"),
        _trade("SELL", 1, 50_000, "2026-01-15"),
    ]
    monthly = apurar_ano(trades, 2026, _history(trades))
    assert monthly[0].darf_vencimento == "2026-02-27"


def test_apuracao_uses_persisted_snapshot_not_trade_recalculation():
    sale = _trade("SELL", 1, 50_000, "2026-01-15")
    history = {sale.trade_id: {"BTC": {"quantity": 1, "avg_cost_brl_ptax": 35_000}}}

    monthly = apurar_ano([sale], 2026, history)

    assert monthly[0].total_custo_brl == 35_000


def test_oversell_raises_data_integrity_error():
    sale = _trade("SELL", 2, 50_000, "2026-01-15")
    history = {sale.trade_id: {"BTC": {"quantity": 1, "avg_cost_brl_ptax": 35_000}}}

    with pytest.raises(ValueError, match="Oversell detected for BTC"):
        apurar_ano([sale], 2026, history)
