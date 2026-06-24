from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path

import requests

CACHE_DIR = Path("data/cache/ptax")
_BCB_URL = (
    "https://olinda.bcb.gov.br/olinda/servico/PTAX/versao/v1/odata/"
    "CotacaoDolarDia(dataCotacao=@dataCotacao)?"
    "@dataCotacao='{date}'&$format=json&$select=cotacaoVenda"
)


def get_ptax(
    trade_date: date, max_lookback: int = 3, cache_dir: Path = CACHE_DIR
) -> float | None:
    """Return PTAX sell rate for trade_date. Walks back up to max_lookback days for weekends/holidays."""
    for delta in range(max_lookback + 1):
        d = trade_date - timedelta(days=delta)
        cached = _load_cache(d, cache_dir)
        if cached is not None:
            return cached
        rate = _fetch_bcb(d)
        if rate is not None:
            _save_cache(d, rate, cache_dir)
            return rate
    return None


def _bcb_date_fmt(d: date) -> str:
    return d.strftime("%m-%d-%Y")


def _cache_path(d: date, cache_dir: Path) -> Path:
    return cache_dir / f"{d.isoformat()}.json"


def _load_cache(d: date, cache_dir: Path) -> float | None:
    p = _cache_path(d, cache_dir)
    if p.exists():
        data = json.loads(p.read_text())
        return data.get("cotacaoVenda")
    return None


def _save_cache(d: date, rate: float, cache_dir: Path) -> None:
    cache_dir.mkdir(parents=True, exist_ok=True)
    _cache_path(d, cache_dir).write_text(json.dumps({"cotacaoVenda": rate}))


def _fetch_bcb(d: date) -> float | None:
    url = _BCB_URL.format(date=_bcb_date_fmt(d))
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()
        values = data.get("value", [])
        if values:
            return float(values[0]["cotacaoVenda"])
    except Exception:
        pass
    return None
