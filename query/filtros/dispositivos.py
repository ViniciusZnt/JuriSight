"""Códigos de dispositivo do acervo (`referencia_legislativa`).

Um dispositivo é um código com uma âncora (art, sumula, oj, convencao, lei)
precedida, opcionalmente, de unidades de detalhe: `prgf_<n>`, `prgf_unico`,
`caput`, incisos romanos e alíneas. Ex.: `b_ii_art_10_adct`.
"""
import re
import unicodedata

ANCORAS = ("art", "sumula", "oj", "convencao", "lei")
SIGLAS = {"clt": "CLT", "cf": "CF", "adct": "ADCT", "cpc": "CPC",
          "ccb": "CC", "cp": "CP", "cdc": "CDC"}
_ROMANO = re.compile(r"^(?=.)(xc|xl|l?x{0,3})(ix|iv|v?i{0,3})$")  # i a lxxxix
_CONECTIVOS = {"de", "da", "do", "das", "dos", "e"}
_ORGAO = re.compile(r"^(tst|stf|stj|tse|oit|sdc|sdi\d|trt\d{1,2})$")


def _indice_ancora(tokens: list[str]) -> int | None:
    for i, t in enumerate(tokens):
        if t in ANCORAS:
            return i
    return None


def _unidades(prefixo: list[str]) -> list[list[str]]:
    """Separa o prefixo em unidades de detalhe (`prgf_<n>` vale por duas fichas)."""
    unidades, k = [], 0
    while k < len(prefixo):
        tam = 2 if prefixo[k] == "prgf" and k + 1 < len(prefixo) else 1
        unidades.append(prefixo[k:k + tam])
        k += tam
    return unidades


def niveis(codigo: str) -> list[str]:
    """O próprio código e todos os níveis acima, do mais específico ao artigo,
    súmula, OJ, convenção ou lei. Vazia se não for dispositivo."""
    tokens = codigo.split("_")
    i = _indice_ancora(tokens)
    if i is None:
        return []
    unidades, resto = _unidades(tokens[:i]), tokens[i:]
    return ["_".join(sum(unidades[k:], []) + resto) for k in range(len(unidades) + 1)]


def eh_dispositivo(codigo: str) -> bool:
    return bool(niveis(codigo))


def _numero(n: str) -> str:
    return f"{int(n):,}".replace(",", ".")


def _rotulo_unidade(u: list[str]) -> str:
    if u[0] == "prgf":
        return "parágrafo único" if u[1] == "unico" else f"§ {u[1]}º"
    if _ROMANO.match(u[0]):
        return u[0].upper()
    return u[0]


def _rotulo_lei(tokens: list[str]) -> str:
    return f"Lei {_numero(tokens[1])}/{tokens[2]}"


def rotulo(codigo: str) -> str:
    """Texto legível do código. Se não for dispositivo, devolve o próprio código."""
    tokens = codigo.split("_")
    i = _indice_ancora(tokens)
    if i is None:
        return codigo
    try:
        detalhes = [_rotulo_unidade(u) for u in reversed(_unidades(tokens[:i]))]
        ancora, resto = tokens[i], tokens[i + 1:]
        if ancora == "art":
            if resto[1] == "lei":
                lei = _rotulo_lei(resto[1:])
            else:
                lei = SIGLAS.get("_".join(resto[1:])) or " ".join(resto[1:]).upper()
            principal = f"{lei} art. {resto[0]}"
        elif ancora == "sumula":
            principal = f"Súmula {resto[0]} do {resto[1].upper()}"
        elif ancora == "oj":
            orgao = f"do {resto[-1].upper()}"
            if len(resto) > 2:
                orgao = f"da {re.sub(r'^sdi(\d)$', r'SDI-\1', resto[1])} {orgao}"
            principal = f"OJ {resto[0]} {orgao}"
        elif ancora == "convencao":
            principal = f"Convenção {resto[0]} da {resto[1].upper()}"
        else:
            principal = _rotulo_lei(tokens[i:])
    except (IndexError, ValueError):
        return codigo
    return ", ".join([principal] + detalhes)


def tokens_da_busca(texto: str) -> list[str]:
    """Fichas normalizadas do texto: sem acento, `art.`/`arts.`->art, `§`->prgf, sem `nº`,
    `CF/88`->cf, `SBDI-1`->sdi1, sem conectivos (de, da, do, das, dos, e)."""
    t = unicodedata.normalize("NFD", texto.lower())
    t = "".join(c for c in t if not unicodedata.combining(c))
    t = re.sub(r"\bn\s*[º°]?\.?\s*(?=\d)", " ", t)  # "nº 85", "n. 85"
    t = re.sub(r"[ºª°]", "", t).replace("§", " prgf ")
    t = re.sub(r"(?<=\d)\.(?=\d)", "", t)
    t = re.sub(r"\bsb?di\s*-?\s*(\d)", r"sdi\1", t)
    t = re.sub(r"\bcf\s*/\s*(19)?88\b", "cf", t)
    trocas = {"artigo": "art", "arts": "art", "paragrafo": "prgf", "cc": "ccb"}
    return [trocas.get(f, f) for f in re.findall(r"[a-z0-9]+", t) if f not in _CONECTIVOS]


def codigo_de_texto(texto: str) -> str | None:
    """Converte uma citação (`CLT art. 791, § 2º`) em código. Conservador:
    sem âncora ou sem lei/órgão, devolve None."""
    fichas = [f for f in tokens_da_busca(texto) if f != "item"]
    lei = []
    for j in range(len(fichas) - 2):
        if fichas[j] == "lei" and fichas[j + 1].isdigit() and fichas[j + 2].isdigit():
            # o acervo usa o ano com 2 dígitos: "Lei 13.467/2017" -> lei_13467_17
            lei, fichas = ["lei", fichas[j + 1], fichas[j + 2][-2:]], fichas[:j] + fichas[j + 3:]
            break
    i = next((k for k, f in enumerate(fichas[:-1])
              if f in ("art", "sumula", "oj") and fichas[k + 1].isdigit()), None)
    if i is None:
        return "_".join(lei) if lei and not fichas else None
    ancora, numero = fichas[i], fichas[i + 1]
    unidades, outros = [], fichas[:i]
    depois, k = fichas[i + 2:], 0
    while k < len(depois):
        f = depois[k]
        if f == "prgf":
            if k + 1 == len(depois) or not (depois[k + 1].isdigit() or depois[k + 1] == "unico"):
                return None
            unidades.append(f"prgf_{depois[k + 1]}")
            k += 1
        elif f == "caput" or _ROMANO.match(f) or (len(f) == 1 and f.isalpha()):
            unidades.append(f)
        else:
            outros.append(f)
        k += 1
    if ancora == "art":
        destino = lei or [f for f in outros if f in SIGLAS][:1]
        sobras = [f for f in outros if f not in destino]
    else:
        destino, sobras = outros, [f for f in outros if not _ORGAO.match(f)]
    if not destino or sobras:
        return None
    return "_".join(unidades[::-1] + [ancora, numero] + destino)
