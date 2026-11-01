"""
Pooling (estilo TREC): para cada tese, une o top-k de 3 buscas diferentes para
decidir quais acórdãos os avaliadores vão julgar. Assim o conjunto-ouro não fica
enviesado para o que o pipeline atual já acha.
"""
from __future__ import annotations

from avaliacao.sistemas import candidatos_hibrido, top_bm25, top_denso
from query.enrichment.schema import EstruturaArgumentativa

# Os nomes com _top10 distinguem o pool novo do antigo, que marcava "bm25" e
# "vetorial" para o top-20 sem guardar o rank.
CORREDORES = ("hibrido", "bm25_top10", "vetorial_top10")


def montar_pool(
    estrutura: EstruturaArgumentativa,
    *,
    hybrid,
    retriever,
    n_hibrido: int = 30,
    k: int = 10,
) -> dict[str, list[str]]:
    """Une os n_hibrido candidatos do híbrido ao top-k do BM25 e ao top-k do denso.

    Input:  estrutura — a tese; hybrid/retriever — os mesmos objetos do pipeline de
            produção; n_hibrido — candidatos do híbrido (o que os rerankers veem);
            k — documentos distintos de cada canal isolado.
    Returns: {documento_id: corredores que o trouxeram}, corredores sempre na
             ordem hibrido, bm25_top10, vetorial_top10. Documentos ausentes do retriever ou
             com ementa e fundamentação vazias são removidos.
    Raises: ValueError se a estrutura não tiver conteúdo (do query_builder).
    """
    ids_por_corredor = {
        "hibrido": candidatos_hibrido(estrutura, hybrid=hybrid, retriever=retriever, n=n_hibrido),
        "bm25_top10": top_bm25(hybrid, estrutura, k),
        "vetorial_top10": top_denso(hybrid, estrutura, k),
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
