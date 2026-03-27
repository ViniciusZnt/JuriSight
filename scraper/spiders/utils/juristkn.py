import asyncio
import re
from datetime import datetime, timezone
from playwright.async_api import async_playwright


class JuristknRefreshError(Exception):
    pass


class TokenManager:
    """
    Gerencia o ciclo de vida do juristkn + sessionId.
    Renova proativamente 5 minutos antes de expirar.
    """
    RENEW_BEFORE_EXPIRY_SECONDS = 300  # renova 5 min antes

    def __init__(self):
        self._tokens: dict | None = None
        self._expires_at: datetime | None = None

    @property
    def is_expired(self) -> bool:
        if self._expires_at is None:
            return True
        now = datetime.now(tz=timezone.utc)
        remaining = (self._expires_at - now).total_seconds()
        return remaining < self.RENEW_BEFORE_EXPIRY_SECONDS

    def get_tokens(self) -> dict:
        """Retorna tokens válidos, renovando se necessário."""
        if self.is_expired:
            self._tokens = self._refresh()
        return self._tokens

    def force_refresh(self) -> dict:
        """Força renovação imediata — chamado ao receber 403."""
        self._tokens = self._refresh()
        return self._tokens

    def _refresh(self) -> dict:
        try:
            return asyncio.run(self._fetch_async())
        except Exception as e:
            raise JuristknRefreshError(f"Erro ao refresh juristkn: {e}") from e

    async def _fetch_async(self) -> dict:
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

            request = await req_info.value
            url = request.url

            # Extrai token e sessionId da URL
            juristkn_match = re.search(r"juristkn=([^&]+)", url)
            session_match = re.search(r"sessionId=([^&]+)", url)

            if not juristkn_match or not session_match:
                await browser.close()
                raise JuristknRefreshError(
                    "Não foi possível capturar juristkn/sessionId."
                )

            # Extrai expiração do cookie de sessão
            cookies = await context.cookies()
            session_cookie = next(
                (c for c in cookies if c["name"] == "SESSION_ID_COOKIE"), None
            )

            await browser.close()

            # Converte unix timestamp para datetime
            if session_cookie and session_cookie.get("expires", -1) > 0:
                self._expires_at = datetime.fromtimestamp(
                    session_cookie["expires"], tz=timezone.utc
                )
            else:
                # Fallback: 30 minutos
                from datetime import timedelta
                self._expires_at = datetime.now(tz=timezone.utc) + timedelta(minutes=30)

            remaining = (self._expires_at - datetime.now(tz=timezone.utc)).total_seconds()

            return {
                "juristkn":    juristkn_match.group(1),
                "sessionId":   session_match.group(1),
                "captured_at": datetime.now().isoformat(),
                "expires_at":  self._expires_at.isoformat(),
                "ttl_seconds": int(remaining),
            }


# Singleton
token_manager = TokenManager()