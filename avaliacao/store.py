"""
Acesso ao schema `avaliacao` (conjunto-ouro do harness de avaliação).

Mesma convenção de conversations/store.py: psycopg puro, uma conexão por
chamada. Juízes são strings `humano:<email>`; linhas antigas `jev:<modelo>` (do
juiz LLM que saiu do harness) ficam no banco, mas não contam como rótulo.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any

import psycopg
from psycopg.types.json import Json


@dataclass(frozen=True)
class Tese:
    id: uuid.UUID
    estrutura: dict[str, Any]
    origem: str
    tema: str
    split: str
    documento_origem_id: str | None = None


@dataclass(frozen=True)
class Par:
    id: uuid.UUID
    tese_id: uuid.UUID
    documento_id: str
    corredores: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class Julgamento:
    par_id: uuid.UUID
    juiz: str
    rodada: int
    relevancia: int
    stance: str
    relevancia_probs: dict | None = None
    stance_probs: dict | None = None
    confianca_rel: float | None = None
    confianca_stance: float | None = None


_TESE_COLS = "id, estrutura, origem, tema, split, documento_origem_id"
_PAR_COLS = "p.id, p.tese_id, p.documento_id, p.corredores"
_JULG_COLS = (
    "par_id, juiz, rodada, relevancia, stance, relevancia_probs, "
    "stance_probs, confianca_rel, confianca_stance"
)


def _tese(row) -> Tese:
    return Tese(*row)


def _par(row) -> Par:
    return Par(row[0], row[1], row[2], list(row[3]))


def _julgamento(row) -> Julgamento:
    return Julgamento(*row)


class AvaliacaoStore:
    def __init__(self, database_url: str):
        self._database_url = database_url

    def _conn(self) -> psycopg.Connection:
        return psycopg.connect(self._database_url)

    # --- teses ---

    def criar_tese(
        self, estrutura: dict, origem: str, tema: str, split: str,
        documento_origem_id: str | None = None,
    ) -> Tese:
        with self._conn() as conn:
            row = conn.execute(
                f"INSERT INTO avaliacao.teses (estrutura, origem, tema, split, documento_origem_id) "
                f"VALUES (%s, %s, %s, %s, %s) RETURNING {_TESE_COLS}",
                (Json(estrutura), origem, tema, split, documento_origem_id),
            ).fetchone()
        return _tese(row)

    def listar_teses(self, split: str | None = None) -> list[Tese]:
        sql = f"SELECT {_TESE_COLS} FROM avaliacao.teses"
        params: tuple = ()
        if split is not None:
            sql += " WHERE split = %s"
            params = (split,)
        sql += " ORDER BY criado_em, id"
        with self._conn() as conn:
            rows = conn.execute(sql, params).fetchall()
        return [_tese(r) for r in rows]

    # --- pares ---

    def adicionar_pares(self, tese_id: uuid.UUID, docs: dict[str, list[str]]) -> list[Par]:
        """Upsert de (tese, documento); em conflito UNE os corredores
        (ordenados, sem repetição). Devolve os pares dos documentos passados."""
        if not docs:
            return []
        pares: list[Par] = []
        with self._conn() as conn:
            for documento_id, corredores in docs.items():
                row = conn.execute(
                    "INSERT INTO avaliacao.pares (tese_id, documento_id, corredores) "
                    "VALUES (%s, %s, ARRAY(SELECT DISTINCT unnest(%s::text[]) ORDER BY 1)) "
                    "ON CONFLICT (tese_id, documento_id) DO UPDATE SET corredores = ARRAY("
                    "  SELECT DISTINCT c FROM unnest(avaliacao.pares.corredores || EXCLUDED.corredores) AS c ORDER BY 1"
                    ") RETURNING id, tese_id, documento_id, corredores",
                    (tese_id, documento_id, list(corredores)),
                ).fetchone()
                pares.append(_par(row))
        return pares

    def pares_da_tese(self, tese_id: uuid.UUID) -> list[Par]:
        with self._conn() as conn:
            rows = conn.execute(
                f"SELECT {_PAR_COLS} FROM avaliacao.pares p WHERE p.tese_id = %s ORDER BY p.documento_id",
                (tese_id,),
            ).fetchall()
        return [_par(r) for r in rows]

    # --- julgamentos ---

    def gravar_julgamento(self, j: Julgamento) -> None:
        with self._conn() as conn:
            conn.execute(
                "INSERT INTO avaliacao.julgamentos "
                "(par_id, juiz, rodada, relevancia, stance, relevancia_probs, stance_probs, "
                " confianca_rel, confianca_stance) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s) "
                "ON CONFLICT (par_id, juiz, rodada) DO UPDATE SET "
                "  relevancia = EXCLUDED.relevancia, stance = EXCLUDED.stance, "
                "  relevancia_probs = EXCLUDED.relevancia_probs, stance_probs = EXCLUDED.stance_probs, "
                "  confianca_rel = EXCLUDED.confianca_rel, confianca_stance = EXCLUDED.confianca_stance, "
                "  criado_em = NOW()",
                (
                    j.par_id, j.juiz, j.rodada, j.relevancia, j.stance,
                    Json(j.relevancia_probs) if j.relevancia_probs is not None else None,
                    Json(j.stance_probs) if j.stance_probs is not None else None,
                    j.confianca_rel, j.confianca_stance,
                ),
            )

    def julgamentos(self, juiz_prefixo: str | None = None) -> list[Julgamento]:
        sql = f"SELECT {_JULG_COLS} FROM avaliacao.julgamentos"
        params: tuple = ()
        if juiz_prefixo is not None:
            sql += " WHERE starts_with(juiz, %s)"
            params = (juiz_prefixo,)
        sql += " ORDER BY criado_em, id"
        with self._conn() as conn:
            rows = conn.execute(sql, params).fetchall()
        return [_julgamento(r) for r in rows]

    def rotulos_finais(self, tese_id: uuid.UUID) -> tuple[dict[str, int], dict[str, str]]:
        """documento_id -> relevância e -> stance, do julgamento humano mais
        recente de cada par. Pares sem julgamento humano ficam de fora."""
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT DISTINCT ON (p.id) p.documento_id, j.relevancia, j.stance "
                "FROM avaliacao.pares p JOIN avaliacao.julgamentos j ON j.par_id = p.id "
                "WHERE p.tese_id = %s AND starts_with(j.juiz, 'humano:') "
                "ORDER BY p.id, j.criado_em DESC",
                (tese_id,),
            ).fetchall()
        return {d: int(r) for d, r, _ in rows}, {d: s for d, _, s in rows}

    # --- amostra e fila de rotulação ---

    def definir_amostra(self, par_ids: dict[uuid.UUID, str]) -> None:
        """Upsert (par -> metade); não apaga pares que já estavam na amostra."""
        if not par_ids:
            return
        with self._conn() as conn:
            for par_id, metade in par_ids.items():
                conn.execute(
                    "INSERT INTO avaliacao.amostra (par_id, metade) VALUES (%s, %s) "
                    "ON CONFLICT (par_id) DO UPDATE SET metade = EXCLUDED.metade",
                    (par_id, metade),
                )

    def amostra(self) -> dict[uuid.UUID, str]:
        with self._conn() as conn:
            rows = conn.execute("SELECT par_id, metade FROM avaliacao.amostra").fetchall()
        return {par_id: metade for par_id, metade in rows}

    def proximo_da_fila(self, juiz: str) -> tuple[Par, Tese] | None:
        with self._conn() as conn:
            row = conn.execute(
                f"SELECT {_PAR_COLS}, " + ", ".join(f"t.{c.strip()}" for c in _TESE_COLS.split(",")) + " "
                "FROM avaliacao.amostra a "
                "JOIN avaliacao.pares p ON p.id = a.par_id "
                "JOIN avaliacao.teses t ON t.id = p.tese_id "
                "WHERE NOT EXISTS (SELECT 1 FROM avaliacao.julgamentos j WHERE j.par_id = p.id AND j.juiz = %s) "
                "ORDER BY (a.metade = 'sorteada') DESC, p.id LIMIT 1",
                (juiz,),
            ).fetchone()
        if row is None:
            return None
        return _par(row[:4]), _tese(row[4:])

    def progresso(self, juiz: str) -> tuple[int, int]:
        with self._conn() as conn:
            feitos, total = conn.execute(
                "SELECT COUNT(*) FILTER (WHERE EXISTS ("
                "  SELECT 1 FROM avaliacao.julgamentos j WHERE j.par_id = a.par_id AND j.juiz = %s)), COUNT(*) "
                "FROM avaliacao.amostra a",
                (juiz,),
            ).fetchone()
        return int(feitos), int(total)
