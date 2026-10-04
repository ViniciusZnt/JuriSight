"""
Acesso a `public.conversas` (CRUD do histórico de busca) — camada de
persistência para a peça de endpoints FastAPI
(`query/api/conversa_routes.py`).

Mesma convenção de `auth/store.py` e `query/search/doc_retriever.py`:
psycopg puro, sem ORM, conecta/cursora/fecha a cada chamada. Deliberadamente
sem import de FastAPI/Pydantic — a camada HTTP decide o mapeamento de
`ConversaNaoEncontradaError` para um HTTPException.

Toda operação (get/rename/delete/set_snapshot) filtra por
`id = %s AND usuario_id = %s` — nunca só por `id`. Isso é o que impede um
usuário autenticado de ler/alterar a conversa de outro só adivinhando um
UUID: a query simplesmente não encontra a linha (mesmo efeito de um 404),
em vez de precisar de uma checagem de autorização separada que alguém
poderia esquecer de chamar.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Any

import psycopg
from psycopg.types.json import Json


@dataclass(frozen=True)
class Conversa:
    """Uma linha de `public.conversas`."""

    id: uuid.UUID
    usuario_id: uuid.UUID
    titulo: str
    criado_em: datetime
    atualizado_em: datetime
    estrutura: dict[str, Any] | None
    has_file: bool | None
    file_name: str | None
    pdf_extraido: bool | None
    aviso: str | None
    resultados: list[dict[str, Any]] | None


class ConversaNaoEncontradaError(Exception):
    """Levantado quando a conversa não existe OU não pertence ao usuário —
    de propósito, os dois casos são indistinguíveis pra quem chama (ver
    docstring do módulo)."""


_SELECT_COLUNAS = (
    "id, usuario_id, titulo, criado_em, atualizado_em, "
    "estrutura, has_file, file_name, pdf_extraido, aviso, resultados"
)

_INSERT = f"""
INSERT INTO public.conversas (usuario_id, titulo)
VALUES (%s, %s)
RETURNING {_SELECT_COLUNAS}
"""

_SELECT_BY_USUARIO = f"""
SELECT {_SELECT_COLUNAS} FROM public.conversas
WHERE usuario_id = %s
ORDER BY criado_em DESC
"""

_UPDATE_TITULO = f"""
UPDATE public.conversas SET titulo = %s, atualizado_em = NOW()
WHERE id = %s AND usuario_id = %s
RETURNING {_SELECT_COLUNAS}
"""

_UPDATE_SNAPSHOT = f"""
UPDATE public.conversas SET
    estrutura = %s, has_file = %s, file_name = %s,
    pdf_extraido = %s, aviso = %s, resultados = %s,
    atualizado_em = NOW()
WHERE id = %s AND usuario_id = %s
RETURNING {_SELECT_COLUNAS}
"""

_DELETE = """
DELETE FROM public.conversas WHERE id = %s AND usuario_id = %s
"""


def _row_para_conversa(row) -> Conversa:
    return Conversa(
        id=row[0],
        usuario_id=row[1],
        titulo=row[2],
        criado_em=row[3],
        atualizado_em=row[4],
        estrutura=row[5],
        has_file=row[6],
        file_name=row[7],
        pdf_extraido=row[8],
        aviso=row[9],
        resultados=row[10],
    )


class ConversaStore:
    """CRUD de `public.conversas` via psycopg. Uma conexão nova por chamada,
    igual a `UsuarioStore`/`DocRetriever` — baixo tráfego, não vale a
    complexidade de um pool aqui."""

    def __init__(self, database_url: str) -> None:
        self.database_url = database_url

    def create(self, usuario_id: uuid.UUID, titulo: str) -> Conversa:
        """Cria uma conversa nova, sem snapshot ainda (criada ao clicar em
        "Nova pesquisa", antes mesmo do primeiro /enrich)."""
        conn = psycopg.connect(self.database_url)
        try:
            with conn.cursor() as cur:
                cur.execute(_INSERT, (usuario_id, titulo))
                row = cur.fetchone()
            conn.commit()
        finally:
            conn.close()
        return _row_para_conversa(row)

    def list_by_usuario(self, usuario_id: uuid.UUID) -> list[Conversa]:
        """Todas as conversas do usuário, mais recente primeiro (histórico da sidebar)."""
        conn = psycopg.connect(self.database_url)
        try:
            with conn.cursor() as cur:
                cur.execute(_SELECT_BY_USUARIO, (usuario_id,))
                rows = cur.fetchall()
        finally:
            conn.close()
        return [_row_para_conversa(r) for r in rows]

    def rename(self, conversa_id: uuid.UUID, usuario_id: uuid.UUID, titulo: str) -> Conversa:
        conn = psycopg.connect(self.database_url)
        try:
            with conn.cursor() as cur:
                cur.execute(_UPDATE_TITULO, (titulo, conversa_id, usuario_id))
                row = cur.fetchone()
            conn.commit()
        finally:
            conn.close()
        if row is None:
            raise ConversaNaoEncontradaError(conversa_id)
        return _row_para_conversa(row)

    def set_snapshot(
        self,
        conversa_id: uuid.UUID,
        usuario_id: uuid.UUID,
        *,
        estrutura: dict[str, Any],
        has_file: bool,
        file_name: str | None,
        pdf_extraido: bool | None,
        aviso: str | None,
        resultados: list[dict[str, Any]] | None,
    ) -> Conversa:
        """Grava/substitui o snapshot de uma conversa — chamado após /enrich
        (resultados=None, nova consulta invalida os anteriores) e de novo
        após /query (resultados preenchido). Cada vez que o usuário refaz a
        busca na mesma conversa, isto sobrescreve o snapshot anterior."""
        conn = psycopg.connect(self.database_url)
        try:
            with conn.cursor() as cur:
                cur.execute(
                    _UPDATE_SNAPSHOT,
                    (
                        Json(estrutura),
                        has_file,
                        file_name,
                        pdf_extraido,
                        aviso,
                        Json(resultados) if resultados is not None else None,
                        conversa_id,
                        usuario_id,
                    ),
                )
                row = cur.fetchone()
            conn.commit()
        finally:
            conn.close()
        if row is None:
            raise ConversaNaoEncontradaError(conversa_id)
        return _row_para_conversa(row)

    def delete(self, conversa_id: uuid.UUID, usuario_id: uuid.UUID) -> None:
        conn = psycopg.connect(self.database_url)
        try:
            with conn.cursor() as cur:
                cur.execute(_DELETE, (conversa_id, usuario_id))
                apagou = cur.rowcount > 0
            conn.commit()
        finally:
            conn.close()
        if not apagou:
            raise ConversaNaoEncontradaError(conversa_id)
