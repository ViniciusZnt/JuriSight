"""
Tabela `public.provimento_jev` e store da classificação de provimento feita
pelo Jev. Ver docs/superpowers/specs/2026-10-20-provimento-jev-design.md.

"Já classificado" = linha com o mesmo `modelo` e `perguntas_sha`. A tabela
referencia `documentos(id)` com ON DELETE CASCADE.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass

import psycopg
from psycopg.types.json import Json

from scraper.provimento_jev import ClassificacaoProvimento

logger = logging.getLogger(__name__)

_DDL = """
CREATE TABLE IF NOT EXISTS public.provimento_jev (
    documento_id          UUID        PRIMARY KEY REFERENCES documentos(id) ON DELETE CASCADE,
    resultado             TEXT        NOT NULL,
    recorrente            TEXT        NOT NULL,
    favorece              TEXT        NOT NULL,
    probs                 JSONB       NOT NULL,
    confianca_resultado   REAL,
    confianca_recorrente  REAL,
    confianca_favorece    REAL,
    provimento_regex      TEXT,
    modelo                TEXT        NOT NULL,
    perguntas_sha         TEXT        NOT NULL,
    criado_em             TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
"""


def ensure_schema(database_url: str) -> None:
    """Cria `public.provimento_jev` (idempotente)."""
    with psycopg.connect(database_url) as conn:
        conn.execute(_DDL)
    logger.info("PostgreSQL conectado — tabela provimento_jev pronta.")


@dataclass(frozen=True)
class ItemPendente:
    """Acórdão a classificar. `acordao` guarda só o TRECHO FINAL (últimos 4000
    caracteres) e `ementa` os primeiros 1500, não o texto inteiro: o acervo
    completo ocupa ~1,1 GB."""
    documento_id: str
    acordao: str
    ementa: str | None
    provimento_regex: str


@dataclass(frozen=True)
class LinhaClassificada:
    documento_id: str
    resultado: str
    recorrente: str
    favorece: str
    confianca_resultado: float
    provimento_regex: str
    provimento_atual: str


_PENDENTE_WHERE = r"""
    d.tipo_documento = 'ACORDAO'
    AND d.acordao ~ '\S'
    AND NOT EXISTS (
        SELECT 1 FROM public.provimento_jev p
        WHERE p.documento_id = d.id AND p.modelo = %s AND p.perguntas_sha = %s
    )
"""


class ProvimentoJevStore:
    def __init__(self, database_url: str):
        self._database_url = database_url

    def _conn(self) -> psycopg.Connection:
        return psycopg.connect(self._database_url)

    def pendentes(
        self,
        modelo: str,
        perguntas_sha: str,
        limite: int | None = None,
        apos_id: str | None = None,
        documento_ids: list[str] | None = None,
    ) -> list[ItemPendente]:
        """Acórdãos sem classificação do mesmo modelo/sha, ordenados por id.
        Traz só o trecho final do acórdão e o início da ementa."""
        sql = (
            "SELECT d.id, right(d.acordao, 4000), left(d.ementa, 1500), "
            "coalesce(d.provimento, '') FROM documentos d WHERE " + _PENDENTE_WHERE
        )
        params: list = [modelo, perguntas_sha]
        if apos_id is not None:
            sql += " AND d.id > %s::uuid"
            params.append(apos_id)
        if documento_ids is not None:
            sql += " AND d.id = ANY(%s::uuid[])"
            params.append(list(documento_ids))
        sql += " ORDER BY d.id"
        if limite is not None:
            sql += " LIMIT %s"
            params.append(limite)
        with self._conn() as conn:
            rows = conn.execute(sql, params).fetchall()
        return [ItemPendente(str(r[0]), r[1], r[2], r[3]) for r in rows]

    def contar_pendentes(
        self, modelo: str, perguntas_sha: str, documento_ids: list[str] | None = None
    ) -> int:
        """Quantos documentos `pendentes` devolveria (mesmo filtro)."""
        sql = "SELECT count(*) FROM documentos d WHERE " + _PENDENTE_WHERE
        params: list = [modelo, perguntas_sha]
        if documento_ids is not None:
            sql += " AND d.id = ANY(%s::uuid[])"
            params.append(list(documento_ids))
        with self._conn() as conn:
            return conn.execute(sql, params).fetchone()[0]

    def contar_sem_texto(self) -> int:
        """Acórdãos com `acordao` nulo ou só whitespace (nunca vão ao Jev)."""
        with self._conn() as conn:
            return conn.execute(
                "SELECT count(*) FROM documentos WHERE tipo_documento = 'ACORDAO' "
                r"AND (acordao IS NULL OR acordao !~ '\S')"
            ).fetchone()[0]

    def gravar(
        self,
        documento_id: str,
        c: ClassificacaoProvimento,
        provimento_regex: str,
        modelo: str,
        perguntas_sha: str,
    ) -> None:
        """Upsert por `documento_id`; renova `criado_em`."""
        with self._conn() as conn:
            conn.execute(
                """
                INSERT INTO public.provimento_jev
                    (documento_id, resultado, recorrente, favorece, probs,
                     confianca_resultado, confianca_recorrente, confianca_favorece,
                     provimento_regex, modelo, perguntas_sha)
                VALUES (%s::uuid, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (documento_id) DO UPDATE SET
                    resultado = EXCLUDED.resultado,
                    recorrente = EXCLUDED.recorrente,
                    favorece = EXCLUDED.favorece,
                    probs = EXCLUDED.probs,
                    confianca_resultado = EXCLUDED.confianca_resultado,
                    confianca_recorrente = EXCLUDED.confianca_recorrente,
                    confianca_favorece = EXCLUDED.confianca_favorece,
                    provimento_regex = coalesce(
                        public.provimento_jev.provimento_regex, EXCLUDED.provimento_regex),
                    modelo = EXCLUDED.modelo,
                    perguntas_sha = EXCLUDED.perguntas_sha,
                    criado_em = NOW()
                """,
                (
                    documento_id, c.resultado, c.recorrente, c.favorece, Json(c.probs),
                    c.confianca_resultado, c.confianca_recorrente, c.confianca_favorece,
                    provimento_regex, modelo, perguntas_sha,
                ),
            )

    def linhas(self, modelo: str, perguntas_sha: str) -> list[LinhaClassificada]:
        """Classificações do par modelo/sha, com o `provimento` atual do documento."""
        with self._conn() as conn:
            rows = conn.execute(
                """
                SELECT p.documento_id, p.resultado, p.recorrente, p.favorece,
                       p.confianca_resultado, coalesce(p.provimento_regex, ''),
                       coalesce(d.provimento, '')
                FROM public.provimento_jev p
                JOIN documentos d ON d.id = p.documento_id
                WHERE p.modelo = %s AND p.perguntas_sha = %s
                ORDER BY p.documento_id
                """,
                (modelo, perguntas_sha),
            ).fetchall()
        return [LinhaClassificada(str(r[0]), r[1], r[2], r[3], r[4], r[5], r[6]) for r in rows]

    def trechos(
        self, documento_ids: list[str], tamanho: int = 1500
    ) -> dict[str, tuple[str | None, str]]:
        """`link_original` e os últimos `tamanho` caracteres do acórdão."""
        if not documento_ids:
            return {}
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT id, link_original, right(coalesce(acordao, ''), %s) "
                "FROM documentos WHERE id = ANY(%s::uuid[])",
                (tamanho, list(documento_ids)),
            ).fetchall()
        return {str(r[0]): (r[1], r[2]) for r in rows}

    def aplicar(self, mudancas: list[tuple[str, str]]) -> int:
        """UPDATE documentos.provimento por (documento_id, novo), numa
        transação. Devolve quantas linhas realmente mudaram."""
        mudou = 0
        with self._conn() as conn:
            for documento_id, novo in mudancas:
                cur = conn.execute(
                    "UPDATE documentos SET provimento = %s "
                    "WHERE id = %s::uuid AND provimento IS DISTINCT FROM %s",
                    (novo, documento_id, novo),
                )
                mudou += cur.rowcount
        return mudou
