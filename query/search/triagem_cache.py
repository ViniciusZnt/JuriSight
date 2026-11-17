"""
Avaliações da triagem já pagas: `public.triagem_cache` guarda a nota, a posição e o motivo de
cada par tese × decisão (chave em query/search/triagem.py::chave_da_triagem). Refinar a busca,
mudar um filtro ou reabrir uma conversa reaproveita o que já foi julgado, sem chamar a OpenAI.
A resposta gerada também lê daqui a posição de cada decisão (não confia no cliente).

Só guarda o que já é público ou já vai à OpenAI. Idempotente (CREATE TABLE IF NOT EXISTS).
"""
from __future__ import annotations

import logging

import psycopg
from psycopg.types.json import Jsonb

from query.enrichment.schema import EstruturaArgumentativa
from query.search.triagem import Avaliacao, chave_da_triagem

logger = logging.getLogger(__name__)

_DDL = """
CREATE TABLE IF NOT EXISTS public.triagem_cache (
    chave      TEXT        PRIMARY KEY,
    avaliacao  JSONB       NOT NULL,
    criada_em  TIMESTAMPTZ NOT NULL DEFAULT now()
)
"""


def ensure_schema(database_url: str) -> None:
    """Cria `public.triagem_cache` (idempotente)."""
    with psycopg.connect(database_url) as conn:
        conn.execute(_DDL)


class TriagemCache:
    def __init__(self, database_url: str):
        self._url = database_url

    def ler_varios(self, chaves: list[str]) -> dict[str, dict]:
        if not chaves:
            return {}
        with psycopg.connect(self._url) as conn:
            linhas = conn.execute(
                "SELECT chave, avaliacao FROM public.triagem_cache WHERE chave = ANY(%s)", (chaves,)
            ).fetchall()
        return dict(linhas)

    def gravar_varios(self, itens: dict[str, dict]) -> None:
        if not itens:
            return
        with psycopg.connect(self._url) as conn, conn.cursor() as cur:
            cur.executemany(
                "INSERT INTO public.triagem_cache (chave, avaliacao) VALUES (%s, %s) ON CONFLICT (chave) DO NOTHING",
                [(c, Jsonb(a)) for c, a in itens.items()],
            )


def avaliacoes_do_cache(
    cache: TriagemCache | None, estrutura: EstruturaArgumentativa, ids: list[str]
) -> dict[str, Avaliacao]:
    """id -> Avaliacao das decisões já avaliadas para esta tese. Cache ausente ou fora do ar = {}
    (só log: quem chama segue sem as avaliações)."""
    if cache is None or not ids:
        return {}
    chaves = {chave_da_triagem(estrutura, i): i for i in ids}
    try:
        salvas = cache.ler_varios(list(chaves))
    except psycopg.Error as exc:
        logger.warning("Cache da triagem indisponível: %s", exc)
        return {}
    return {chaves[c]: Avaliacao.model_validate(a) for c, a in salvas.items() if c in chaves}
