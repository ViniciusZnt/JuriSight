"""
Tabela `public.conversas`: o histórico de busca de cada usuário (barra lateral).

Cada busca (a original e cada "Refinar consulta") é uma VERSÃO no array JSONB
`versoes`, sem sobrescrever a anterior, para o seletor V1/V2/V3 do frontend. Item:
{numero, estrutura, has_file, file_name, pdf_extraido, aviso, resultados, criado_em}.
`estrutura` é a EstruturaArgumentativa já revisada e `resultados` são os ResultCard
do /query. Nunca se persiste o PDF enviado nem o texto extraído dele: `has_file` e
`file_name` são só metadados de exibição (RFC §6.1, LGPD).

Fica em `public` porque é dado de uso, não credencial. A FK para `auth.usuarios`
com ON DELETE CASCADE apaga o histórico junto com a conta. Idempotente, inclusive
sobre a versão antiga da tabela (snapshot único em colunas soltas), que as
migrações abaixo convertem.
"""
import logging
import os

import psycopg

logger = logging.getLogger(__name__)

_CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS public.conversas (
    id              UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    usuario_id      UUID        NOT NULL REFERENCES auth.usuarios(id) ON DELETE CASCADE,
    titulo          TEXT        NOT NULL,
    criado_em       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    atualizado_em   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    versoes         JSONB       NOT NULL DEFAULT '[]'::jsonb
);
"""

# Migração do schema anterior (snapshot único em colunas soltas) pro array de
# versões — idempotente nos dois sentidos: roda sem erro tanto numa tabela
# nova (nada a adicionar/remover) quanto numa já populada pela versão antiga.
_MIGRACAO_ADICIONA_VERSOES = """
ALTER TABLE public.conversas ADD COLUMN IF NOT EXISTS versoes JSONB NOT NULL DEFAULT '[]'::jsonb;
"""
_MIGRACAO_REMOVE_COLUNAS_SNAPSHOT_UNICO = """
ALTER TABLE public.conversas
    DROP COLUMN IF EXISTS estrutura,
    DROP COLUMN IF EXISTS has_file,
    DROP COLUMN IF EXISTS file_name,
    DROP COLUMN IF EXISTS pdf_extraido,
    DROP COLUMN IF EXISTS aviso,
    DROP COLUMN IF EXISTS resultados;
"""

# Sidebar lista as conversas do usuário ordenadas por recência — índice cobre
# exatamente esse acesso (WHERE usuario_id = ... ORDER BY criado_em DESC).
_CREATE_INDEX = """
CREATE INDEX IF NOT EXISTS conversas_usuario_id_criado_em_idx
    ON public.conversas (usuario_id, criado_em DESC);
"""


def ensure_schema(database_url: str | None = None) -> None:
    """Garante a tabela `conversas` (com o array `versoes`) e seu índice.
    Idempotente — inclui a migração do schema de snapshot único anterior.

    Lê DATABASE_URL do ambiente se `database_url` não for passado, igual ao
    padrão de auth/db.py e query/api/app.py. Pressupõe que `auth.usuarios`
    já existe (a FK falha se não) — por isso o lifespan chama
    `auth.db.ensure_schema` antes deste.
    """
    database_url = database_url or os.getenv("DATABASE_URL")
    if not database_url:
        raise RuntimeError("DATABASE_URL não definida (env ou parâmetro).")

    conn = psycopg.connect(database_url)
    try:
        with conn.cursor() as cur:
            cur.execute(_CREATE_TABLE)
            cur.execute(_MIGRACAO_ADICIONA_VERSOES)
            cur.execute(_MIGRACAO_REMOVE_COLUNAS_SNAPSHOT_UNICO)
            cur.execute(_CREATE_INDEX)
        conn.commit()
        logger.info("PostgreSQL conectado — tabela public.conversas (com versoes) pronta.")
    finally:
        conn.close()
