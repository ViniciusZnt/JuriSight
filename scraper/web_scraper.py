"""
Web Scraper (componente C4 — Pipeline de Ingestão).

Coleta documentos e metadados do portal da Justiça do Trabalho via a API REST
pública (no-auth), usando `requests`.
"""
import requests


DEFAULT_BASE_URL = (
    "https://jurisprudencia.jt.jus.br"
    "/jurisprudencia-nacional-backend/api/no-auth/pesquisa"
)

DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
    "Origin": "https://jurisprudencia.jt.jus.br",
    "Referer": "https://jurisprudencia.jt.jus.br/jurisprudencia-nacional/",
}


class ApiResponseError(RuntimeError):
    pass


class BlockedResponseError(ApiResponseError):
    pass


class TransientApiError(ApiResponseError):
    pass


class WebScraper:
    def __init__(self, session=None, base_url=DEFAULT_BASE_URL, timeout=30):
        self.session = session or requests.Session()
        self.base_url = base_url
        self.timeout = timeout

    def search_page(self, date_str: str, page: int, colecao: str = "acordaos") -> dict:
        params = {
            "colecao":    colecao,
            "page":       page,
            "size":       10,
            "dataInicio": date_str,
            "dataFim":    date_str,
        }
        try:
            response = self.session.get(
                self.base_url,
                params=params,
                headers=DEFAULT_HEADERS,
                timeout=self.timeout,
            )
        except requests.RequestException as exc:
            raise TransientApiError(str(exc)) from exc

        payload = self._safe_json(response)
        if response.status_code == 200:
            return payload
        if response.status_code == 429:
            retry_after = response.headers.get("x-rate-limit-retry-after-seconds", "?")
            raise BlockedResponseError(
                f"Rate limit (429) — tente novamente em {retry_after}s"
            )
        if response.status_code == 403:
            raise BlockedResponseError(self._extract_message(payload, response))
        if response.status_code >= 500:
            raise TransientApiError(self._extract_message(payload, response))
        raise ApiResponseError(self._extract_message(payload, response))

    @staticmethod
    def _safe_json(response):
        try:
            return response.json()
        except ValueError:
            return {"rawText": response.text}

    @staticmethod
    def _extract_message(payload, response):
        if isinstance(payload, dict):
            for key in ("developerMessage", "userMessage", "message", "rawText"):
                value = payload.get(key)
                if value:
                    return str(value)
        return f"HTTP {response.status_code}"
