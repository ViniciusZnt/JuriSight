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
"""
from __future__ import annotations

from datetime import date

from scraper.schema import DocumentoJuridico

Ordenacao = str  # "relevancia" | "data"


def ordenar(
    resultados: list[tuple[DocumentoJuridico, float]],
    por: Ordenacao = "relevancia",
) -> list[DocumentoJuridico]:
    """Ordena (doc, score_rrf) por hierarquia e depois por relevância ou data.

    Input:  resultados — lista de (DocumentoJuridico, score_rrf) vinda da busca;
            por — "relevancia" (default) ou "data".
    Returns: lista de DocumentoJuridico ordenada para exibição.

    TODO:
      - montar a chave de ordenação composta:
          primário  = doc.hierarquia_categoria           (asc: súmula antes de acórdão)
          secundário= -score_rrf            se por == "relevancia"
                      data_julgamento desc   se por == "data"  (cuidar de None)
      - usar sorted(resultados, key=...) e devolver só os DocumentoJuridico.
      - dica p/ data desc com None por último: usar uma chave que trate None como
        a data mínima (date.min) e inverter (reverse ou negação via ordinal).
    """
    raise NotImplementedError


def _chave_data(doc: DocumentoJuridico) -> date:
    """Chave de data para ordenação (trata data_julgamento None).

    Input:  doc.
    Returns: doc.data_julgamento, ou date.min quando ausente (vai para o fim no desc).

    TODO: return doc.data_julgamento or date.min
    """
    raise NotImplementedError
