"""
Filtro restrito: autocompletar de dispositivos e contagem de decisões elegíveis.

GET /filtros/dispositivos?q=  — até 10 dispositivos que casam com o texto digitado.
POST /filtros/contagem        — quantas decisões cumprem os filtros (juntos e cada um).
Dependem do preparo (`python -m query.filtros.preparar`); sem ele, 503.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from starlette.concurrency import run_in_threadpool

from query.api.auth_routes import get_current_user
from query.filtros.store import FiltroIndisponivel, FiltroStore

router = APIRouter(prefix="/filtros", tags=["filtros"], dependencies=[Depends(get_current_user)])

MSG_INDISPONIVEL = "Filtro restrito indisponível. Rode python -m query.filtros.preparar no servidor."


def get_filtro_store(request: Request) -> FiltroStore | None:
    return getattr(request.app.state, "filtro_store", None)


def filtro_indisponivel() -> HTTPException:
    return HTTPException(status_code=503, detail=MSG_INDISPONIVEL)


class DispositivoView(BaseModel):
    codigo: str
    rotulo: str
    total: int


class ExpressaoView(BaseModel):
    texto: str
    total: int


class ContagemRequest(BaseModel):
    dispositivos: list[str] = Field(default_factory=list, max_length=20)
    expressoes: list[str] = Field(default_factory=list, max_length=20)


class ContagemResponse(BaseModel):
    total: int
    dispositivos: list[DispositivoView]
    expressoes: list[ExpressaoView]


@router.get("/dispositivos", response_model=list[DispositivoView])
async def sugerir_dispositivos(q: str = "", store: FiltroStore | None = Depends(get_filtro_store)):
    if store is None:
        raise filtro_indisponivel()
    try:
        sugestoes = await run_in_threadpool(store.sugerir, q, 10)
    except FiltroIndisponivel as exc:
        raise filtro_indisponivel() from exc
    return [DispositivoView(codigo=s.codigo, rotulo=s.rotulo, total=s.total) for s in sugestoes]


@router.post("/contagem", response_model=ContagemResponse)
async def contar(body: ContagemRequest, store: FiltroStore | None = Depends(get_filtro_store)):
    if store is None:
        raise filtro_indisponivel()
    try:
        c = await run_in_threadpool(store.contar, body.dispositivos, body.expressoes)
    except FiltroIndisponivel as exc:
        raise filtro_indisponivel() from exc
    return ContagemResponse(
        total=c.total,
        dispositivos=[DispositivoView(codigo=d.codigo, rotulo=d.rotulo, total=d.total) for d in c.dispositivos],
        expressoes=[ExpressaoView(texto=t, total=n) for t, n in c.expressoes],
    )
