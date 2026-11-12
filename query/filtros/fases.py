"""Fase do processo, deduzida da classe processual (`documentos.sigla_classe`)."""
from __future__ import annotations

from typing import Literal

from query.enrichment.schema import EstruturaArgumentativa

Fase = Literal["conhecimento", "execucao", "outras"]

CLASSES: dict[str, tuple[str, ...]] = {
    "conhecimento": ("ROT", "RORSum", "RO", "RemNecRO", "RemNecTrab", "AIRO"),
    "execucao": ("AP", "AIAP"),
}


def condicao_fase(fase: Fase) -> tuple[str, list]:
    """SQL sobre `x.sigla_classe` e os parâmetros. "Outras" é tudo fora das duas listas, inclusive nulo."""
    if fase == "outras":
        return "(x.sigla_classe IS NULL OR NOT (x.sigla_classe = ANY(%s)))", [[*CLASSES["conhecimento"], *CLASSES["execucao"]]]
    return "x.sigla_classe = ANY(%s)", [list(CLASSES[fase])]


def tem_filtro_restrito(e: EstruturaArgumentativa) -> bool:
    return bool(e.dispositivos or e.expressoes or e.tribunais or e.fase)
