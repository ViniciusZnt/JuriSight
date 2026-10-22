"""
Pooling (estilo TREC): para cada tese, une o top-k de 3 buscas diferentes para
decidir quais acórdãos os avaliadores vão julgar. Assim o conjunto-ouro não fica
enviesado para o que o pipeline atual já acha.
"""
from __future__ import annotations

from avaliacao.sistemas import top_bm25, top_denso
from query.enrichment.schema import EstruturaArgumentativa
from query.search.pipeline import buscar

CORREDORES = ("bm25", "vetorial", "pipeline")


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
    ids_por_corredor = {
        "bm25": top_bm25(hybrid, estrutura, k),
        "vetorial": top_denso(hybrid, estrutura, k),
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
