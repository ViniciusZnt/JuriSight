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


def alfa_krippendorff_ordinal(pares: list[tuple[int, int]]) -> float | None:
    """Alfa de Krippendorff ordinal para dois avaliadores e dados completos.

    Krippendorff (2011), "Computing Krippendorff's Alpha-Reliability". Matriz de
    coincidências o_ck (cada par contribui com (c,k) e (k,c)), n_c = marginais,
    n = 2 * len(pares). Distância ordinal:
        delta²_ck = (n_c/2 + soma_{g entre c e k, exclusive} n_g + n_k/2)²
    (equivale a (soma_{g=c..k} n_g - (n_c+n_k)/2)²).
    alfa = 1 - (n-1) * soma o_ck*delta²_ck / soma n_c*n_k*delta²_ck.
    Retorna None com menos de 2 pares ou quando a discordância esperada é 0
    (todas as notas iguais).
    """
    if len(pares) < 2:
        return None
    for par in pares:
        for valor in par:
            if not isinstance(valor, int) or valor < 0:
                raise ValueError(f"nota inválida: {valor!r}")
    q = max(max(p) for p in pares) + 1
    coinc = [[0] * q for _ in range(q)]
    for a, b in pares:
        coinc[a][b] += 1
        coinc[b][a] += 1
    n_c = [sum(linha) for linha in coinc]
    n = sum(n_c)

    obs = 0.0
    esp = 0.0
    for c in range(q):
        for k in range(q):
            if c == k:
                continue
            lo, hi = min(c, k), max(c, k)
            delta2 = (sum(n_c[lo : hi + 1]) - (n_c[c] + n_c[k]) / 2) ** 2
            obs += coinc[c][k] * delta2
            esp += n_c[c] * n_c[k] * delta2
    if esp == 0:
        return None
    return 1 - (n - 1) * obs / esp


def ac2_gwet(pares: list[tuple[int, int]], n_niveis: int = 4) -> float | None:
    """AC2 de Gwet com pesos quadráticos para dois avaliadores.

    Gwet (2014), "Handbook of Inter-Rater Reliability", AC2:
        w_kl = 1 - (k-l)² / (q-1)²
        Pa = média de w_{a_i,b_i} sobre os itens
        pi_k = (marginal_a_k + marginal_b_k) / (2n)
        Pe = soma_{k,l} w_kl / (q(q-1)) * soma_k pi_k (1 - pi_k)
        AC2 = (Pa - Pe) / (1 - Pe)
    Retorna None sem pares ou se Pe = 1.
    """
    n = len(pares)
    if n == 0:
        return None
    for par in pares:
        for valor in par:
            if not 0 <= valor < n_niveis:
                raise ValueError(f"valor {valor} fora de 0..{n_niveis - 1}")
    q = n_niveis

    def peso(k: int, l: int) -> float:
        return 1 - (k - l) ** 2 / (q - 1) ** 2

    pa = sum(peso(a, b) for a, b in pares) / n
    pi = [0.0] * q
    for a, b in pares:
        pi[a] += 1 / (2 * n)
        pi[b] += 1 / (2 * n)
    t_w = sum(peso(k, l) for k in range(q) for l in range(q))
    pe = t_w / (q * (q - 1)) * sum(p * (1 - p) for p in pi)
    if pe == 1:
        return None
    return (pa - pe) / (1 - pe)
