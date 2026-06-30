from fastapi import APIRouter, Query

from web.readers.history_jsonl import read_history

router = APIRouter(prefix="/api")


@router.get("/history")
def get_history(days: int = Query(default=90, ge=1, le=3650)) -> list[dict]:
    return read_history(days)
