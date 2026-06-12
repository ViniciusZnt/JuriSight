"""
Classificador de provimento (RFC §RN05 / Decisão 5).

Componente "Provimento Clf [Regex]" do diagrama C4. A partir do dispositivo do
acórdão, classifica a decisão. Para súmulas e OJs (que não julgam um pedido) o
valor é sempre NAO_APLICAVEL.

Estratégia em camadas (ver discussão do componente):
  1. normaliza o texto (minúsculas, sem acento, hífen→espaço);
  2. ancora no dispositivo (trecho após "ante o exposto", "isto posto", ...);
  3. casa vocabulário de resultado por família (recurso/embargos/MS/mérito),
     na ordem NEGADO → PARCIAL → APROVADO.

O regex cobre a maioria de alta confiança; o restante (NAO_APLICAVEL em
acórdãos) deve cair no fallback de LLM previsto na arquitetura (§5.5).
"""
from __future__ import annotations

import re
import unicodedata

from scraper.schema import Provimento, TipoDocumento

# Enquanto PARCIAL não for um valor próprio no schema, mapeia para cá.
# Trocar para um Provimento.PARCIAL dedicado é a recomendação (ver conversa).
_PARCIAL_MAPS_TO = Provimento.APROVADO


def _normalize(text: str) -> str:
    """Minúsculas, sem acento, com hífen/pronome enclítico virando espaço."""
    text = text.lower()
    text = unicodedata.normalize("NFKD", text)
    text = "".join(c for c in text if not unicodedata.combining(c))
    text = re.sub(r"[-–—]", " ", text)       # negar-lhe -> negar lhe
    return re.sub(r"\s+", " ", text).strip()


# Marcadores que abrem o dispositivo — classificamos só o que vem depois deles.
_DISPOSITIVO_MARKERS = (
    "ante o exposto", "diante do exposto", "isto posto", "isto exposto",
    "posto isso", "pelo exposto", "em face do exposto", "do exposto, decido",
    "do exposto, decide",
)


def _dispositivo(text: str) -> str:
    """Recorta o trecho a partir do último marcador de dispositivo (se houver)."""
    cut = max((text.rfind(m) for m in _DISPOSITIVO_MARKERS), default=-1)
    return text[cut:] if cut >= 0 else text


# Ordem importa: NEGADO antes de APROVADO ("negar provimento" contém "provimento");
# PARCIAL antes de APROVADO ("provimento parcial" é um subconjunto).
_NEGADO_PATTERNS = (
    r"\bneg\w*\s+(?:lhes?\s+)?provimento\b",         # nego/negar(-lhe) provimento
    r"\bnao\s+(?:[oa]s?\s+|lhes?\s+)?prov\w*",        # não (o) prover
    r"\bimprov\w*",                                   # improvido
    r"\bimproced\w*",                                 # improcedente
    r"\bdeneg\w*",                                    # denego/denegar a segurança
    r"\brejeit\w*",                                   # rejeitar/rejeito os embargos
    r"\bnao\s+conhec\w*",                             # não conhecer (inadmitido)
    r"\bnao\s+acolh\w*",                             # não acolher
)

_PARCIAL_PATTERNS = (
    r"\bprovimento\s+parcial",                        # dar/dou provimento parcial
    r"\bparcial\w*\s+provimento",
    r"\bconced\w*\s+parcial",                         # concedo parcialmente a segurança
    r"\bproced\w*\s+em\s+parte",                      # procedente em parte
    r"\bparcial\w*\s+proced\w*",
)

_APROVADO_PATTERNS = (
    r"\b(?:dar|dou|deu|dao|dado|dada)\s+(?:lhes?\s+)?provimento\b",
    r"\bprovido\b",
    r"\bdefer\w*",                                    # deferido
    r"\bacolh\w*",                                    # acolher embargos
    r"\bproced\w*nte\b",                             # procedente
    r"\bproced\w*ncia\b",                            # procedência
    r"\bconced\w*\s+(?:a\s+)?(?:seguranca|ordem)",    # conceder a segurança/ordem
)

_NEGADO_RE   = re.compile("|".join(_NEGADO_PATTERNS))
_PARCIAL_RE  = re.compile("|".join(_PARCIAL_PATTERNS))
_APROVADO_RE = re.compile("|".join(_APROVADO_PATTERNS))


def _classify_outcome(dispositivo: str) -> str:
    """Resultado bruto: NEGADO | PARCIAL | APROVADO | NAO_APLICAVEL."""
    texto = _dispositivo(_normalize(dispositivo))
    if _NEGADO_RE.search(texto):
        return "NEGADO"
    if _PARCIAL_RE.search(texto):
        return "PARCIAL"
    if _APROVADO_RE.search(texto):
        return "APROVADO"
    return "NAO_APLICAVEL"


def classify(dispositivo: str, tipo_documento: TipoDocumento) -> Provimento:
    """Classifica o provimento de um documento (apenas ACORDAO é classificável)."""
    if tipo_documento is not TipoDocumento.ACORDAO or not dispositivo:
        return Provimento.NAO_APLICAVEL

    outcome = _classify_outcome(dispositivo)
    if outcome == "NEGADO":
        return Provimento.NEGADO
    if outcome == "APROVADO":
        return Provimento.APROVADO
    if outcome == "PARCIAL":
        return _PARCIAL_MAPS_TO
    return Provimento.NAO_APLICAVEL
