import logging
from datetime import datetime, timezone
from pathlib import Path

import psycopg

from scraper.html_parser import parse_document

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


_COLECAO_META = {
    "sumulas":     {"tipo_documento": "SUMULA",     "hierarquia_categoria": 1},
    "ojs":         {"tipo_documento": "OJ",         "hierarquia_categoria": 2},
    "precedentes": {"tipo_documento": "PRECEDENTE", "hierarquia_categoria": 3},
    "acordaos":    {"tipo_documento": "ACORDAO",    "hierarquia_categoria": 4},
}

# Possíveis nomes do campo de ID por coleção
_ID_FIELDS = [
    "idDocumentoAcordao",
    "idDocumento",
    "id",
]


class PostgresStore:
    """Substitui o JsonlStore do teste — persiste direto no PostgreSQL."""

    def __init__(self, database_url: str):
        self.database_url = database_url
        self._conn = None
        self._buffer: list[dict] = []

    def connect(self) -> None:
        self._conn = psycopg.connect(self.database_url)
        with self._conn.cursor() as cur:
            cur.execute(_CREATE_TABLE)
        self._conn.commit()
        logger.info("PostgreSQL conectado — tabela documentos pronta.")

    def close(self) -> None:
        if self._buffer:
            self._flush()
        if self._conn:
            self._conn.close()

    def append_document(self, doc: dict) -> bool:
        doc_id = next((doc[f] for f in _ID_FIELDS if doc.get(f)), "")
        if not doc_id:
            logger.warning("Documento sem ID ignorado: %s", doc.get("numeroProcesso"))
            return False

        colecao = doc.get("_colecao", "acordaos")
        meta    = _COLECAO_META.get(colecao, _COLECAO_META["acordaos"])

        parsed   = parse_document(doc.get("ementa", ""), doc.get("textoAcordao", ""))
        sections = parsed["acordao_section"]

        row = {
            "id_documento":           doc_id,
            "tipo_documento":         meta["tipo_documento"],
            "hierarquia_categoria":   meta["hierarquia_categoria"],
            "data_filtro":            doc.get("_data_filtro", ""),
            "numero_processo":        doc.get("numeroProcesso", ""),
            "tribunal":               doc.get("tribunal", ""),
            "classe_processo":        doc.get("classeProcesso", ""),
            "sigla_classe":           doc.get("siglaClasseProcesso", ""),
            "relator":                doc.get("relator", ""),
            "turma":                  doc.get("turma", ""),
            "gabinete":               doc.get("gabinete", ""),
            "data_julgamento":        doc.get("dataJulgamento", ""),
            "data_juntada":           doc.get("dataJuntada", ""),
            "cabecalho":              sections.get("cabecalho", ""),
            "ementa":                 parsed["ementa"] or sections.get("ementa", ""),
            "relatorio":              sections.get("relatorio", ""),
            "fundamentacao":          sections.get("fundamentacao", ""),
            "acordao":                sections.get("acordao", ""),
            "votos":                  sections.get("votos", ""),
            "possui_ementa":          doc.get("possuiEmenta", "N") == "S",
            "referencia_legislativa": doc.get("referenciaLegislativa", []),
            "scraped_at":             datetime.now(tz=timezone.utc),
        }

        self._buffer.append(row)
        if len(self._buffer) >= BUFFER_SIZE:
            self._flush()

        return True

    def get_last_collected_date(self) -> str | None:
        """Retorna o maior data_filtro já coletado, ou None se vazio."""
        with self._conn.cursor() as cur:
            cur.execute(r"""
                SELECT MAX(
                    CASE
                        WHEN data_filtro ~ '^\d{4}-\d{2}-\d{2}$' THEN TO_DATE(data_filtro, 'YYYY-MM-DD')
                        WHEN data_filtro ~ '^\d{2}/\d{2}/\d{4}$' THEN TO_DATE(data_filtro, 'DD/MM/YYYY')
                    END
                )
                FROM documentos
                WHERE data_filtro IS NOT NULL AND data_filtro != ''
            """)
            result = cur.fetchone()
        return result[0].isoformat() if result and result[0] else None

    def _flush(self) -> None:
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


class CheckpointStore:
    """Salva o progresso em arquivo para permitir retomada após interrupção."""

    import json as _json
    from datetime import datetime as _dt

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def load(self) -> dict | None:
        if not self.path.exists():
            return None
        import json
        return json.loads(self.path.read_text(encoding="utf-8"))

    def save(self, state: dict) -> None:
        import json
        from datetime import datetime
        payload = dict(state)
        payload["updated_at"] = datetime.utcnow().isoformat() + "Z"
        self.path.write_text(
            json.dumps(payload, indent=2, sort_keys=True),
            encoding="utf-8",
        )
