"""
Definição dos campos de um documento jurídico coletado do TST.
"""

# scraper/items/document_item.py

import scrapy

class DocumentItem(scrapy.Item):
    # Metadados do pipeline
    tipo_documento          = scrapy.Field()
    hierarquia_categoria    = scrapy.Field()
    data_filtro             = scrapy.Field()

    # Identificação
    id_documento            = scrapy.Field()
    numero_processo         = scrapy.Field()
    tribunal                = scrapy.Field()
    classe_processo         = scrapy.Field()
    sigla_classe            = scrapy.Field()

    # Pessoas
    relator                 = scrapy.Field()
    turma                   = scrapy.Field()
    gabinete                = scrapy.Field()
    id_gabinete             = scrapy.Field()
    id_turma                = scrapy.Field()

    # Datas
    data_julgamento         = scrapy.Field()
    data_juntada            = scrapy.Field()

    # Conteúdo Acordão — seções separadas
    cabecalho               = scrapy.Field()  # partes, recorrente, recorrido
    ementa                  = scrapy.Field()  # campo "ementa" da API (já limpo)
    relatorio               = scrapy.Field()  # resumo do caso
    fundamentacao           = scrapy.Field()  # argumentação jurídica
    acordao                 = scrapy.Field()
    votos                   = scrapy.Field()  # quem participou

    # Metadados jurídicos
    possui_ementa           = scrapy.Field()
    referencia_legislativa  = scrapy.Field()