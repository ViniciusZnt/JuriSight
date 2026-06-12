"""
HTML Extractor (componente C4 — Pipeline de Ingestão).

Extrai as seções estruturadas do HTML do documento (ementa, relatório,
fundamentação, acórdão/dispositivo, votos) usando BeautifulSoup. O texto do
acórdão é a base para a classificação de provimento.
"""
import re
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


# Mapeamento dos títulos das seções para nomes de campo
_SECTION_MAP = {
    "CABEÇALHO": "cabecalho",
    "EMENTA":        "ementa",
    "RELATÓRIO":     "relatorio",
    "FUNDAMENTAÇÃO": "fundamentacao",
    "ACÓRDÃO":       "acordao",
    "VOTOS":         "votos",
}


def extract_ementa(ementa_html: str) -> str:
    """
    Extrai o texto puro do campo textoEmenta.

    textoEmenta é um HTML simples — apenas parágrafos <p> com o texto
    da ementa, sem a estrutura de id_XXXXX_titulo/conteudo.
    Não passa por extract_sections.
    """
    return html_to_text(ementa_html)


def extract_sections(acordao_html: str) -> dict:
    """
    Extrai as seções do campo textoAcordao separadamente.

    O HTML segue o padrão:
        id_XXXXXXX_titulo    → título da seção (ex: "EMENTA", "RELATÓRIO")
        id_XXXXXXX_conteudo  → conteúdo da seção

    Retorna dict com as seções encontradas. Seções ausentes ficam como "".
    """
    result = {field: "" for field in _SECTION_MAP.values()}

    if not acordao_html:
        return result

    soup = BeautifulSoup(_remove_base64(acordao_html), "html.parser")

    # Busca divs de título — exclui os "_titulo_completo"
    titulo_divs = soup.find_all(
        "div",
        id=lambda x: x and x.endswith("_titulo") and "completo" not in x,
    )

    for titulo_div in titulo_divs:
        titulo_texto = titulo_div.get_text(strip=True)

        field_name = _SECTION_MAP.get(titulo_texto)
        if not field_name:
            ##Talvez nessa parte criar logica de logger
            continue

        content_id = titulo_div["id"].replace("_titulo", "_conteudo")
        content_div = soup.find("div", id=content_id)

        if not content_div:
            ##Talvez nessa parte criar logica de logger
            continue

        text = content_div.get_text(separator=" ", strip=True)
        if not text:
            ##Talvez nessa parte criar logica de logger
            continue

        # Acumula se o mesmo campo aparecer mais de uma vez (ex: dois blocos de VOTOS)
        if result[field_name]:
            result[field_name] += " " + text
        else:
            result[field_name] = text

    return result


def parse_document(ementa_html: str, acordao_html: str) -> dict:
    """
    Ponto de entrada principal — processa os dois campos separados da API.

    Args:
        ementa_html:  campo textoEmenta da resposta da API
        acordao_html: campo textoAcordao da resposta da API

    Returns:
        dict com ementa (do textoEmenta) + seções do textoAcordao
    """
    sections = {}
    sections["acordao_section"] = extract_sections(acordao_html)
    sections["ementa"] = extract_ementa(ementa_html) or sections.get("ementa", "")

    return sections