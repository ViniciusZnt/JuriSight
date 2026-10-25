"""
Result Formatter (RFC Tabela 6) — última etapa do pipeline de busca.

Serializa os (documento_id, DocumentoJuridico, score_rrf) já ordenados por
categorical_sort.ordenar() nos cards de resposta da API — tipo, ementa, relator,
provimento e link (RF05/RF06/RF09).
"""
from __future__ import annotations

from datetime import date

from pydantic import BaseModel

from scraper.schema import DocumentoJuridico, Provimento, TipoDocumento


class ResultCard(BaseModel):
    """Card de resultado devolvido por POST /query."""

    id: str
    tipo_documento: TipoDocumento
    hierarquia_categoria: int
    numero_processo: str
    tribunal: str
    turma: str
    relator: str
    data_julgamento: date | None
    ementa: str
    provimento: Provimento
    link_original: str | None
    score_rrf: float


class DocumentoDetalhe(DocumentoJuridico):
    """DocumentoJuridico completo + o id (UUID) que o schema de ingestão exclui
    de propósito (é devolvido à parte pelo DocRetriever). Usado por GET /document/{id}."""

    id: str


def format_results(resultados: list[tuple[str, DocumentoJuridico, float]]) -> list[ResultCard]:
    """Projeta os triplos ordenados em cards de resposta.

    Não reordena — resultados já deve vir ordenado de categorical_sort.ordenar().

    Input:  resultados — lista de (documento_id, DocumentoJuridico, score_rrf).
    Returns: lista de ResultCard, na mesma ordem de entrada.
    """
    return [
        ResultCard(
            id=documento_id,
            tipo_documento=doc.tipo_documento,
            hierarquia_categoria=doc.hierarquia_categoria,
            numero_processo=doc.numero_processo,
            tribunal=doc.tribunal,
            turma=doc.turma,
            relator=doc.relator,
            data_julgamento=doc.data_julgamento,
            ementa=doc.ementa,
            provimento=doc.provimento,
            link_original=doc.link_original,
            score_rrf=score,
        )
        for documento_id, doc, score in resultados
    ]
