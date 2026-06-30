from fastapi import APIRouter

from web.readers.common import PROJECT_ROOT
from web.readers.markdown import render_markdown

router = APIRouter(prefix="/api")
DIVIDEND_REPORT = PROJECT_ROOT / "reports/dividend_tracker/dividend_daily_report.md"


@router.get("/report/dividends")
def get_dividend_report() -> dict:
    return render_markdown(DIVIDEND_REPORT)
