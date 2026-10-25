"""
Categorical Sort / Hierarchical Ranker.

Ordena os documentos recuperados para exibição. Regras (RN02):
  - a hierarquia jurídica é o critério PRIMÁRIO (súmula → OJ → precedente →
    acórdão), via hierarquia_categoria (1 = súmula ... 4 = acórdão);
  - dentro de cada categoria, a ordem é escolhida pelo usuário:
      * "relevancia" → maior score do RRF primeiro;
      * "data"       → data_julgamento mais recente primeiro.

Peça que você já pode usar:
  - HIERARQUIA_CATEGORIA (scraper/schema.py) — mapa TipoDocumento -> prioridade;
    o próprio DocumentoJuridico já carrega o campo `hierarquia_categoria`.

Nota sobre a assinatura de ordenar(): recebe e devolve triplos
(documento_id, DocumentoJuridico, score_rrf), não só (doc, score). O
DocumentoJuridico não carrega o UUID de propósito (é devolvido à parte pelo
DocRetriever) — sem carregar o id através da ordenação, o Result Formatter não
teria como montar o link para GET /document/{id}.
"""
from __future__ import annotations

from datetime import date

from scraper.schema import DocumentoJuridico

Ordenacao = str  # "relevancia" | "data"


def _chave_data(doc: DocumentoJuridico) -> date:
    """Chave de data para ordenação (trata data_julgamento None).

    Input:  doc.
    Returns: doc.data_julgamento, ou date.min quando ausente (vai para o fim no desc).
    """
    return doc.data_julgamento or date.min


def _chave_ordenacao(item: tuple[str, DocumentoJuridico, float], por: Ordenacao) -> tuple[int, float]:
    """Chave de ordenação composta: hierarquia_categoria (primário) + relevância/data (secundário).

    Input:  item — (documento_id, doc, score_rrf); por — "relevancia" ou "data".
    Returns: tupla (hierarquia_categoria, chave_secundaria) para sorted() em ordem asc.
    """
    _, doc, score = item
    if por == "data":
        secundaria = -_chave_data(doc).toordinal()  # date.min -> maior ordinal negado -> vai ao fim
    else:
        secundaria = -score
    return (doc.hierarquia_categoria, secundaria)


def ordenar(
    resultados: list[tuple[str, DocumentoJuridico, float]],
    por: Ordenacao = "relevancia",
) -> list[tuple[str, DocumentoJuridico, float]]:
    """Ordena (documento_id, doc, score_rrf) por hierarquia e depois por relevância ou data.

    Input:  resultados — lista de (documento_id, DocumentoJuridico, score_rrf)
            vinda da busca; por — "relevancia" (default) ou "data".
    Returns: mesma lista de triplos, ordenada para exibição.
    """
    return sorted(resultados, key=lambda item: _chave_ordenacao(item, por))
