"""
Auth DB.

Cria o schema `auth` e a tabela `auth.usuarios` — cadastro e credenciais dos
usuários reais da aplicação (hoje a autenticação é toda mockada no frontend,
ver frontend/src/lib/*; isto é a base de dados para a peça de login real).

Deliberadamente isolado do schema `public`, onde vivem `documentos` e
`scraper_state` (scraper/db_writer.py) — nenhuma operação daqui encosta em
dados de jurisprudência, e um `DROP SCHEMA auth` futuro (ex.: testes) nunca
arrisca a base coletada. Ver auth/SCHEMA.md para o raciocínio completo do
desenho (schema/tabela/colunas, e-mail case-insensitive).

Idempotente (CREATE SCHEMA/TABLE/INDEX IF NOT EXISTS) — seguro rodar mais de
uma vez. Segue o mesmo estilo de scraper/db_writer.py: psycopg puro, sem
ORM/Alembic, string(s) de DDL em módulo + função que aplica via DATABASE_URL.
"""
import logging
import os

import psycopg

logger = logging.getLogger(__name__)

_CREATE_SCHEMA = """
CREATE SCHEMA IF NOT EXISTS auth;
"""

# E-mail é armazenado como o usuário digitou (preserva capitalização para
# exibição), mas login/unicidade são case-insensitive — ver o índice funcional
# abaixo. Optamos por lower(email) em vez da extensão `citext` (motivo em
# auth/SCHEMA.md): nenhuma outra parte do projeto usa extensões Postgres além
# do gen_random_uuid() nativo (>= PG13, já usado por scraper/db_writer.py), e
# isto evita depender de uma extensão adicional só para esta tabela.
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
