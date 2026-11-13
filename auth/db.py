"""
Schema `auth`: tabelas `usuarios` e `redefinicoes_senha`. Fica separado de `public`
para que nada aqui encoste nos dados de jurisprudência. Idempotente (`IF NOT EXISTS`)
e em psycopg puro, como `scraper/db_writer.py`. Decisões em `auth/DESIGN.md`.
"""
import logging
import os

import psycopg

logger = logging.getLogger(__name__)

_CREATE_SCHEMA = """
CREATE SCHEMA IF NOT EXISTS auth;
"""

# O e-mail guarda a capitalização digitada; a unicidade ignora maiúsculas pelo índice
# em lower(email) abaixo, e não pela extensão `citext` (ver auth/DESIGN.md).
_CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS auth.usuarios (
    id              UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    email           TEXT        NOT NULL,
    hashed_password TEXT        NOT NULL,
    nome            TEXT,
    is_active       BOOLEAN     NOT NULL DEFAULT TRUE,
    criado_em       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    atualizado_em   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT usuarios_email_trimmed CHECK (email = btrim(email) AND email <> '')
);
"""

# Dados de perfil que antes ficavam só no navegador (issue #15). ADD COLUMN IF NOT EXISTS
# mantém o ensure_schema idempotente sobre tabelas já criadas sem essas colunas.
_ADD_PERFIL = """
ALTER TABLE auth.usuarios
    ADD COLUMN IF NOT EXISTS telefone TEXT,
    ADD COLUMN IF NOT EXISTS oab      TEXT,
    ADD COLUMN IF NOT EXISTS papel    TEXT;
"""

# Links de redefinição de senha (issue #14). Só o hash do token fica no banco: quem ler a
# tabela não consegue usar um link. Uso único, com validade curta.
_CREATE_REDEFINICOES = """
CREATE TABLE IF NOT EXISTS auth.redefinicoes_senha (
    id          UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    usuario_id  UUID        NOT NULL REFERENCES auth.usuarios(id) ON DELETE CASCADE,
    token_hash  TEXT        NOT NULL UNIQUE,
    criado_em   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expira_em   TIMESTAMPTZ NOT NULL,
    usado_em    TIMESTAMPTZ
);
"""

# Garante unicidade de e-mail ignorando maiúsculas/minúsculas e é o índice que
# a query de login (`WHERE lower(email) = lower(%s)`) deve usar.
_CREATE_EMAIL_INDEX = """
CREATE UNIQUE INDEX IF NOT EXISTS usuarios_email_lower_idx
    ON auth.usuarios (lower(email));
"""


def ensure_schema(database_url: str | None = None) -> None:
    """Garante schema `auth`, tabela `usuarios` e índice de e-mail. Idempotente.

    Lê DATABASE_URL do ambiente se `database_url` não for passado, igual ao
    padrão de scraper/run.py e query/api/app.py.
    """
    database_url = database_url or os.getenv("DATABASE_URL")
    if not database_url:
        raise RuntimeError("DATABASE_URL não definida (env ou parâmetro).")

    conn = psycopg.connect(database_url)
    try:
        with conn.cursor() as cur:
            cur.execute(_CREATE_SCHEMA)
            cur.execute(_CREATE_TABLE)
            cur.execute(_CREATE_EMAIL_INDEX)
            cur.execute(_ADD_PERFIL)
            cur.execute(_CREATE_REDEFINICOES)
        conn.commit()
        logger.info("PostgreSQL conectado — schema auth e tabela auth.usuarios prontos.")
    finally:
        conn.close()


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    ensure_schema()
