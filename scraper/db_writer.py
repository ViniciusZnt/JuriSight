"""
DB Writer.

Persiste o `DocumentoJuridico` validado no PostgreSQL (source of truth, RFC §5.2).
Recebe o documento bruto da API, delega a montagem/validação ao Doc Builder e
faz upsert em lote. A chave natural `id_documento` garante idempotência; o `id`
UUID é a referência usada como FK (`documento_id`) pelos chunks no ChromaDB.
"""
import logging
from datetime import datetime, timezone

import psycopg
from psycopg.types.json import Jsonb

from scraper.doc_builder import build_document

logger = logging.getLogger(__name__)

BUFFER_SIZE = 100

_CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS documentos (
    id                     UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    id_documento           TEXT        UNIQUE NOT NULL,
    tipo_documento         TEXT,
    hierarquia_categoria   INTEGER,
    data_filtro            DATE,
    numero_processo        TEXT,
    tribunal               TEXT,
    classe_processo        TEXT,
    sigla_classe           TEXT,
    relator                TEXT,
    turma                  TEXT,
    gabinete               TEXT,
    data_julgamento        DATE,
    data_juntada           DATE,
    cabecalho              TEXT,
    ementa                 TEXT,
    relatorio              TEXT,
    fundamentacao          TEXT,
    acordao                TEXT,
    votos                  TEXT,
    possui_ementa          BOOLEAN,
    referencia_legislativa TEXT[],
    provimento             TEXT,
    link_original          TEXT,
    created_at             TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    scraped_at             TIMESTAMPTZ NOT NULL
);
"""

# created_at fica de fora do DO UPDATE — preserva a data original do primeiro scrape.
# id (UUID) também: gerado uma vez no INSERT e estável entre re-scrapes.
_UPSERT = """
INSERT INTO documentos (
    id_documento, tipo_documento, hierarquia_categoria, data_filtro,
    numero_processo, tribunal, classe_processo, sigla_classe,
    relator, turma, gabinete, data_julgamento, data_juntada,
    cabecalho, ementa, relatorio, fundamentacao, acordao, votos,
    possui_ementa, referencia_legislativa, provimento, link_original, scraped_at
) VALUES (
    %(id_documento)s, %(tipo_documento)s, %(hierarquia_categoria)s, %(data_filtro)s,
    %(numero_processo)s, %(tribunal)s, %(classe_processo)s, %(sigla_classe)s,
    %(relator)s, %(turma)s, %(gabinete)s, %(data_julgamento)s, %(data_juntada)s,
    %(cabecalho)s, %(ementa)s, %(relatorio)s, %(fundamentacao)s, %(acordao)s, %(votos)s,
    %(possui_ementa)s, %(referencia_legislativa)s, %(provimento)s, %(link_original)s, %(scraped_at)s
)
ON CONFLICT (id_documento) DO UPDATE SET
    tipo_documento         = EXCLUDED.tipo_documento,
    hierarquia_categoria   = EXCLUDED.hierarquia_categoria,
    data_filtro            = EXCLUDED.data_filtro,
    numero_processo        = EXCLUDED.numero_processo,
    tribunal               = EXCLUDED.tribunal,
    classe_processo        = EXCLUDED.classe_processo,
    sigla_classe           = EXCLUDED.sigla_classe,
    relator                = EXCLUDED.relator,
    turma                  = EXCLUDED.turma,
    gabinete               = EXCLUDED.gabinete,
    data_julgamento        = EXCLUDED.data_julgamento,
    data_juntada           = EXCLUDED.data_juntada,
    cabecalho              = EXCLUDED.cabecalho,
    ementa                 = EXCLUDED.ementa,
    relatorio              = EXCLUDED.relatorio,
    fundamentacao          = EXCLUDED.fundamentacao,
    acordao                = EXCLUDED.acordao,
    votos                  = EXCLUDED.votos,
    possui_ementa          = EXCLUDED.possui_ementa,
    referencia_legislativa = EXCLUDED.referencia_legislativa,
    provimento             = EXCLUDED.provimento,
    link_original          = EXCLUDED.link_original,
    scraped_at             = EXCLUDED.scraped_at;
"""

# Estado retomável da coleta, por coleção — substitui o checkpoint em arquivo.
_CREATE_STATE_TABLE = """
CREATE TABLE IF NOT EXISTS scraper_state (
    colecao    TEXT        PRIMARY KEY,
    estado     JSONB       NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
"""


class PostgresWriter:
    """Persiste documentos jurídicos no PostgreSQL em lote (buffer + upsert)."""

    def __init__(self, database_url: str):
        self.database_url = database_url
        self._conn = None
        self._buffer: list[dict] = []

    def connect(self) -> None:
        self._conn = psycopg.connect(self.database_url)
        with self._conn.cursor() as cur:
            cur.execute(_CREATE_TABLE)
            cur.execute(_CREATE_STATE_TABLE)
        self._conn.commit()
        logger.info("PostgreSQL conectado — tabelas documentos e scraper_state prontas.")

    def reset(self) -> None:
        """Dropa e recria documentos e zera o scraper_state — re-scrape do zero."""
        with self._conn.cursor() as cur:
            cur.execute("DROP TABLE IF EXISTS documentos;")
            cur.execute(_CREATE_TABLE)
            cur.execute("DELETE FROM scraper_state;")
        self._conn.commit()
        logger.warning("Tabela documentos recriada e scraper_state zerado (reset).")

    def close(self) -> None:
        if self._buffer:
            self._flush()
        if self._conn:
            self._conn.close()

    def append_document(self, raw: dict) -> bool:
        """Monta, valida e enfileira um documento bruto da API. Retorna False se descartado."""
        documento = build_document(raw)
        if documento is None:
            return False

        row = documento.model_dump(mode="json")
        row["scraped_at"] = datetime.now(tz=timezone.utc)
        self._buffer.append(row)

        if len(self._buffer) >= BUFFER_SIZE:
            self._flush()

        return True

    def get_last_collected_date(self) -> str | None:
        """Retorna o maior data_filtro já coletado, ou None se vazio."""
        with self._conn.cursor() as cur:
            cur.execute("SELECT MAX(data_filtro) FROM documentos WHERE data_filtro IS NOT NULL")
            result = cur.fetchone()
        return result[0].isoformat() if result and result[0] else None

    def find_all_gaps(self, start_date: str, end_date_exclusive: str) -> str | None:
        """Retorna todas as datas sem documento no intervalo [start_date, end_date_exclusive)."""
        if start_date >= end_date_exclusive:
            return 
        with self._conn.cursor() as cur:
            cur.execute(
                """
                WITH limites AS (
                    SELECT 
                        MIN(data_filtro) AS primeiro_dia,
                        MAX(data_filtro) AS ultimo_dia
                    FROM documentos
                ), calendario AS (
                    SELECT generate_series(
                        (SELECT primeiro_dia FROM limites),
                        (SELECT ultimo_dia FROM limites),
                        '1 day'::INTERVAL
                    )::DATE AS dia
                )
                SELECT 
                    c.dia AS data_sem_coleta
                FROM calendario c
                LEFT JOIN documentos d ON c.dia = d.data_filtro
                WHERE d.data_filtro IS NULL
                ORDER BY c.dia;
                """
            )
            rows = cur.fetchall()
        if not rows:
            return None
        return "\n".join(row[0].isoformat() for row in rows)

    def load_state(self, colecao: str) -> dict | None:
        """Lê o estado JSONB salvo para a coleção (scraper_state), ou None."""
        with self._conn.cursor() as cur:
            cur.execute("SELECT estado FROM scraper_state WHERE colecao = %s", (colecao,))
            row = cur.fetchone()
        return row[0] if row else None

    def save_state(self, colecao: str, estado: dict) -> None:
        """Grava (upsert) o estado JSONB da coleção, com updated_at = agora."""
        with self._conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO scraper_state (colecao, estado, updated_at)
                VALUES (%s, %s, NOW())
                ON CONFLICT (colecao) DO UPDATE
                  SET estado = EXCLUDED.estado, updated_at = NOW()
                """,
                (colecao, Jsonb(estado)),
            )
        self._conn.commit()

    def _flush(self) -> None:
        if not self._buffer:
            return
        try:
            with self._conn.cursor() as cur:
                cur.executemany(_UPSERT, self._buffer)
            self._conn.commit()
            logger.info("Flush: %d documentos persistidos.", len(self._buffer))
        except Exception as e:
            self._conn.rollback()
            logger.error("Erro no flush: %s", e)
        finally:
            self._buffer.clear()
