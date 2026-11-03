"""
Limite diário de uso: cada conta faz até LIMITE_DIARIO_POR_CONTA chamadas de cada ação pagas
(enrich = CPU do Llama; query = embeddings; resposta = gpt, só quando gera de verdade) por dia, e
todas as contas juntas até LIMITE_DIARIO_TOTAL. O dia vira à meia-noite de Brasília.

`public.uso_diario` guarda um contador por (conta, dia, ação). Falha no banco não bloqueia a
busca: o limite protege o gasto, não pode derrubar o produto.
"""
from __future__ import annotations

import logging
import os
import uuid

import psycopg

logger = logging.getLogger(__name__)

_DDL = """
CREATE TABLE IF NOT EXISTS public.uso_diario (
    usuario_id  UUID     NOT NULL REFERENCES auth.usuarios(id) ON DELETE CASCADE,
    dia         DATE     NOT NULL,
    acao        TEXT     NOT NULL,
    quantidade  INTEGER  NOT NULL,
    PRIMARY KEY (usuario_id, dia, acao)
)
"""
_HOJE = "(now() AT TIME ZONE 'America/Sao_Paulo')::date"


def ensure_schema(database_url: str) -> None:
    """Cria `public.uso_diario` (idempotente). Depende de auth.usuarios."""
    with psycopg.connect(database_url) as conn:
        conn.execute(_DDL)


class LimiteDiarioExcedido(Exception):
    """Mensagem pronta para o usuário."""


class UsoDiario:
    def __init__(self, database_url: str, por_conta: int | None = None, total: int | None = None):
        self._url = database_url
        self.por_conta = por_conta if por_conta is not None else int(os.getenv("LIMITE_DIARIO_POR_CONTA", "30"))
        self.total = total if total is not None else int(os.getenv("LIMITE_DIARIO_TOTAL", "300"))

    def consumir(self, usuario_id: uuid.UUID, acao: str) -> None:
        """Conta mais um uso de `acao` hoje. Acima de um dos limites, desfaz e levanta
        LimiteDiarioExcedido; erro do banco só vira aviso no log."""
        try:
            with psycopg.connect(self._url) as conn:
                (da_conta,) = conn.execute(
                    f"INSERT INTO public.uso_diario (usuario_id, dia, acao, quantidade) VALUES (%s, {_HOJE}, %s, 1) "
                    "ON CONFLICT (usuario_id, dia, acao) DO UPDATE SET quantidade = uso_diario.quantidade + 1 "
                    "RETURNING quantidade",
                    (usuario_id, acao),
                ).fetchone()
                (de_todos,) = conn.execute(
                    f"SELECT sum(quantidade) FROM public.uso_diario WHERE dia = {_HOJE} AND acao = %s", (acao,)
                ).fetchone()
                if da_conta > self.por_conta:
                    conn.rollback()
                    raise LimiteDiarioExcedido(
                        f"Você atingiu o limite de {self.por_conta} consultas por dia. Ele renova à meia-noite."
                    )
                if de_todos > self.total:
                    conn.rollback()
                    raise LimiteDiarioExcedido(
                        "O JuriSight atingiu o limite de consultas de hoje. Ele renova à meia-noite."
                    )
        except psycopg.Error as exc:
            logger.warning("Limite diário sem verificar (banco indisponível): %s", exc)
