"""
Filtro restrito: autocompletar de dispositivos e contagem de decisões elegíveis.

GET /filtros/dispositivos?q=  — até 10 dispositivos que casam com o texto digitado.
GET /filtros/tribunais        — tribunais do acervo com o total de decisões.
POST /filtros/contagem        — quantas decisões cumprem os filtros (juntos e cada um).
Dependem do preparo (`python -m query.filtros.preparar`); sem ele, 503.
"""
from __future__ import annotations

import logging
import re
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from starlette.concurrency import run_in_threadpool

from query.api.auth_routes import get_current_user
from query.filtros.fases import Fase
from query.filtros.store import FiltroIndisponivel, FiltroStore

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/filtros", tags=["filtros"], dependencies=[Depends(get_current_user)])

MSG_INDISPONIVEL = "O filtro restrito está indisponível no momento."
MAX_FILTROS = 20     # dispositivos e expressões por pedido (aqui, no /query e no /query/livre)
MAX_TRIBUNAIS = 25   # tribunais por pedido
MAX_TEXTO = 200      # caracteres de cada dispositivo ou expressão
Texto = Annotated[str, Field(max_length=MAX_TEXTO)]


def get_filtro_store(request: Request) -> FiltroStore | None:
    return getattr(request.app.state, "filtro_store", None)


def exigir_filtro_store(store: FiltroStore | None = Depends(get_filtro_store)) -> FiltroStore:
    """Para as rotas que não funcionam sem o preparo do filtro restrito."""
    if store is None:
        raise FiltroIndisponivel()
    return store


def tratar_filtro_indisponivel(request: Request, exc: FiltroIndisponivel) -> JSONResponse:
    """Registrado em app.py: `FiltroIndisponivel` (sem store ou sem as tabelas) vira 503."""
    logger.warning("Filtro restrito indisponível: rode `python -m query.filtros.preparar` no servidor.")
    return JSONResponse(status_code=503, content={"detail": MSG_INDISPONIVEL})


class DispositivoView(BaseModel):
    codigo: str
    rotulo: str
    total: int


class ExpressaoView(BaseModel):
    texto: str
    total: int


class TribunalView(BaseModel):
    tribunal: str
    rotulo: str
    total: int


class ContagemRequest(BaseModel):
    dispositivos: list[Texto] = Field(default_factory=list, max_length=MAX_FILTROS)
    expressoes: list[Texto] = Field(default_factory=list, max_length=MAX_FILTROS)
    tribunais: list[Texto] = Field(default_factory=list, max_length=MAX_TRIBUNAIS)
    fase: Fase | None = None


class ContagemResponse(BaseModel):
    total: int
    dispositivos: list[DispositivoView]
    expressoes: list[ExpressaoView]


@router.get("/dispositivos", response_model=list[DispositivoView])
async def sugerir_dispositivos(q: str = Query("", max_length=MAX_TEXTO), store: FiltroStore = Depends(exigir_filtro_store)):
    sugestoes = await run_in_threadpool(store.sugerir, q, 10)
    return [DispositivoView(codigo=s.codigo, rotulo=s.rotulo, total=s.total) for s in sugestoes]


def rotulo_do_tribunal(t: str) -> str:
    return re.sub(r"^TRT(\d+)$", r"TRT-\1", t)


@router.get("/tribunais", response_model=list[TribunalView])
async def listar_tribunais(store: FiltroStore = Depends(exigir_filtro_store)):
    lista = await run_in_threadpool(store.tribunais)
    return [TribunalView(tribunal=t, rotulo=rotulo_do_tribunal(t), total=n) for t, n in lista]


@router.post("/contagem", response_model=ContagemResponse)
async def contar(body: ContagemRequest, store: FiltroStore = Depends(exigir_filtro_store)):
    c = await run_in_threadpool(store.contar, body.dispositivos, body.expressoes, body.tribunais, body.fase)
    return ContagemResponse(
        total=c.total,
        dispositivos=[DispositivoView(codigo=d.codigo, rotulo=d.rotulo, total=d.total) for d in c.dispositivos],
        expressoes=[ExpressaoView(texto=t, total=n) for t, n in c.expressoes],
    )
