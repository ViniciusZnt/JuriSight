"""
Refresh automático do juristkn + sessionId
"""

import asyncio
from datetime import datetime
from playwright.async_api import async_playwright
import re

class JuristknRefreshError(Exception):
    """Erro customizado quando não consegue capturar o token."""
    pass

async def _fetch_fresh_tokens_async() -> dict:
    """Função interna assíncrona."""
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                       "(KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36"
        )
        page = await context.new_page()

        captured = {}

        def capture_api_request(req):
            if "/api/no-auth/pesquisa" in req.url:
                url = req.url
                # Extrai juristkn e sessionId com regex (mais robusto)
                juristkn_match = re.search(r'juristkn=([^&]+)', url)
                session_match = re.search(r'sessionId=([^&]+)', url)
                if juristkn_match:
                    captured["juristkn"] = juristkn_match.group(1)
                if session_match:
                    captured["sessionId"] = session_match.group(1)

        page.on("request", capture_api_request)

        await page.goto(
            "https://jurisprudencia.jt.jus.br/jurisprudencia-nacional/pesquisa",
            wait_until="load"
        )

        # Preenche filtros mínimos para disparar a API (sem depender de placeholder exato)
        await page.evaluate("""
            () => {
                const inputs = document.querySelectorAll('input[type="text"], input[placeholder]');
                for (const input of inputs) {
                    const ph = input.placeholder.toLowerCase();
                    if (ph.includes('início') || ph.includes('inicio')) input.value = '01/03/2025';
                    if (ph.includes('fim') || ph.includes('fim')) input.value = '31/03/2025';
                }
            }
        """)

        await page.click('button:has-text("PESQUISAR")')
        await page.wait_for_timeout(7000)  # espera a primeira chamada da API

        await browser.close()

        if "juristkn" not in captured or "sessionId" not in captured:
            raise JuristknRefreshError(
                "Não foi possível capturar juristkn/sessionId. "
                "Rode com headless=False para debug visual."
            )

        return {
            "juristkn": captured["juristkn"],
            "sessionId": captured["sessionId"],
            "captured_at": datetime.now().isoformat(),
            "source": "playwright_auto_refresh"
        }


def get_fresh_juristkn() -> dict:
    """
    FUNÇÃO PRINCIPAL
    """
    try:
        return asyncio.run(_fetch_fresh_tokens_async())
    except Exception as e:
        raise JuristknRefreshError(f"Erro ao refresh juristkn: {e}") from e