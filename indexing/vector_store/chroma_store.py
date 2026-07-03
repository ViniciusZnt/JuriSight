"""
Vector Indexer / ChromaDB (componente C4 — Pipeline de Ingestão / RFC §5.3 etapa 5, Decisão 11).

Persiste os chunks e seus dois embeddings Poly-Vector no ChromaDB local, junto com
os metadados mínimos de filtragem. O ChromaDB guarda APENAS chunks/embeddings/metadados
de filtro — o documento integral fica no PostgreSQL (source of truth, Decisão 11).

Poly-Vector: o Chroma armazena um embedding por registro/coleção. Modelamos DUAS
coleções espelhadas pelo mesmo `chunk_id`:
  - COLLECTION_COMPLETO → embedding_completo (chunk + SAC);
  - COLLECTION_EMENTA   → embedding_ementa (ementa/tese).
Na busca, consulta-se as duas e funde-se via RRF.

Metadados gravados por chunk (RFC §5.2 — schema de metadados do ChromaDB):
  documento_id, tipo_documento, provimento, data_julgamento,
  numero_processo, hierarquia_categoria, posicao.
"""
from __future__ import annotations

import os

import chromadb

from processing.chunking.sac_chunker import Chunk

CHROMA_PERSIST_DIR = os.getenv("CHROMA_PERSIST_DIR", "./data/index")
COLLECTION_COMPLETO = "chunks_completo"
COLLECTION_EMENTA = "chunks_ementa"

Vector = list[float]


def _to_metadata(chunk: Chunk) -> dict:
    """Extrai o dict de metadados de filtragem de um Chunk para o ChromaDB.

    ChromaDB aceita só tipos escalares (str/int/float/bool) — nada de None/listas.
    TODO: mapear campos e tratar data_julgamento None (ex.: string vazia).
    """
    raise NotImplementedError


class ChromaStore:
    """Wrapper do ChromaDB persistente com as duas coleções Poly-Vector."""

    def __init__(self, persist_dir: str = CHROMA_PERSIST_DIR) -> None:
        self._client = chromadb.PersistentClient(path=persist_dir)
        # TODO: get_or_create_collection para COLLECTION_COMPLETO e COLLECTION_EMENTA.
        #       Definir metadata={"hnsw:space": "cosine"} (alinhar com normalização do embedder).
        self._col_completo = None
        self._col_ementa = None

    def add_chunks(
        self,
        chunks: list[Chunk],
        emb_completo: list[Vector],
        emb_ementa: list[Vector],
    ) -> None:
        """Indexa um lote de chunks nas duas coleções.

        Usa o mesmo `chunk_id` como id nas duas coleções (espelhamento).
        TODO:
          - col_completo.upsert(ids, embeddings=emb_completo, documents=textos, metadatas);
          - col_ementa.upsert(ids,   embeddings=emb_ementa,   documents=sac_summaries, metadatas);
          - upsert (não add) p/ idempotência em re-indexação.
        """
        raise NotImplementedError

    def query(
        self,
        embedding: Vector,
        n_results: int = 20,
        where: dict | None = None,
        collection: str = COLLECTION_COMPLETO,
    ) -> list[dict]:
        """Busca vetorial numa das coleções, com filtro opcional de metadados.

        `where` segue a sintaxe do Chroma, ex.: {"provimento": "APROVADO"} ou
        {"data_julgamento": {"$gte": "2020-01-01"}} (UC03/UC05).
        Retorna lista de {chunk_id, documento_id, distance, metadata}.
        TODO: implementar e normalizar o formato de retorno.
        """
        raise NotImplementedError

    def reset(self) -> None:
        """Apaga e recria as coleções (re-indexação do zero)."""
        raise NotImplementedError
