from __future__ import annotations

import json
from dataclasses import asdict
from datetime import date
from pathlib import Path
from typing import Any

import pandas as pd
import yaml

from irpf_report.ptax import CACHE_DIR, get_ptax
from web.readers.common import PROJECT_ROOT
from web.readers.history_jsonl import read_account_snapshot
from web.readers.ibkr_csv import read_positions

BTG_OPCOES_POS = PROJECT_ROOT / "data/btg/btg_opcoes_positions.csv"
BTG_GERAL_POS = PROJECT_ROOT / "data/btg/btg_geral_positions.csv"
BTG_RF = PROJECT_ROOT / "data/btg/renda_fixa_all.csv"
BTG_PROVENTOS = PROJECT_ROOT / "data/btg/proventos_futuros_all.csv"
BTG_CASH = PROJECT_ROOT / "data/btg/conta_corrente_all.csv"
TARGETS_PATH = PROJECT_ROOT / "config/patrimonio_targets.yaml"
PTAX_CACHE_DIR = PROJECT_ROOT / CACHE_DIR

ASSET_CLASS_ORDER = (
    "renda_fixa_br",
    "acoes_br",
    "bdr",
    "opcoes_br",
    "acoes_usd",
    "etf_usd",
    "opcoes_usd",
    "caixa",
)


def read_patrimonio(reference_date: date | None = None) -> dict[str, Any]:
    """Consolidate local IBKR and BTG position files into BRL."""
    today = reference_date or date.today()
    ptax_rate, ptax_date = _resolve_ptax(today)
    targets = _read_targets()

    ibkr = _read_ibkr_account(ptax_rate)
    btg_opcoes = _read_btg_account(BTG_OPCOES_POS, "BTG-Opções")
    btg_geral = _read_btg_account(BTG_GERAL_POS, "BTG-Geral")
    fixed_income = _read_fixed_income()
    cash = _read_btg_cash()
    proventos = _read_proventos()

    for account_key, account_name in (
        ("btg_opcoes", "BTG-Opções"),
        ("btg_geral", "BTG-Geral"),
    ):
        account = btg_opcoes if account_key == "btg_opcoes" else btg_geral
        account["renda_fixa_brl"] = fixed_income["totals_by_account"].get(
            account_name, 0.0
        )
        account["cash_brl"] = cash["totals_by_account"].get(account_name, 0.0)
        account["total_brl"] += account["renda_fixa_brl"] + account["cash_brl"]
        if account["status"] == "no_data" and (
            account["renda_fixa_brl"] or account["cash_brl"]
        ):
            account["status"] = "ok"
            account["hint"] = None

    total_brl = ibkr["nlv_brl"] + btg_opcoes["total_brl"] + btg_geral["total_brl"]
    allocation_values = _allocation_values(
        ibkr, btg_opcoes, btg_geral, fixed_income, cash, ptax_rate
    )
    allocation = _compare_to_targets(allocation_values, total_brl, targets)
    currency_mix = _currency_mix(
        ibkr["nlv_brl"],
        btg_opcoes["total_brl"] + btg_geral["total_brl"],
        total_brl,
        targets,
    )

    return {
        "total_brl": total_brl,
        "complete": not (
            ibkr["status"] == "ptax_unavailable"
            or ibkr["status"] == "no_data"
            or btg_opcoes["status"] == "no_data"
            or btg_geral["status"] == "no_data"
        ),
        "ptax": ptax_rate,
        "ptax_date": ptax_date,
        "accounts": {
            "ibkr": ibkr,
            "btg_opcoes": btg_opcoes,
            "btg_geral": btg_geral,
        },
        "renda_fixa": fixed_income,
        "allocation": allocation,
        "allocation_vs_targets": allocation,
        "currency_mix": currency_mix,
        "proventos_futuros": proventos["rows"],
        "proventos_total_brl": proventos["total_brl"],
    }


def _resolve_ptax(reference_date: date) -> tuple[float | None, str | None]:
    cached = _latest_cached_ptax()
    if cached is not None:
        return cached
    rate = get_ptax(reference_date, cache_dir=PTAX_CACHE_DIR)
    if rate is None:
        return None, None
    cached = _latest_cached_ptax()
    return cached if cached is not None else (rate, reference_date.isoformat())


def _latest_cached_ptax() -> tuple[float, str] | None:
    if not PTAX_CACHE_DIR.exists():
        return None
    for cache_path in sorted(PTAX_CACHE_DIR.glob("*.json"), reverse=True):
        try:
            rate = float(json.loads(cache_path.read_text())["cotacaoVenda"])
            date.fromisoformat(cache_path.stem)
        except (KeyError, TypeError, ValueError, json.JSONDecodeError):
            continue
        return rate, cache_path.stem
    return None


def _read_targets() -> dict[str, Any]:
    return yaml.safe_load(TARGETS_PATH.read_text(encoding="utf-8"))


def _read_ibkr_account(ptax_rate: float | None) -> dict[str, Any]:
    snapshot = read_account_snapshot()
    positions = [asdict(position) for position in read_positions()]
    if snapshot is None:
        return {
            "status": "no_data",
            "hint": "Run: just ibkr-positions",
            "nlv_usd": 0.0,
            "nlv_brl": 0.0,
            "cash_usd": 0.0,
            "positions": positions,
        }
    return {
        "status": "ok" if ptax_rate is not None else "ptax_unavailable",
        "hint": None if ptax_rate is not None else "PTAX unavailable",
        "nlv_usd": snapshot.nlv,
        "nlv_brl": snapshot.nlv * ptax_rate if ptax_rate is not None else 0.0,
        "cash_usd": snapshot.cash,
        "as_of": snapshot.as_of,
        "positions": positions,
    }


def _read_btg_account(path: Path, account_name: str) -> dict[str, Any]:
    if not path.exists():
        return {
            "status": "no_data",
            "hint": "Run: just btg-parse",
            "total_brl": 0.0,
            "positions": [],
        }
    rows = _read_csv(path)
    positions = [
        row for row in rows if _text(row.get("asset_type")).upper() != "ALUGUEL"
    ]
    return {
        "status": "ok",
        "hint": None,
        "total_brl": sum(_number(row.get("saldo_bruto")) for row in positions),
        "account": account_name,
        "positions": positions,
    }


def _read_fixed_income() -> dict[str, Any]:
    rows = _read_csv(BTG_RF)
    totals = _totals_by_account(rows, ("saldo_liquido", "saldo_bruto"))
    return {
        "status": "ok" if BTG_RF.exists() else "no_data",
        "hint": None if BTG_RF.exists() else "Run: just btg-parse",
        "total_brl": sum(totals.values()),
        "totals_by_account": totals,
        "positions": rows,
    }


def _read_btg_cash() -> dict[str, Any]:
    rows = _read_csv(BTG_CASH)
    latest_by_account: dict[str, dict[str, Any]] = {}
    for row in rows:
        account = _text(row.get("account"))
        if not account:
            continue
        current = latest_by_account.get(account)
        if current is None or _text(row.get("date")) >= _text(current.get("date")):
            latest_by_account[account] = row
    return {
        "rows": list(latest_by_account.values()),
        "totals_by_account": {
            account: _number(row.get("saldo"))
            for account, row in latest_by_account.items()
        },
    }


def _read_proventos() -> dict[str, Any]:
    rows = _read_csv(BTG_PROVENTOS)
    normalized = [
        {
            "data_liquidacao": _text(row.get("data_liquidacao")),
            "descricao": _text(row.get("descricao")),
            "valor": _number(row.get("valor")),
            "account": _text(row.get("account")),
        }
        for row in rows
    ]
    return {
        "rows": normalized,
        "total_brl": sum(row["valor"] for row in normalized),
    }


def _allocation_values(
    ibkr: dict[str, Any],
    btg_opcoes: dict[str, Any],
    btg_geral: dict[str, Any],
    fixed_income: dict[str, Any],
    cash: dict[str, Any],
    ptax_rate: float | None,
) -> dict[str, float]:
    values = dict.fromkeys(ASSET_CLASS_ORDER, 0.0)
    conversion_rate = ptax_rate or 0.0
    ibkr_position_total_brl = 0.0
    ibkr_mapping = {"STK": "acoes_usd", "ETF": "etf_usd", "OPT": "opcoes_usd"}
    for position in ibkr["positions"]:
        value_brl = _number(position.get("market_value")) * conversion_rate
        asset_class = ibkr_mapping.get(_text(position.get("asset_type")).upper())
        if asset_class:
            values[asset_class] += value_brl
            ibkr_position_total_brl += value_brl
    values["caixa"] += ibkr["nlv_brl"] - ibkr_position_total_brl

    btg_mapping = {
        "ACAO": "acoes_br",
        "AÇÃO": "acoes_br",
        "BDR": "bdr",
        "OPT": "opcoes_br",
    }
    for account in (btg_opcoes, btg_geral):
        for position in account["positions"]:
            asset_class = btg_mapping.get(_text(position.get("asset_type")).upper())
            if asset_class:
                values[asset_class] += _number(position.get("saldo_bruto"))
    values["renda_fixa_br"] = fixed_income["total_brl"]
    values["caixa"] += sum(cash["totals_by_account"].values())
    return values


def _compare_to_targets(
    values: dict[str, float], total_brl: float, targets: dict[str, Any]
) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for asset_class in ASSET_CLASS_ORDER:
        config = targets["asset_classes"][asset_class]
        percentage = values[asset_class] / total_brl * 100 if total_brl else 0.0
        result[asset_class] = {
            "label": config["label"],
            "color": config["color"],
            "value_brl": values[asset_class],
            "pct_of_total": percentage,
            "target_min": config["target_min"],
            "target_max": config["target_max"],
            "status": _target_status(
                percentage, config["target_min"], config["target_max"]
            ),
            "severity": _target_severity(
                percentage, config["target_min"], config["target_max"]
            ),
        }
    return result


def _currency_mix(
    usd_brl: float,
    brl: float,
    total_brl: float,
    targets: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    result = {}
    for key, value in (("brl_pct", brl), ("usd_pct", usd_brl)):
        config = targets["currency_mix"][key]
        percentage = value / total_brl * 100 if total_brl else 0.0
        result[key] = {
            "label": config["label"],
            "value_brl": value,
            "pct_of_total": percentage,
            "target_min": config["target_min"],
            "target_max": config["target_max"],
            "status": _target_status(
                percentage, config["target_min"], config["target_max"]
            ),
        }
    return result


def _target_status(value: float, target_min: float, target_max: float) -> str:
    if value < target_min:
        return "below"
    if value > target_max:
        return "above"
    return "within"


def _target_severity(value: float, target_min: float, target_max: float) -> str:
    if target_min <= value <= target_max:
        return "within"
    distance = target_min - value if value < target_min else value - target_max
    return "near" if distance <= 5 else "outside"


def _totals_by_account(
    rows: list[dict[str, Any]], value_columns: tuple[str, ...]
) -> dict[str, float]:
    totals: dict[str, float] = {}
    for row in rows:
        account = _text(row.get("account"))
        if not account:
            continue
        value = next(
            (
                _number(row.get(column))
                for column in value_columns
                if row.get(column) not in (None, "")
            ),
            0.0,
        )
        totals[account] = totals.get(account, 0.0) + value
    return totals


def _read_csv(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    try:
        frame = pd.read_csv(path)
    except pd.errors.EmptyDataError:
        return []
    return [
        {key: None if pd.isna(value) else value for key, value in row.items()}
        for row in frame.to_dict(orient="records")
    ]


def _number(value: object) -> float:
    try:
        return float(value) if value is not None and not pd.isna(value) else 0.0
    except (TypeError, ValueError):
        return 0.0


def _text(value: object) -> str:
    return "" if value is None or pd.isna(value) else str(value).strip()
