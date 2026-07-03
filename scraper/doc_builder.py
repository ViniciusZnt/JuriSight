"""
Doc Builder).

Converte o documento bruto vindo da API (Web Scraper) num `DocumentoJuridico`
validado: resolve identidade, mapeia o tipo/hierarquia da coleção, extrai as
seções do HTML (HTML Extractor) e classifica o provimento (Provimento Clf).
"""
from __future__ import annotations

import logging
from datetime import date, datetime

from scraper.html_extractor import parse_document
from scraper.provimento import classify
from scraper.schema import (
    HIERARQUIA_CATEGORIA,
    DocumentoJuridico,
    TipoDocumento,
)

logger = logging.getLogger(__name__)

# Mapeia o nome da coleção (parâmetro da API) para o tipo de documento.
_COLECAO_TIPO: dict[str, TipoDocumento] = {
    "acordaos":    TipoDocumento.ACORDAO,
    "sumulas":     TipoDocumento.SUMULA,
    "ojs":         TipoDocumento.OJ,
    "precedentes": TipoDocumento.PRECEDENTE,
}

# Possíveis nomes do campo de ID por coleção, em ordem de preferência.
_ID_FIELDS = ("idDocumentoAcordao", "idDocumento", "id")


def _parse_api_date(value: str) -> date | None:
    """Parse de datas da API (DD/MM/YYYY ou YYYY-MM-DD). None se vazio/inválido."""
    if not value:
        return None
    for fmt in ("%d/%m/%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            continue
    logger.debug("Data da API não reconhecida, ignorando: %r", value)
    return None


_CITACAO_BASE = "https://jurisprudencia.jt.jus.br/jurisprudencia-nacional/citacao"


def _build_link_original(tribunal: str, doc_id: str, colecao: str) -> str | None:
    """Monta o link verificável do portal.

    Padrão de citação direta ao documento:
        /jurisprudencia-nacional/citacao/{colecao}/{tribunal}/{idDocumentoAcordao}
    Ex.: .../citacao/acordaos/TRT6/52258967

    Requer tribunal e id; sem um deles, não há link verificável.
    """
    if not (tribunal and doc_id):
        return None
    return f"{_CITACAO_BASE}/{colecao}/{tribunal}/{doc_id}"


def build_document(raw: dict) -> DocumentoJuridico | None:
    """Monta e valida um `DocumentoJuridico` a partir do documento bruto da API.

    Retorna None se o documento não tiver identificador (descartado a montante).
    """
    doc_id = ""
    for f in _ID_FIELDS:
        if raw.get(f):
            doc_id = raw[f]
            break
    if not doc_id:
        logger.warning("Documento sem ID ignorado: %s", raw.get("numeroProcesso"))
        return None

    colecao = raw.get("_colecao", "acordaos")
    tipo    = _COLECAO_TIPO.get(colecao, TipoDocumento.ACORDAO)

    parsed   = parse_document(raw.get("ementa", ""), raw.get("textoAcordao", ""))
    sections = parsed["acordao_section"]

    acordao = sections.get("texto_completo", "")
    provimento = classify(acordao, tipo)

    return DocumentoJuridico(
        id_documento=doc_id,
        tipo_documento=tipo,
        hierarquia_categoria=HIERARQUIA_CATEGORIA[tipo],
        data_filtro=_parse_api_date(raw.get("_data_filtro", "")),
        numero_processo=raw.get("numeroProcesso", ""),
        tribunal=raw.get("tribunal", ""),
        classe_processo=raw.get("classeProcesso", ""),
        sigla_classe=raw.get("siglaClasseProcesso", ""),
        relator=raw.get("relator", ""),
        turma=raw.get("turma", ""),
        gabinete=raw.get("gabinete", ""),
        data_julgamento=_parse_api_date(raw.get("dataJulgamento", "")),
        data_juntada=_parse_api_date(raw.get("dataJuntada", "")),
        cabecalho=sections.get("cabecalho", ""),
        ementa=parsed["ementa"] or sections.get("ementa", ""),
        relatorio=sections.get("relatorio", ""),
        fundamentacao=sections.get("fundamentacao", ""),
        acordao=acordao,
        votos=sections.get("votos", ""),
        possui_ementa=raw.get("possuiEmenta", "N") == "S",
        referencia_legislativa=raw.get("referenciaLegislativa", []) or [],
        provimento=provimento,
        link_original=_build_link_original(raw.get("tribunal", ""), doc_id, colecao),
    )
