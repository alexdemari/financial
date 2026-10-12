from fastapi import APIRouter

from web.readers.sources_reader import read_sources

router = APIRouter(prefix="/api")


@router.get("/sources")
def get_sources() -> dict:
    """Return only local data-source metadata for the overview."""
    return {"sources": read_sources()}
