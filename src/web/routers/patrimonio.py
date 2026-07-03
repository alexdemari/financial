from fastapi import APIRouter

from web.readers.patrimonio_reader import read_patrimonio

router = APIRouter(prefix="/api")


@router.get("/patrimonio")
def get_patrimonio() -> dict:
    return read_patrimonio()
