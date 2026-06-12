"""
Classificador de provimento (RFC §RN05 / Decisão 5).

Componente "Provimento Clf [Regex]" do diagrama C4. A partir do texto do
dispositivo do acórdão, classifica a decisão em APROVADO / NEGADO. Para
súmulas e OJs, que não julgam um pedido, o valor é sempre NAO_APLICAVEL.

⚠️ PROVISÓRIO — as regras abaixo são um primeiro rascunho a partir dos exemplos
do RN05. O conjunto definitivo de padrões (e a fonte exata do dispositivo, já
que a API não o entrega isolado) será fechado na conversa específica deste
componente. A interface (`classify`) deve permanecer estável.
"""
from __future__ import annotations

import re

from scraper.schema import Provimento, TipoDocumento

# Padrões aplicados sobre o dispositivo, em ordem de prioridade.
# NEGADO é checado antes de APROVADO porque "nego provimento" contém "provimento".
_NEGADO_PATTERNS = [
    r"\bneg\w*\s+provimento\b",   # "nego/negar/negado provimento"
    r"\bimprovido\b",
    r"\bimproced\w*\b",           # improcedente / improcedência
    r"\bdenega\w*\b",             # denegado / denegação
    r"\bnão\s+provido\b",
]

_APROVADO_PATTERNS = [
    r"\bdou\s+provimento\b",
    r"\bdar\s+provimento\b",
    r"\bprovido\b",
    r"\bdefer\w*\b",              # deferido / deferimento
    r"\bproced\w*\b",            # procedente / procedência
]

_NEGADO_RE   = re.compile("|".join(_NEGADO_PATTERNS), re.IGNORECASE)
_APROVADO_RE = re.compile("|".join(_APROVADO_PATTERNS), re.IGNORECASE)


def classify(dispositivo: str, tipo_documento: TipoDocumento) -> Provimento:
    """Classifica o provimento de um documento.

    Args:
        dispositivo: texto do dispositivo/acórdão (onde consta a decisão).
        tipo_documento: tipo do documento; apenas ACORDAO é classificável.

    Returns:
        Provimento.APROVADO / NEGADO / NAO_APLICAVEL.
    """
    if tipo_documento is not TipoDocumento.ACORDAO:
        return Provimento.NAO_APLICAVEL

    if not dispositivo:
        return Provimento.NAO_APLICAVEL

    if _NEGADO_RE.search(dispositivo):
        return Provimento.NEGADO
    if _APROVADO_RE.search(dispositivo):
        return Provimento.APROVADO

    # Sem padrão reconhecido — não inventa um posicionamento (RNF01).
    return Provimento.NAO_APLICAVEL
