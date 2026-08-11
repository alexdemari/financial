from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

import pandas as pd
import yaml

from web.readers.common import PROJECT_ROOT

CONFIG_PATH = PROJECT_ROOT / "config/cash_accounts.yaml"
BTG_CASH_PATH = PROJECT_ROOT / "data/btg/conta_corrente_all.csv"
STALE_AFTER_DAYS = 7


@dataclass(frozen=True, slots=True)
class CashAccount:
    id: str
    name: str
    institution: str
    currency: str
    category: str
    balance: float
    as_of: str


def read_cash_accounts() -> list[CashAccount]:
    """Read the local cash configuration file.

    Returns an empty list when the file does not exist or is empty.
    """
    if not CONFIG_PATH.exists():
        return []
    try:
        raw_config = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError):
        return []
    if not isinstance(raw_config, dict):
        return []
    accounts = raw_config.get("accounts", [])
    if not isinstance(accounts, list):
        return []
    return [
        _parse_account(account) for account in accounts if isinstance(account, dict)
    ]


def total_cash_brl(accounts: list[CashAccount]) -> float:
    return sum(account.balance for account in accounts)


def read_btg_cash_accounts(path: Path = BTG_CASH_PATH) -> list[CashAccount]:
    """Read BTG conta-corrente balances from the parsed CSV output."""
    if not path.exists():
        return []
    rows = _read_csv(path)
    latest_by_account: dict[str, dict[str, Any]] = {}
    for row in rows:
        account_name = _text(row.get("account"))
        if not account_name:
            continue
        current = latest_by_account.get(account_name)
        row_date = _text(row.get("date"))
        if current is None or row_date >= _text(current.get("date")):
            latest_by_account[account_name] = row
    return [
        CashAccount(
            id=f"btg_{_slug(account_name)}_cash",
            name=f"BTG — {account_name}",
            institution="BTG",
            currency="BRL",
            category="caixa",
            balance=_number(row.get("saldo")),
            as_of=_text(row.get("date")),
        )
        for account_name, row in sorted(latest_by_account.items())
    ]


def cash_accounts_are_stale(
    accounts: list[CashAccount], reference_date: date | None = None
) -> bool:
    today = reference_date or date.today()
    for account in accounts:
        if not account.as_of:
            return True
        try:
            as_of_date = date.fromisoformat(account.as_of)
        except ValueError:
            return True
        age_days = (today - as_of_date).days
        if age_days > STALE_AFTER_DAYS or age_days < 0:
            return True
    return False


def _parse_account(raw_account: dict[str, Any]) -> CashAccount:
    return CashAccount(
        id=_text(raw_account.get("id")),
        name=_text(raw_account.get("name")),
        institution=_text(raw_account.get("institution")),
        currency=_text(raw_account.get("currency")) or "BRL",
        category=_text(raw_account.get("category")),
        balance=_number(raw_account.get("balance")),
        as_of=_text(raw_account.get("as_of")),
    )


def _number(value: object) -> float:
    try:
        numeric_value = float(value) if value is not None else 0.0
        return 0.0 if numeric_value != numeric_value else numeric_value
    except (TypeError, ValueError):
        return 0.0


def _text(value: object) -> str:
    return "" if value is None else str(value).strip()


def _slug(value: str) -> str:
    normalized = re.sub(r"^btg[-_ ]*", "", value, flags=re.IGNORECASE)
    ascii_value = (
        unicodedata.normalize("NFKD", normalized)
        .encode("ascii", "ignore")
        .decode("ascii")
    )
    slug = re.sub(r"[^a-z0-9]+", "_", ascii_value.lower()).strip("_")
    return slug or "cash"


def _read_csv(path: Path) -> list[dict[str, Any]]:
    try:
        frame = pd.read_csv(path)
    except (OSError, pd.errors.EmptyDataError):
        return []
    return [
        {key: None if pd.isna(value) else value for key, value in row.items()}
        for row in frame.to_dict(orient="records")
    ]
