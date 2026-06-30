from fastapi import APIRouter

from web.readers.macro_report import read_macro

router = APIRouter(prefix="/api")


@router.get("/macro")
def get_macro() -> dict:
    return read_macro()
