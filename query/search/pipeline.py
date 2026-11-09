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
# Pool fundido pelo RRF antes do re-ranking (query/search/reranker.py) — maior
# que N_RESULTS_FINAL de propósito: a prática de 2026 é "funde um pool maior
# via RRF, depois um cross-encoder reordena esse pool", não só reordenar os
# mesmos 20 que já seriam devolvidos. 50 (o número usual na literatura) media
# ~14s nesta infra — o hybrid_search pede 5x isso por canal (ver
# CANDIDATOS_POR_CANAL em hybrid_search.py), então o pool maior também pesa na
# BUSCA, não só no re-ranking. 30 é o equilíbrio medido: ~50% de folga sobre
# os 20 finais, latência total ficando ~2x o baseline sem re-ranking.
N_CANDIDATOS_PARA_RERANK = 30
# Pool de candidatos maior quando algum filtro (provimento/período) está ativo —
# o filtro é aplicado em Python DEPOIS da busca (ver aplicar_filtros), então um
# pool maior evita perder recall. Já cobre a folga do re-ranking acima.
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
    """Min-max normaliza os scores do re-ranking pro intervalo [0, 1].

    Por quê: o cross-encoder (query/search/reranker.py) devolve scores muito
    comprimidos pra esse domínio (ex.: 0.97–0.999 — ver o módulo) — ótimo pra
    REORDENAR (é só a ordem relativa que importa), péssimo pro "% de
    relevância" exibido no frontend, que já divide pelo score máximo do lote
    (relevancePercent): sem normalizar, todo resultado apareceria como
    "~99% relevante". Esticar pro intervalo [0, 1] aqui resolve os dois usos
    com a MESMA métrica, sem precisar de um campo novo no ResultCard.

    Input:  scores — um por candidato, em qualquer ordem.
    Returns: mesma lista, normalizada; todos 1.0 se não houver variação
    (evita divisão por zero quando só 1 candidato, ou scores empatados).
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
    reranker: Reranker,
    provimento: Provimento | None = None,
    data_inicio: date | None = None,
    data_fim: date | None = None,
) -> list[ResultCard]:
    """Roda o pipeline completo do /query (síncrono).

    Raises: ValueError (do query_builder) se a estrutura não tiver conteúdo.
    """
    bm25_query = query_builder.build_bm25_query(estrutura)
    frase_tese = query_builder.build_frase_tese(estrutura)

    tem_filtro = provimento is not None or data_inicio is not None or data_fim is not None
    n_candidatos = N_CANDIDATOS_COM_FILTRO if tem_filtro else N_CANDIDATOS_PARA_RERANK

    rankings = hybrid.search(frase_tese, n_candidatos, bm25_query=bm25_query)
    docs = retriever.fetch([doc_id for doc_id, _ in rankings])

    triplos = [(doc_id, docs[doc_id], score) for doc_id, score in rankings if doc_id in docs]
    if tem_filtro:
        triplos = aplicar_filtros(triplos, provimento, data_inicio, data_fim)

    # Re-ranking: o RRF funde bem os RANKS de cada canal, mas não lê o
    # conteúdo — um cross-encoder pontua tese+ementa juntas e reordena por
    # relevância de verdade (ver query/search/reranker.py). Ordena pelo score
    # BRUTO do cross-encoder (reordenar por score bruto ou normalizado dá a
    # MESMA ordem — min-max é uma transformação monótona — então normalizar
    # antes não muda quem entra no corte, só a escala).
    if triplos:
        scores_rerank = reranker.rerank_scores(frase_tese, [doc.ementa for _, doc, _ in triplos])
        triplos = [
            (doc_id, doc, score_bruto)
            for (doc_id, doc, _), score_bruto in zip(triplos, scores_rerank)
        ]
        triplos.sort(key=lambda t: t[2], reverse=True)

    triplos = triplos[:N_RESULTS_FINAL]

    # Normaliza DEPOIS do corte — só sobre os 20 exibidos, não o pool de 30.
    # Por quê: o cross-encoder devolve scores comprimidos nesse domínio (ex.:
    # 0.997-0.999); normalizar ANTES do corte usava os candidatos descartados
    # (os piores do pool) para ancorar o "0%", deixando os top-20 — que são os
    # melhores, logo os mais parecidos entre si — todos espremidos perto de
    # 100% (o bug visto em produção: toda carta mostrando "100% relevante").
    # Normalizar só os 20 exibidos espalha o score pelo intervalo completo
    # 0-100% de novo, sem mudar a ordem (a mesma transformação monótona).
    if triplos:
        scores_normalizados = normalizar_scores([t[2] for t in triplos])
        triplos = [
            (doc_id, doc, score_norm)
            for (doc_id, doc, _), score_norm in zip(triplos, scores_normalizados)
        ]

    return format_results(triplos)
