"""Expressão obrigatória do filtro restrito → tsquery do Postgres.

Cada palavra vira suas variantes (singular/plural) e as palavras são ligadas
em sequência (`<->`), para casar a frase inteira. O índice é sobre texto sem
acento, então tudo aqui sai minúsculo, sem acento e só com `[a-z0-9]`.
"""
import re
import unicodedata

_CONECTIVOS = {"de", "da", "do", "das", "dos", "e", "em", "por", "para",
               "a", "o", "no", "na", "ao"}
_PARES = [("ais", "al"), ("eis", "el"), ("oes", "ao"), ("res", "r"), ("zes", "z")]


def sem_acento(texto: str) -> str:
    t = unicodedata.normalize("NFD", texto.lower())
    return "".join(c for c in t if not unicodedata.combining(c))


def variantes(palavra: str) -> list[str]:
    if palavra in _CONECTIVOS:
        return [palavra]
    for a, b in _PARES:
        if palavra.endswith(a):
            return sorted({palavra, palavra[:-len(a)] + b})
        if palavra.endswith(b):
            return sorted({palavra, palavra[:-len(b)] + a})
    alt = palavra[:-1] if palavra.endswith("s") else palavra + "s"
    return sorted({palavra, alt} - {""})


def tsquery_da_expressao(expressao: str) -> str | None:
    palavras = re.findall(r"[a-z0-9]+", sem_acento(expressao))
    if all(p in _CONECTIVOS for p in palavras):
        return None
    partes = []
    for p in palavras:
        vs = variantes(p)
        partes.append(f"({' | '.join(vs)})" if len(vs) > 1 else vs[0])
    return " <-> ".join(partes)
