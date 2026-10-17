"""
Amostra mista que a especialista vai rotular: metade sorteada por estrato
(para medir concordância/kappa) e metade onde o Jev teve menos confiança
(para achar onde ele erra). Módulo puro, sem acesso a banco.
"""
from __future__ import annotations

import random
import uuid
from collections import defaultdict
from typing import NamedTuple

SORTEADA = "sorteada"
INCERTA = "incerta"


class ItemAmostra(NamedTuple):
    par_id: uuid.UUID
    tema: str
    origem: str
    relevancia: int
    stance: str
    confianca: float  # min(confianca_rel, confianca_stance)


def escolher_amostra(
    itens: list[ItemAmostra],
    *,
    n_sorteada: int = 75,
    n_incerta: int = 75,
    seed: int,
    obrigatorios: set[uuid.UUID] = frozenset(),
) -> dict[uuid.UUID, str]:
    rng = random.Random(seed)
    # Ordena por id antes de sortear: o resultado não depende da ordem de entrada.
    itens = sorted(itens, key=lambda i: str(i.par_id))

    resultado: dict[uuid.UUID, str] = {
        i.par_id: SORTEADA for i in itens if i.par_id in obrigatorios
    }

    estratos: dict[tuple, list[ItemAmostra]] = defaultdict(list)
    for item in itens:
        if item.par_id not in resultado:
            estratos[(item.tema, item.relevancia, item.stance, item.origem)].append(item)

    chaves = sorted(estratos)
    rng.shuffle(chaves)
    for chave in chaves:
        rng.shuffle(estratos[chave])

    # Round-robin: uma volta pega 1 item de cada estrato, então estratos raros
    # aparecem antes de os comuns receberem o segundo.
    while len(resultado) < n_sorteada and any(estratos[c] for c in chaves):
        for chave in chaves:
            if len(resultado) >= n_sorteada:
                break
            if estratos[chave]:
                resultado[estratos[chave].pop().par_id] = SORTEADA

    restantes = sorted((i for i in itens if i.par_id not in resultado),
                       key=lambda i: (i.confianca, str(i.par_id)))
    for item in restantes[:n_incerta]:
        resultado[item.par_id] = INCERTA

    return resultado
