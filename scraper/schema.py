"""
Schema tipado do pipeline de ingestão (RFC §5.2).

Define o contrato `DocumentoJuridico` validado via Pydantic v2 antes da
persistência no PostgreSQL — corresponde ao componente "Doc Builder [Pydantic v2]"
do diagrama C4 (Nível 3 — Pipeline de Ingestão).

A fonte de verdade é o PostgreSQL; o UUID `id` é a chave referenciada como
`documento_id` (FK) pelos chunks no ChromaDB.
"""
from __future__ import annotations

from datetime import date
from enum import Enum

from pydantic import BaseModel, Field


class TipoDocumento(str, Enum):
    ACORDAO    = "ACORDAO"
    SUMULA     = "SUMULA"
    OJ         = "OJ"
    PRECEDENTE = "PRECEDENTE"


class Provimento(str, Enum):
    """Posicionamento da decisão — extraído via regex do dispositivo (RN05).

    Para súmulas/OJs (que não julgam um pedido) o valor é sempre NAO_APLICAVEL.
    """
    APROVADO      = "APROVADO"
    NEGADO        = "NEGADO"
    NAO_APLICAVEL = "NAO_APLICAVEL"


# Prioridade de ordenação categórica (RFC §5.2 — hierarquia_categoria).
HIERARQUIA_CATEGORIA: dict[TipoDocumento, int] = {
    TipoDocumento.SUMULA:     1,
    TipoDocumento.OJ:         2,
    TipoDocumento.PRECEDENTE: 3,
    TipoDocumento.ACORDAO:    4,
}


class DocumentoJuridico(BaseModel):
    """Documento jurídico coletado do portal (acórdão, súmula, OJ, precedente).

    Validado antes de persistir. Campos ausentes na origem ficam vazios/None,
    nunca inventados (RNF01 / RN06).
    """

    # Identidade
    id_documento:         str            # identificador original do portal (chave natural)
    tipo_documento:       TipoDocumento
    hierarquia_categoria: int

    # Metadados processuais
    data_filtro:          date | None = None  # dia usado no scraping (controle interno)
    numero_processo:      str = ""
    tribunal:             str = ""
    classe_processo:      str = ""
    sigla_classe:         str = ""
    relator:              str = ""
    turma:                str = ""
    gabinete:             str = ""
    data_julgamento:      date | None = None
    data_juntada:         date | None = None

    # Conteúdo (seções extraídas do HTML — RFC §5.3 etapa 2)
    cabecalho:            str = ""
    ementa:               str = ""
    relatorio:            str = ""
    fundamentacao:        str = ""
    acordao:              str = ""   # seção "ACÓRDÃO"/dispositivo — base da classificação de provimento
    votos:                str = ""
    possui_ementa:        bool = False
    referencia_legislativa: list[str] = Field(default_factory=list)

    # Alinhamento argumentativo (RN04 / RN05)
    provimento:           Provimento = Provimento.NAO_APLICAVEL
    link_original:        str | None = None  # link verificável do portal (RN04)
