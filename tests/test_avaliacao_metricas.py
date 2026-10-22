import pytest

from avaliacao.metricas import (
    fracao_fortalece,
    fracao_nao_julgados,
    ac2_gwet,
    alfa_krippendorff_ordinal,
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


# Exemplo à mão: pares (0,1),(1,1),(2,3),(3,3)
def test_alfa_ordinal_concordancia_perfeita():
    assert alfa_krippendorff_ordinal([(0, 0), (1, 1), (2, 2), (3, 3)]) == 1.0


def test_alfa_ordinal_exemplo_a_mao():
    # valores 0,1,1,1,2,3,3,3 -> n0=1 n1=3 n2=1 n3=3, n=8
    # delta²: 01=4, 23=4, 12=4, 02=16, 13=16, 03=36
    # observada (soma o*delta², ambas ordens) = 2*4 + 2*4 = 16
    # esperada (soma n_c*n_k*delta²) = 2*(12+16+108+12+144+12) = 608
    # alfa = 1 - 7*16/608 = 31/38
    r = alfa_krippendorff_ordinal([(0, 1), (1, 1), (2, 3), (3, 3)])
    assert abs(r - 31 / 38) < 1e-12


def test_alfa_ordinal_degenerados():
    assert alfa_krippendorff_ordinal([(2, 2), (2, 2)]) is None
    assert alfa_krippendorff_ordinal([(1, 2)]) is None


def test_ac2_concordancia_perfeita():
    assert abs(ac2_gwet([(0, 0), (1, 1), (2, 2), (3, 3)]) - 1.0) < 1e-12


def test_ac2_exemplo_a_mao():
    # a=[0,1,2,3], b=[1,1,3,3], q=4, pesos w=1-(k-l)²/9
    # Pa = (8/9 + 1 + 8/9 + 1)/4 = 17/18
    # pi = [1,3,1,3]/8 -> soma pi(1-pi) = 11/16
    # soma w_kl = 16 - 40/9 = 104/9 -> Pe = (104/9)/12 * 11/16 = 143/216
    # AC2 = (17/18 - 143/216)/(1 - 143/216) = 61/73
    r = ac2_gwet([(0, 1), (1, 1), (2, 3), (3, 3)])
    assert abs(r - 61 / 73) < 1e-12


def test_ac2_entrada_invalida():
    import pytest

    with pytest.raises(ValueError):
        ac2_gwet([(0, 4)])
    assert ac2_gwet([]) is None
