"""
Métricas dos KPIs de recuperação (RFC §1.6, Tabela 3).

Funções PURAS, sem I/O — operam sobre ids/listas/escalares, então rodam offline
(sem OpenAI, Chroma ou DB) e são cobertas por testes unitários. O runner
(run_eval.py) alimenta essas funções com os resultados da busca real.
"""
from __future__ import annotations

from statistics import mean


def precision_at_k(retrieved: list[str], relevant: set[str], k: int) -> float:
    """Precisão@K: fração dos K primeiros recuperados que são relevantes.

    Input:  retrieved — documento_id ordenados (melhor primeiro); relevant —
            documento_id julgados relevantes; k — corte.
    Returns: P@K em [0,1]. Divide sempre por k (posição faltante conta como erro).
    """
    if k <= 0:
        raise ValueError("k deve ser > 0")
    topo = retrieved[:k]
    acertos = sum(1 for doc_id in topo if doc_id in relevant)
    return acertos / k


def mean_precision_at_k(casos: list[tuple[list[str], set[str]]], k: int) -> float:
    """Média (macro) de P@K sobre várias queries.

    Input:  casos — lista de (retrieved, relevant) por query; k — corte.
    Returns: média das P@K, ou 0.0 se não há casos.
    """
    if not casos:
        return 0.0
    return mean(precision_at_k(ret, rel, k) for ret, rel in casos)


def provimento_rate(provimentos: list[str], alvo: str = "APROVADO") -> float:
    """Fração dos docs cujo provimento == alvo (KPI do filtro favorável).

    Input:  provimentos — provimento dos docs retornados; alvo — valor esperado
            quando o usuário filtra por favorável.
    Returns: fração em [0,1], ou 0.0 se a lista é vazia.
    """
    if not provimentos:
        return 0.0
    return sum(1 for p in provimentos if p == alvo) / len(provimentos)


def citation_completeness(citacoes: list[dict]) -> float:
    """Fração de docs com fonte real completa: número, tipo e link (RNF01/RN03).

    Input:  citacoes — dicts com 'numero_processo', 'tipo_documento', 'link_original'.
    Returns: fração com os três campos preenchidos, ou 0.0 se vazio.
    """
    if not citacoes:
        return 0.0
    def completa(c: dict) -> bool:
        return bool(c.get("numero_processo")) and bool(c.get("tipo_documento")) \
            and bool(c.get("link_original"))
    return sum(1 for c in citacoes if completa(c)) / len(citacoes)


def type_coverage(presentes: set[str], esperados: set[str]) -> float:
    """Cobertura dos tipos de documento do Falcão presentes no índice.

    Input:  presentes — tipos encontrados no índice; esperados — tipos do Falcão.
    Returns: fração dos esperados que estão presentes, em [0,1].
    """
    if not esperados:
        return 0.0
    return len(esperados & presentes) / len(esperados)


def latency_summary(amostras: list[float]) -> dict[str, float]:
    """Resumo das latências por consulta (segundos).

    Input:  amostras — tempos de resposta por query.
    Returns: {'p50','p95','max','mean'}; zeros se vazio.
    """
    if not amostras:
        return {"p50": 0.0, "p95": 0.0, "max": 0.0, "mean": 0.0}
    ordenadas = sorted(amostras)

    def percentil(p: float) -> float:
        # nearest-rank, simples e sem numpy.
        idx = min(len(ordenadas) - 1, round(p * (len(ordenadas) - 1)))
        return ordenadas[idx]

    return {
        "p50": percentil(0.50),
        "p95": percentil(0.95),
        "max": ordenadas[-1],
        "mean": mean(ordenadas),
    }
