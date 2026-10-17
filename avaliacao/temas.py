"""Atribuição de tema a uma tese (lista fixa), via Jev Choice."""
from __future__ import annotations

import os

from typesafe_sdk import Choice, TypeSafeClient

from avaliacao.juiz import MODELO_PADRAO

TEMAS: list[str] = [
    "insalubridade",
    "periculosidade",
    "horas extras",
    "intervalo intrajornada",
    "dano moral",
    "assédio moral",
    "acidente de trabalho / doença ocupacional",
    "vínculo empregatício",
    "rescisão indireta",
    "equiparação salarial",
    "estabilidade",
    "verbas rescisórias",
    "outro",
]

_DESCRICOES: dict[str, str | None] = {
    "insalubridade": "Adicional de insalubridade por exposição a agentes nocivos à saúde.",
    "periculosidade": "Adicional de periculosidade (inflamáveis, eletricidade, vigilância, motocicleta).",
    "horas extras": "Horas extras, jornada, banco de horas, cargo de confiança.",
    "intervalo intrajornada": "Intervalo para repouso e alimentação dentro da jornada.",
    "dano moral": "Indenização por dano moral que não seja assédio moral.",
    "assédio moral": "Assédio moral, humilhação ou perseguição no ambiente de trabalho.",
    "acidente de trabalho / doença ocupacional": None,
    "vínculo empregatício": "Reconhecimento de vínculo, pejotização, terceirização, fraude.",
    "rescisão indireta": "Falta grave do empregador que justifica a rescisão pelo empregado.",
    "equiparação salarial": "Equiparação ou isonomia salarial, desvio de função.",
    "estabilidade": "Estabilidade provisória (gestante, acidentária, cipeiro, dirigente sindical).",
    "verbas rescisórias": "Pagamento de verbas da rescisão, multas dos arts. 467 e 477 da CLT, FGTS.",
    "outro": "Nenhum dos temas acima.",
}


def atribuir_tema(
    estrutura: dict,
    client: TypeSafeClient | None = None,
    model: str | None = None,
) -> str:
    client = client or TypeSafeClient()
    model = model or os.getenv("TYPESAFE_MODEL", MODELO_PADRAO)
    pergunta = Choice(
        instructions="Qual é o tema jurídico principal da tese do advogado (`tese`)?",
        criteria={t: _DESCRICOES[t] for t in TEMAS},
    )
    resposta = client.system_one(
        state={"tese": estrutura}, questions={"tema": pergunta}, model=model
    )
    tema = resposta.answers["tema"].choice
    return tema if tema in TEMAS else "outro"
