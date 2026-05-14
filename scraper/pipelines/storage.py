import logging
from datetime import datetime, timezone
import psycopg

logger = logging.getLogger(__name__)

BUFFER_SIZE = 100

_CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS documentos (
    id                     SERIAL PRIMARY KEY,
    id_documento           TEXT        UNIQUE NOT NULL,
    tipo_documento         TEXT,
    hierarquia_categoria   INTEGER,
    data_filtro            TEXT,
    numero_processo        TEXT,
    tribunal               TEXT,
    classe_processo        TEXT,
    sigla_classe           TEXT,
    relator                TEXT,
    turma                  TEXT,
    gabinete               TEXT,
    data_julgamento        TEXT,
    data_juntada           TEXT,
    cabecalho              TEXT,
    ementa                 TEXT,
    relatorio              TEXT,
    fundamentacao          TEXT,
    acordao                TEXT,
    votos                  TEXT,
    possui_ementa          BOOLEAN,
    referencia_legislativa TEXT[],
    created_at             TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    scraped_at             TIMESTAMPTZ NOT NULL
);
"""

# created_at fica de fora do DO UPDATE — preserva a data original do primeiro scrape.
_UPSERT = """
INSERT INTO documentos (
    id_documento, tipo_documento, hierarquia_categoria, data_filtro,
    numero_processo, tribunal, classe_processo, sigla_classe,
    relator, turma, gabinete, data_julgamento, data_juntada,
    cabecalho, ementa, relatorio, fundamentacao, acordao, votos,
    possui_ementa, referencia_legislativa, scraped_at
) VALUES (
    %(id_documento)s, %(tipo_documento)s, %(hierarquia_categoria)s, %(data_filtro)s,
    %(numero_processo)s, %(tribunal)s, %(classe_processo)s, %(sigla_classe)s,
    %(relator)s, %(turma)s, %(gabinete)s, %(data_julgamento)s, %(data_juntada)s,
    %(cabecalho)s, %(ementa)s, %(relatorio)s, %(fundamentacao)s, %(acordao)s, %(votos)s,
    %(possui_ementa)s, %(referencia_legislativa)s, %(scraped_at)s
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
    scraped_at             = EXCLUDED.scraped_at;
"""


class PostgresStoragePipeline:
    def __init__(self, database_url: str):
        self.database_url = database_url
        self._conn = None
        self._buffer: list[dict] = []

    @classmethod
    def from_crawler(cls, crawler):
        return cls(
            database_url=crawler.settings.get(
                "DATABASE_URL",
                "postgresql://postgres:postgres@localhost:5432/jurisight",
            )
        )

    def open_spider(self):
        self._conn = psycopg.connect(self.database_url)
        with self._conn.cursor() as cur:
            cur.execute(_CREATE_TABLE)
        self._conn.commit()
        logger.info("PostgreSQL conectado — tabela documentos pronta.")

    def close_spider(self):
        if self._buffer:
            self._flush()
        if self._conn:
            self._conn.close()

    def process_item(self, item):
        doc_id = item.get("id_documento")
        if not doc_id:
            logger.warning(
                f"Item sem id_documento descartado: {item.get('numero_processo')}"
            )
            return item

        row = dict(item)
        row["scraped_at"] = datetime.now(tz=timezone.utc)
        self._buffer.append(row)

        if len(self._buffer) >= BUFFER_SIZE:
            self._flush()

        return item

    def _flush(self):
        if not self._buffer:
            return
        try:
            with self._conn.cursor() as cur:
                cur.executemany(_UPSERT, self._buffer)
            self._conn.commit()
            logger.info(f"Flush: {len(self._buffer)} documentos persistidos.")
        except Exception as e:
            self._conn.rollback()
            logger.error(f"Erro no flush: {e}")
        finally:
            self._buffer.clear()
