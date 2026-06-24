from __future__ import annotations

import json
import urllib.request
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta


@dataclass
class MacroSnapshot:
    selic_pct: float | None
    usd_brl: float | None
    sp500_close: float | None
    sp500_change_pct: float | None
    ibov_close: float | None
    ibov_change_pct: float | None
    fetched_at: str  # ISO datetime


_BCB_SELIC_URL = (
    "https://api.bcb.gov.br/dados/serie/bcdata.sgs.432/dados/ultimos/1?formato=json"
)
_BCB_PTAX_URL = (
    "https://olinda.bcb.gov.br/olinda/servico/PTAX/versao/v1/odata/"
    "CotacaoDolarDia(dataCotacao=@dataCotacao)?"
    "@dataCotacao='{date}'&$format=json&$select=cotacaoVenda"
)
_TIMEOUT = 5


def _fetch_selic() -> float | None:
    try:
        with urllib.request.urlopen(_BCB_SELIC_URL, timeout=_TIMEOUT) as resp:
            data = json.loads(resp.read())
            if data:
                return float(str(data[0]["valor"]).replace(",", "."))
    except Exception:
        pass
    return None


def _fetch_ptax(target_date: date, max_lookback: int = 3) -> float | None:
    for delta in range(max_lookback + 1):
        d = target_date - timedelta(days=delta)
        url = _BCB_PTAX_URL.format(date=d.strftime("%m-%d-%Y"))
        try:
            with urllib.request.urlopen(url, timeout=_TIMEOUT) as resp:
                data = json.loads(resp.read())
                values = data.get("value", [])
                if values:
                    return float(values[0]["cotacaoVenda"])
        except Exception:
            pass
    return None


def _fetch_equity(ticker: str) -> tuple[float | None, float | None]:
    """Return (last_price, change_pct_1d). Both None on any failure."""
    try:
        import yfinance as yf

        info = yf.Ticker(ticker).fast_info
        last_price = getattr(info, "last_price", None)
        prev_close = getattr(info, "previous_close", None)
        if last_price is None or prev_close is None or prev_close == 0:
            return None, None
        change_pct = (last_price - prev_close) / prev_close * 100.0
        return float(last_price), float(change_pct)
    except Exception:
        return None, None


def fetch_macro() -> MacroSnapshot:
    """Fetch all macro indicators. All failures return None for affected field. Never raises."""
    selic = _fetch_selic()
    usd_brl = _fetch_ptax(date.today())
    sp500_close, sp500_change_pct = _fetch_equity("^GSPC")
    ibov_close, ibov_change_pct = _fetch_equity("^BVSP")

    return MacroSnapshot(
        selic_pct=selic,
        usd_brl=usd_brl,
        sp500_close=sp500_close,
        sp500_change_pct=sp500_change_pct,
        ibov_close=ibov_close,
        ibov_change_pct=ibov_change_pct,
        fetched_at=datetime.now(UTC).isoformat(),
    )


def _fmt(v: float | None, fmt_str: str, suffix: str = "") -> str:
    return f"{v:{fmt_str}}{suffix}" if v is not None else "N/A"


def format_macro_block(snap: MacroSnapshot) -> str:
    """Markdown table for the daily report header."""
    sp500_str = (
        f"{_fmt(snap.sp500_close, ',.0f')} ({_fmt(snap.sp500_change_pct, '+.2f', '%')})"
    )
    ibov_str = (
        f"{_fmt(snap.ibov_close, ',.0f')} ({_fmt(snap.ibov_change_pct, '+.2f', '%')})"
    )
    return (
        f"## Macro Context — {snap.fetched_at[:10]}\n"
        "\n"
        "| Indicator | Value |\n"
        "|-----------|-------|\n"
        f"| Selic (meta) | {_fmt(snap.selic_pct, '.2f', '%')} |\n"
        f"| USD/BRL (PTAX) | {_fmt(snap.usd_brl, '.4f')} |\n"
        f"| S&P 500 | {sp500_str} |\n"
        f"| Ibovespa | {ibov_str} |\n"
    )


def format_macro_prompt_block(snap: MacroSnapshot) -> str:
    """Compact single-line version for LLM prompt injection (≤150 tokens)."""
    parts = [
        f"Selic={_fmt(snap.selic_pct, '.2f', '%')}",
        f"USD/BRL={_fmt(snap.usd_brl, '.4f')}",
        f"SP500={_fmt(snap.sp500_close, ',.0f')}({_fmt(snap.sp500_change_pct, '+.2f', '%')})",
        f"IBOV={_fmt(snap.ibov_close, ',.0f')}({_fmt(snap.ibov_change_pct, '+.2f', '%')})",
    ]
    return f"[Macro {snap.fetched_at[:10]}] {' | '.join(parts)}"
