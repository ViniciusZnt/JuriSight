"""
Correção do provimento pelo usuário: POST /provimento/{documento_id}/correcao.

Grava (upsert por documento + usuário) o que o usuário acha que o Jev deveria ter
respondido, para medir os erros do classificador e servir de dado de treino depois.
Não muda `documentos.provimento` nem a busca.
"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field, field_validator

from auth.store import Usuario
from query.api.auth_routes import get_current_user
from scraper.provimento_jev import FAVORECE, RECORRENTES, RESULTADOS
from scraper.provimento_jev_db import DocumentoNaoEncontrado, ProvimentoJevStore

router = APIRouter(prefix="/provimento", tags=["provimento"])


def get_provimento_store(request: Request) -> ProvimentoJevStore | None:
    return getattr(request.app.state, "provimento_store", None)


class CorrecaoRequest(BaseModel):
    resultado: str
    recorrente: str
    favorece: str
    comentario: str | None = Field(default=None, max_length=1000)

    @field_validator("resultado")
    @classmethod
    def _resultado(cls, v: str) -> str:
        return _valida(v, RESULTADOS)

    @field_validator("recorrente")
    @classmethod
    def _recorrente(cls, v: str) -> str:
        return _valida(v, RECORRENTES)

    @field_validator("favorece")
    @classmethod
    def _favorece(cls, v: str) -> str:
        return _valida(v, FAVORECE)


def _valida(valor: str, aceitos: tuple[str, ...]) -> str:
    if valor not in aceitos:
        raise ValueError(f"valor deve ser um de {', '.join(aceitos)}")
    return valor


class CorrecaoResponse(CorrecaoRequest):
    documento_id: str
    atualizado_em: str


@router.post("/{documento_id}/correcao", response_model=CorrecaoResponse)
def enviar_correcao(
    documento_id: str,
    body: CorrecaoRequest,
    usuario: Usuario = Depends(get_current_user),
    store: ProvimentoJevStore | None = Depends(get_provimento_store),
) -> CorrecaoResponse:
    try:
        uuid.UUID(documento_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Documento não encontrado.")
    if store is None:
        raise HTTPException(status_code=503, detail="Registro de correções indisponível.")
    try:
        quando = store.salvar_correcao(
            documento_id, str(usuario.id), body.resultado, body.recorrente, body.favorece, body.comentario
        )
    except DocumentoNaoEncontrado:
        raise HTTPException(status_code=404, detail="Documento não encontrado.")
    return CorrecaoResponse(documento_id=documento_id, atualizado_em=quando.isoformat(), **body.model_dump())
