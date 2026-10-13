from fastapi import APIRouter

from web.readers.sources_reader import read_alerts, read_sources

router = APIRouter(prefix="/api")


@router.get("/sources")
def get_sources() -> dict:
    """Return local data-source metadata and critical alerts for the overview."""
    return {"sources": read_sources(), "alerts": read_alerts()}
