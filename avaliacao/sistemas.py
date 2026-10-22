"""Sistemas S0-S6 do benchmark de rerankers.

S0 BM25 sozinho; S1 denso sozinho; S2 híbrido RRF sem reranker; S3-S6 = S2 +
um reranker. Cada sistema devolve o top-20 de ids de documento.
"""
from __future__ import annotations

from indexing.vector_store.qdrant_store import COLLECTION_COMPLETO, COLLECTION_EMENTA
from query.enrichment import query_builder
from query.enrichment.schema import EstruturaArgumentativa
from query.search.hybrid_search import (
    CANDIDATOS_POR_CANAL,
    _dedup_ordenado,
    _doc_id_do_chunk,
    reciprocal_rank_fusion,
)
from query.search.pipeline import N_CANDIDATOS_PARA_RERANK, N_RESULTS_FINAL, buscar

SISTEMAS: tuple[str, ...] = ("S0", "S1", "S2", "S3", "S4", "S5", "S6")


def top_bm25(hybrid, estrutura: EstruturaArgumentativa, k: int) -> list[str]:
    """Top-k documentos distintos só do canal BM25."""
    texto_bm25 = query_builder.build_bm25_query(estrutura)
    hits = hybrid.bm25.search(texto_bm25, n=k * CANDIDATOS_POR_CANAL)
    return _dedup_ordenado([_doc_id_do_chunk(cid) for cid, _ in hits])[:k]


def top_denso(hybrid, estrutura: EstruturaArgumentativa, k: int) -> list[str]:
    """Top-k documentos distintos só do canal denso (2 coleções, RRF)."""
    frase_tese = query_builder.build_frase_tese(estrutura)
    # Mesma fusão do HybridSearch.search, só que sem o canal BM25.
    vetor = hybrid.embedder.embed_text(frase_tese)
    n = k * CANDIDATOS_POR_CANAL
    rankings = [
        _dedup_ordenado(
            [h["documento_id"] for h in hybrid.store.query(vetor, n_results=n, collection=colecao)]
        )
        for colecao in (COLLECTION_COMPLETO, COLLECTION_EMENTA)
    ]
    return [doc_id for doc_id, _ in reciprocal_rank_fusion(rankings)[:k]]


def candidatos_hibrido(
    estrutura: EstruturaArgumentativa, *, hybrid, retriever, n: int = N_CANDIDATOS_PARA_RERANK
) -> list[str]:
    """Os n candidatos do híbrido (ordem do RRF) que o retriever encontra."""
    bm25_query = query_builder.build_bm25_query(estrutura)
    frase_tese = query_builder.build_frase_tese(estrutura)
    rankings = hybrid.search(frase_tese, n, bm25_query=bm25_query)
    docs = retriever.fetch([doc_id for doc_id, _ in rankings])
    return [doc_id for doc_id, _ in rankings if doc_id in docs]


def rodar_sistema(
    sistema: str, estrutura: EstruturaArgumentativa, deps, rerankers: dict[str, object]
) -> list[str]:
    """Top-20 de ids do sistema. `rerankers` mapeia "S3".."S6" ao reranker."""
    if sistema not in SISTEMAS:
        raise KeyError(f"Sistema desconhecido: {sistema!r} (esperado um de {SISTEMAS})")
    if sistema == "S0":
        return top_bm25(deps.hybrid, estrutura, N_RESULTS_FINAL)
    if sistema == "S1":
        return top_denso(deps.hybrid, estrutura, N_RESULTS_FINAL)
    reranker = None
    if sistema != "S2":
        if sistema not in rerankers:
            raise KeyError(f"Reranker do sistema {sistema} não foi passado em `rerankers`")
        reranker = rerankers[sistema]
    cards = buscar(estrutura, hybrid=deps.hybrid, retriever=deps.retriever, reranker=reranker)
    return [card.id for card in cards]
