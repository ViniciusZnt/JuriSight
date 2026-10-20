"""
Carrega o dataset golden de avaliação (evaluation/golden.toml).

Cada query traz o texto da busca, um filtro opcional de metadados e a lista de
documento_id julgados relevantes (preenchida à mão com a especialista).
"""
from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from pathlib import Path

GOLDEN_PATH = Path(__file__).parent / "golden.toml"


@dataclass
class GoldenQuery:
    """Uma query do dataset golden com seus rótulos de relevância."""

    id: str
    query: str
    relevantes: list[str] = field(default_factory=list)
    filtro: dict | None = None

    @property
    def rotulada(self) -> bool:
        """True se já tem relevantes preenchidos (só então entra no P@K)."""
        return bool(self.relevantes)


def carregar(path: Path = GOLDEN_PATH) -> list[GoldenQuery]:
    """Lê o golden.toml e devolve as queries.

    Input:  path — caminho do TOML.
    Returns: lista de GoldenQuery.
    """
    with open(path, "rb") as f:
        data = tomllib.load(f)
    return [
        GoldenQuery(
            id=q["id"],
            query=q["query"],
            relevantes=q.get("relevantes", []),
            filtro=q.get("filtro") or None,
        )
        for q in data.get("query", [])
    ]
