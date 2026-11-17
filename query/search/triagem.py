"""
Triagem por IA (POST /triagem): para cada ementa de um lote de até 10, a IA dá uma nota de
0 a 3 de relação com a tese (a escala do conjunto-ouro, avaliacao/) e a posição da decisão
(deferiu / negou / fato diferente / outro). A nota ordena a lista na tela; a posição alimenta
a resposta gerada (query/search/resposta.py).

Ao modelo vão SÓ os campos da tese (sem os filtros: eles já decidiram quem é elegível e não
mudam a relevância) e as ementas públicas, cortadas — nunca o PDF nem texto do caso.
"""
from __future__ import annotations

import hashlib
import json
import os
from typing import Literal

from openai import OpenAI
from pydantic import BaseModel

from query.enrichment.schema import EstruturaArgumentativa
from query.search.resposta import PosicaoTese, _cabecalho, posicao_de
from scraper.schema import DocumentoJuridico

MODELO_PADRAO = "gpt-4o-mini"
TIMEOUT_S = 20
MAX_EMENTA_TRIAGEM = 1200  # basta para o fato decisivo (começo) e o desfecho (fim)
MAX_LOTE = 10
CAMPOS_DA_TESE = ("pedido_principal", "agente_nocivo", "violacoes", "normas", "tese_central")

_PROMPT = (
    "Você é um advogado trabalhista brasileiro fazendo a triagem de jurisprudência para uma tese. "
    "Para CADA ementa numerada (#1, #2…), preencha um item, na ordem dos campos:\n"
    "- `motivo`: o fato decisivo da decisão e o que ela decidiu sobre o pedido, em até 12 palavras.\n"
    "- `nota`: quanto a decisão serve à tese:\n"
    "  0 = outro problema jurídico;\n"
    "  1 = mesmo ramo, mas outro pedido ou outro fato central;\n"
    "  2 = mesmo pedido, com fato decisivo diferente ou só em parte;\n"
    "  3 = mesmo problema e mesmo fato decisivo (um advogado citaria na peça).\n"
    "- `pedido_da_tese`: \"deferiu\" ou \"negou\" ao trabalhador o pedido da tese, lendo o desfecho no "
    "fim da ementa; \"outro\" se não decidiu esse pedido.\n"
    "- `fatos_da_premissa`: false se os fatos que a decisão deu por provados contradizem a premissa da "
    "tese (ex.: a premissa diz proteção ineficaz e a decisão a deu por eficaz; a premissa diz acima do "
    "limite e a decisão achou abaixo; outro agente); true se são os mesmos fatos.\n"
    "Julgue a decisão pela tese, não pelo resultado: uma decisão que negou o pedido com os mesmos fatos "
    "também é nota 3."
)

NotaTriagem = Literal[0, 1, 2, 3]


class Avaliacao(BaseModel):
    nota: NotaTriagem
    posicao: PosicaoTese
    motivo: str


# --- Schema pedido ao modelo ------------------------------------------------------------------

class ItemTriagem(BaseModel):
    numero: int
    motivo: str  # antes da nota: o modelo lê o fato decisivo e só então classifica
    nota: int
    pedido_da_tese: Literal["deferiu", "negou", "outro"]
    fatos_da_premissa: bool


class TriagemGerada(BaseModel):
    itens: list[ItemTriagem]


def tese_para_ia(estrutura: EstruturaArgumentativa) -> dict:
    """Só os campos da tese, sem os vazios (o que vai ao modelo e entra na chave do cache)."""
    return estrutura.model_dump(mode="json", include=set(CAMPOS_DA_TESE), exclude_defaults=True)


def _modelo() -> str:
    return os.getenv("OPENAI_TRIAGEM_MODEL", MODELO_PADRAO)


def _temperatura() -> str:
    return os.getenv("OPENAI_GEN_TEMPERATURE", "0")


def chave_da_triagem(estrutura: EstruturaArgumentativa, documento_id: str) -> str:
    """Chave do cache por par tese × decisão: muda com o modelo, a temperatura, o prompt, a tese
    ou a decisão — e não com os filtros, que não vão ao modelo."""
    partes = {"modelo": _modelo(), "temperatura": _temperatura(), "prompt": _PROMPT,
              "tese": tese_para_ia(estrutura), "documento_id": documento_id}
    return hashlib.sha256(json.dumps(partes, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def _trecho_triagem(ementa: str) -> str:
    """Até MAX_EMENTA_TRIAGEM; acima disso, começo (fatos) e fim (desfecho)."""
    e = ementa.strip()
    return e if len(e) <= MAX_EMENTA_TRIAGEM else f"{e[:800]} […] {e[-400:]}"


def avaliar_lote(
    estrutura: EstruturaArgumentativa,
    decisoes: dict[str, DocumentoJuridico],
    client: OpenAI,
) -> dict[str, Avaliacao]:
    """Pede ao modelo a nota e a posição de cada decisão do lote.

    Input:  estrutura — a tese revisada; decisoes — id -> documento, na ordem #1..#k.
    Returns: id -> Avaliacao, só dos itens válidos (número do lote, primeira ocorrência, nota 0-3).
    Raises: openai.OpenAIError (rede, timeout, status) — o endpoint vira 503.
    """
    if not decisoes:
        return {}
    ids = list(decisoes)
    ementas = "\n\n".join(
        f"{_cabecalho(n, d)}\n{_trecho_triagem(d.ementa)}" for n, d in enumerate(decisoes.values(), start=1)
    )
    tese = json.dumps(tese_para_ia(estrutura), ensure_ascii=False)
    resposta = client.chat.completions.parse(
        model=_modelo(),
        temperature=float(_temperatura()),
        messages=[
            {"role": "system", "content": _PROMPT},
            {"role": "user", "content": f"Tese:\n{tese}\n\nEmentas:\n{ementas}"},
        ],
        response_format=TriagemGerada,
        timeout=TIMEOUT_S,
    )
    gerada = resposta.choices[0].message.parsed
    if gerada is None:  # recusa do modelo
        return {}
    avaliacoes: dict[str, Avaliacao] = {}
    for item in gerada.itens:
        if not 1 <= item.numero <= len(ids) or item.nota not in (0, 1, 2, 3):
            continue
        doc_id = ids[item.numero - 1]
        if doc_id not in avaliacoes:
            avaliacoes[doc_id] = Avaliacao(
                nota=item.nota, posicao=posicao_de(item.pedido_da_tese, item.fatos_da_premissa),
                motivo=item.motivo.strip(),
            )
    return avaliacoes
