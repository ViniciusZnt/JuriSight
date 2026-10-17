"""Métricas de ranking e de concordância do harness de avaliação.

Funções puras, sem dependências externas. Os casos sem base para cálculo
(ex.: nenhum relevante, kappa indefinido) retornam None em vez de levantar erro.
"""

import math
from collections import Counter

# Spec §3.8: "relevante" = relevância >= 2 (usado no Recall e na fração "fortalece").
LIMIAR_RELEVANTE = 2


def ndcg_at_k(ranking: list[str], ganhos: dict[str, int], k: int = 10) -> float | None:
    """nDCG@k com ganho = relevância. Documento fora de `ganhos` vale 0.

    Retorna None quando o ideal é 0 (nenhum documento com ganho positivo).
    """
    dcg = sum(
        (2 ** ganhos.get(doc, 0) - 1) / math.log2(i + 2)
        for i, doc in enumerate(ranking[:k])
    )
    ideal = sorted(ganhos.values(), reverse=True)[:k]
    idcg = sum((2**g - 1) / math.log2(i + 2) for i, g in enumerate(ideal))
    if idcg == 0:
        return None
    return dcg / idcg


def recall_at_k(
    ranking: list[str],
    ganhos: dict[str, int],
    k: int = 20,
    limiar: int = LIMIAR_RELEVANTE,
) -> float | None:
    """Fração dos relevantes (ganho >= limiar) recuperados no top-k.

    Retorna None quando não há nenhum relevante.
    """
    relevantes = {doc for doc, g in ganhos.items() if g >= limiar}
    if not relevantes:
        return None
    recuperados = sum(1 for doc in ranking[:k] if doc in relevantes)
    return recuperados / len(relevantes)


def fracao_fortalece(
    ranking: list[str],
    ganhos: dict[str, int],
    stances: dict[str, str],
    k: int = 10,
) -> float | None:
    """Fração de stance "fortalece" entre os relevantes do top-k.

    Retorna None quando nenhum relevante aparece no top-k.
    """
    relevantes_topo = [
        doc for doc in ranking[:k] if ganhos.get(doc, 0) >= LIMIAR_RELEVANTE
    ]
    if not relevantes_topo:
        return None
    fortalecem = sum(1 for doc in relevantes_topo if stances.get(doc) == "fortalece")
    return fortalecem / len(relevantes_topo)


def fracao_nao_julgados(ranking: list[str], ganhos: dict[str, int], k: int = 10) -> float:
    """Fração dos documentos do top-k sem julgamento em `ganhos`.

    Retorna 0.0 quando o ranking está vazio.
    """
    topo = ranking[:k]
    if not topo:
        return 0.0
    nao_julgados = sum(1 for doc in topo if doc not in ganhos)
    return nao_julgados / len(topo)


def kappa_cohen(a: list[str], b: list[str]) -> float | None:
    """Kappa de Cohen (categórico) entre dois avaliadores.

    Retorna None com menos de 2 itens ou quando a concordância esperada é 1.
    """
    if len(a) != len(b):
        raise ValueError("as listas devem ter o mesmo tamanho")
    n = len(a)
    if n < 2:
        return None

    po = sum(1 for x, y in zip(a, b) if x == y) / n
    contagem_a = Counter(a)
    contagem_b = Counter(b)
    pe = sum(contagem_a[c] * contagem_b[c] for c in contagem_a.keys() | contagem_b.keys()) / (n * n)
    if pe == 1:
        return None
    return (po - pe) / (1 - pe)


def kappa_ponderado_quadratico(a: list[int], b: list[int], n_niveis: int = 4) -> float | None:
    """Kappa ponderado quadrático para escalas ordinais 0..n_niveis-1.

    Pesos w_ij = (i-j)^2 / (n_niveis-1)^2: discordar por dois níveis pesa 4x
    mais que discordar por um. Retorna None com menos de 2 itens ou quando o
    denominador é 0 (ex.: os dois avaliadores só usam uma categoria).
    """
    if len(a) != len(b):
        raise ValueError("as listas devem ter o mesmo tamanho")
    n = len(a)
    if n < 2:
        return None
    for valor in [*a, *b]:
        if not 0 <= valor < n_niveis:
            raise ValueError(f"valor {valor} fora de 0..{n_niveis - 1}")

    observada = [[0] * n_niveis for _ in range(n_niveis)]
    for x, y in zip(a, b):
        observada[x][y] += 1
    marg_a = [sum(linha) for linha in observada]
    marg_b = [sum(observada[i][j] for i in range(n_niveis)) for j in range(n_niveis)]

    fator = (n_niveis - 1) ** 2
    soma_w_o = 0.0
    soma_w_e = 0.0
    for i in range(n_niveis):
        for j in range(n_niveis):
            w = (i - j) ** 2 / fator
            soma_w_o += w * observada[i][j]
            soma_w_e += w * marg_a[i] * marg_b[j] / n
    if soma_w_e == 0:
        return None
    return 1 - soma_w_o / soma_w_e
