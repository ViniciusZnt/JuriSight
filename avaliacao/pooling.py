"""
Pooling (estilo TREC): para cada tese, une o top-k de 3 buscas diferentes para
decidir quais acórdãos os avaliadores vão julgar. Assim o conjunto-ouro não fica
enviesado para o que o pipeline atual já acha.
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
from query.search.pipeline import buscar

CORREDORES = ("bm25", "vetorial", "pipeline")


def _corredor_bm25(hybrid, texto_bm25: str, k: int) -> list[str]:
    hits = hybrid.bm25.search(texto_bm25, n=k * CANDIDATOS_POR_CANAL)
    return _dedup_ordenado([_doc_id_do_chunk(cid) for cid, _ in hits])[:k]


def _corredor_vetorial(hybrid, frase_tese: str, k: int) -> list[str]:
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


def montar_pool(
    estrutura: EstruturaArgumentativa,
    *,
    hybrid,
    retriever,
    reranker,
    k: int = 20,
) -> dict[str, list[str]]:
    """Une o top-k de documentos de cada corredor (bm25, vetorial, pipeline).

    Input:  estrutura — a tese; hybrid/retriever/reranker — os mesmos objetos do
            pipeline de produção; k — documentos distintos por corredor.
    Returns: {documento_id: corredores que o trouxeram}, corredores sempre na
             ordem bm25, vetorial, pipeline. Documentos ausentes do retriever ou
             com ementa e fundamentação vazias são removidos.
    Raises: ValueError se a estrutura não tiver conteúdo (do query_builder).
    """
    texto_bm25 = query_builder.build_bm25_query(estrutura)
    frase_tese = query_builder.build_frase_tese(estrutura)

    ids_por_corredor = {
        "bm25": _corredor_bm25(hybrid, texto_bm25, k),
        "vetorial": _corredor_vetorial(hybrid, frase_tese, k),
        "pipeline": [
            card.id
            for card in buscar(estrutura, hybrid=hybrid, retriever=retriever, reranker=reranker)
        ][:k],
    }

    pool: dict[str, list[str]] = {}
    for corredor in CORREDORES:
        for doc_id in ids_por_corredor[corredor]:
            pool.setdefault(doc_id, []).append(corredor)

    docs = retriever.fetch(list(pool))
    return {
        doc_id: corredores
        for doc_id, corredores in pool.items()
        if doc_id in docs
        and ((docs[doc_id].ementa or "").strip() or (docs[doc_id].fundamentacao or "").strip())
    }
