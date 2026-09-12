"""Monthly crypto capital-gain calculation using a chronological CMM basis."""

import calendar
from collections import defaultdict
from dataclasses import dataclass
from datetime import date

from crypto_trades.models import CryptoTrade

ISENCAO_MENSAL_BRL = 35_000.0
DARF_CODE = "4600"
ALIQUOTAS = (
    (5_000_000.0, 0.15),
    (10_000_000.0, 0.175),
    (30_000_000.0, 0.20),
    (float("inf"), 0.225),
)


@dataclass
class SaleDetail:
    date: str
    asset: str
    quantity: float
    proceeds_brl: float
    average_cost_brl: float
    cost_brl: float
    gain_loss_brl: float


@dataclass
class ApuracaoMensal:
    ano_mes: str
    total_vendas_brl: float
    total_custo_brl: float
    ganho_liquido_brl: float
    isento: bool
    darf_valor: float
    darf_codigo: str
    darf_vencimento: str
    trades: list[SaleDetail]


def apurar_ano(
    trades: list[CryptoTrade],
    year: int,
    cost_basis_history: dict[str, dict[str, dict[str, object]]],
) -> list[ApuracaoMensal]:
    """Calculate gains from T25's persisted CMM snapshot before each sale."""
    sales_by_month: dict[str, list[SaleDetail]] = defaultdict(list)
    for trade in sorted(trades, key=lambda item: item.datetime):
        if int(trade.date[:4]) > year:
            break
        if trade.trade_type in {"SELL", "SWAP_SELL"}:
            if int(trade.date[:4]) == year:
                sales_by_month[trade.date[:7]].append(
                    _sale_detail(trade, cost_basis_history)
                )
    return [
        _apurar_mes(month, sales) for month, sales in sorted(sales_by_month.items())
    ]


def _sale_detail(
    trade: CryptoTrade, cost_basis_history: dict[str, dict[str, dict[str, object]]]
) -> SaleDetail:
    snapshot = cost_basis_history.get(trade.trade_id, {})
    asset_basis = snapshot.get(trade.asset)
    if asset_basis is None:
        raise ValueError(
            f"Missing cost-basis snapshot for {trade.asset} before trade {trade.trade_id}; "
            "run 'just crypto-cost-basis' to refresh data/crypto/cost_basis.json"
        )
    available_quantity = float(asset_basis["quantity"])
    if trade.quantity > available_quantity:
        raise ValueError(
            f"Oversell detected for {trade.asset} on {trade.date}: "
            f"selling {trade.quantity:g} with only {available_quantity:g} available"
        )
    proceeds_brl = trade.value_brl_ptax
    average_cost_brl = float(asset_basis["avg_cost_brl_ptax"])
    cost_brl = average_cost_brl * trade.quantity
    return SaleDetail(
        date=trade.date,
        asset=trade.asset,
        quantity=trade.quantity,
        proceeds_brl=proceeds_brl,
        average_cost_brl=average_cost_brl,
        cost_brl=cost_brl,
        gain_loss_brl=proceeds_brl - cost_brl,
    )


def _apurar_mes(month: str, sales: list[SaleDetail]) -> ApuracaoMensal:
    total_vendas = sum(sale.proceeds_brl for sale in sales)
    total_custo = sum(sale.cost_brl for sale in sales)
    ganho = total_vendas - total_custo
    isento = total_vendas <= ISENCAO_MENSAL_BRL
    darf_valor = _calcular_imposto(ganho) if not isento and ganho > 0 else 0.0
    return ApuracaoMensal(
        ano_mes=month,
        total_vendas_brl=total_vendas,
        total_custo_brl=total_custo,
        ganho_liquido_brl=ganho,
        isento=isento,
        darf_valor=darf_valor,
        darf_codigo=DARF_CODE,
        darf_vencimento=_ultimo_dia_util_mes_seguinte(month),
        trades=sales,
    )


def _calcular_imposto(ganho: float) -> float:
    """Apply the progressive capital-gains rates to a positive gain."""
    imposto = 0.0
    lower_limit = 0.0
    for upper_limit, rate in ALIQUOTAS:
        taxable_amount = min(ganho, upper_limit) - lower_limit
        if taxable_amount <= 0:
            break
        imposto += taxable_amount * rate
        lower_limit = upper_limit
        if ganho <= upper_limit:
            break
    return round(imposto, 2)


def _ultimo_dia_util_mes_seguinte(ano_mes: str) -> str:
    year, month = (int(value) for value in ano_mes.split("-"))
    next_year, next_month = (year + 1, 1) if month == 12 else (year, month + 1)
    day = calendar.monthrange(next_year, next_month)[1]
    due_date = date(next_year, next_month, day)
    while due_date.weekday() >= 5:
        due_date = date(next_year, next_month, due_date.day - 1)
    return due_date.isoformat()
