"""
Endpoints da tela de rotulação do harness de avaliação: a especialista recebe
um par (tese, acórdão) por vez e grava relevância (0-3) e stance.

Mesmo padrão de query/api/conversa_routes.py. O acesso é restrito aos e-mails
de `AVALIACAO_EMAILS`. A resposta da fila não diz qual sistema trouxe o acórdão
nem a nota de outros avaliadores: quem rotula julga às cegas.
"""
from __future__ import annotations

import os
import uuid
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, Field

from auth.store import Usuario
from avaliacao.store import AvaliacaoStore, Julgamento
from query.api.auth_routes import get_current_user
from query.enrichment.schema import EstruturaArgumentativa
from query.search.doc_retriever import DocRetriever

router = APIRouter(prefix="/avaliacao", tags=["avaliacao"])

# Convenção: humanos sempre gravam na rodada 1; o upsert (par, juiz, rodada)
# faz uma correção do mesmo humano sobrescrever o rótulo anterior.
RODADA_HUMANO = 1
# Quanto da fundamentação vai para a tela, junto com a ementa.
TAMANHO_FUNDAMENTACAO = 3000


def get_avaliacao_store(request: Request) -> AvaliacaoStore:
    return request.app.state.avaliacao_store


def get_avaliacao_doc_retriever(request: Request) -> DocRetriever:
    # Dependency própria: importar get_doc_retriever de app.py criaria import circular.
    return request.app.state.doc_retriever


def _emails_permitidos() -> set[str]:
    # Lida a cada requisição (não no import) para os testes poderem usar monkeypatch.
    bruto = os.getenv("AVALIACAO_EMAILS", "")
    return {e.strip().lower() for e in bruto.split(",") if e.strip()}


def exigir_rotulador(usuario: Usuario = Depends(get_current_user)) -> Usuario:
    if usuario.email.strip().lower() not in _emails_permitidos():
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Acesso restrito à avaliação.")
    return usuario


def _juiz_humano(usuario: Usuario) -> str:
    return f"humano:{usuario.email.strip().lower()}"


# --------------------------------------------------------------------------- #
# Modelos Pydantic                                                             #
# --------------------------------------------------------------------------- #

class DocumentoFila(BaseModel):
    id: str
    ementa: str | None = None
    fundamentacao_inicio: str | None = None
    link_original: str | None = None
    numero_processo: str | None = None
    tribunal: str | None = None


class ParFila(BaseModel):
    id: str
    tese: EstruturaArgumentativa
    documento: DocumentoFila


class FilaResponse(BaseModel):
    par: ParFila | None
    feitos: int
    total: int


class RotuloRequest(BaseModel):
    relevancia: int = Field(ge=0, le=3)
    stance: Literal["fortalece", "enfraquece", "neutro"]


# --------------------------------------------------------------------------- #
# Rotas                                                                        #
# --------------------------------------------------------------------------- #

@router.get("/fila", response_model=FilaResponse)
def fila(
    usuario: Usuario = Depends(exigir_rotulador),
    store: AvaliacaoStore = Depends(get_avaliacao_store),
    retriever: DocRetriever = Depends(get_avaliacao_doc_retriever),
) -> FilaResponse:
    juiz = _juiz_humano(usuario)
    feitos, total = store.progresso(juiz)
    proximo = store.proximo_da_fila(juiz)
    if proximo is None:
        return FilaResponse(par=None, feitos=feitos, total=total)

    par, tese = proximo
    doc = retriever.fetch([par.documento_id]).get(par.documento_id)
    if doc is None:
        documento = DocumentoFila(id=par.documento_id)
    else:
        documento = DocumentoFila(
            id=par.documento_id,
            ementa=doc.ementa,
            fundamentacao_inicio=(doc.fundamentacao or "")[:TAMANHO_FUNDAMENTACAO],
            link_original=doc.link_original,
            numero_processo=doc.numero_processo,
            tribunal=doc.tribunal,
        )
    return FilaResponse(
        par=ParFila(id=str(par.id), tese=EstruturaArgumentativa.model_validate(tese.estrutura), documento=documento),
        feitos=feitos,
        total=total,
    )


@router.post("/pares/{par_id}/rotulo", status_code=status.HTTP_204_NO_CONTENT)
def rotular(
    par_id: str,
    body: RotuloRequest,
    usuario: Usuario = Depends(exigir_rotulador),
    store: AvaliacaoStore = Depends(get_avaliacao_store),
) -> Response:
    try:
        par_uuid = uuid.UUID(par_id)
    except ValueError:
        par_uuid = None
    if par_uuid is None or par_uuid not in store.amostra():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Par fora da amostra.")
    store.gravar_julgamento(
        Julgamento(
            par_id=par_uuid, juiz=_juiz_humano(usuario), rodada=RODADA_HUMANO,
            relevancia=body.relevancia, stance=body.stance,
        )
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)
