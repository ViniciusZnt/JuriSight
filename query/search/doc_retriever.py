"""
Doc Retriever (RFC §5.3 etapa 9 — M4).

Busca os DocumentoJuridico COMPLETOS no PostgreSQL (source of truth) a partir dos
documento_id (UUID) que a busca híbrida devolveu. O ChromaDB/BM25 guardam só
chunks e ids; o conteúdo integral (ementa, acórdão, relator, link...) vem daqui.

Reaproveitamento: a montagem de linha → DocumentoJuridico já existe em
indexing/doc_source.py (DocumentSource._row_to_documento) sobre a MESMA ordem de
colunas do _SELECT. Vale espelhar aquela lógica aqui (ou extrair para um helper
compartilhado) para não divergir.
"""
from __future__ import annotations

import psycopg

from scraper.schema import DocumentoJuridico

# Mesmas colunas do _SELECT de indexing/doc_source.py, filtrando por id (UUID).
_SELECT_BY_IDS = """
SELECT id, id_documento, tipo_documento, hierarquia_categoria, data_filtro,
       numero_processo, tribunal, classe_processo, sigla_classe,
       relator, turma, gabinete, data_julgamento, data_juntada,
       cabecalho, ementa, relatorio, fundamentacao, acordao, votos,
       possui_ementa, referencia_legislativa, provimento, link_original
FROM documentos
WHERE id = ANY(%s)
"""


class DocRetriever:
    """Busca DocumentoJuridico completos por documento_id (UUID) no PostgreSQL."""

    def __init__(self, database_url: str) -> None:
        """Guarda a URL de conexão.

        Input:  database_url — DSN do PostgreSQL.
        Returns: None.
        """
        self.database_url = database_url

    def fetch(self, documento_ids: list[str]) -> dict[str, DocumentoJuridico]:
        """Busca os documentos pelos UUIDs e devolve um mapa id -> documento.

        Devolve um DICT (não lista) para o chamador reordenar conforme o ranking do
        RRF — o SELECT ... WHERE id = ANY(...) não preserva a ordem dos ids.

        Input:  documento_ids — lista de UUIDs (os do top-N do HybridSearch).
        Returns: {documento_id: DocumentoJuridico} apenas dos ids encontrados.

        TODO:
          - if not documento_ids: return {}
          - conectar (psycopg.connect), cur.execute(_SELECT_BY_IDS, (documento_ids,));
          - para cada row: doc_uuid = str(row[0]); doc = _row_para_documento(row);
            acumular {doc_uuid: doc};
          - fechar a conexão e devolver o dict.
        """
        raise NotImplementedError


def _row_para_documento(row) -> DocumentoJuridico:
    """Constrói um DocumentoJuridico a partir de uma linha do _SELECT_BY_IDS.

    Os índices seguem a ORDEM das colunas do _SELECT_BY_IDS (row[0] = UUID id, que
    NÃO entra no schema — é a FK devolvida à parte). Colunas TEXT nulas viram "".

    Input:  row — tupla da query.
    Returns: DocumentoJuridico validado.

    TODO: espelhar indexing/doc_source.py::DocumentSource._row_to_documento
          (mesma ordem de colunas). Converter tipo_documento/provimento para os
          enums (TipoDocumento(...), Provimento(...)); TEXT nulo -> "".
    """
    raise NotImplementedError
