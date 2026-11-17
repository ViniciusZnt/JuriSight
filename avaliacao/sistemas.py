"""Sistemas do benchmark.

S0 BM25 sozinho; S1 denso sozinho; S2 híbrido RRF (os 50 do /query, na ordem do RRF).
Cada sistema devolve o top-20 de ids de documento.
"""
from __future__ import annotations

from indexing.vector_store.qdrant_store import COLLECTION_COMPLETO, COLLECTION_EMENTA
from query.enrichment import query_builder
from query.enrichment.schema import EstruturaArgumentativa
from query.search.hybrid_search import (
    CANDIDATOS_POR_CANAL,
    _doc_id_do_chunk,
    reciprocal_rank_fusion,
)
from query.search.pipeline import N_RESULTADOS_TRIAGEM, buscar

SISTEMAS: tuple[str, ...] = ("S0", "S1", "S2")

# Quantos ids cada sistema devolve (o que as métricas avaliam).
TOP_K = 20

# Profundidade da consulta de cada canal, igual para qualquer k: assim o top-10 de
# referência do pool é prefixo do top-20 de S0/S1 (com k variável, o corte mudava).
PROFUNDIDADE = TOP_K * CANDIDATOS_POR_CANAL


def top_bm25(hybrid, estrutura: EstruturaArgumentativa, k: int) -> list[str]:
    """Top-k documentos distintos só do canal BM25."""
    texto_bm25 = query_builder.build_bm25_query(estrutura)
    hits = hybrid.bm25.search(texto_bm25, n=PROFUNDIDADE)
    return list(dict.fromkeys(_doc_id_do_chunk(cid) for cid, _ in hits))[:k]


def top_denso(hybrid, estrutura: EstruturaArgumentativa, k: int) -> list[str]:
    """Top-k documentos distintos só do canal denso (2 coleções, RRF)."""
    frase_tese = query_builder.build_frase_tese(estrutura)
    # Mesma fusão do HybridSearch.search, só que sem o canal BM25.
    vetor = hybrid.embedder.embed_text(frase_tese)
    n = PROFUNDIDADE
    rankings = [
        list(dict.fromkeys(h["documento_id"] for h in hybrid.store.query(vetor, n_results=n, collection=colecao)))
        for colecao in (COLLECTION_COMPLETO, COLLECTION_EMENTA)
    ]
    return [doc_id for doc_id, _ in reciprocal_rank_fusion(rankings)[:k]]


def candidatos_hibrido(
    estrutura: EstruturaArgumentativa, *, hybrid, retriever, n: int = N_RESULTADOS_TRIAGEM
) -> list[str]:
    """Os n candidatos do híbrido (ordem do RRF) que o retriever encontra."""
    bm25_query = query_builder.build_bm25_query(estrutura)
    frase_tese = query_builder.build_frase_tese(estrutura)
    rankings = hybrid.search(frase_tese, n, bm25_query=bm25_query)
    docs = retriever.fetch([doc_id for doc_id, _ in rankings])
    return [doc_id for doc_id, _ in rankings if doc_id in docs]


def rodar_sistema(sistema: str, estrutura: EstruturaArgumentativa, deps) -> list[str]:
    """Top-20 de ids do sistema."""
    if sistema not in SISTEMAS:
        raise KeyError(f"Sistema desconhecido: {sistema!r} (esperado um de {SISTEMAS})")
    if sistema == "S0":
        return top_bm25(deps.hybrid, estrutura, TOP_K)
    if sistema == "S1":
        return top_denso(deps.hybrid, estrutura, TOP_K)
    cards = buscar(estrutura, hybrid=deps.hybrid, retriever=deps.retriever, n_resultados=N_RESULTADOS_TRIAGEM)
    return [card.id for card in cards][:TOP_K]
