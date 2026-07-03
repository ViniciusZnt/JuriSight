"""
Web Scraper (componente C4 — Pipeline de Ingestão).

Coleta documentos e metadados do portal da Justiça do Trabalho via a API REST
pública (no-auth), usando `requests`. A API exige uma sessão autenticada
(cookies anti-bot + `sessionId`) cunhada por um navegador real — ver
`SessionMinter`. Os cookies são reusados na `requests.Session`; ao receber 403
(sessão expirada), recunha e repete a requisição.
"""
import logging

import requests

from scraper.session_minter import DEFAULT_USER_AGENT, SessionMinter

logger = logging.getLogger(__name__)

DEFAULT_BASE_URL = (
    "https://jurisprudencia.jt.jus.br"
    "/jurisprudencia-nacional-backend/api/no-auth/pesquisa"
)

DEFAULT_HEADERS = {
    "User-Agent": DEFAULT_USER_AGENT, 
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
    "Origin": "https://jurisprudencia.jt.jus.br",
    "Referer": "https://jurisprudencia.jt.jus.br/jurisprudencia-nacional/pesquisa",
}

PAGE_SIZE = 10  # tamanho de página aceito pela API (3 e 20 são rejeitados; 5 e 10 ok)


class ApiResponseError(RuntimeError):
    pass


class BlockedResponseError(ApiResponseError):
    pass


class TransientApiError(ApiResponseError):
    pass


class WebScraper:
    def __init__(self, session_minter=None, http_session=None, base_url=DEFAULT_BASE_URL, timeout=30):
        self.minter   = session_minter or SessionMinter()
        self.session  = http_session or requests.Session()
        self.base_url = base_url
        self.timeout  = timeout
        self._session_id: str | None = None

    def search_page(self, date_str: str, page: int, colecao: str = "acordaos") -> dict:
        if self._session_id is None:
            self._ensure_session()

        response = self._request(date_str, page, colecao)
        if response.status_code == 403:
            logger.warning("403 — sessão possivelmente expirada; recunhando e repetindo.")
            self._ensure_session(force=True)
            response = self._request(date_str, page, colecao)

        return self._resolve(response)

    def _ensure_session(self, force: bool = False) -> None:
        cookies, session_id = self.minter.force_refresh() if force else self.minter.get()
        self.session.cookies.clear()
        for c in cookies:
            self.session.cookies.set(
                c["name"], c["value"], domain=c.get("domain"), path=c.get("path", "/")
            )
        self._session_id = session_id

    def _request(self, date_str: str, page: int, colecao: str):
        params = {
            "sessionId":                 self._session_id,
            "latitude":                  0,
            "longitude":                 0,
            "texto":                     "",
            "verTodosPrecedentes":       "false",
            "pesquisaSomenteNasEmentas": "false",
            "colecao":                   colecao,
            "page":                      page,
            "size":                      PAGE_SIZE,
            "dataInicio":                date_str,
            "dataFim":                   date_str,
        }
        try:
            return self.session.get(
                self.base_url,
                params=params,
                headers=DEFAULT_HEADERS,
                timeout=self.timeout,
            )
        except requests.RequestException as exc:
            raise TransientApiError(str(exc)) from exc

    def _resolve(self, response) -> dict:
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
