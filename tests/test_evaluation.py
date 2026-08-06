"""
Testes das métricas de avaliação (evaluation/metrics.py) e do loader do dataset.

Unit tests puros — sem OpenAI, Chroma nem DB. Cobrem a matemática dos KPIs e os
casos-limite (listas vazias, k fora do intervalo, query sem rótulo).
"""
import pytest

from evaluation import metrics
from evaluation.dataset import GoldenQuery, carregar


# --------------------------------------------------------------------------- #
# precision_at_k                                                              #
# --------------------------------------------------------------------------- #

def test_precision_at_k_todos_relevantes():
    assert metrics.precision_at_k(["a", "b", "c"], {"a", "b", "c"}, 3) == 1.0


def test_precision_at_k_metade():
    # top-4: a(✓) b(✗) c(✓) d(✗) → 2/4
    got = metrics.precision_at_k(["a", "b", "c", "d"], {"a", "c"}, 4)
    assert got == pytest.approx(0.5)


def test_precision_at_k_divide_sempre_por_k():
    # só 2 recuperados mas k=5 → posições faltantes contam como erro → 1/5
    assert metrics.precision_at_k(["a", "x"], {"a"}, 5) == pytest.approx(0.2)


def test_precision_at_k_ignora_alem_do_corte():
    # o relevante está na posição 3, fora do top-2 → 0
    assert metrics.precision_at_k(["x", "y", "a"], {"a"}, 2) == 0.0


def test_precision_at_k_k_invalido():
    with pytest.raises(ValueError):
        metrics.precision_at_k(["a"], {"a"}, 0)


def test_mean_precision_at_k():
    casos = [(["a", "b"], {"a"}), (["c", "d"], {"c", "d"})]
    # P@2 = 0.5 e 1.0 → média 0.75
    assert metrics.mean_precision_at_k(casos, 2) == pytest.approx(0.75)


def test_mean_precision_at_k_vazio():
    assert metrics.mean_precision_at_k([], 5) == 0.0


# --------------------------------------------------------------------------- #
# provimento_rate                                                             #
# --------------------------------------------------------------------------- #

def test_provimento_rate():
    provs = ["APROVADO", "APROVADO", "NEGADO", "APROVADO"]
    assert metrics.provimento_rate(provs) == pytest.approx(0.75)


def test_provimento_rate_vazio():
    assert metrics.provimento_rate([]) == 0.0


# --------------------------------------------------------------------------- #
# citation_completeness                                                       #
# --------------------------------------------------------------------------- #

def _cit(num="RR-1", tipo="ACORDAO", link="http://x"):
    return {"numero_processo": num, "tipo_documento": tipo, "link_original": link}


def test_citation_completeness_todas_completas():
    assert metrics.citation_completeness([_cit(), _cit()]) == 1.0


def test_citation_completeness_campo_faltando():
    # uma sem link → 1/2
    assert metrics.citation_completeness([_cit(), _cit(link=None)]) == pytest.approx(0.5)


def test_citation_completeness_numero_vazio_conta_como_incompleto():
    assert metrics.citation_completeness([_cit(num="")]) == 0.0


# --------------------------------------------------------------------------- #
# type_coverage                                                               #
# --------------------------------------------------------------------------- #

def test_type_coverage_completa():
    esperados = {"ACORDAO", "SUMULA", "OJ", "PRECEDENTE"}
    assert metrics.type_coverage(set(esperados), esperados) == 1.0


def test_type_coverage_faltando_um():
    esperados = {"ACORDAO", "SUMULA", "OJ", "PRECEDENTE"}
    presentes = {"ACORDAO", "SUMULA", "OJ"}
    assert metrics.type_coverage(presentes, esperados) == pytest.approx(0.75)


def test_type_coverage_ignora_tipos_extras():
    esperados = {"ACORDAO"}
    presentes = {"ACORDAO", "ALGO_ESTRANHO"}
    assert metrics.type_coverage(presentes, esperados) == 1.0


# --------------------------------------------------------------------------- #
# latency_summary                                                             #
# --------------------------------------------------------------------------- #

def test_latency_summary_basico():
    resumo = metrics.latency_summary([1.0, 2.0, 3.0, 4.0])
    assert resumo["max"] == 4.0
    assert resumo["mean"] == pytest.approx(2.5)


def test_latency_summary_vazio():
    resumo = metrics.latency_summary([])
    assert resumo == {"p50": 0.0, "p95": 0.0, "max": 0.0, "mean": 0.0}


# --------------------------------------------------------------------------- #
# dataset loader                                                             #
# --------------------------------------------------------------------------- #

def test_golden_carrega_e_tem_queries():
    queries = carregar()
    assert len(queries) >= 1
    assert all(isinstance(q, GoldenQuery) for q in queries)


def test_golden_ids_unicos():
    ids = [q.id for q in carregar()]
    assert len(ids) == len(set(ids))


def test_goldenquery_rotulada():
    assert GoldenQuery(id="x", query="q", relevantes=["d1"]).rotulada is True
    assert GoldenQuery(id="y", query="q", relevantes=[]).rotulada is False
