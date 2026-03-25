"""
Spider para coleta de acórdãos do TST.
Portal: https://jurisprudencia.tst.jus.br

Usa Scrapy-Playwright para renderizar o JavaScript do portal antes de extrair.
"""

import scrapy
from scrapy_playwright.page import PageMethod
from scraper.items.document_item import DocumentItem


class TSTAcordaosSpider(scrapy.Spider):
    name = "tst_acordaos"
    allowed_domains = ["jurisprudencia.tst.jus.br"]

    # Tipo e hierarquia categórica (1=Súmula ... 5=Decisão Monocrática)
    TIPO_DOCUMENTO = "ACORDAO"
    HIERARQUIA_CATEGORIA = 4

    custom_settings = {
        "DOWNLOAD_HANDLERS": {
            "https": "scrapy_playwright.handler.ScrapyPlaywrightDownloadHandler",
        }
    }

    def start_requests(self):
        url = "https://jurisprudencia.tst.jus.br/"
        yield scrapy.Request(
            url,
            meta={
                "playwright": True,
                "playwright_include_page": True,
                "playwright_page_methods": [
                    # Aguarda o portal carregar completamente
                    PageMethod("wait_for_selector", "input[type='text']", timeout=15_000),
                ],
            },
            callback=self.parse_search,
            errback=self.errback,
        )

    async def parse_search(self, response):
        """
        Ponto de entrada: interage com o formulário de busca do TST.
        TODO: implementar lógica de busca por tipo de documento e paginação.
        """
        page = response.meta["playwright_page"]
        # TODO: preencher campos de busca e iterar resultados
        await page.close()

    async def parse_document(self, response):
        """
        Extrai os dados de um acórdão individual.
        """
        page = response.meta.get("playwright_page")

        item = DocumentItem()
        item["tipo_documento"] = self.TIPO_DOCUMENTO
        item["hierarquia_categoria"] = self.HIERARQUIA_CATEGORIA
        item["url_original"] = response.url

        # TODO: implementar extração dos campos do acórdão
        # item["numero_processo"] = ...
        # item["data_julgamento"] = ...
        # item["relator"] = ...
        # item["ementa"] = ...

        if page:
            await page.close()

        yield item

    async def errback(self, failure):
        page = failure.request.meta.get("playwright_page")
        if page:
            await page.close()
        self.logger.error(f"Erro na requisição: {failure}")
