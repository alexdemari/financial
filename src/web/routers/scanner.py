from fastapi import APIRouter

from web.readers.common import PROJECT_ROOT
from web.readers.markdown import render_markdown
from web.readers.scan_csv import read_scan

router = APIRouter(prefix="/api")
SCANNER_REPORT = PROJECT_ROOT / "reports/market_scanner/daily_report.md"


@router.get("/scanner")
def get_scanner() -> dict:
    return read_scan()


@router.get("/report/scanner")
def get_scanner_report() -> dict:
    return render_markdown(SCANNER_REPORT)
