"""
Prepara o Postgres para o filtro restrito (idempotente): função de unaccent, tabela de
dispositivos citados por decisão (com todos os níveis), totais por dispositivo e texto
indexado (tsvector + GIN). Decisões novas entram ao rodar de novo; se a forma do texto indexado
mudou (`_VERSAO_TEXTO`), o índice de texto é refeito do zero. Uso: python -m query.filtros.preparar
"""
from __future__ import annotations

import os

import psycopg

from query.filtros.dispositivos import codigos_do_texto, niveis

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

# O texto indexado tem só [a-z0-9], como a expressão (query/filtros/expressoes.py): sem isso o parser do
# Postgres guarda "auxilio-doenca" e "13.467" como fichas inteiras e a frase não casa. O ponto entre
# dígitos sai ("13.467" -> 13467); qualquer outro sinal vira espaço.
_TSV_CARGA = r"""
INSERT INTO public.documento_tsv (id, tsv)
SELECT d.id, to_tsvector('simple', regexp_replace(regexp_replace(
    lower(public.jurisight_unaccent(coalesce(d.ementa,'') || ' ' || coalesce(d.fundamentacao,''))),
    '(?<=[0-9])\.(?=[0-9])', '', 'g'), '[^a-z0-9]+', ' ', 'g'))
FROM public.documentos d
WHERE NOT EXISTS (SELECT 1 FROM public.documento_tsv t WHERE t.id = d.id)
"""

# Muda quando a forma de _TSV_CARGA muda; fica no comentário da tabela.
_VERSAO_TEXTO = "texto v2: so [a-z0-9], sem ponto entre digitos"

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
        # NR, Tema e súmula vinculante não vêm codificados: saem do texto (cursor no servidor, sem
        # carregar todos os textos de uma vez).
        with conn.cursor(name="textos") as leitura:
            leitura.execute("SELECT id, coalesce(ementa,'') || ' ' || coalesce(fundamentacao,'') FROM public.documentos")
            for doc_id, texto in leitura:
                pares.update((doc_id, c) for c in codigos_do_texto(texto))
        with conn.cursor() as cur, cur.copy("COPY public.documento_dispositivo (documento_id, codigo) FROM STDIN") as copy:
            for par in pares:
                copy.write_row(par)
        conn.execute("TRUNCATE public.dispositivo")
        conn.execute("INSERT INTO public.dispositivo SELECT codigo, count(*) FROM public.documento_dispositivo GROUP BY codigo")
        conn.execute("ANALYZE public.documento_dispositivo, public.dispositivo")
        n_disp = conn.execute("SELECT count(*) FROM public.dispositivo").fetchone()[0]
    with psycopg.connect(database_url) as conn:
        versao = conn.execute("SELECT obj_description(to_regclass('public.documento_tsv'))").fetchone()[0]
        if versao != _VERSAO_TEXTO:
            conn.execute("DROP TABLE IF EXISTS public.documento_tsv")  # texto antigo: refaz tudo
        conn.execute(_TSV)
        conn.execute(_TSV_CARGA)
        conn.execute(_INDICE)
        conn.execute(f"COMMENT ON TABLE public.documento_tsv IS '{_VERSAO_TEXTO}'")
        conn.execute("ANALYZE public.documento_tsv")
    print(f"{n_disp} dispositivos, {len(pares)} linhas em documento_dispositivo")


if __name__ == "__main__":
    preparar(os.environ["DATABASE_URL"])
