"""
HTML Extractor (componente C4 — Pipeline de Ingestão).

Extrai as seções estruturadas do HTML do documento usando BeautifulSoup.

Os templates do portal variam o caixa dos títulos por tribunal (`EMENTA` vs
`Ementa`, `ACÓRDÃO` vs `Acórdão`) e usam seções de título livre (`Conhecimento.`,
`Mérito.`, `Do pedido de...`). Por isso:
  - os títulos são normalizados (minúsculas, sem acento, sem pontuação final)
    antes de casar com as seções nomeadas;
  - além das seções nomeadas, monta-se o `texto_completo` concatenando TODO o
    conteúdo — fonte robusta para a classificação de provimento (que ancora no
    dispositivo onde quer que ele esteja).
"""
import re
import unicodedata

from bs4 import BeautifulSoup


def _remove_base64(html: str) -> str:
    """Remove imagens base64 para não poluir o texto extraído."""
    return re.sub(r'src="data:image/[^"]*"', 'src=""', html)


def html_to_text(html: str) -> str:
    """Converte HTML para texto puro."""
    if not html:
        return ""
    soup = BeautifulSoup(_remove_base64(html), "html.parser")
    return soup.get_text(separator=" ", strip=True)


def _normalize_title(titulo: str) -> str:
    """minúsculas, sem acento, sem pontuação/espaço final (Ementa/EMENTA/Conclusão. → ementa...)."""
    t = unicodedata.normalize("NFKD", titulo.lower())
    t = "".join(c for c in t if not unicodedata.combining(c))
    return t.strip(" .:;-").strip()


# Seções nomeadas de interesse — chave = título normalizado.
_SECTION_MAP = {
    "cabecalho":     "cabecalho",
    "ementa":        "ementa",
    "relatorio":     "relatorio",
    "fundamentacao": "fundamentacao",
    "votos":         "votos",
}
_SECTION_FIELDS = ("cabecalho", "ementa", "relatorio", "fundamentacao", "votos")


def extract_ementa(ementa_html: str) -> str:
    """Extrai o texto puro do campo textoEmenta (HTML simples de parágrafos)."""
    return html_to_text(ementa_html)


def extract_sections(acordao_html: str) -> dict:
    """Extrai as seções nomeadas do textoAcordao + o `texto_completo`.

    O HTML segue o padrão `id_XXXXX_titulo` (título da seção) +
    `id_XXXXX_conteudo` (conteúdo). Seções ausentes ficam como "".
    """
    result = {field: "" for field in _SECTION_FIELDS}
    result["texto_completo"] = ""

    if not acordao_html:
        return result

    soup = BeautifulSoup(_remove_base64(acordao_html), "html.parser")

    # Seções nomeadas (casamento por título normalizado).
    titulo_divs = soup.find_all(
        "div",
        id=lambda x: x and x.endswith("_titulo") and "completo" not in x,
    )
    for titulo_div in titulo_divs:
        field = _SECTION_MAP.get(_normalize_title(titulo_div.get_text(strip=True)))
        if not field:
            continue
        content_div = soup.find("div", id=titulo_div["id"].replace("_titulo", "_conteudo"))
        if not content_div:
            continue
        text = content_div.get_text(separator=" ", strip=True)
        if not text:
            continue
        # Acumula se o mesmo campo aparecer mais de uma vez.
        result[field] = f"{result[field]} {text}".strip() if result[field] else text

    # Texto completo: todo o conteúdo, na ordem do documento — independe de título.
    partes = [
        text
        for cdiv in soup.find_all("div", id=lambda x: x and x.endswith("_conteudo"))
        if (text := cdiv.get_text(separator=" ", strip=True))
    ]
    result["texto_completo"] = " ".join(partes)

    return result


def parse_document(ementa_html: str, acordao_html: str) -> dict:
    """Processa os dois campos da API (textoEmenta + textoAcordao).

    Returns:
        dict com `acordao_section` (seções + texto_completo) e `ementa`
        (preferindo o textoEmenta dedicado, com fallback à seção ementa).
    """
    sections = extract_sections(acordao_html)
    return {
        "acordao_section": sections,
        "ementa": extract_ementa(ementa_html) or sections.get("ementa", ""),
    }
