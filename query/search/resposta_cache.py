"""
Respostas geradas já pagas: `public.resposta_cache` guarda cada resposta do POST /resposta
pela chave (modelo, temperatura, prompt, tese e ids das decisões), para reabrir uma consulta
ou recarregar a página não chamar a OpenAI de novo. Mudou qualquer parte da chave (outro
modelo, prompt novo, tese refinada, outra lista), a resposta é gerada de novo.

Só guarda o que já é público ou já vai à OpenAI: a resposta (frases e posições) sobre ementas
públicas. Idempotente (CREATE TABLE IF NOT EXISTS).
"""
from __future__ import annotations

import psycopg
from psycopg.types.json import Jsonb

_DDL = """
CREATE TABLE IF NOT EXISTS public.resposta_cache (
    chave      TEXT        PRIMARY KEY,
    resposta   JSONB       NOT NULL,
    criada_em  TIMESTAMPTZ NOT NULL DEFAULT now()
)
"""


def ensure_schema(database_url: str) -> None:
    """Cria `public.resposta_cache` (idempotente)."""
    with psycopg.connect(database_url) as conn:
        conn.execute(_DDL)


class RespostaCache:
    def __init__(self, database_url: str):
        self._url = database_url

    def ler(self, chave: str) -> dict | None:
        with psycopg.connect(self._url) as conn:
            linha = conn.execute("SELECT resposta FROM public.resposta_cache WHERE chave = %s", (chave,)).fetchone()
        return linha[0] if linha else None

    def gravar(self, chave: str, resposta: dict) -> None:
        with psycopg.connect(self._url) as conn:
            conn.execute(
                "INSERT INTO public.resposta_cache (chave, resposta) VALUES (%s, %s) ON CONFLICT (chave) DO NOTHING",
                (chave, Jsonb(resposta)),
            )
