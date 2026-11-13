"""
Result Formatter (RFC Tabela 6) — última etapa do pipeline de busca.

Serializa os (documento_id, DocumentoJuridico, score_rrf) já ordenados pelo
reranker (query/search/pipeline.py) nos cards de resposta da API — tipo, ementa, relator,
provimento e link (RF05/RF06/RF09).
"""
from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, Field

from scraper.schema import DocumentoJuridico, Provimento, TipoDocumento


class ClassificacaoProvimentoView(BaseModel):
    """Classificação do Jev (public.provimento_jev) mostrada no frontend."""

    resultado: str
    recorrente: str
    favorece: str
    probabilidades: dict[str, dict[str, float]]
    confianca_resultado: float | None = None
    confianca_recorrente: float | None = None
    confianca_favorece: float | None = None
    modelo: str


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
    sigla_classe: str = ""  # default: cards antigos salvos nas conversas não têm
    provimento: Provimento
    link_original: str | None
    score_rrf: float
    classificacao_provimento: ClassificacaoProvimentoView | None = None
    faixa: Literal["restrita", "livre"] = "livre"
    # por onde a decisão foi achada antes da fusão; vazio em cards antigos (conversas salvas)
    canais: list[Literal["semantica", "termos"]] = Field(default_factory=list)


class DocumentoDetalhe(DocumentoJuridico):
    """DocumentoJuridico completo + o id (UUID) que o schema de ingestão exclui
    de propósito (é devolvido à parte pelo DocRetriever). Usado por GET /document/{id}."""

    id: str
    classificacao_provimento: ClassificacaoProvimentoView | None = None


# Campos do documento que o card repete com o mesmo nome.
_CAMPOS_DO_DOCUMENTO = {
    "tipo_documento", "hierarquia_categoria", "numero_processo", "tribunal", "turma", "relator",
    "data_julgamento", "ementa", "sigla_classe", "provimento", "link_original",
}


def format_results(resultados: list[tuple[str, DocumentoJuridico, float]]) -> list[ResultCard]:
    """Projeta os triplos ordenados em cards de resposta.

    Não reordena — resultados já deve vir ordenado pelo pipeline.

    Input:  resultados — lista de (documento_id, DocumentoJuridico, score_rrf).
    Returns: lista de ResultCard, na mesma ordem de entrada.
    """
    return [
        ResultCard(id=documento_id, score_rrf=score, **doc.model_dump(include=_CAMPOS_DO_DOCUMENTO))
        for documento_id, doc, score in resultados
    ]
