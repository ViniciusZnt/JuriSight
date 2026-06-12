"""
Session Minter — autenticação do Web Scraper (Pipeline de Ingestão).

A API do portal protege as buscas com um desafio anti-bot baseado em cookies
(JSESSIONID + cookie de WAF + SESSION_ID_COOKIE_PUJ) que só são emitidos quando
o SPA é carregado num navegador real. Este módulo sobe um Chromium headless
(Playwright) uma única vez por sessão, carrega o portal e colhe esses cookies +
o `sessionId`. A coleta em si segue via `requests` reusando os cookies.

Os cookies expiram; renova automaticamente por TTL e sob demanda (ao receber 403).
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone

logger = logging.getLogger(__name__)

# Página de resultados qualquer: força o SPA a completar o fluxo de busca e a
# assentar os cookies de sessão/anti-bot.
WARMUP_URL = (
    "https://jurisprudencia.jt.jus.br/jurisprudencia-nacional/pesquisa/numero/"
    "0000039-30.2025.5.06.0001?abaSelecionada=acordaos"
)
SESSION_ID_COOKIE = "SESSION_ID_COOKIE_PUJ"
DEFAULT_TTL_SECONDS = 3000  # ~50 min; cookies renovados por TTL e sob 403.
DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36"
)


class SessionMintError(RuntimeError):
    pass


class SessionMinter:
    """Cunha e mantém cookies + sessionId do portal via Chromium headless."""

    def __init__(
        self,
        ttl_seconds: int = DEFAULT_TTL_SECONDS,
        user_agent: str = DEFAULT_USER_AGENT,
        headless: bool = True,
    ):
        self.ttl_seconds = ttl_seconds
        self.user_agent  = user_agent
        self.headless    = headless
        self._cookies: list[dict] | None = None
        self._session_id: str | None = None
        self._expires_at: datetime | None = None

    @property
    def is_expired(self) -> bool:
        return self._expires_at is None or datetime.now(tz=timezone.utc) >= self._expires_at

    def get(self) -> tuple[list[dict], str]:
        """Retorna (cookies, sessionId), renovando se expirado."""
        if self.is_expired:
            self._refresh()
        return self._cookies, self._session_id

    def force_refresh(self) -> tuple[list[dict], str]:
        """Força renovação imediata — chamar ao receber 403."""
        self._refresh()
        return self._cookies, self._session_id

    def _refresh(self) -> None:
        logger.info("Cunhando nova sessão do portal (Chromium headless)...")
        try:
            cookies = asyncio.run(self._fetch_cookies())
        except Exception as exc:
            raise SessionMintError(f"Falha ao cunhar sessão: {exc}") from exc

        session_id = next(
            (c["value"] for c in cookies if c["name"] == SESSION_ID_COOKIE), None
        )
        if not session_id:
            raise SessionMintError(f"Cookie {SESSION_ID_COOKIE} não encontrado.")

        self._cookies    = cookies
        self._session_id = session_id
        self._expires_at = datetime.now(tz=timezone.utc) + timedelta(seconds=self.ttl_seconds)
        logger.info("Sessão cunhada (sessionId=%s, %d cookies).", session_id, len(cookies))

    async def _fetch_cookies(self) -> list[dict]:
        from playwright.async_api import async_playwright

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=self.headless)
            try:
                ctx  = await browser.new_context(user_agent=self.user_agent)
                page = await ctx.new_page()
                await page.goto(WARMUP_URL, wait_until="networkidle")
                await page.wait_for_timeout(2500)
                return await ctx.cookies()
            finally:
                await browser.close()
