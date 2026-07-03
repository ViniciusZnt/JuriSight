"""
Document Source — leitura do PostgreSQL para a etapa de Indexação.

O PostgreSQL é a source of truth. A Indexação NÃO faz scraping; ela
lê os `DocumentoJuridico` já persistidos pelo Pipeline de Ingestão (scraper/) e os
entrega ao SAC Chunker. Importante: devolve também o UUID `id` da linha, que é a FK
`documento_id` referenciada no ChromaDB (não confundir com `id_documento` natural).
"""

from collections.abc import Iterator
import psycopg
from scraper.schema import DocumentoJuridico, Provimento, TipoDocumento

# Colunas necessárias para reconstruir o DocumentoJuridico + o UUID `id`.
_SELECT = """
SELECT id, id_documento, tipo_documento, hierarquia_categoria, data_filtro,
       numero_processo, tribunal, classe_processo, sigla_classe,
       relator, turma, gabinete, data_julgamento, data_juntada,
       cabecalho, ementa, relatorio, fundamentacao, acordao, votos,
       possui_ementa, referencia_legislativa, provimento, link_original
FROM documentos
ORDER BY id
"""


class DocumentSource:
    """Itera os documentos do PostgreSQL em lotes, para a Indexação."""

    def __init__(self, database_url: str) -> None:
        self.database_url = database_url
        self.conn = None

    def iter_documents(self, batch_size: int = 100) -> Iterator[tuple[str, DocumentoJuridico]]:
        """Gera (documento_id_uuid, DocumentoJuridico) usando server-side cursor.
        """
        self.conn = psycopg.connect(self.database_url)
        with self.conn.cursor(name="idx_docs") as cur:
          cur.itersize = batch_size
          cur.execute(_SELECT)
          for row in cur:
            doc_uuid = str(row[0])
            doc = self._row_to_documento(row)
            yield (doc_uuid, doc)
    
    
    def _row_to_documento(self, row) -> DocumentoJuridico:
        """Constrói um DocumentoJuridico a partir de uma linha do _SELECT.

        Os índices seguem a ORDEM EXATA das colunas em _SELECT — row[0] é o UUID
        `id` (tratado à parte em iter_documents, não entra no schema). 
        Colunas TEXT nulas voltam como None; transformamos para "" (o schema tipa esses campos como
        str não-opcional). referencia_legislativa (TEXT[]) volta como list ou None.
        """
        return DocumentoJuridico(
            # row[0] = id (UUID) — não entra aqui, é a FK devolvida separadamente
            id_documento         = row[1],
            tipo_documento       = TipoDocumento(row[2]),
            hierarquia_categoria = row[3],
            data_filtro          = row[4],
            numero_processo      = row[5]  or "",
            tribunal             = row[6]  or "",
            classe_processo      = row[7]  or "",
            sigla_classe         = row[8]  or "",
            relator              = row[9]  or "",
            turma                = row[10] or "",
            gabinete             = row[11] or "",
            data_julgamento      = row[12],
            data_juntada         = row[13],
            cabecalho            = row[14] or "",
            ementa               = row[15] or "",
            relatorio            = row[16] or "",
            fundamentacao        = row[17] or "",
            acordao              = row[18] or "",
            votos                = row[19] or "",
            possui_ementa        = row[20] or False,
            referencia_legislativa = row[21] or [],
            provimento           = Provimento(row[22]),
            link_original        = row[23],
        )
