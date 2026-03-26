"""
Spider para coleta de acórdãos do Falcão (JT Nacional).
API REST pura — sem Playwright no spider, token fresco automático.
"""

import json
from urllib.parse import urlencode
import scrapy
from scraper.items.document_item import DocumentItem
from scraper.spiders.utils.juristkn import get_fresh_juristkn, JuristknRefreshError


class FalcaoSpider(scrapy.Spider):
    name = "falcao_acordaos"
    allowed_domains = ["jurisprudencia.jt.jus.br"]

    BASE_URL = "https://jurisprudencia.jt.jus.br/jurisprudencia-nacional-backend/api/no-auth/pesquisa"
    PAGE_SIZE = 10
    TASKS_FILE = "tasks.json" ## Melhor armzenar as task no Mongo

    custom_settings = {
        "CONCURRENT_REQUESTS": 2,
        "DOWNLOAD_DELAY": 1.5,
        "AUTOTHROTTLE_ENABLED": True,
        "AUTOTHROTTLE_TARGET_CONCURRENCY": 1.5,
        "RETRY_TIMES": 5,
        "RETRY_HTTP_CODES": [429, 500, 502, 503, 504, 401],  # 401 agora retry
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._load_fresh_tokens()

    def _load_fresh_tokens(self):
        """Carrega token fresco toda vez que o spider inicia."""
        try:
            tokens = get_fresh_juristkn()
            self.JURIS_TOKEN = tokens["juristkn"]
            self.DEFAULT_SESSION_ID = tokens["sessionId"]

            self.logger.info(
                f"juristkn atualizado com sucesso "
                f"(gerado às {tokens['captured_at'][:19]})"
            )
        except JuristknRefreshError as e:
            self.logger.critical(f"{e}")
            raise

    def build_url(self, data_inicio: str, data_fim: str, page: int) -> str:
        params = {
            "sessionId": self.DEFAULT_SESSION_ID,
            "juristkn": self.JURIS_TOKEN,
            "latitude": 0,
            "longitude": 0,
            "texto": "",
            "verTodosPrecedentes": "false",
            "tribunais": "",
            "pesquisaSomenteNasEmentas": "false",
            "filtroRapidoData": "Personalizado",
            "dataInicio": data_inicio,
            "dataFim": data_fim,
            "colecao": "acordaos",
            "page": page,
            "size": self.PAGE_SIZE,
        }
        return f"{self.BASE_URL}?{urlencode(params)}"

    def start_requests(self):
        try:
            with open(self.TASKS_FILE, encoding="utf-8") as f:
                tasks = json.load(f)
        except FileNotFoundError:
            self.logger.error(
                f"'{self.TASKS_FILE}' não encontrado. "
                "Rode primeiro: python orchestrator/generate_tasks.py"
            )
            return

        if not tasks:
            self.logger.info("Nenhuma task pendente.")
            return

        self.logger.info(f"{len(tasks)} tasks carregadas.")

        for task in tasks:
            yield scrapy.Request(
                self.build_url(task["data_inicio"], task["data_fim"], page=0),
                meta={"task": task, "page": 0},
                callback=self.parse_results,
                errback=self.errback,
                dont_filter=True,
            )

    def parse_results(self, response):
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
                f"0 documentos na página {page}."
            )
            return

        self.logger.info(
            f"Task {task['id']} | página {page} | {len(documentos)} docs"
        )

        for doc in documentos:
            yield self.extract_item(doc, task)

        # Paginação: se retornou PAGE_SIZE documentos, pode haver mais
        if len(documentos) == self.PAGE_SIZE:
            next_page = page + 1
            yield scrapy.Request(
                self.build_url(task["data_inicio"], task["data_fim"], page=next_page),
                meta={"task": task, "page": next_page},
                callback=self.parse_results,
                errback=self.errback,
                dont_filter=True,
            )

    def extract_item(self, doc: dict, task: dict) -> DocumentItem:
        item = DocumentItem()

        item["tipo_documento"]      = "ACORDAO"
        item["hierarquia_categoria"] = 4
        item["ano"]                 = task["ano"]
        item["mes"]                 = task["mes"]

        # Campos diretos da API
        item["numero_processo"]     = doc.get("numeroProcesso", "")
        item["tribunal"]            = doc.get("tribunal", "")
        item["relator"]             = doc.get("relator", "")
        item["turma"]               = doc.get("turma", "")
        item["gabinete"]            = doc.get("gabinete", "")
        item["classe_processo"]     = doc.get("classeProcesso", "")
        item["sigla_classe"]        = doc.get("siglaClasseProcesso", "")
        item["data_julgamento"]     = doc.get("dataJulgamento", "")
        item["data_juntada"]        = doc.get("dataJuntada", "")
        item["id_documento"]        = doc.get("idDocumentoAcordao", "")
        item["referencia_legislativa"] = doc.get("referenciaLegislativa", [])

        # HTML → texto puro
        item["ementa"]              = html_to_text(doc.get("ementa", ""))
        item["texto_acordao"]       = html_to_text(doc.get("textoAcordao", ""))

        return item

    def errback(self, failure):
        task = failure.request.meta.get("task", {})
        self.logger.error(
            f"Falha na task {task.get('id')} "
            f"({task.get('data_inicio')} → {task.get('data_fim')}): {failure}"
        )