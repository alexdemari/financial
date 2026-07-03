from __future__ import annotations

import datetime as dt
import re
from dataclasses import dataclass
from pathlib import Path

import openpyxl

from btg_parser.models import (
    BTGContaCorrenteMovimento,
    BTGFixedIncome,
    BTGPosition,
    BTGProvento,
    BTGTrade,
)

DIRECTION_MAP = {
    "COMPRA": "BUY",
    "VENDA": "SELL",
    "VENDA DEFINITIVA": "SELL",
    "RECEBIMENTO DIVIDENDOS": "DIVIDEND",
    "JUROS S/CAPITAL": "JCP",
    "EMPRESTIMO": "EMPRESTIMO",
    "VENCIMENTO DA OPCAO": "EXPIRATION",
    "BONIFICACAO/SPLIT": "OTHER",
}

ASSET_TYPE_ACOES = "ACAO"
ASSET_TYPE_OPCOES = "OPT"
ASSET_TYPE_BDR = "BDR"
ASSET_TYPE_ALUGUEL = "ALUGUEL"


def _find_section(rows: list[tuple], header_text: str) -> int | None:
    """Scan rows for a cell containing header_text (partial match). Returns row index."""
    for i, row in enumerate(rows):
        if any(isinstance(cell, str) and header_text in cell for cell in row):
            return i
    return None


def _normalize(text: str) -> str:
    return " ".join(text.split())


def _header_map(rows: list[tuple], header_row_idx: int) -> dict[str, int]:
    """Map normalized column header text to column index for the given row."""
    header_row = rows[header_row_idx]
    return {
        _normalize(cell): idx
        for idx, cell in enumerate(header_row)
        if isinstance(cell, str) and cell.strip()
    }


def _is_blank_row(row: tuple) -> bool:
    return all(cell is None for cell in row)


def _is_total_row(row: tuple) -> bool:
    first = next((cell for cell in row if cell is not None), None)
    return isinstance(first, str) and first.strip().lower().startswith("total")


def _read_table_rows(rows: list[tuple], start_idx: int) -> list[tuple]:
    """Read data rows after start_idx until a blank row or a totals row."""
    data_rows = []
    for row in rows[start_idx:]:
        if _is_blank_row(row) or _is_total_row(row):
            break
        data_rows.append(row)
    return data_rows


def _cell(row: tuple, header_map: dict[str, int], name: str) -> object:
    idx = header_map.get(name)
    return row[idx] if idx is not None and idx < len(row) else None


def _float(value: object) -> float | None:
    if value is None or value == "-" or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _text(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text or text == "-":
        return None
    return text


def _date_text(value: object) -> str | None:
    if value is None or value == "-" or value == "":
        return None
    if isinstance(value, dt.datetime):
        return value.date().isoformat()
    if isinstance(value, dt.date):
        return value.isoformat()
    try:
        return dt.datetime.fromisoformat(str(value)).date().isoformat()
    except ValueError:
        return None


def _direction(raw_transacao: object) -> str:
    text = (_text(raw_transacao) or "").upper()
    return DIRECTION_MAP.get(text, text or "OTHER")


def parse_acoes_positions(
    rows: list[tuple], account: str, source_file: str, period_end: str | None
) -> list[BTGPosition]:
    section = _find_section(rows, "Posição > Ações")
    if section is None:
        return []
    header_map = _header_map(rows, section + 1)
    positions = []
    for row in _read_table_rows(rows, section + 2):
        positions.append(
            BTGPosition(
                account=account,
                codigo=_text(_cell(row, header_map, "Código")) or "",
                nome=_text(_cell(row, header_map, "Ação")) or "",
                asset_type=ASSET_TYPE_ACOES,
                quantidade=_float(_cell(row, header_map, "Qtde.")) or 0.0,
                preco_fechamento=_float(_cell(row, header_map, "Preço Fechamento R$")),
                preco_medio=_float(_cell(row, header_map, "Preço Médio R$")),
                saldo_bruto=_float(_cell(row, header_map, "Saldo Bruto R$")),
                currency="BRL",
                tipo_opcao=None,
                preco_exercicio=None,
                data_exercicio=None,
                posicao=None,
                taxa_ano_pct=None,
                valor_repasse=None,
                source_file=source_file,
                period_end=period_end,
            )
        )
    return positions


def parse_bdr_positions(
    rows: list[tuple], account: str, source_file: str, period_end: str | None
) -> list[BTGPosition]:
    section = _find_section(rows, "Posição > BDR")
    if section is None:
        return []
    header_map = _header_map(rows, section + 1)
    positions = []
    for row in _read_table_rows(rows, section + 2):
        positions.append(
            BTGPosition(
                account=account,
                codigo=_text(_cell(row, header_map, "Código")) or "",
                nome=_text(_cell(row, header_map, "Ativo")) or "",
                asset_type=ASSET_TYPE_BDR,
                quantidade=_float(_cell(row, header_map, "Qtde.")) or 0.0,
                preco_fechamento=_float(_cell(row, header_map, "Preço Fechamento R$")),
                preco_medio=_float(_cell(row, header_map, "Preço Médio R$")),
                saldo_bruto=_float(_cell(row, header_map, "Saldo Bruto R$")),
                currency="BRL",
                tipo_opcao=None,
                preco_exercicio=None,
                data_exercicio=None,
                posicao=None,
                taxa_ano_pct=None,
                valor_repasse=None,
                source_file=source_file,
                period_end=period_end,
            )
        )
    return positions


def parse_opcoes_positions(
    rows: list[tuple], account: str, source_file: str, period_end: str | None
) -> list[BTGPosition]:
    section = _find_section(rows, "Posição > Opções")
    if section is None:
        return []
    header_map = _header_map(rows, section + 1)
    data_exercicio_key = next(
        (key for key in header_map if key.startswith("Data Exercício")),
        "Data Exercício",
    )
    positions = []
    for row in _read_table_rows(rows, section + 2):
        positions.append(
            BTGPosition(
                account=account,
                codigo=_text(_cell(row, header_map, "Código")) or "",
                nome=_text(_cell(row, header_map, "Ativo Ref.")) or "",
                asset_type=ASSET_TYPE_OPCOES,
                quantidade=_float(_cell(row, header_map, "Qtde.")) or 0.0,
                preco_fechamento=None,
                preco_medio=None,
                saldo_bruto=_float(_cell(row, header_map, "Valor de Mercado R$")),
                currency="BRL",
                tipo_opcao=_text(_cell(row, header_map, "Tipo")),
                preco_exercicio=_float(_cell(row, header_map, "Preço Exercício R$")),
                data_exercicio=_date_text(_cell(row, header_map, data_exercicio_key)),
                posicao=_text(_cell(row, header_map, "Posição")),
                taxa_ano_pct=None,
                valor_repasse=None,
                source_file=source_file,
                period_end=period_end,
            )
        )
    return positions


def parse_aluguel_positions(
    rows: list[tuple], account: str, source_file: str, period_end: str | None
) -> list[BTGPosition]:
    section = _find_section(rows, "Posição > Ações | Aluguel")
    if section is None:
        return []
    header_map = _header_map(rows, section + 1)
    positions = []
    for row in _read_table_rows(rows, section + 2):
        positions.append(
            BTGPosition(
                account=account,
                codigo=_text(_cell(row, header_map, "Código")) or "",
                nome="",
                asset_type=ASSET_TYPE_ALUGUEL,
                quantidade=_float(_cell(row, header_map, "Qtde.")) or 0.0,
                preco_fechamento=None,
                preco_medio=None,
                saldo_bruto=_float(_cell(row, header_map, "Valor Contratado R$")),
                currency="BRL",
                tipo_opcao=None,
                preco_exercicio=None,
                data_exercicio=None,
                posicao=_text(_cell(row, header_map, "Posição")),
                taxa_ano_pct=_float(_cell(row, header_map, "Taxa Ano %")),
                valor_repasse=_float(_cell(row, header_map, "Valor Repasse R$")),
                source_file=source_file,
                period_end=period_end,
            )
        )
    return positions


def parse_acoes_movimentacoes(
    rows: list[tuple], account: str, source_file: str
) -> list[BTGTrade]:
    section = _find_section(rows, "Movimentação > Ações")
    if section is None:
        return []
    header_map = _header_map(rows, section + 1)
    return _read_stock_like_trades(
        rows, section + 2, header_map, account, source_file, ASSET_TYPE_ACOES
    )


def parse_bdr_movimentacoes(
    rows: list[tuple], account: str, source_file: str
) -> list[BTGTrade]:
    section = _find_section(rows, "Movimentação > BDR")
    if section is None:
        return []
    header_map = _header_map(rows, section + 1)
    return _read_stock_like_trades(
        rows, section + 2, header_map, account, source_file, ASSET_TYPE_BDR
    )


def _read_stock_like_trades(
    rows: list[tuple],
    start_idx: int,
    header_map: dict[str, int],
    account: str,
    source_file: str,
    asset_type: str,
) -> list[BTGTrade]:
    trades = []
    for row in _read_table_rows(rows, start_idx):
        trades.append(
            BTGTrade(
                date=_date_text(_cell(row, header_map, "Data")) or "",
                account=account,
                symbol=_text(_cell(row, header_map, "Código")) or "",
                asset_type=asset_type,
                direction=_direction(_cell(row, header_map, "Transação")),
                quantity=_float(_cell(row, header_map, "Qtde.")) or 0.0,
                price=_float(_cell(row, header_map, "Preço R$")),
                proceeds=_float(_cell(row, header_map, "Valor Bruto R$")),
                commission=_float(
                    _cell(row, header_map, "Corretagem e Emolumentos R$")
                ),
                net_value=_float(_cell(row, header_map, "Valor Líquido R$")),
                pnl_realized=None,
                currency="BRL",
                option_type=None,
                expiration=None,
                source_file=source_file,
            )
        )
    return trades


def parse_opcoes_movimentacoes(
    rows: list[tuple], account: str, source_file: str
) -> list[BTGTrade]:
    section = _find_section(rows, "Movimentação > Opções")
    if section is None:
        return []
    header_map = _header_map(rows, section + 1)
    trades = []
    for row in _read_table_rows(rows, section + 2):
        trades.append(
            BTGTrade(
                date=_date_text(_cell(row, header_map, "Data")) or "",
                account=account,
                symbol=_text(_cell(row, header_map, "Código")) or "",
                asset_type=ASSET_TYPE_OPCOES,
                direction=_direction(_cell(row, header_map, "Transação")),
                quantity=_float(_cell(row, header_map, "Qtde. de Contratos")) or 0.0,
                price=_float(_cell(row, header_map, "Prêmio de Mercado R$")),
                proceeds=_float(_cell(row, header_map, "Valor Financeiro Bruto R$")),
                commission=_float(
                    _cell(row, header_map, "Corretagem e Emolumentos R$")
                ),
                net_value=_float(_cell(row, header_map, "Prêmio Pago/Recebido R$")),
                pnl_realized=None,
                currency="BRL",
                option_type=_text(_cell(row, header_map, "Tipo")),
                expiration=_date_text(_cell(row, header_map, "Data Exercício")),
                source_file=source_file,
            )
        )
    return trades


def parse_cdb_positions(
    rows: list[tuple], account: str, source_file: str, period_end: str | None
) -> list[BTGFixedIncome]:
    section = _find_section(rows, "Posição > CDB")
    if section is None:
        return []
    header_map = _header_map(rows, section + 1)
    entries = []
    for row in _read_table_rows(rows, section + 2):
        entries.append(
            BTGFixedIncome(
                account=account,
                emissor=_text(_cell(row, header_map, "Emissor")) or "",
                ativo=_text(_cell(row, header_map, "Ativo")) or "",
                emissao=_date_text(_cell(row, header_map, "Emissão")),
                vencimento=_date_text(_cell(row, header_map, "Vencimento")),
                quantidade=_float(_cell(row, header_map, "Quantidade")),
                preco=_float(_cell(row, header_map, "Preço R$")),
                saldo_bruto=_float(_cell(row, header_map, "Saldo Bruto R$")),
                saldo_liquido=_float(_cell(row, header_map, "Saldo Líquido R$")),
                currency="BRL",
                source_file=source_file,
            )
        )
    return entries


def parse_conta_corrente(
    rows: list[tuple], account: str, source_file: str
) -> list[BTGContaCorrenteMovimento]:
    section = _find_section(rows, "Saldo conta investimentos")
    if section is None:
        return []
    header_map = _header_map(rows, section)
    entries = []
    for row in _read_table_rows(rows, section + 1):
        entries.append(
            BTGContaCorrenteMovimento(
                account=account,
                date=_date_text(_cell(row, header_map, "Data")) or "",
                descricao=_text(_cell(row, header_map, "Descrição")) or "",
                movimentacao=_float(_cell(row, header_map, "Movimentação R$")),
                saldo=_float(_cell(row, header_map, "Saldo conta investimentos R$")),
                currency="BRL",
                source_file=source_file,
            )
        )
    return entries


def parse_proventos_futuros(
    rows: list[tuple], account: str, source_file: str
) -> list[BTGProvento]:
    section = _find_section(rows, "Data Liquidação")
    if section is None:
        return []
    header_map = _header_map(rows, section)
    entries = []
    for row in _read_table_rows(rows, section + 1):
        valor = _float(_cell(row, header_map, "Valor R$"))
        if valor is None:
            continue
        entries.append(
            BTGProvento(
                account=account,
                data_liquidacao=_date_text(_cell(row, header_map, "Data Liquidação"))
                or "",
                descricao=_text(_cell(row, header_map, "Descrição")) or "",
                valor=valor,
                currency="BRL",
                source_file=source_file,
            )
        )
    return entries


def _extract_period_end(sumario_rows: list[tuple]) -> str | None:
    """Find the most recent 'Saldo Bruto R$ dd/mm/yy' column header in the Sumário sheet."""
    dates = []
    for row in sumario_rows:
        for cell in row:
            if not isinstance(cell, str):
                continue
            match = re.search(r"(\d{2})/(\d{2})/(\d{2})", cell)
            if match:
                day, month, year = match.groups()
                dates.append(dt.date(2000 + int(year), int(month), int(day)))
    return max(dates).isoformat() if dates else None


@dataclass(frozen=True)
class WorkbookData:
    positions: list[BTGPosition]
    trades: list[BTGTrade]
    fixed_income: list[BTGFixedIncome]
    proventos: list[BTGProvento]
    conta_corrente: list[BTGContaCorrenteMovimento]


def parse_workbook(path: Path, account: str) -> WorkbookData:
    """Parse a BTG extrato XLSX into canonical records for a single account."""
    workbook = openpyxl.load_workbook(path, read_only=True, data_only=True)
    source_file = path.name

    period_end = None
    if "Sumario" in workbook.sheetnames:
        sumario_rows = list(workbook["Sumario"].iter_rows(values_only=True))
        period_end = _extract_period_end(sumario_rows)

    positions: list[BTGPosition] = []
    trades: list[BTGTrade] = []
    fixed_income: list[BTGFixedIncome] = []
    proventos: list[BTGProvento] = []
    conta_corrente: list[BTGContaCorrenteMovimento] = []

    if "Renda Variavel" in workbook.sheetnames:
        rv_rows = list(workbook["Renda Variavel"].iter_rows(values_only=True))
        positions += parse_acoes_positions(rv_rows, account, source_file, period_end)
        positions += parse_bdr_positions(rv_rows, account, source_file, period_end)
        positions += parse_opcoes_positions(rv_rows, account, source_file, period_end)
        positions += parse_aluguel_positions(rv_rows, account, source_file, period_end)
        trades += parse_acoes_movimentacoes(rv_rows, account, source_file)
        trades += parse_bdr_movimentacoes(rv_rows, account, source_file)
        trades += parse_opcoes_movimentacoes(rv_rows, account, source_file)

    if "Renda Fixa" in workbook.sheetnames:
        rf_rows = list(workbook["Renda Fixa"].iter_rows(values_only=True))
        fixed_income += parse_cdb_positions(rf_rows, account, source_file, period_end)

    if "Valores em Trânsito" in workbook.sheetnames:
        vt_rows = list(workbook["Valores em Trânsito"].iter_rows(values_only=True))
        proventos += parse_proventos_futuros(vt_rows, account, source_file)

    if "Conta Corrente" in workbook.sheetnames:
        cc_rows = list(workbook["Conta Corrente"].iter_rows(values_only=True))
        conta_corrente += parse_conta_corrente(cc_rows, account, source_file)

    workbook.close()
    return WorkbookData(
        positions=positions,
        trades=trades,
        fixed_income=fixed_income,
        proventos=proventos,
        conta_corrente=conta_corrente,
    )
