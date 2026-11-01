"""
Acesso a `public.conversas` (CRUD do histórico de busca) — camada de
persistência para a peça de endpoints FastAPI
(`query/api/conversa_routes.py`).

Mesma convenção de `auth/store.py` e `query/search/doc_retriever.py`:
psycopg puro, sem ORM, conecta/cursora/fecha a cada chamada. Deliberadamente
sem import de FastAPI/Pydantic — a camada HTTP decide o mapeamento de
`ConversaNaoEncontradaError` para um HTTPException.

Toda operação (get/rename/delete/add_versao) filtra por
`id = %s AND usuario_id = %s` — nunca só por `id`. Isso é o que impede um
usuário autenticado de ler/alterar a conversa de outro só adivinhando um
UUID: a query simplesmente não encontra a linha (mesmo efeito de um 404),
em vez de precisar de uma checagem de autorização separada que alguém
poderia esquecer de chamar.

Cada busca (a original + cada "Refinar consulta") vira uma VERSÃO própria no
array `versoes`, não sobrescreve a anterior — ver conversations/db.py.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

import psycopg
from psycopg.types.json import Json


@dataclass(frozen=True)
class Conversa:
    """Uma linha de `public.conversas`. `versoes` vem do Postgres já como
    lista de dicts (JSONB decodificado pelo psycopg) — cada item tem
    {numero, estrutura, has_file, file_name, pdf_extraido, aviso, resultados,
    criado_em}, numerados a partir de 1 na ordem em que foram buscados."""

    id: uuid.UUID
    usuario_id: uuid.UUID
    titulo: str
    criado_em: datetime
    atualizado_em: datetime
    versoes: list[dict[str, Any]]


class ConversaNaoEncontradaError(Exception):
    """Levantado quando a conversa não existe OU não pertence ao usuário —
    de propósito, os dois casos são indistinguíveis pra quem chama (ver
    docstring do módulo)."""


_SELECT_COLUNAS = "id, usuario_id, titulo, criado_em, atualizado_em, versoes"

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

# `jsonb_array_length(versoes) + 1` calcula o número da versão nova a partir
# do tamanho ATUAL do array, no mesmo UPDATE — atômico (o lock de linha do
# Postgres no UPDATE evita a corrida de ler o tamanho numa query separada e
# escrever depois, que duas buscas simultâneas na mesma conversa poderiam
# atropelar). `versoes || jsonb_build_object(...)` acrescenta ao array em vez
# de substituir — é o que torna isto versionamento, não um snapshot único.
_ADD_VERSAO = f"""
UPDATE public.conversas SET
    versoes = versoes || jsonb_build_object(
        'numero', jsonb_array_length(versoes) + 1,
        'estrutura', %s::jsonb,
        'has_file', %s::boolean,
        'file_name', %s::text,
        'pdf_extraido', %s::boolean,
        'aviso', %s::text,
        'resultados', %s::jsonb,
        'criado_em', %s::text
    ),
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
        versoes=row[5] or [],
    )


class ConversaStore:
    """CRUD de `public.conversas` via psycopg. Uma conexão nova por chamada,
    igual a `UsuarioStore`/`DocRetriever` — baixo tráfego, não vale a
    complexidade de um pool aqui."""

    def __init__(self, database_url: str) -> None:
        self.database_url = database_url

    def create(self, usuario_id: uuid.UUID, titulo: str) -> Conversa:
        """Cria uma conversa nova, sem nenhuma versão ainda (criada ao
        clicar em "Nova pesquisa", antes mesmo do primeiro /enrich)."""
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

    def add_versao(
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
        """Acrescenta uma nova versão ao array `versoes` — chamado após
        /enrich (resultados=None, é uma busca nova começando) e de novo após
        /query (resultados preenchido, mesma versão sendo completada). Cada
        "Refinar consulta" bem-sucedida gera uma versão nova (V2, V3, ...),
        nunca sobrescreve a anterior."""
        conn = psycopg.connect(self.database_url)
        try:
            with conn.cursor() as cur:
                cur.execute(
                    _ADD_VERSAO,
                    (
                        Json(estrutura),
                        has_file,
                        file_name,
                        pdf_extraido,
                        aviso,
                        Json(resultados),
                        datetime.now(timezone.utc).isoformat(),
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
