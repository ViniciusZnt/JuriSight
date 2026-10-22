"""
Schema `avaliacao` do harness de avaliação (conjunto-ouro): teses, pares
(tese, acórdão), julgamentos humanos e a fila de rotulação (tabela `amostra`).
Ver docs/superpowers/specs/2026-10-17-harness-avaliacao-design.md §3.2.

Idempotente (CREATE ... IF NOT EXISTS) — seguro rodar a cada subida.
`documento_id` em `pares` é texto solto, sem FK: o conjunto-ouro não deve
depender do ciclo de vida de `public.documentos`.
"""
import logging
import os

import psycopg

logger = logging.getLogger(__name__)

_DDL = [
    "CREATE SCHEMA IF NOT EXISTS avaliacao;",
    """
    CREATE TABLE IF NOT EXISTS avaliacao.teses (
        id                   UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
        estrutura            JSONB       NOT NULL,
        origem               TEXT        NOT NULL CHECK (origem IN ('sintetica', 'real')),
        tema                 TEXT        NOT NULL,
        split                TEXT        NOT NULL CHECK (split IN ('dev', 'teste')),
        documento_origem_id  TEXT,
        criado_em            TIMESTAMPTZ NOT NULL DEFAULT NOW()
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS avaliacao.pares (
        id            UUID   PRIMARY KEY DEFAULT gen_random_uuid(),
        tese_id       UUID   NOT NULL REFERENCES avaliacao.teses(id) ON DELETE CASCADE,
        documento_id  TEXT   NOT NULL,
        corredores    TEXT[] NOT NULL DEFAULT '{}',
        UNIQUE (tese_id, documento_id)
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS avaliacao.julgamentos (
        id                UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
        par_id            UUID        NOT NULL REFERENCES avaliacao.pares(id) ON DELETE CASCADE,
        juiz              TEXT        NOT NULL,
        relevancia        SMALLINT    NOT NULL CHECK (relevancia BETWEEN 0 AND 3),
        stance            TEXT        NOT NULL CHECK (stance IN ('fortalece', 'enfraquece', 'neutro')),
        relevancia_probs  JSONB,
        stance_probs      JSONB,
        confianca_rel     REAL,
        confianca_stance  REAL,
        rodada            INT         NOT NULL,
        criado_em         TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        UNIQUE (par_id, juiz, rodada)
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS avaliacao.amostra (
        par_id  UUID PRIMARY KEY REFERENCES avaliacao.pares(id) ON DELETE CASCADE,
        metade  TEXT NOT NULL CHECK (metade IN ('sorteada', 'incerta'))
    );
    """,
]


def ensure_schema(database_url: str | None = None) -> None:
    """Cria o schema `avaliacao` e suas tabelas. Lê DATABASE_URL do ambiente
    se `database_url` não for passado (mesmo padrão de auth/db.py)."""
    database_url = database_url or os.getenv("DATABASE_URL")
    if not database_url:
        raise RuntimeError("DATABASE_URL não definida (env ou parâmetro).")

    conn = psycopg.connect(database_url)
    try:
        with conn.cursor() as cur:
            for ddl in _DDL:
                cur.execute(ddl)
        conn.commit()
        logger.info("PostgreSQL conectado — schema avaliacao pronto.")
    finally:
        conn.close()
