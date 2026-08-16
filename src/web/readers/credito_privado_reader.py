from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any

import yaml

from web.readers.common import PROJECT_ROOT

CONFIG_PATH = PROJECT_ROOT / "config/credito_privado.yaml"


@dataclass(frozen=True, slots=True)
class CreditoPrivadoItem:
    id: str
    emissor: str
    produto: str
    indexador: str
    taxa_pct: float | str
    valor_investido: float
    valor_atual: float
    valor_estimado: bool
    data_aplicacao: str
    vencimento: str
    liquidez_diaria: bool
    data_liquidez: str | None
    conta: str
    status: str


def read_credito_privado(
    reference_date: date | None = None
) -> list[CreditoPrivadoItem]:
    """Read the local private-credit configuration.

    Missing, empty, malformed, or structurally invalid configuration degrades
    to an empty list, as does the cash reader.
    """
    if not CONFIG_PATH.exists():
        return []
    try:
        raw_config = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError):
        return []
    if not isinstance(raw_config, dict):
        return []
    entries = raw_config.get("items", [])
    if not isinstance(entries, list):
        return []

    today = reference_date or date.today()
    return [_parse_item(entry, today) for entry in entries if isinstance(entry, dict)]


def total_credito_privado_brl(items: list[CreditoPrivadoItem]) -> float:
    """Sum active item values, including conservative estimates."""
    return sum(item.valor_atual for item in items if item.status == "ativo")


def _parse_item(entry: dict[str, Any], today: date) -> CreditoPrivadoItem:
    valor_investido = _number(entry.get("valor_investido"))
    valor_atual_raw = entry.get("valor_atual")
    valor_estimado = valor_atual_raw is None
    valor_atual = valor_investido if valor_estimado else _number(valor_atual_raw)
    vencimento = _text(entry.get("vencimento"))
    return CreditoPrivadoItem(
        id=_text(entry.get("id")),
        emissor=_text(entry.get("emissor")),
        produto=_text(entry.get("produto")),
        indexador=_text(entry.get("indexador")),
        taxa_pct=entry.get("taxa_pct", ""),
        valor_investido=valor_investido,
        valor_atual=valor_atual,
        valor_estimado=valor_estimado,
        data_aplicacao=_text(entry.get("data_aplicacao")),
        vencimento=vencimento,
        liquidez_diaria=bool(entry.get("liquidez_diaria", False)),
        data_liquidez=(
            None
            if entry.get("data_liquidez") is None
            else _text(entry.get("data_liquidez"))
        ),
        conta=_text(entry.get("conta")),
        status="ativo" if _is_ativo(vencimento, today) else "vencido",
    )


def _is_ativo(vencimento: str, today: date) -> bool:
    if not vencimento:
        return True
    try:
        vencimento_date = date.fromisoformat(vencimento)
    except ValueError:
        return False
    return vencimento_date >= today


def _number(value: object) -> float:
    try:
        numeric_value = float(value) if value is not None else 0.0
        return 0.0 if numeric_value != numeric_value else numeric_value
    except (TypeError, ValueError):
        return 0.0


def _text(value: object) -> str:
    return "" if value is None else str(value).strip()
