"""
Filtro restrito: autocompletar de dispositivos e contagem de decisões elegíveis.

GET /filtros/dispositivos?q=  — até 10 dispositivos que casam com o texto digitado.
POST /filtros/contagem        — quantas decisões cumprem os filtros (juntos e cada um).
Dependem do preparo (`python -m query.filtros.preparar`); sem ele, 503.
"""
from __future__ import annotations

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field
from starlette.concurrency import run_in_threadpool

from query.api.auth_routes import get_current_user
from query.filtros.store import FiltroIndisponivel, FiltroStore

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/filtros", tags=["filtros"], dependencies=[Depends(get_current_user)])

MSG_INDISPONIVEL = "O filtro restrito está indisponível no momento."
MAX_FILTROS = 20     # dispositivos e expressões por pedido (aqui, no /query e no /query/livre)
MAX_TEXTO = 200      # caracteres de cada dispositivo ou expressão
Texto = Annotated[str, Field(max_length=MAX_TEXTO)]


def get_filtro_store(request: Request) -> FiltroStore | None:
    return getattr(request.app.state, "filtro_store", None)


def filtro_indisponivel() -> HTTPException:
    logger.warning("Filtro restrito indisponível: rode `python -m query.filtros.preparar` no servidor.")
    return HTTPException(status_code=503, detail=MSG_INDISPONIVEL)


class DispositivoView(BaseModel):
    codigo: str
    rotulo: str
    total: int


class ExpressaoView(BaseModel):
    texto: str
    total: int


class ContagemRequest(BaseModel):
    dispositivos: list[Texto] = Field(default_factory=list, max_length=MAX_FILTROS)
    expressoes: list[Texto] = Field(default_factory=list, max_length=MAX_FILTROS)


class ContagemResponse(BaseModel):
    total: int
    dispositivos: list[DispositivoView]
    expressoes: list[ExpressaoView]


@router.get("/dispositivos", response_model=list[DispositivoView])
async def sugerir_dispositivos(q: str = Query("", max_length=MAX_TEXTO), store: FiltroStore | None = Depends(get_filtro_store)):
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
