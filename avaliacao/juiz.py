"""
Juiz do harness de avaliação: rotula pares (tese, acórdão) com relevância 0-3
e stance, usando o Jev (TypeSafe System One). A interface `Juiz` permite
trocar o modelo sem tocar no resto do pacote.
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import uuid
from concurrent.futures import ThreadPoolExecutor
from typing import Callable, Protocol

from typesafe_sdk import Choice, Score, TypeSafeClient, TypeSafeError

from avaliacao.store import Julgamento
from scraper.schema import DocumentoJuridico

logger = logging.getLogger(__name__)

MODELO_PADRAO = "jev-1.13.0"
TAMANHO_FUNDAMENTACAO = 3000

PERGUNTAS: dict[str, Score | Choice] = {
    "relevancia": Score(
        instructions=(
            "Quão relevante este acórdão (`acordao`) é para a tese do advogado (`tese`)?"
        ),
        criteria=[
            "O acórdão trata de outro problema jurídico.",
            "O acórdão é do mesmo ramo, mas o pedido ou o fato central é outro.",
            "O acórdão trata do mesmo pedido, mas o fato decisivo é diferente.",
            "O acórdão trata do mesmo problema jurídico e do mesmo fato decisivo.",
        ],
    ),
    "stance": Choice(
        instructions=(
            "A conclusão deste acórdão (`acordao`) fortalece, enfraquece ou é neutra "
            "em relação à tese do advogado (`tese`)?"
        ),
        criteria={
            "fortalece": "A conclusão do acórdão apoia a tese do advogado.",
            "enfraquece": "A conclusão do acórdão contraria a tese do advogado.",
            "neutro": "O acórdão não toma posição que apoie ou contrarie a tese.",
        },
    ),
}


def perguntas_sha() -> str:
    """sha256 das perguntas do Jev (instruções e critérios).

    Serializa cada pergunta com `model_dump(mode="json")` e `json.dumps(sort_keys=True)`,
    então só muda quando o texto das perguntas muda. Gravada no cabeçalho do CLI e no
    relatório para saber se dois julgamentos foram feitos com as mesmas perguntas."""
    dump = {nome: p.model_dump(mode="json") for nome, p in PERGUNTAS.items()}
    texto = json.dumps(dump, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(texto.encode("utf-8")).hexdigest()


class Juiz(Protocol):
    nome: str

    def julgar(
        self, tese: dict, documento: DocumentoJuridico, rodada: int, par_id: uuid.UUID
    ) -> Julgamento: ...


def montar_estado(tese: dict, documento: DocumentoJuridico) -> dict:
    return {
        "tese": tese,
        "acordao": {
            "ementa": documento.ementa or "",
            "fundamentacao_inicio": (documento.fundamentacao or "")[:TAMANHO_FUNDAMENTACAO],
        },
    }


class JuizJev:
    def __init__(self, client: TypeSafeClient | None = None, model: str | None = None):
        self.client = client or TypeSafeClient()
        self.model = model or os.getenv("TYPESAFE_MODEL", MODELO_PADRAO)
        self.nome = f"jev:{self.model}"

    def julgar(
        self, tese: dict, documento: DocumentoJuridico, rodada: int, par_id: uuid.UUID
    ) -> Julgamento:
        resposta = self.client.system_one(
            state=montar_estado(tese, documento),
            questions=PERGUNTAS,
            model=self.model,
        )
        rel = resposta.answers["relevancia"]
        stance = resposta.answers["stance"]
        # O SDK real devolve as chaves como int; no banco (JSONB) viram str.
        # Normaliza para str para o valor ser igual antes e depois de gravar.
        probs_rel = {str(k): v for k, v in rel.probabilities.items()}
        return Julgamento(
            par_id=par_id,
            juiz=self.nome,
            rodada=rodada,
            relevancia=int(max(probs_rel, key=probs_rel.get)),
            stance=stance.choice,
            relevancia_probs=probs_rel,
            stance_probs=dict(stance.probabilities),
            confianca_rel=rel.confidence,
            confianca_stance=stance.confidence,
        )


def julgar_lote(
    juiz: Juiz,
    itens: list[tuple[uuid.UUID, dict, DocumentoJuridico]],
    rodada: int,
    ao_julgar: Callable[[Julgamento], None],
    max_workers: int = 8,
) -> int:
    """Julga os itens em paralelo; devolve quantos deram certo.

    Falha do SDK num item é registrada e o item é pulado (o lote segue).
    `ao_julgar` roda na thread principal, então pode gravar sem lock.
    """

    def _um(item):
        par_id, tese, documento = item
        try:
            return juiz.julgar(tese, documento, rodada, par_id)
        except TypeSafeError:
            logger.exception("Falha ao julgar o par %s; pulado", par_id)
            return None

    ok = 0
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        for julgamento in pool.map(_um, itens):
            if julgamento is not None:
                ao_julgar(julgamento)
                ok += 1
    return ok
