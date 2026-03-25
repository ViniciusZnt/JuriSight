"""
Definição dos campos de um documento jurídico coletado do TST.
"""

import scrapy


class DocumentItem(scrapy.Item):
    # --- Identificação ---
    numero_processo = scrapy.Field()
    tipo_documento  = scrapy.Field()   # ACORDAO | SUMULA | OJ | PRECEDENTE_NORMATIVO | DECISAO_MONOCRATICA
    hierarquia_categoria = scrapy.Field()  # 1=Súmula ... 5=Decisão Monocrática (só para ordenação)
    url_original    = scrapy.Field()

    # --- Metadados ---
    data_julgamento = scrapy.Field()
    relator         = scrapy.Field()
    orgao_julgador  = scrapy.Field()

    # --- Partes ---
    partes = scrapy.Field()  # [{"nome": str, "tipo": "RECLAMANTE"|"RECLAMADO"}]

    # --- Seções do documento ---
    ementa     = scrapy.Field()
    relatorio  = scrapy.Field()
    votos      = scrapy.Field()   # [str]
    resultado  = scrapy.Field()   # PROVIDO | NAO_PROVIDO | PARCIALMENTE_PROVIDO

    # --- Classificação (preenchida pelo NER após coleta) ---
    tipo_violacao  = scrapy.Field()   # insalubridade | periculosidade | horas_extras | rescisao
    agente_nocivo  = scrapy.Field()   # benzeno | ruido | calor | ...
    nrs_citadas    = scrapy.Field()   # [str]

    # --- Texto bruto (para reprocessamento) ---
    texto_integral = scrapy.Field()
