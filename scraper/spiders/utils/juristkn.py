import asyncio
import re
from datetime import datetime, timedelta, timezone
from playwright.async_api import async_playwright
 
# Tempo do token extraido empiricamente
TOKEN_TTL_SECONDS = 3600
 
 
class JuristknRefreshError(Exception):
    pass
 
 
class TokenManager:
    """
    Gerencia juristkn + sessionId do portal TST.
 
    Como o cookie não possui expires_at, o TTL é fixo via TOKEN_TTL_SECONDS.
    Renova automaticamente quando o token expira.
    """
 
    def __init__(self, ttl_seconds: int = TOKEN_TTL_SECONDS):
        self._ttl_seconds = ttl_seconds
        self._juristkn: str | None = None
        self._session_id: str | None = None
        self._expires_at: datetime | None = None
 
    @property
    def is_expired(self) -> bool:
        if self._expires_at is None:
            return True
        return datetime.now(tz=timezone.utc) >= self._expires_at
 
    def get_tokens(self) -> tuple[str, str]:
        """Retorna (juristkn, sessionId), renovando se necessário."""
        if self.is_expired:
            self._refresh()
        return self._juristkn, self._session_id
 
    def force_refresh(self) -> tuple[str, str]:
        """Força renovação imediata — chamar ao receber 403."""
        self._refresh()
        return self._juristkn, self._session_id
 
    def _refresh(self) -> None:
        try:
            asyncio.run(self._fetch_async())
        except Exception as e:
            raise JuristknRefreshError(f"Erro ao renovar token: {e}") from e
 
    async def _fetch_async(self) -> None:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/134.0.0.0 Safari/537.36"
                )
            )
            page = await context.new_page()
 
            await page.goto(
                "https://jurisprudencia.jt.jus.br/jurisprudencia-nacional/pesquisa",
                wait_until="load",
            )
 
            async with page.expect_request(
                lambda r: "/api/no-auth/pesquisa" in r.url
            ) as req_info:
                await page.reload()
 
            url = (await req_info.value).url
            await browser.close()
 
        juristkn_match = re.search(r"juristkn=([^&]+)", url)
        session_match  = re.search(r"sessionId=([^&]+)", url)
 
        if not juristkn_match or not session_match:
            raise JuristknRefreshError(
                "juristkn/sessionId não encontrados na URL capturada."
            )
 
        self._juristkn   = juristkn_match.group(1)
        self._session_id = session_match.group(1)
        self._expires_at = datetime.now(tz=timezone.utc) + timedelta(seconds=self._ttl_seconds)
 
 
# Singleton
token_manager = TokenManager()