"""
Vector Indexer / ChromaDB.

Persiste os chunks e seus dois embeddings Poly-Vector no ChromaDB local, junto com
os metadados mínimos de filtragem. O ChromaDB guarda APENAS chunks/embeddings/metadados
de filtro — o documento integral fica no PostgreSQL (source of truth).

Poly-Vector: o Chroma armazena um embedding por registro/coleção. Modelamos DUAS
coleções espelhadas pelo mesmo `chunk_id`:
  - COLLECTION_COMPLETO → embedding_completo (chunk + SAC);
  - COLLECTION_EMENTA   → embedding_ementa (ementa/tese).
Na busca, consulta-se as duas e funde-se via RRF.

Metadados gravados por chunk:
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
    return {
        "documento_id":         chunk.documento_id,
        "tipo_documento":       chunk.tipo_documento,
        "provimento":           chunk.provimento,
        "data_julgamento":      chunk.data_julgamento or "",   # Chroma não aceita None
        "numero_processo":      chunk.numero_processo,
        "hierarquia_categoria": chunk.hierarquia_categoria,
        "posicao":              chunk.posicao,
    }
        
    


class ChromaStore:
    """Wrapper do ChromaDB persistente com as duas coleções Poly-Vector."""

    def __init__(self, persist_dir: str = CHROMA_PERSIST_DIR) -> None:
        """Abre o cliente persistente e as duas coleções.

        Input:  persist_dir — diretório de persistência do ChromaDB.
        Returns: None.
        """
        self._client = chromadb.PersistentClient(path=persist_dir)
        self._col_completo = self._abrir_colecao(COLLECTION_COMPLETO)
        self._col_ementa = self._abrir_colecao(COLLECTION_EMENTA)

    def _abrir_colecao(self, nome: str):
        """Cria (ou reabre) uma coleção com distância de cosseno como métrica de definição dos vetores.

        Input:  nome — nome da coleção.
        Returns: o objeto Collection do ChromaDB.
        """
        return self._client.get_or_create_collection(
            name=nome, metadata={"hnsw:space": "cosine"}
        )

    def add_chunks(
        self,
        chunks: list[Chunk],
        emb_completo: list[Vector],
        emb_ementa: list[Vector],
    ) -> None:
        """Indexa (upsert) um lote de chunks nas duas coleções, espelhadas por chunk_id.

        Input:  chunks; emb_completo/emb_ementa — vetores na mesma ordem dos chunks.
        Returns: None.
        """
        if not chunks:
            return
        if not (len(chunks) == len(emb_completo) == len(emb_ementa)):
            raise ValueError(
                f"Tamanhos divergentes: {len(chunks)} chunks, "
                f"{len(emb_completo)} emb_completo, {len(emb_ementa)} emb_ementa."
            )

        ids = [c.chunk_id for c in chunks]
        metadatas = [_to_metadata(c) for c in chunks]

        # upsert (não add) → re-indexar o mesmo chunk_id sobrescreve em vez de duplicar.
        self._col_completo.upsert(
            ids=ids,
            embeddings=emb_completo,
            documents=[c.texto for c in chunks],
            metadatas=metadatas,
        )
        self._col_ementa.upsert(
            ids=ids,
            embeddings=emb_ementa,
            # espelha o texto que gerou o embedding_ementa (fallback do sac vazio).
            documents=[c.sac_summary or c.texto for c in chunks],
            metadatas=metadatas,
        )

    def query(
        self,
        embedding: Vector,
        n_results: int = 20,
        where: dict | None = None,
        collection: str = COLLECTION_COMPLETO,
    ) -> list[dict]:
        """Busca vetorial numa coleção, com filtro opcional de metadados.

        Input:  embedding — vetor da query; n_results; where — filtro Chroma
                (ex.: {"provimento": "APROVADO"} ou {"data_julgamento": {"$gte": "2020-01-01"}});
                collection — COLLECTION_COMPLETO ou COLLECTION_EMENTA.
        Returns: lista de {chunk_id, documento_id, distance, metadata}, mais próximos primeiro.
        """
        col = self._col_completo if collection == COLLECTION_COMPLETO else self._col_ementa
        res = col.query(
            query_embeddings=[embedding],
            n_results=n_results,
            where=where or None,
        )
        # O Chroma devolve listas-de-listas (uma por query); pegamos a query 0.
        ids = res["ids"][0]
        distancias = res["distances"][0]
        metadatas = res["metadatas"][0]
        return [
            {
                "chunk_id": cid,
                "documento_id": meta.get("documento_id"),
                "distance": dist,
                "metadata": meta,
            }
            for cid, dist, meta in zip(ids, distancias, metadatas)
        ]

    def reset(self) -> None:
        """Apaga e recria as duas coleções (re-indexação do zero).

        Input:  nenhum.
        Returns: None.
        """
        for nome in (COLLECTION_COMPLETO, COLLECTION_EMENTA):
            try:
                self._client.delete_collection(nome)
            except Exception:
                pass  # coleção pode não existir ainda — tudo bem
        self._col_completo = self._abrir_colecao(COLLECTION_COMPLETO)
        self._col_ementa = self._abrir_colecao(COLLECTION_EMENTA)
