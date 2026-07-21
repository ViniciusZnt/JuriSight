"""
Doc Retriever .

Busca os DocumentoJuridico COMPLETOS no PostgreSQL (source of truth) a partir dos
documento_id (UUID) que a busca híbrida devolveu.
"""
import psycopg
from scraper.schema import DocumentoJuridico, Provimento, TipoDocumento

# Mesmas colunas do _SELECT de indexing/doc_source.py, filtrando por id (UUID).
_SELECT_BY_IDS = """
SELECT id, id_documento, tipo_documento, hierarquia_categoria, data_filtro,
       numero_processo, tribunal, classe_processo, sigla_classe,
       relator, turma, gabinete, data_julgamento, data_juntada,
       cabecalho, ementa, relatorio, fundamentacao, acordao, votos,
       possui_ementa, referencia_legislativa, provimento, link_original
FROM documentos
WHERE id = ANY(%s::uuid[])
"""


class DocRetriever:
    """Busca DocumentoJuridico completos por documento_id (UUID) no PostgreSQL."""

    def __init__(self, database_url: str) -> None:
        """Guarda a URL de conexão.

        Input:  database_url — DSN do PostgreSQL.
        Returns: None.
        """
        self.database_url = database_url
        self._conn = None

    def fetch(self, documento_ids: list[str]) -> dict[str, DocumentoJuridico]:
        """Busca os documentos pelos UUIDs e devolve um mapa id -> documento.


        Input:  documento_ids — lista de UUIDs.
        Returns: {documento_id: DocumentoJuridico} apenas dos ids encontrados (não vem ordenado).
        """
        if not documento_ids:
            return {}

        self._conn = psycopg.connect(self.database_url)
        try:
            with self._conn.cursor() as cur:
                cur.execute(_SELECT_BY_IDS, (documento_ids,))
                rows = cur.fetchall()
        finally:
            self._conn.close()

        return {str(row[0]): _row_para_documento(row) for row in rows}


def _row_para_documento(row) -> DocumentoJuridico:
    """Constrói um DocumentoJuridico a partir de uma linha do _SELECT_BY_IDS.

    Os índices seguem a ORDEM das colunas do _SELECT_BY_IDS (row[0] = UUID id, que
    NÃO entra no schema — é a FK devolvida à parte). Colunas TEXT nulas viram "".

    Input:  row — tupla da query.
    Returns: DocumentoJuridico validado.
    """
    return DocumentoJuridico(
        # row[0] = id (UUID) — devolvido à parte, não entra no schema
        id_documento           = row[1],
        tipo_documento         = TipoDocumento(row[2]),
        hierarquia_categoria   = row[3],
        data_filtro            = row[4],
        numero_processo        = row[5]  or "",
        tribunal               = row[6]  or "",
        classe_processo        = row[7]  or "",
        sigla_classe           = row[8]  or "",
        relator                = row[9]  or "",
        turma                  = row[10] or "",
        gabinete               = row[11] or "",
        data_julgamento        = row[12],
        data_juntada           = row[13],
        cabecalho              = row[14] or "",
        ementa                 = row[15] or "",
        relatorio              = row[16] or "",
        fundamentacao          = row[17] or "",
        acordao                = row[18] or "",
        votos                  = row[19] or "",
        possui_ementa          = row[20] or False,
        referencia_legislativa = row[21] or [],
        provimento             = Provimento(row[22]),
        link_original          = row[23],
    )
