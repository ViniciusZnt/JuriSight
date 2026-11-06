"""
Trecho da ementa para o reranker: início + "Tese de julgamento".

As ementas no formato "I. CASO EM EXAME ... Tese de julgamento: ..." trazem a tese
perto do fim, depois do corte de caracteres do reranker. Hoje só o sistema S7 do
benchmark usa este trecho; a produção segue com o corte simples até a medição dizer
se vale a troca.
"""
from __future__ import annotations

import re

_INICIO_TESE = re.compile(r"teses?\s+de\s+julgamento", re.IGNORECASE)
_FIM_TESE = re.compile(
    r"(dispositivos?|legisla[çc][ãa]o|normas?|jurisprud[êe]ncia)(\s+\w+)?\s+citad[oa]s?",
    re.IGNORECASE,
)
# A tese não ocupa o trecho inteiro: o início da ementa traz o tema e os fatos.
_FRACAO_MAXIMA_DA_TESE = 2 / 3


def trecho_para_rerank(ementa: str, limite: int) -> str:
    """Ementa que caberia no corte, ou início + tese de julgamento em até `limite` chars.

    Volta a ementa inteira quando ela cabe, quando não tem tese de julgamento e quando
    a tese já está dentro do `limite`: nesses casos o corte simples não perde a tese.
    """
    if len(ementa) <= limite:
        return ementa
    inicio_tese = _INICIO_TESE.search(ementa)
    if inicio_tese is None:
        return ementa
    fim_tese = _FIM_TESE.search(ementa, inicio_tese.end())
    fim = fim_tese.start() if fim_tese else len(ementa)
    if fim <= limite:
        return ementa
    tese = ementa[inicio_tese.start():fim].strip()[: int(limite * _FRACAO_MAXIMA_DA_TESE)]
    # O início para onde a tese começa, para o trecho não repetir o texto dela.
    inicio = ementa[: min(inicio_tese.start(), limite - len(tese) - 1)].rstrip()
    return f"{inicio} {tese}".strip()


class RerankerComTese:
    """Qualquer reranker, recebendo o `trecho_para_rerank` no lugar da ementa."""

    def __init__(self, reranker, limite: int) -> None:
        self._reranker = reranker
        self._limite = limite

    def rerank_scores(self, query: str, passagens: list[str]) -> list[float]:
        return self._reranker.rerank_scores(query, [trecho_para_rerank(p, self._limite) for p in passagens])
