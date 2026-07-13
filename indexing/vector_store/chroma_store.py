"""
Vector Indexer / ChromaDB.

Persiste os chunks e seus dois embeddings Poly-Vector no ChromaDB local, junto com
os metadados mínimos de filtragem. O ChromaDB guarda APENAS chunks/embeddings/metadados
de filtro — o documento integral fica no PostgreSQL (source of truth).

Poly-Vector: o Chroma armazena um embedding por registro/coleção. Modelamos DUAS
coleções, em granularidades diferentes:
  - COLLECTION_COMPLETO → embedding_completo (chunk + SAC): um registro por CHUNK
    (id = chunk_id);
  - COLLECTION_EMENTA   → embedding_ementa (ementa/tese): um registro por DOCUMENTO
    (id = documento_id). A ementa é a mesma em todos os chunks do doc, então
    guardá-la por chunk seria redundante prejudicaria o ranking.

Metadados de filtragem: documento_id, tipo_documento, provimento, data_julgamento,
numero_processo, hierarquia_categoria (+ posicao só na coleção por chunk).
"""
import os
import chromadb
from processing.chunking.sac_chunker import Chunk

CHROMA_PERSIST_DIR = os.getenv("CHROMA_PERSIST_DIR", "./data/index")
COLLECTION_COMPLETO = "chunks_completo"
COLLECTION_EMENTA = "chunks_ementa"

Vector = list[float]


def _to_metadata(chunk: Chunk) -> dict:
    """Monta os metadados de filtragem por-CHUNK para o ChromaDB.

    Input:  chunk.
    Returns: dict só com escalares (Chroma não aceita None/listas); data_julgamento None vira "".
    """
    return {
        "documento_id":         chunk.documento_id,
        "tipo_documento":       chunk.tipo_documento,
        "provimento":           chunk.provimento,
        "data_julgamento":      chunk.data_julgamento or "",
        "numero_processo":      chunk.numero_processo,
        "hierarquia_categoria": chunk.hierarquia_categoria,
        "posicao":              chunk.posicao,
    }


def _to_metadata_documento(chunk: Chunk) -> dict:
    """Metadados por-DOCUMENTO para a coleção da ementa.

    Input:  chunk — um representante do documento.
    Returns: mesmo dict de _to_metadata, sem a chave 'posicao'.
    """
    meta = _to_metadata(chunk)
    meta.pop("posicao", None)
    return meta


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
        """Indexa (upsert) um lote nas duas coleções.

        COMPLETO é por chunk (id = chunk_id); EMENTA é por documento (id =
        documento_id) - (a ementa é a mesma em todos os chunks do doc).

        Input:  chunks; (emb_completo, emb_ementa) — vetores na mesma ordem dos chunks.
        Returns: None.
        """
        if not chunks:
            return
        if not (len(chunks) == len(emb_completo) == len(emb_ementa)):
            raise ValueError(
                f"Tamanhos divergentes: {len(chunks)} chunks, "
                f"{len(emb_completo)} emb_completo, {len(emb_ementa)} emb_ementa."
            )

        # COMPLETO: um registro por chunk. upsert → chunk_id sobrescreve em vez de duplicar
        self._col_completo.upsert(
            ids=[c.chunk_id for c in chunks],
            embeddings=emb_completo,
            documents=[c.texto for c in chunks],
            metadatas=[_to_metadata(c) for c in chunks],
        )

        # EMENTA: um registro por documento. Como o vetor de ementa é o mesmo em
        # todos os chunks de um doc, percorremos os chunks e guardamos só o 1º de
        # cada documento_id (o `set` lembra quais já entraram).
        vistos: set[str] = set()
        ids, embeddings, documents, metadatas = [], [], [], []
        for c, emb in zip(chunks, emb_ementa):
            if c.documento_id in vistos:
                continue
            vistos.add(c.documento_id)
            ids.append(c.documento_id)
            embeddings.append(emb)
            documents.append(c.sac_summary or c.texto)
            metadatas.append(_to_metadata_documento(c))

        self._col_ementa.upsert(
            ids=ids,
            embeddings=embeddings,
            documents=documents,
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
                collection — COLLECTION_COMPLETO (id = chunk_id) ou COLLECTION_EMENTA
                (id = documento_id).
        Returns: lista de {id, documento_id, distance, metadata}, mais próximos primeiro.
                 Em COMPLETO o id é o chunk_id; em EMENTA o id é o próprio documento_id.
        """
        col = self._col_completo if collection == COLLECTION_COMPLETO else self._col_ementa
        res = col.query(
            query_embeddings=[embedding],
            n_results=n_results,
            where=where or None,
        )
        # O Chroma devolve list[list] (uma por query); pegamos a query 0.
        ids = res["ids"][0]
        distancias = res["distances"][0]
        metadatas = res["metadatas"][0]

        resultados = []
        for rid, dist, meta in zip(ids, distancias, metadatas):
            resultados.append(
                {
                    "id": rid,
                    "documento_id": meta.get("documento_id"),
                    "distance": dist,
                    "metadata": meta,
                }
            )
        return resultados

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
