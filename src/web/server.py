from __future__ import annotations

import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from web.readers.common import PROJECT_ROOT, file_mtime
from web.readers.ibkr_csv import latest_ibkr_csv
from web.routers import account, dividends, history, macro, scanner

STATIC_DIR = Path(__file__).parent / "static"

app = FastAPI(title="financial dashboard", docs_url=None, redoc_url=None)
if os.environ.get("WEB_DEV_CORS") == "1":
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
        allow_methods=["GET"],
        allow_headers=["*"],
    )
for api_router in (account, history, scanner, dividends, macro):
    app.include_router(api_router.router)


@app.get("/api/status")
def get_status() -> dict:
    expected = [
        ("ibkr_positions", latest_ibkr_csv()),
        ("options_tracker", PROJECT_ROOT / "options_tracker.csv"),
        ("history", PROJECT_ROOT / "data/ibkr/history.jsonl"),
        ("scan_daily", PROJECT_ROOT / "reports/market_scanner/scan_daily.csv"),
        (
            "scanner_report",
            PROJECT_ROOT / "reports/market_scanner/daily_report.md",
        ),
        (
            "dividend_report",
            PROJECT_ROOT / "reports/dividend_tracker/dividend_daily_report.md",
        ),
    ]
    return {
        "files": [
            {
                "name": name,
                "exists": bool(path and path.exists()),
                "mtime": file_mtime(path) if path and path.exists() else None,
            }
            for name, path in expected
        ]
    }


if (STATIC_DIR / "assets").exists():
    app.mount(
        "/assets",
        StaticFiles(directory=STATIC_DIR / "assets"),
        name="assets",
    )


@app.get("/{full_path:path}")
def spa_fallback(full_path: str):
    index = STATIC_DIR / "index.html"
    if index.exists():
        return FileResponse(index)
    return {"error": "Frontend not built. Run: cd frontend && npm run build"}
