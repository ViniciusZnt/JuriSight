import json
import re
from html.parser import HTMLParser
from urllib.parse import urlencode

import scrapy
from scraper.items.document_item import DocumentItem
from scraper.spiders.utils.juristkn import token_manager, JuristknRefreshError
from scraper.spiders.utils.html_parser import parse_document


class FalcaoSpider(scrapy.Spider):
    name = "falcao_acordaos"
    allowed_domains = ["jurisprudencia.jt.jus.br"]

    BASE_URL = "https://jurisprudencia.jt.jus.br/jurisprudencia-nacional-backend/api/no-auth/pesquisa"
    PAGE_SIZE = 10
    TASKS_FILE = "tasks.json" # Pode ser alterado depois para uma lógica melhor

    custom_settings = {
        "CONCURRENT_REQUESTS": 2,
        "DOWNLOAD_DELAY": 1.5,
        "AUTOTHROTTLE_ENABLED": True,
        "AUTOTHROTTLE_TARGET_CONCURRENCY": 1.5,
        "RETRY_TIMES": 3,
        "RETRY_HTTP_CODES": [429, 500, 502, 503, 504],
        # 403 NÃO entra aqui — tratado errback
    }

    def build_url(self, data_inicio: str, data_fim: str, page: int) -> str:
        tokens = token_manager.get_tokens()  # renova se necessário
        params = {
            "sessionId":              tokens["sessionId"],
            "latitude":               0,
            "longitude":              0,
            "juristkn":               tokens["juristkn"],
            "texto":                  "",
            "verTodosPrecedentes":    "false",
            "tribunais":              "",
            "pesquisaSomenteNasEmentas": "false",
            "filtroRapidoData":       "IntervaloSelecionado",
            "dataInicio":             data_inicio,
            "dataFim":                data_fim,
            "colecao":                "acordaos",
            "page":                   page,
            "size":                   self.PAGE_SIZE,
        }
        return f"{self.BASE_URL}?{urlencode(params)}"

    async def start_requests(self):
        try:
            with open(self.TASKS_FILE, encoding="utf-8") as f:
                tasks = json.load(f)
        except FileNotFoundError:
            self.logger.error("tasks.json não encontrado.")
            return

        if not tasks:
            self.logger.info("Nenhuma task pendente.")
            return

        # Valida token uma vez antes de começar
        try:
            tokens = token_manager.get_tokens()
            self.logger.info(
                f"Token válido até {tokens['expires_at']} "
                f"({tokens['ttl_seconds']}s restantes)"
            )
        except JuristknRefreshError as e:
            self.logger.critical(f"Não foi possível obter token: {e}")
            return

        self.logger.info(f"{len(tasks)} tasks carregadas.")

        for task in tasks:
            yield scrapy.Request(
                self.build_url(task["data_inicio"], task["data_fim"], page=0),
                meta={"task": task, "page": 0, "retry_on_403": True},
                callback=self.parse_results,
                errback=self.errback,
                dont_filter=True,
            )

    def parse_results(self, response):
        # 403 durante a coleta — token expirou no meio do caminho
        if response.status == 403:
            return self._handle_expired_token(response)

        try:
            data = response.json()
        except Exception as e:
            self.logger.error(f"Resposta não é JSON: {e} | URL: {response.url}")
            return

        documentos = data.get("documentos", [])
        task = response.meta["task"]
        page = response.meta["page"]

        if not documentos:
            self.logger.info(
                f"Task {task['id']} ({task['data_inicio']} → {task['data_fim']}): "
                f"0 docs na página {page}."
            )
            return

        self.logger.info(f"Task {task['id']} | página {page} | {len(documentos)} docs")

        for doc in documentos:
            yield self.extract_item(doc, task)

        if len(documentos) == self.PAGE_SIZE:
            next_page = page + 1
            yield scrapy.Request(
                self.build_url(task["data_inicio"], task["data_fim"], page=next_page),
                meta={"task": task, "page": next_page, "retry_on_403": True},
                callback=self.parse_results,
                errback=self.errback,
                dont_filter=True,
            )

    def _handle_expired_token(self, response):
        """Token expirou durante a coleta — renova e re-emite a request."""
        task = response.meta["task"]
        page = response.meta["page"]

        if not response.meta.get("retry_on_403", False):
            self.logger.error(
                f"403 persistente após renovação de token na task {task['id']}. "
                "Abortando essa request."
            )
            return

        self.logger.warning(
            f"403 detectado na task {task['id']} página {page}. "
            "Renovando token e re-tentando..."
        )

        try:
            tokens = token_manager.force_refresh()
            self.logger.info(
                f"Token renovado. Novo TTL: {tokens['ttl_seconds']}s"
            )
        except JuristknRefreshError as e:
            self.logger.error(f"Falha ao renovar token: {e}")
            return

        # Re-emite a mesma request com token novo e sem retry_on_403
        # para evitar loop infinito
        yield scrapy.Request(
            self.build_url(task["data_inicio"], task["data_fim"], page=page),
            meta={"task": task, "page": page, "retry_on_403": False},
            callback=self.parse_results,
            errback=self.errback,
            dont_filter=True,
        )

    def extract_item(self, doc: dict, task: dict) -> DocumentItem:
        item = DocumentItem()

        # Metadados do pipeline
        item["tipo_documento"]       = "ACORDAO"
        item["hierarquia_categoria"] = 4
        item["data_filtro"]          = task["data_inicio"]            # Data que o filtro foi aplicado para extração = DataJuntada

        # Campos diretos — confirmados no JSON real
        item["numero_processo"]      = doc.get("numeroProcesso", "")
        item["tribunal"]             = doc.get("tribunal", "")                # "TRT4"
        item["relator"]              = doc.get("relator", "")                 # "PLAUTO CARNEIRO PORTO"
        item["turma"]                = doc.get("turma", "")                   # "3ª Turma"
        item["gabinete"]             = doc.get("gabinete", "")                # "Gab. Des. Plauto Carneiro Porto"
        item["classe_processo"]      = doc.get("classeProcesso", "")          # "Recurso Ordinário Trabalhista"
        item["sigla_classe"]         = doc.get("siglaClasseProcesso", "")     # "ROT"
        item["data_julgamento"]      = doc.get("dataJulgamento", "")          # "11/03/2026"
        item["data_juntada"]         = doc.get("dataJuntada", "")             # "12/03/2026"
        item["id_documento"]         = doc.get("idDocumentoAcordao", "") 
        item["referencia_legislativa"] = doc.get("referenciaLegislativa", []) # "art_11_clt", "trt7", "sumula_214_tst"....
        item["possui_ementa"]        = doc.get("possuiEmenta", "N") == "S"    # "S"


        # HTML para texto
        ementa_Acordao = parse_document(doc.get("ementa", ""),doc.get("textoAcordao", ""))
        item["ementa"]               = ementa_Acordao["ementa"]
        item["texto_acordao"]        = ementa_Acordao["acordao_section"]

        return item
    
    def errback(self, failure):
        task = failure.request.meta.get("task", {})
        self.logger.error(
            f"Falha na task {task.get('id')} "
            f"({task.get('data_inicio')} → {task.get('data_fim')}): {failure}"
        )