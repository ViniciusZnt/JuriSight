"""
Resposta gerada e ancorada (POST /resposta): poucas frases que respondem à tese,
cada uma citando as decisões (#1..#N, a numeração dos cards) que a sustentam.

Ao modelo vão SÓ a EstruturaArgumentativa (que já vai à OpenAI no embedding) e as
ementas públicas dos resultados — nunca o PDF nem texto do caso. Frase sem citação
ou com número fora das decisões enviadas é descartada aqui, no servidor.
"""
from __future__ import annotations

import os

from openai import OpenAI
from pydantic import BaseModel

from query.enrichment.schema import EstruturaArgumentativa
from scraper.schema import DocumentoJuridico

MODELO_PADRAO = "gpt-4o-mini"
TIMEOUT_S = 20
MAX_EMENTA = 2000  # caracteres por ementa no prompt

_PROMPT = (
    "Você é um advogado trabalhista brasileiro. Responda à tese do usuário só com base nas "
    "ementas numeradas (#1, #2…). Escreva em português, curto e técnico:\n"
    "1. A primeira frase responde diretamente à pergunta (Sim/Não/Depende), condicionada à "
    "premissa da tese (ex.: \"Sim, quando a perícia confirma ruído acima do limite do Anexo 1 "
    "da NR-15 e o EPI não neutraliza o agente…\").\n"
    "2. Depois, 2 a 4 frases com o fundamento e o que precisa ser provado.\n"
    "3. Por fim, 1 frase sobre a divergência explicada pelo MOTIVO (ex.: \"as decisões "
    "contrárias negaram porque o laudo atestou EPI eficaz\"), nunca por contagem. Se não houver "
    "divergência nas ementas, diga isso.\n"
    "Cada frase cita em `citacoes` os números das decisões que a sustentam. Não invente: só "
    "mencione lei, súmula, OJ ou NR que apareça nas ementas citadas naquela frase. Não escreva "
    "os números (#3) dentro do texto."
)


class Frase(BaseModel):
    texto: str
    citacoes: list[int]


class RespostaGerada(BaseModel):
    frases: list[Frase]


def _cabecalho(n: int, doc: DocumentoJuridico) -> str:
    """'#3 (RORSum, TRT2, 11ª Turma, 2025-05-12)' — só metadados públicos da decisão."""
    meta = [doc.sigla_classe, doc.tribunal, doc.turma, doc.data_julgamento and doc.data_julgamento.isoformat()]
    return f"#{n} ({', '.join(m for m in meta if m)})"


def gerar_resposta(
    estrutura: EstruturaArgumentativa,
    decisoes: dict[int, DocumentoJuridico],
    client: OpenAI,
) -> list[Frase]:
    """Pede a resposta ao modelo e devolve só as frases com citações válidas.

    Input:  estrutura — a tese revisada; decisoes — número do card (#n) -> documento.
    Returns: frases cujas citações são todas números de `decisoes` (sem repetição).
    Raises: openai.OpenAIError (rede, timeout, status) — o endpoint vira 503.
    """
    if not decisoes:
        return []
    ementas = "\n\n".join(
        f"{_cabecalho(n, d)}\n{d.ementa.strip()[:MAX_EMENTA]}" for n, d in sorted(decisoes.items())
    )
    tese = estrutura.model_dump_json(exclude_defaults=True)
    resposta = client.chat.completions.parse(
        model=os.getenv("OPENAI_GEN_MODEL", MODELO_PADRAO),
        temperature=float(os.getenv("OPENAI_GEN_TEMPERATURE", "0")),
        messages=[
            {"role": "system", "content": _PROMPT},
            {"role": "user", "content": f"Tese:\n{tese}\n\nEmentas:\n{ementas}"},
        ],
        response_format=RespostaGerada,
        timeout=TIMEOUT_S,
    )
    gerada = resposta.choices[0].message.parsed
    if gerada is None:  # recusa do modelo
        return []
    return [
        Frase(texto=f.texto.strip(), citacoes=list(dict.fromkeys(f.citacoes)))
        for f in gerada.frases
        if f.texto.strip() and f.citacoes and all(c in decisoes for c in f.citacoes)
    ]
