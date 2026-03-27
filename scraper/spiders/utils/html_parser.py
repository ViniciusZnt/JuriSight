# scraper/spiders/utils/html_parser.py

import re
from html.parser import HTMLParser
from bs4 import BeautifulSoup


def _remove_base64(html: str) -> str:
    """Remove imagens base64 que chegam a centenas de KB por documento."""
    return re.sub(r'src="data:image/[^"]*"', 'src=""', html)


class _TextExtractor(HTMLParser):
    """Parser simples que coleta apenas o texto entre as tags."""
    def __init__(self):
        super().__init__()
        self._parts = []

    def handle_data(self, data):
        stripped = data.strip()
        if stripped:
            self._parts.append(stripped)

    def get_text(self) -> str:
        return " ".join(self._parts)


def html_to_text(html: str) -> str:
    """Converte HTML para texto puro."""
    if not html:
        return ""
    html = _remove_base64(html)
    parser = _TextExtractor()
    parser.feed(html)
    return parser.get_text()


# Mapeamento dos títulos das seções para nomes de campo
_SECTION_MAP = {
    "Identificação":  "cabecalho",
    "EMENTA":         "ementa_secao",   # ementa extraída do textoAcordao
    "ACÓRDÃO":        "dispositivo",
    "RELATÓRIO":      "relatorio",
    "FUNDAMENTAÇÃO":  "fundamentacao",
    "Fundamentação":  "fundamentacao",  # alguns TRTs usam capitalização diferente
    "VOTOS":          "votos",
    "Votos":          "votos",
}


def extract_sections(html: str) -> dict:
    """
    Extrai as seções do textoAcordao separadamente.

    O HTML do acórdão tem uma estrutura de divs com IDs no padrão:
        id_XXXXXXX_titulo    → título da seção (ex: "EMENTA")
        id_XXXXXXX_conteudo  → conteúdo da seção

    Retorna um dicionário com as seções encontradas.
    Seções não encontradas ficam como string vazia.
    """
    result = {field: "" for field in _SECTION_MAP.values()}

    if not html:
        return result

    html = _remove_base64(html)

    try:
        soup = BeautifulSoup(html, "html.parser")
    except Exception:
        return result

    # Busca todos os divs de título (excluindo os "_titulo_completo")
    titulo_divs = soup.find_all(
        "div",
        id=lambda x: x and x.endswith("_titulo") and "completo" not in x
    )

    for titulo_div in titulo_divs:
        titulo_texto = titulo_div.get_text(strip=True)

        if titulo_texto not in _SECTION_MAP:
            continue

        field_name = _SECTION_MAP[titulo_texto]

        # O conteúdo tem o mesmo prefixo numérico mas termina em "_conteudo"
        content_id = titulo_div["id"].replace("_titulo", "_conteudo")
        content_div = soup.find("div", id=content_id)

        if content_div:
            text = content_div.get_text(separator=" ", strip=True)
            # Acumula se o mesmo campo aparecer mais de uma vez
            if result[field_name]:
                result[field_name] += " " + text
            else:
                result[field_name] = text

    return result