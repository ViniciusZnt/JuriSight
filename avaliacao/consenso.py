"""Rótulo final de um par julgado por mais de uma pessoa.

Regra pura (sem banco) para ser testada isoladamente; o store só busca os
julgamentos humanos e aplica `rotulo_final`.
"""
from __future__ import annotations

LIMIAR_STANCE = 2  # stance só vale com nota >= 2 (abaixo disso grava-se 'neutro')


def juiz_humano(email: str) -> str:
    return f"humano:{email.strip().lower()}"


RODADA_ADJUDICACAO = 2  # a rodada 1 é a avaliação normal; a 2 é a adjudicação


def rotulo_final(julgamentos: list[tuple], adjudicador: str | None) -> tuple[int, str] | None:
    """Rótulo (relevância, stance) de um par, ou None se estiver pendente.

    `julgamentos` = (juiz, relevância, stance[, rodada]) de juízes humanos; sem
    rodada, vale 1. Regras:
    - o julgamento de rodada 2 do adjudicador (e-mail) prevalece;
    - senão, só as demais rodadas contam, um julgamento por juiz (o último da lista;
      a rodada 1 do adjudicador, se ele também avalia, entra como a de qualquer um);
    - um único juiz: vale ele; notas iguais: a nota; diferença de 1: a menor;
    - diferença >= 2: pendente;
    - stance diferente entre julgamentos com nota >= 2: pendente.
    """
    juiz_adj = juiz_humano(adjudicador) if adjudicador else None
    por_juiz: dict[str, tuple[int, str]] = {}
    for item in julgamentos:
        juiz, rel, stance = item[:3]
        rodada = item[3] if len(item) > 3 else 1
        if juiz == juiz_adj and rodada == RODADA_ADJUDICACAO:
            return rel, stance
        por_juiz[juiz] = (rel, stance)
    if not por_juiz:
        return None
    resolvidos = [(j, rel, st) for j, (rel, st) in por_juiz.items()]
    if len(resolvidos) == 1:
        _, rel, stance = resolvidos[0]
        return rel, stance

    notas = [rel for _, rel, _ in resolvidos]
    if max(notas) - min(notas) >= 2:
        return None
    stances_fortes = {st for _, rel, st in resolvidos if rel >= LIMIAR_STANCE}
    if len(stances_fortes) > 1:
        return None
    menor = min(notas)
    # entre os de nota mínima, o primeiro (ordem estável do chamador)
    stance = next(st for _, rel, st in resolvidos if rel == menor)
    return menor, stance
