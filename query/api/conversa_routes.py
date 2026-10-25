"""
Endpoints de conversas — o histórico de busca do usuário (sidebar), agora
persistido no Postgres em vez de só no localStorage do navegador.

Mesmo padrão de query/api/auth_routes.py: esta é a única camada que conhece
FastAPI de um lado e `conversations.*` (cego a HTTP) do outro. Toda rota
exige sessão (`Depends(get_current_user)`) e toda operação de leitura/escrita
é escopada ao usuário autenticado — `ConversaStore` já filtra por
`usuario_id` em cada query, então um usuário nunca consegue ler/alterar a
conversa de outro.

Cada busca bem-sucedida (a original + cada "Refinar consulta") vira uma
VERSÃO própria (`POST /conversas/{id}/versoes` acrescenta, nunca sobrescreve)
— é o que dá o histórico V1/V2/V3 navegável no frontend.
"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field

from auth.store import Usuario
from conversations.store import Conversa, ConversaNaoEncontradaError, ConversaStore
from query.api.auth_routes import get_current_user
from query.enrichment.schema import EstruturaArgumentativa
from query.search.result_formatter import ResultCard

router = APIRouter(prefix="/conversas", tags=["conversas"])


def get_conversa_store(request: Request) -> ConversaStore:
    """Mesmo padrão de get_usuario_store/get_hybrid: singleton em request.app.state."""
    return request.app.state.conversa_store


# --------------------------------------------------------------------------- #
# Modelos Pydantic                                                             #
# --------------------------------------------------------------------------- #

class VersaoResponse(BaseModel):
    """Uma versão de busca dentro de uma conversa — "V{numero}" no frontend."""

    numero: int
    estrutura: EstruturaArgumentativa
    has_file: bool
    file_name: str | None
    pdf_extraido: bool | None
    aviso: str | None
    resultados: list[ResultCard] | None
    criado_em: str


class ConversaResponse(BaseModel):
    id: str
    titulo: str
    criado_em: str
    atualizado_em: str
    versoes: list[VersaoResponse]

    @classmethod
    def de_conversa(cls, c: Conversa) -> "ConversaResponse":
        return cls(
            id=str(c.id),
            titulo=c.titulo,
            criado_em=c.criado_em.isoformat(),
            atualizado_em=c.atualizado_em.isoformat(),
            versoes=[VersaoResponse(**v) for v in c.versoes],
        )


class CriarConversaRequest(BaseModel):
    titulo: str = Field(min_length=1, max_length=255)


class RenomearConversaRequest(BaseModel):
    titulo: str = Field(min_length=1, max_length=255)


class NovaVersaoRequest(BaseModel):
    estrutura: EstruturaArgumentativa
    has_file: bool
    file_name: str | None = None
    pdf_extraido: bool | None = None
    aviso: str | None = None
    resultados: list[ResultCard] | None = None


def _parse_id(conversa_id: str) -> uuid.UUID:
    try:
        return uuid.UUID(conversa_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversa não encontrada.")


# --------------------------------------------------------------------------- #
# Rotas                                                                        #
# --------------------------------------------------------------------------- #

@router.get("", response_model=list[ConversaResponse])
def listar(
    usuario: Usuario = Depends(get_current_user),
    store: ConversaStore = Depends(get_conversa_store),
) -> list[ConversaResponse]:
    return [ConversaResponse.de_conversa(c) for c in store.list_by_usuario(usuario.id)]


@router.post("", response_model=ConversaResponse, status_code=status.HTTP_201_CREATED)
def criar(
    body: CriarConversaRequest,
    usuario: Usuario = Depends(get_current_user),
    store: ConversaStore = Depends(get_conversa_store),
) -> ConversaResponse:
    return ConversaResponse.de_conversa(store.create(usuario.id, body.titulo))


@router.patch("/{conversa_id}", response_model=ConversaResponse)
def renomear(
    conversa_id: str,
    body: RenomearConversaRequest,
    usuario: Usuario = Depends(get_current_user),
    store: ConversaStore = Depends(get_conversa_store),
) -> ConversaResponse:
    try:
        return ConversaResponse.de_conversa(store.rename(_parse_id(conversa_id), usuario.id, body.titulo))
    except ConversaNaoEncontradaError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversa não encontrada.")


@router.post("/{conversa_id}/versoes", response_model=ConversaResponse, status_code=status.HTTP_201_CREATED)
def adicionar_versao(
    conversa_id: str,
    body: NovaVersaoRequest,
    usuario: Usuario = Depends(get_current_user),
    store: ConversaStore = Depends(get_conversa_store),
) -> ConversaResponse:
    """Acrescenta uma versão nova ao array `versoes` — nunca sobrescreve as
    anteriores (ver conversations/store.py::add_versao). Devolve a conversa
    inteira (todas as versões) pra o frontend já ter o dropdown V1/V2/...
    completo sem precisar de outra chamada."""
    try:
        conversa = store.add_versao(
            _parse_id(conversa_id),
            usuario.id,
            estrutura=body.estrutura.model_dump(mode="json"),
            has_file=body.has_file,
            file_name=body.file_name,
            pdf_extraido=body.pdf_extraido,
            aviso=body.aviso,
            resultados=[r.model_dump(mode="json") for r in body.resultados] if body.resultados is not None else None,
        )
    except ConversaNaoEncontradaError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversa não encontrada.")
    return ConversaResponse.de_conversa(conversa)


@router.delete("/{conversa_id}", status_code=status.HTTP_204_NO_CONTENT)
def apagar(
    conversa_id: str,
    usuario: Usuario = Depends(get_current_user),
    store: ConversaStore = Depends(get_conversa_store),
) -> None:
    try:
        store.delete(_parse_id(conversa_id), usuario.id)
    except ConversaNaoEncontradaError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversa não encontrada.")
