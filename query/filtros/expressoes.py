"""Expressão obrigatória do filtro restrito → tsquery do Postgres.

Cada palavra vira suas variantes (singular/plural) e as palavras são ligadas
em sequência (`<->`), para casar a frase inteira. O índice é sobre texto sem
acento, então tudo aqui sai minúsculo, sem acento e só com `[a-z0-9]`.
"""
import re
import unicodedata

_CONECTIVOS = {"de", "da", "do", "das", "dos", "e", "em", "por", "para",
               "a", "o", "no", "na", "ao"}
_PARES = [("ais", "al"), ("res", "r"), ("zes", "z")]


def sem_acento(texto: str) -> str:
    t = unicodedata.normalize("NFD", texto.lower())
    return "".join(c for c in t if not unicodedata.combining(c))


def _especificas(p: str) -> set[str] | None:
    if p.endswith("ao"):
        return {p, p + "s", p[:-2] + "oes"}
    if p.endswith("oes"):
        return {p, p[:-3] + "ao", p[:-3] + "aos"}
    if p.endswith("eis"):
        return {p, p[:-3] + "el", p[:-1]}
    if p.endswith("el"):
        return {p, p[:-2] + "eis"}
    for a, b in _PARES:
        if p.endswith(a):
            return {p, p[:-len(a)] + b}
        if p.endswith(b):
            return {p, p[:-len(b)] + a}
    return None


def variantes(palavra: str) -> list[str]:
    if palavra in _CONECTIVOS or palavra.isdigit():
        return [palavra]
    vs = _especificas(palavra)
    if vs is None:
        vs = {palavra, palavra[:-1] if palavra.endswith("s") else palavra + "s"}
    return sorted(v for v in vs if v)


def tsquery_da_expressao(expressao: str) -> str | None:
    palavras = re.findall(r"[a-z0-9]+", sem_acento(expressao))
    if all(p in _CONECTIVOS for p in palavras):
        return None
    partes = []
    for p in palavras:
        vs = variantes(p)
        partes.append(f"({' | '.join(vs)})" if len(vs) > 1 else vs[0])
    return " <-> ".join(partes)
