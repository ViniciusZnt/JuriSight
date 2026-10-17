import pytest

from avaliacao.metricas import (
    fracao_fortalece,
    fracao_nao_julgados,
    kappa_cohen,
    kappa_ponderado_quadratico,
    ndcg_at_k,
    recall_at_k,
)


def test_ndcg_ranking_ideal_e_1():
    assert ndcg_at_k(["a", "b"], {"a": 3, "b": 1}) == 1.0


def test_ndcg_invertido_menor_que_1():
    assert ndcg_at_k(["b", "a"], {"a": 3, "b": 1}) < 1.0


def test_recall_conta_so_relevancia_2_ou_mais():
    assert recall_at_k(["a", "x"], {"a": 2, "b": 3, "c": 1}, k=2) == 0.5


def test_recall_sem_relevantes_retorna_none():
    assert recall_at_k(["a"], {"a": 1}) is None


def test_fracao_fortalece():
    resultado = fracao_fortalece(
        ["a", "b", "c"],
        {"a": 3, "b": 2, "c": 0},
        {"a": "fortalece", "b": "enfraquece", "c": "fortalece"},
    )
    assert resultado == 0.5


def test_fracao_nao_julgados():
    assert fracao_nao_julgados(["a", "z", "y"], {"a": 1}, k=3) == pytest.approx(2 / 3)


def test_kappa_concordancia_perfeita_e_1():
    assert kappa_cohen(["f", "e", "n"], ["f", "e", "n"]) == 1.0


def test_kappa_valor_conhecido():
    assert kappa_cohen(["s", "s", "n", "n"], ["s", "n", "n", "n"]) == pytest.approx(0.5)


def test_kappa_ponderado_penaliza_distancia():
    assert kappa_ponderado_quadratico([0, 3, 1, 2], [1, 3, 1, 2]) > kappa_ponderado_quadratico(
        [0, 3, 1, 2], [3, 3, 1, 2]
    )


def test_kappa_degenerado_retorna_none():
    assert kappa_cohen(["n", "n"], ["n", "n"]) is None
    assert kappa_cohen(["n"], ["f"]) is None
    assert kappa_ponderado_quadratico([1, 1], [1, 1]) is None
    assert kappa_ponderado_quadratico([1], [2]) is None
