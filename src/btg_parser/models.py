from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class BTGPosition:
    account: str
    codigo: str
    nome: str
    asset_type: str
    quantidade: float
    preco_fechamento: float | None
    preco_medio: float | None
    saldo_bruto: float | None
    currency: str
    tipo_opcao: str | None
    preco_exercicio: float | None
    data_exercicio: str | None
    posicao: str | None
    taxa_ano_pct: float | None
    valor_repasse: float | None
    source_file: str
    period_end: str | None


@dataclass(frozen=True)
class BTGTrade:
    date: str
    account: str
    symbol: str
    asset_type: str
    direction: str
    quantity: float
    price: float | None
    proceeds: float | None
    commission: float | None
    net_value: float | None
    pnl_realized: float | None
    currency: str
    option_type: str | None
    expiration: str | None
    source_file: str


@dataclass(frozen=True)
class BTGFixedIncome:
    account: str
    emissor: str
    ativo: str
    emissao: str | None
    vencimento: str | None
    quantidade: float | None
    preco: float | None
    saldo_bruto: float | None
    saldo_liquido: float | None
    currency: str
    source_file: str


@dataclass(frozen=True)
class BTGProvento:
    account: str
    data_liquidacao: str
    descricao: str
    valor: float
    currency: str
    source_file: str


@dataclass(frozen=True)
class BTGContaCorrenteMovimento:
    account: str
    date: str
    descricao: str
    movimentacao: float | None
    saldo: float | None
    currency: str
    source_file: str
