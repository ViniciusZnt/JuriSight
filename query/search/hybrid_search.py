"""
Hybrid Search.

Funde busca vetorial (Qdrant) e lexical (BM25) via Reciprocal Rank Fusion (RRF),
no nível de documento_id, e devolve os documentos mais relevantes para a query.

Três canais de recuperação:
  - Qdrant COMPLETO (por chunk)  → casa a passagem semanticamente;
  - Qdrant EMENTA   (por doc)    → casa a tese semanticamente;
  - BM25            (por chunk)  → casa termos exatos (NR-15, art. 193).
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

from indexing.lexical.bm25_builder import LoadedBM25
from indexing.vector_store.qdrant_store import (
    COLLECTION_COMPLETO,
    COLLECTION_EMENTA,
    QdrantStore,
)
from processing.embeddings.poly_vector import PolyVectorEmbedder

# Constante de amortecimento do RRF (60 é o padrão da literatura).
RRF_K = 60
# Quantos candidatos pedir por canal (chunks colapsam em docs, então buscamos mais).
CANDIDATOS_POR_CANAL = 5


def _doc_id_do_chunk(chunk_id: str) -> str:
    """Extrai o documento_id de um chunk_id no formato 'documento_id:posicao'.

    Input:  chunk_id.
    Returns: o documento_id.
    """
    return chunk_id.rsplit(":", 1)[0]



def _dedup_ordenado(doc_ids: list[str]) -> list[str]:
    """Remove duplicatas preservando a ordem.

    Input:  doc_ids — lista de documento_id, melhor primeiro.
    Returns: mesma lista sem repetições.
    """
    vistos: set[str] = set()
    ordem: list[str] = []
    for d in doc_ids:
        if d not in vistos:
            vistos.add(d)
            ordem.append(d)
    return ordem


def reciprocal_rank_fusion(
    rankings: list[list[str]],
    k: int = RRF_K
) -> list[tuple[str, float]]:
    """Funde várias listas ranqueadas de documento_id via RRF.

    RRF: RRF(d) = Σ(r ∈ R) 1 / (k + r(d))

        Where:
        - d is a document
        - R is the set of rankers (retrievers)
        - k is a constant (typically 60)
        - r(d) is the rank of document d in ranker r

    Input:  rankings — lista de rankings; cada ranking é uma lista de documento_id
            ordenada (melhor primeiro); k — constante de amortecimento.
    Returns: lista [(documento_id, score_rrf)] ordenada por score desc.
    """
    scores: dict[str, float] = {}
    for ranking in rankings:
        for posicao, doc_id in enumerate(ranking):
            scores[doc_id] = scores.get(doc_id, 0.0) + 1.0 / (k + posicao + 1)
    return sorted(scores.items(), key=lambda item: item[1], reverse=True)


class HybridSearch:
    def __init__(self, embedder: PolyVectorEmbedder, store: QdrantStore, bm25: LoadedBM25):
        self.embedder = embedder
        self.store = store
        self.bm25 = bm25

    def search(
        self,
        query: str,
        n_results: int = 20,
        where: dict | None = None,
        *,
        bm25_query: str | None = None,
        provimento: str | None = None,
        documento_ids: list[str] | None = None,
        canais: dict[str, list[str]] | None = None,
    ) -> list[tuple[str, float]]:
        """Busca híbrida: vetorial (2 coleções) + lexical, fundidos por RRF.

        `query` é embedada para o canal vetorial; `bm25_query` (se diferente) vai ao BM25.
        `provimento` e `documento_ids` (filtro restrito) valem nos TRÊS canais. `where` filtra
        só o Qdrant; o BM25 só filtra por provimento e documento_ids, então outros filtros
        rígidos ficam para depois, sobre o documento recuperado. `canais`, se vier, recebe
        {documento_id: ["semantica", "termos"]} com os canais em que cada documento apareceu.
        Retorna [(documento_id, score_rrf)] top-N, melhor primeiro.
        """
        n_candidates = n_results * CANDIDATOS_POR_CANAL
        texto_bm25 = bm25_query if bm25_query is not None else query

        if provimento is not None:
            where = {**(where or {}), "provimento": provimento}
            kwargs_bm25 = {"provimento": provimento}
        else:
            kwargs_bm25 = {}
        if documento_ids is not None:
            where = {**(where or {}), "documento_id": documento_ids}
            kwargs_bm25["documento_ids"] = set(documento_ids)

        # Os 3 canais são independentes: em paralelo o tempo é o do mais lento, não a soma.
        with ThreadPoolExecutor(max_workers=3) as executor:
            fut_bm25 = executor.submit(self.bm25.search, texto_bm25, n=n_candidates, **kwargs_bm25)
            query_vector = self.embedder.embed_text(query)
            fut_completo = executor.submit(
                self.store.query, query_vector, n_results=n_candidates, where=where, collection=COLLECTION_COMPLETO
            )
            fut_ementa = executor.submit(
                self.store.query, query_vector, n_results=n_candidates, where=where, collection=COLLECTION_EMENTA
            )
            hits_bm25 = fut_bm25.result()
            hits_completo = fut_completo.result()
            hits_ementa = fut_ementa.result()

        # Projeta cada canal para uma lista ranqueada de documento_id, sem duplicar.
        r_completo = _dedup_ordenado([h["documento_id"] for h in hits_completo])
        r_ementa = _dedup_ordenado([h["documento_id"] for h in hits_ementa])
        r_bm25 = _dedup_ordenado([_doc_id_do_chunk(cid) for cid, _ in hits_bm25])

        fundidos = reciprocal_rank_fusion([r_completo, r_ementa, r_bm25])
        if canais is not None:  # por onde cada documento foi achado ("Como esta busca foi feita")
            semantica, termos = set(r_completo) | set(r_ementa), set(r_bm25)
            for doc_id, _ in fundidos[:n_results]:
                canais[doc_id] = [c for c, ids in (("semantica", semantica), ("termos", termos)) if doc_id in ids]
        return fundidos[:n_results]
