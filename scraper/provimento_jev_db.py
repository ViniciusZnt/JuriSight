"""
Tabela `public.provimento_jev` e store da classificação de provimento feita
pelo Jev. Ver docs/superpowers/specs/2026-10-20-provimento-jev-design.md.

"Já classificado" = linha com o mesmo `modelo` e `perguntas_sha`. A tabela
referencia `documentos(id)` com ON DELETE CASCADE.
"""
from __future__ import annotations

import contextlib
import logging
from contextlib import contextmanager
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


_DDL_CORRECAO = """
CREATE TABLE IF NOT EXISTS public.provimento_correcao (
    documento_id    UUID        NOT NULL REFERENCES documentos(id) ON DELETE CASCADE,
    usuario_id      UUID        NOT NULL REFERENCES auth.usuarios(id) ON DELETE CASCADE,
    resultado       TEXT        NOT NULL,
    recorrente      TEXT        NOT NULL,
    favorece        TEXT        NOT NULL,
    comentario      TEXT,
    jev_resultado   TEXT,
    jev_recorrente  TEXT,
    jev_favorece    TEXT,
    modelo          TEXT,
    perguntas_sha   TEXT,
    criado_em       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    atualizado_em   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (documento_id, usuario_id)
);
"""

_COLUNAS_CORRECAO = (
    "documento_id", "usuario_id", "resultado", "recorrente", "favorece", "comentario",
    "jev_resultado", "jev_recorrente", "jev_favorece", "modelo", "perguntas_sha",
    "criado_em", "atualizado_em",
)


class DocumentoNaoEncontrado(LookupError):
    """Correção para um documento que não existe."""


def ensure_schema_correcoes(database_url: str) -> None:
    """Cria `public.provimento_correcao` (idempotente). Depende de auth.usuarios."""
    with psycopg.connect(database_url) as conn:
        conn.execute(_DDL_CORRECAO)


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

    @contextmanager
    def conexao_de_gravacao(self):
        """Uma conexão só para gravar um lote. Em autocommit: cada `gravar` fica salvo na hora,
        como com uma conexão por chamada (o lote é pago e pode ser interrompido)."""
        with psycopg.connect(self._database_url, autocommit=True) as conn:
            yield conn

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
        conn: psycopg.Connection | None = None,
    ) -> None:
        """Upsert por `documento_id`; renova `criado_em`. `conn`: a de `conexao_de_gravacao`
        (sem ela, abre e fecha uma só para esta linha)."""
        with contextlib.nullcontext(conn) if conn is not None else self._conn() as conn:
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

    def provimentos_documentos(self) -> dict[str, str]:
        """`documento_id -> provimento` de todos os documentos (NULL vira NAO_APLICAVEL)."""
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT id::text, coalesce(provimento, 'NAO_APLICAVEL') FROM documentos"
            ).fetchall()
        return {r[0]: r[1] for r in rows}

    def detalhes(self, documento_ids: list[str]) -> dict[str, dict]:
        """Classificação do Jev de cada documento, para o frontend. Ids sem linha ficam fora."""
        if not documento_ids:
            return {}
        with self._conn() as conn:
            rows = conn.execute(
                """
                SELECT documento_id::text, resultado, recorrente, favorece, probs,
                       confianca_resultado, confianca_recorrente, confianca_favorece, modelo
                FROM public.provimento_jev WHERE documento_id = ANY(%s::uuid[])
                """,
                (list(documento_ids),),
            ).fetchall()
        chaves = ("resultado", "recorrente", "favorece", "probabilidades",
                  "confianca_resultado", "confianca_recorrente", "confianca_favorece", "modelo")
        return {r[0]: dict(zip(chaves, r[1:])) for r in rows}

    def salvar_correcao(
        self, documento_id: str, usuario_id: str, resultado: str, recorrente: str,
        favorece: str, comentario: str | None,
    ):
        """Upsert da correção do usuário, com cópia da resposta atual do Jev. Devolve atualizado_em."""
        try:
            with self._conn() as conn:
                return conn.execute(
                    """
                    INSERT INTO public.provimento_correcao
                        (documento_id, usuario_id, resultado, recorrente, favorece, comentario,
                         jev_resultado, jev_recorrente, jev_favorece, modelo, perguntas_sha)
                    SELECT v.d, v.u, %s, %s, %s, %s,
                           p.resultado, p.recorrente, p.favorece, p.modelo, p.perguntas_sha
                    FROM (SELECT %s::uuid AS d, %s::uuid AS u) v
                    LEFT JOIN public.provimento_jev p ON p.documento_id = v.d
                    ON CONFLICT (documento_id, usuario_id) DO UPDATE SET
                        resultado = EXCLUDED.resultado, recorrente = EXCLUDED.recorrente,
                        favorece = EXCLUDED.favorece, comentario = EXCLUDED.comentario,
                        jev_resultado = EXCLUDED.jev_resultado, jev_recorrente = EXCLUDED.jev_recorrente,
                        jev_favorece = EXCLUDED.jev_favorece, modelo = EXCLUDED.modelo,
                        perguntas_sha = EXCLUDED.perguntas_sha, atualizado_em = NOW()
                    RETURNING atualizado_em
                    """,
                    (resultado, recorrente, favorece, comentario, documento_id, usuario_id),
                ).fetchone()[0]
        except psycopg.errors.ForeignKeyViolation as e:
            raise DocumentoNaoEncontrado(documento_id) from e

    def correcoes(self) -> list[dict]:
        """Todas as correções, da mais antiga para a mais recente."""
        with self._conn() as conn:
            rows = conn.execute(
                f"SELECT {', '.join(_COLUNAS_CORRECAO)} FROM public.provimento_correcao "
                "ORDER BY atualizado_em"
            ).fetchall()
        return [{k: (str(v) if k in ("documento_id", "usuario_id") else v)
                 for k, v in zip(_COLUNAS_CORRECAO, r)} for r in rows]
