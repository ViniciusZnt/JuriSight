"""Expressão obrigatória do filtro restrito → tsquery do Postgres.

Cada palavra vira suas variantes (singular/plural) e as palavras são ligadas
em sequência (`<->`), para casar a frase inteira. O índice é sobre texto sem
acento, então tudo aqui sai minúsculo, sem acento e só com `[a-z0-9]`.
"""
import re
import unicodedata

# Conectivos ficam fora das variantes, menos os que têm plural: "do empregador" casa "dos empregadores".
_PLURAL_CONECTIVO = {"do": "dos", "da": "das", "no": "nos", "na": "nas", "ao": "aos", "o": "os", "a": "as"}
_PLURAL_CONECTIVO |= {p: s for s, p in _PLURAL_CONECTIVO.items()}
_CONECTIVOS = {"de", "e", "em", "por", "para", *_PLURAL_CONECTIVO}
_PARES = [("ais", "al"), ("ois", "ol"), ("res", "r"), ("zes", "z"), ("ns", "m")]


def sem_acento(texto: str) -> str:
    """Minúsculo e sem acento (NFD). Também usado por dispositivos.py; o BM25 usa NFKD, de propósito à parte."""
    t = unicodedata.normalize("NFD", texto.lower())
    return "".join(c for c in t if not unicodedata.combining(c))


def _especificas(p: str) -> set[str] | None:
    if p.endswith("ao"):
        return {p, p + "s", p[:-2] + "oes", p[:-2] + "aes"}
    if p.endswith(("oes", "aes")):
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
    if p.endswith("is"):
        return {p, p[:-2] + "il", p[:-1]}     # civis -> civil; taxis -> taxi
    if p.endswith("il"):
        return {p, p[:-2] + "is"}
    if p.endswith("eses"):
        return {p, p[:-2], p[:-1]}            # meses -> mes; teses -> tese
    if p.endswith("es"):
        return {p, p[:-1], p + "es"}          # mes -> meses; partes -> parte
    return None


def variantes(palavra: str) -> list[str]:
    if palavra in _PLURAL_CONECTIVO:
        return sorted({palavra, _PLURAL_CONECTIVO[palavra]})
    if palavra in _CONECTIVOS or palavra.isdigit():
        return [palavra]
    vs = _especificas(palavra)
    if vs is None:
        vs = {palavra, palavra[:-1] if palavra.endswith("s") else palavra + "s"}
    return sorted(v for v in vs if v)


def tsquery_da_expressao(expressao: str) -> str | None:
    # Como no texto indexado: só [a-z0-9] (hífen separa palavras) e sem o ponto entre dígitos ("13.467" -> 13467).
    palavras = re.findall(r"[a-z0-9]+", re.sub(r"(?<=\d)\.(?=\d)", "", sem_acento(expressao)))
    if all(p in _CONECTIVOS for p in palavras):
        return None
    partes = []
    for p in palavras:
        vs = variantes(p)
        partes.append(f"({' | '.join(vs)})" if len(vs) > 1 else vs[0])
    return " <-> ".join(partes)
