"""
Pipeline de busca do /query, sem HTTP.

Query Builder -> Hybrid Search (RRF) -> Doc Retriever -> filtros -> re-ranking
-> corte -> normalização -> Result Formatter.

Extraído de query/api/app.py para que o harness de avaliação (eval/) rode o
MESMO pipeline do endpoint, sem passar por HTTP. O endpoint só adapta:
ValueError (estrutura vazia) vira 422.
"""
from __future__ import annotations

from datetime import date

from query.enrichment import query_builder
from query.enrichment.schema import EstruturaArgumentativa
from query.search.doc_retriever import DocRetriever
from query.search.hybrid_search import HybridSearch
from query.search.reranker import Reranker
from query.search.result_formatter import ResultCard, format_results
from scraper.schema import Provimento

# Top-N final devolvido por /query (RFC: RRF Fusion "retorna os top-20").
N_RESULTS_FINAL = 20
# Pool fundido pelo RRF antes do re-ranking: maior que os 20 finais, para o cross-encoder
# ter o que reordenar, mas pequeno porque o hybrid_search pede 5x isso por canal
# (CANDIDATOS_POR_CANAL) e a latência cresce junto.
N_CANDIDATOS_PARA_RERANK = 30
# Pool maior quando há filtro de período, aplicado em Python DEPOIS da busca (ver
# aplicar_filtros): evita perder recall. Provimento e filtro restrito já chegam filtrados
# dos canais e dispensam o pool maior, que custa no re-ranking.
N_CANDIDATOS_COM_FILTRO = 80


def aplicar_filtros(
    triplos: list[tuple[str, object, float]],
    provimento: Provimento | None,
    data_inicio: date | None,
    data_fim: date | None,
) -> list[tuple[str, object, float]]:
    """Filtra os triplos (documento_id, doc, score) por provimento/período.

    Feito em Python pós-recuperação (não via `where` do Qdrant): hybrid_search.py
    já documenta que o BM25 não filtra por metadados e que um filtro rígido deve
    ser aplicado depois, sobre o DocumentoJuridico recuperado.
    """
    def ok(doc) -> bool:
        if provimento is not None and doc.provimento != provimento:
            return False
        if data_inicio is not None and (doc.data_julgamento is None or doc.data_julgamento < data_inicio):
            return False
        if data_fim is not None and (doc.data_julgamento is None or doc.data_julgamento > data_fim):
            return False
        return True

    return [t for t in triplos if ok(t[1])]


def normalizar_scores(scores: list[float]) -> list[float]:
    """Min-max dos scores do re-ranking para [0, 1]; todos 1.0 se não houver variação.

    O cross-encoder devolve scores comprimidos neste domínio (ex.: 0.97-0.999): serve
    para ordenar, mas o "% de relevância" do frontend mostraria tudo como ~99%.
    """
    if not scores:
        return []
    lo, hi = min(scores), max(scores)
    if hi == lo:
        return [1.0] * len(scores)
    return [(s - lo) / (hi - lo) for s in scores]


def buscar(
    estrutura: EstruturaArgumentativa,
    *,
    hybrid: HybridSearch,
    retriever: DocRetriever,
    reranker: Reranker | None = None,
    provimento: Provimento | None = None,
    data_inicio: date | None = None,
    data_fim: date | None = None,
    documento_ids: list[str] | None = None,
    marcar_canais: bool = False,
) -> list[ResultCard]:
    """Roda o pipeline completo do /query (síncrono).

    documento_ids: restringe a busca a essa lista (filtro restrito); lista vazia
    devolve [] sem buscar. marcar_canais: preenche ResultCard.canais (por onde
    cada decisão foi achada) — o kwarg só vai ao hybrid quando pedido.

    Raises: ValueError (do query_builder) se a estrutura não tiver conteúdo.
    """
    bm25_query = query_builder.build_bm25_query(estrutura)
    frase_tese = query_builder.build_frase_tese(estrutura)

    tem_filtro = provimento is not None or data_inicio is not None or data_fim is not None
    # Provimento é filtrado dentro dos canais e já devolve só candidatos válidos: o pool
    # normal basta. Período (sempre pós-busca) precisa do pool maior.
    filtro_pos_busca = data_inicio is not None or data_fim is not None
    restrito = documento_ids is not None
    if restrito and not documento_ids:
        return []
    n_candidatos = N_CANDIDATOS_COM_FILTRO if filtro_pos_busca else N_CANDIDATOS_PARA_RERANK

    kwargs_busca = {"provimento": provimento.value} if provimento is not None else {}
    if restrito:
        kwargs_busca["documento_ids"] = documento_ids
    canais: dict[str, list[str]] = {}
    if marcar_canais:
        kwargs_busca["canais"] = canais
    rankings = hybrid.search(frase_tese, n_candidatos, bm25_query=bm25_query, **kwargs_busca)
    docs = retriever.fetch([doc_id for doc_id, _ in rankings])

    triplos = [(doc_id, docs[doc_id], score) for doc_id, score in rankings if doc_id in docs]
    if tem_filtro:
        triplos = aplicar_filtros(triplos, provimento, data_inicio, data_fim)

    # Re-ranking: o RRF funde os ranks mas não lê o conteúdo; o cross-encoder pontua tese
    # e ementa juntas (query/search/reranker.py). Ordena pelo score bruto.
    # reranker=None: sem reordenar, mantém a ordem do RRF (benchmark, sistema S2).
    if triplos and reranker is not None:
        scores_rerank = reranker.rerank_scores(frase_tese, [doc.ementa for _, doc, _ in triplos])
        triplos = [
            (doc_id, doc, score_bruto)
            for (doc_id, doc, _), score_bruto in zip(triplos, scores_rerank)
        ]
        triplos.sort(key=lambda t: t[2], reverse=True)

    triplos = triplos[:N_RESULTS_FINAL]

    # Normaliza DEPOIS do corte, só sobre os exibidos: com os descartados (os piores do
    # pool) ancorando o "0%", os melhores, parecidos entre si, apareciam todos perto de
    # 100% (o bug de "100% relevante" em toda carta). A ordem não muda (min-max é monótono).
    if triplos:
        scores_normalizados = normalizar_scores([t[2] for t in triplos])
        triplos = [
            (doc_id, doc, score_norm)
            for (doc_id, doc, _), score_norm in zip(triplos, scores_normalizados)
        ]

    cards = format_results(triplos)
    if marcar_canais:
        cards = [c.model_copy(update={"canais": canais.get(c.id, [])}) for c in cards]
    return cards
