"""Rótulo final de um par julgado por mais de uma pessoa.

Regra pura (sem banco) para ser testada isoladamente; o store só busca os
julgamentos humanos e aplica `rotulo_final`.
"""
from __future__ import annotations

LIMIAR_STANCE = 2  # stance só vale com nota >= 2 (abaixo disso grava-se 'neutro')


def juiz_humano(email: str) -> str:
    return f"humano:{email.strip().lower()}"


def rotulo_final(
    julgamentos: list[tuple[str, int, str]], adjudicador: str | None
) -> tuple[int, str] | None:
    """Rótulo (relevância, stance) de um par, ou None se estiver pendente.

    `julgamentos` = (juiz, relevância, stance), um por juiz humano.
    - o adjudicador (e-mail), se julgou, prevalece;
    - um único julgamento: vale ele;
    - notas iguais: a nota; diferença de 1: a menor;
    - diferença >= 2: pendente;
    - stance diferente entre julgamentos com nota >= 2: pendente.
    """
    if not julgamentos:
        return None
    if adjudicador:
        juiz_adj = juiz_humano(adjudicador)
        for juiz, rel, stance in julgamentos:
            if juiz == juiz_adj:
                return rel, stance
    if len(julgamentos) == 1:
        _, rel, stance = julgamentos[0]
        return rel, stance

    notas = [rel for _, rel, _ in julgamentos]
    if max(notas) - min(notas) >= 2:
        return None
    stances_fortes = {st for _, rel, st in julgamentos if rel >= LIMIAR_STANCE}
    if len(stances_fortes) > 1:
        return None
    menor = min(notas)
    # entre os de nota mínima, o primeiro (ordem estável do chamador)
    stance = next(st for _, rel, st in julgamentos if rel == menor)
    return menor, stance
