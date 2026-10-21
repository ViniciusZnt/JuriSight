"""Atribuição de tema a uma tese (lista fixa), via OpenAI com saída estruturada."""
from __future__ import annotations

import json
import os
from typing import Literal

from openai import OpenAI
from pydantic import BaseModel

from avaliacao.geracao import MODELO_GERACAO_PADRAO

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


class _Tema(BaseModel):
    tema: Literal[tuple(TEMAS)]  # type: ignore[valid-type]


_PROMPT_TEMA = (
    "Você classifica teses de advogados trabalhistas brasileiros. Escolha o tema "
    "jurídico principal da tese, entre os temas da lista:\n"
    + "\n".join(f"- {t}: {d}" if d else f"- {t}" for t, d in _DESCRICOES.items())
)


def atribuir_tema(estrutura: dict, client: OpenAI | None = None) -> str:
    """Tema principal da tese, um dos TEMAS ("outro" se o modelo não escolher nenhum)."""
    client = client or OpenAI()
    resposta = client.chat.completions.parse(
        model=os.getenv("OPENAI_GEN_MODEL", MODELO_GERACAO_PADRAO),
        messages=[
            {"role": "system", "content": _PROMPT_TEMA},
            {"role": "user", "content": json.dumps(estrutura, ensure_ascii=False)},
        ],
        response_format=_Tema,
        temperature=0,
    )
    escolha = resposta.choices[0].message.parsed
    return escolha.tema if escolha is not None else "outro"
