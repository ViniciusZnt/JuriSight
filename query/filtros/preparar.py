"""
Prepara o Postgres para o filtro restrito (idempotente): função de unaccent, tabela de
dispositivos citados por decisão (com todos os níveis), totais por dispositivo e texto
indexado (tsvector + GIN). Decisões novas entram ao rodar de novo. Uso: python -m query.filtros.preparar
"""
from __future__ import annotations

import os

import psycopg

from query.filtros.dispositivos import niveis

_FUNCAO = """
CREATE OR REPLACE FUNCTION public.jurisight_unaccent(text) RETURNS text
    LANGUAGE sql IMMUTABLE PARALLEL SAFE AS $$ SELECT public.unaccent('public.unaccent', $1) $$
"""

_TABELA = """
CREATE TABLE IF NOT EXISTS public.documento_dispositivo (
    documento_id uuid NOT NULL,
    codigo       text NOT NULL,
    PRIMARY KEY (codigo, documento_id)
)
"""

_TOTAIS = """
CREATE TABLE IF NOT EXISTS public.dispositivo (codigo text PRIMARY KEY, total int NOT NULL)
"""

# O texto vira tsvector guardado: GIN não resolve frase (<->) sozinho, a conferência relê o
# tsvector de cada candidato, e recalculá-lo do texto levava segundos por consulta.
_TSV = """
CREATE TABLE IF NOT EXISTS public.documento_tsv (id uuid PRIMARY KEY, tsv tsvector NOT NULL)
"""

_TSV_CARGA = """
INSERT INTO public.documento_tsv (id, tsv)
SELECT d.id, to_tsvector('simple', public.jurisight_unaccent(coalesce(d.ementa,'') || ' ' || coalesce(d.fundamentacao,'')))
FROM public.documentos d
WHERE NOT EXISTS (SELECT 1 FROM public.documento_tsv t WHERE t.id = d.id)
"""

_INDICE = "CREATE INDEX IF NOT EXISTS documento_tsv_gin ON public.documento_tsv USING gin (tsv)"


def preparar(database_url: str) -> None:
    """Cria/recarrega as tabelas de dispositivos e o índice de texto."""
    with psycopg.connect(database_url) as conn:
        conn.execute("CREATE EXTENSION IF NOT EXISTS unaccent")
        conn.execute(_FUNCAO)
        conn.execute(_TABELA)
        conn.execute(_TOTAIS)
        conn.execute("TRUNCATE public.documento_dispositivo")
        pares: set[tuple] = set()
        with conn.cursor() as leitura:
            leitura.execute("SELECT id, referencia_legislativa FROM public.documentos "
                            "WHERE referencia_legislativa IS NOT NULL")
            for doc_id, refs in leitura:
                pares.update((doc_id, n) for r in refs for n in niveis(r))
        with conn.cursor() as cur, cur.copy("COPY public.documento_dispositivo (documento_id, codigo) FROM STDIN") as copy:
            for par in pares:
                copy.write_row(par)
        conn.execute("TRUNCATE public.dispositivo")
        conn.execute("INSERT INTO public.dispositivo SELECT codigo, count(*) FROM public.documento_dispositivo GROUP BY codigo")
        n_disp = conn.execute("SELECT count(*) FROM public.dispositivo").fetchone()[0]
    with psycopg.connect(database_url) as conn:
        conn.execute(_TSV)
        conn.execute(_TSV_CARGA)
        conn.execute(_INDICE)
    print(f"{n_disp} dispositivos, {len(pares)} linhas em documento_dispositivo")


if __name__ == "__main__":
    preparar(os.environ["DATABASE_URL"])
