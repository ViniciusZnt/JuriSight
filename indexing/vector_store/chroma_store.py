"""
Vector Indexer.

Persiste os chunks e seus dois embeddings Poly-Vector no ChromaDB, com os metadados
de filtragem. O Chroma guarda um embedding por registro, então usamos DUAS coleções:

  - COLLECTION_COMPLETO → um registro por CHUNK  (id = chunk_id);
  - COLLECTION_EMENTA   → um registro por DOCUMENTO (id = documento_id).
    Como a ementa já está sendo abordada pelo SAC em todos os chunks do doc, então
    guardá-la novamente aqui seria redundante, por isso guardamos apenas o documento_id.

Metadados de filtragem: documento_id, tipo_documento, provimento, data_julgamento,
numero_processo, hierarquia_categoria.
"""
import logging
from chromadb import Collection
from chromadb.api import ClientAPI
from processing.chunking.sac_chunker import Chunk

logger = logging.getLogger(__name__)

COLLECTION_COMPLETO = "chunks_completo"
COLLECTION_EMENTA = "chunks_ementa"

# Parâmetros do HNSW (grafo de busca vetorial):
# - sync_threshold: a cada N vetores, grava o grafo no disco. Controla a frequência de
#   escrita (o grafo fica todo em RAM de qualquer forma); mais alto = menos fsyncs.
# - batch_size: buffer em memória mesclado no grafo ao encher. Deve ser <= sync_threshold.
_SYNC_THRESHOLD = 10000
_BATCH_SIZE = 3000

Vector = list[float]


def _to_metadata(chunk: Chunk) -> dict:
    """Monta os metadados de filtragem por-CHUNK para COLLECTION_COMPLETO.

    Input:  chunk.
    Returns: dict só com escalares (Chroma não aceita None/listas).
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
    """Metadados por-DOCUMENTO para a COLLECTION_EMENTA.

    Input:  chunk.
    Returns: dict, sem a chave 'posicao'.
    """
    meta = _to_metadata(chunk)
    meta.pop("posicao", None)
    return meta


class ChromaStore:
    """Wrapper do ChromaDB persistente com as duas coleções Poly-Vector."""

    def __init__(self, client: ClientAPI) -> None:
        """Recebe o cliente Chroma (injetado) e abre as duas coleções.

        Input:  client — cliente Chroma síncrono (PersistentClient ou HttpClient).
        Returns: None.
        """
        self._client = client
        self._col_completo = self._abrir_colecao(COLLECTION_COMPLETO)
        self._col_ementa = self._abrir_colecao(COLLECTION_EMENTA)

    def _abrir_colecao(self, nome: str) -> Collection:
        """Cria ou reabre uma coleção com distância de cosseno como métrica de definição dos vetores.

        Input:  nome — nome da coleção.
        Returns: o objeto Collection do ChromaDB.
        """
        col = self._client.get_or_create_collection(
            name=nome, metadata={"hnsw:space": "cosine"}
        )
        # Ajusta os parâmetros do HNSW.
        try:
            hnsw = col._model.configuration_json.get("hnsw", {})
            if hnsw.get("sync_threshold") != _SYNC_THRESHOLD:
                col.modify(
                    configuration={
                        "hnsw": {
                            "sync_threshold": _SYNC_THRESHOLD,
                            "batch_size": _BATCH_SIZE}
                    }
                )
        except Exception:
            logger.warning(
                "Não foi possível ajustar o HNSW da coleção '%s' (API interna do "
                "Chroma pode ter mudado); seguindo com os defaults.", nome, exc_info=True
            )
        return col

    def add_chunks(
        self,
        chunks: list[Chunk],
        emb_completo: list[Vector],
        emb_ementa: list[Vector],
    ) -> None:
        """Indexa (upsert) um lote nas duas coleções.

        emb_completo é por chunk (id = chunk_id);
        emb_ementa é por documento (id = documento_id).

        Input:  chunks, (emb_completo, emb_ementa) — vetores na mesma ordem dos chunks.
        Returns: None.
        """
        if not chunks:
            return
        if not (len(chunks) == len(emb_completo) == len(emb_ementa)):
            raise ValueError(
                f"Tamanhos divergentes: {len(chunks)} chunks, "
                f"{len(emb_completo)} emb_completo, {len(emb_ementa)} emb_ementa."
            )

        # COMPLETO: Upsert de UM registro POR chunk.
        self._col_completo.upsert(
            ids=[c.chunk_id for c in chunks],
            embeddings=emb_completo,
            documents=[c.texto for c in chunks],
            metadatas=[_to_metadata(c) for c in chunks],
        )

        # EMENTA: Upsert de UM registro POR documento.
        # Percorremos os chunks e guardamos só o 1º de cada documento_id.
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
                (ex.: {"provimento": "APROVADO"}); collection — qual coleção usar.
        Returns: lista de {id, documento_id, distance, metadata}, mais próximos primeiro
                 (id = chunk_id em COMPLETO, documento_id em EMENTA).
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

    def documento_ids_indexados(self) -> set[str]:
        """Retorna os documento_id já presentes na coleção da ementa.
        Usado pela indexação delta para pular o embedding de quem já foi indexado.
        
        Input:  None.
        Returns: set de documento_id (vazio após reset ou base nova).
        """
        return set(self._col_ementa.get(include=[])["ids"])

    def reset(self) -> None:
        """Apaga e recria as duas coleções (re-indexação do zero).

        Input:  None.
        Returns: None.
        """
        for nome in (COLLECTION_COMPLETO, COLLECTION_EMENTA):
            try:
                self._client.delete_collection(nome)
            except Exception:
                pass
        self._col_completo = self._abrir_colecao(COLLECTION_COMPLETO)
        self._col_ementa = self._abrir_colecao(COLLECTION_EMENTA)
