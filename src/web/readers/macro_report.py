from __future__ import annotations

from web.readers.common import PROJECT_ROOT, file_mtime

REPORT_PATH = PROJECT_ROOT / "reports/market_scanner/daily_report.md"
LABELS = {
    "Selic (meta)": "selic",
    "USD/BRL (PTAX)": "usd_brl",
    "S&P 500": "sp500",
    "Ibovespa": "ibov",
}


def read_macro() -> dict:
    result = {key: None for key in LABELS.values()}
    result["last_updated"] = None
    if not REPORT_PATH.exists():
        return result
    for line in REPORT_PATH.read_text(encoding="utf-8").splitlines():
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if len(cells) != 2:
            continue
        label, value = cells
        key = LABELS.get(label)
        if key is not None:
            result[key] = value
    result["last_updated"] = file_mtime(REPORT_PATH)
    return result
