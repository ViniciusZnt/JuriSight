"""
Refresh automático do juristkn + sessionId
"""

import asyncio
from datetime import datetime
from playwright.async_api import async_playwright
import re

class JuristknRefreshError(Exception):
    pass

async def fetch_fresh_tokens_async() -> dict:
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True, timeout=2000)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                       "(KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36"
        )
        page = await context.new_page()

        await page.goto(
            "https://jurisprudencia.jt.jus.br/jurisprudencia-nacional/pesquisa",
            wait_until="load"
        )

        # espera a request da API acontecer
        async with page.expect_request(lambda request: "/api/no-auth/pesquisa" in request.url) as req_info:
            # Refresh para fazer requisição
            await page.reload()
            

        request = await req_info.value
        url = request.url

        juristkn_match = re.search(r'juristkn=([^&]+)', url)
        session_match = re.search(r'sessionId=([^&]+)', url)

        await browser.close()

        if not juristkn_match or not session_match:
            raise JuristknRefreshError(
                "Não foi possível capturar juristkn/sessionId. "
                "Rode com headless=False para debug visual."
            )

        return {
            "juristkn": juristkn_match.group(1),
            "sessionId": session_match.group(1),
            "captured_at": datetime.now().isoformat(),
            "source": "playwright_auto_refresh"
        }


def get_fresh_juristkn() -> dict:
    """
    Main Function
    """
    try:
        return asyncio.run(fetch_fresh_tokens_async())
    except Exception as e:
        raise JuristknRefreshError(f"Erro ao refresh juristkn: {e}") from e
    

def main():
    dict = get_fresh_juristkn()
    print(dict)

if __name__ == "__main__":
    main()