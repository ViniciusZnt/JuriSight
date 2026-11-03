"""
Testes de integração de query/api/uso_diario.py contra um Postgres DE VERDADE: o contador
usa INSERT ... ON CONFLICT e rollback quando passa do limite, que só o Postgres executa.

Cada teste usa uma ação própria (`teste-<uuid>`), para o limite total não somar o uso real
do banco. Pulado se DATABASE_URL não estiver definida ou o Postgres não responder.
"""
from __future__ import annotations

import os
import uuid

import psycopg
import pytest

from auth.db import ensure_schema as ensure_auth_schema
from auth.store import UsuarioStore
from query.api.uso_diario import LimiteDiarioExcedido, UsoDiario, ensure_schema

DATABASE_URL = os.getenv("DATABASE_URL")


def _postgres_disponivel() -> bool:
    if not DATABASE_URL:
        return False
    try:
        psycopg.connect(DATABASE_URL, connect_timeout=2).close()
        return True
    except psycopg.OperationalError:
        return False


pytestmark = pytest.mark.skipif(
    not _postgres_disponivel(),
    reason="Requer DATABASE_URL apontando para um Postgres real e acessível.",
)


@pytest.fixture(autouse=True)
def _schema_pronto():
    ensure_auth_schema(DATABASE_URL)
    ensure_schema(DATABASE_URL)


@pytest.fixture
def usuarios():
    """Duas contas descartáveis; ON DELETE CASCADE limpa o uso delas."""
    store = UsuarioStore(DATABASE_URL)
    ids = [
        store.create(email=f"uso-integ-{uuid.uuid4().hex}@teste-integracao.invalid", hashed_password="x", nome=None).id
        for _ in range(2)
    ]
    yield ids
    with psycopg.connect(DATABASE_URL) as conn:
        conn.execute("DELETE FROM auth.usuarios WHERE id = ANY(%s)", (ids,))


def _uso_de(usuario_id, acao) -> int:
    with psycopg.connect(DATABASE_URL) as conn:
        linha = conn.execute(
            "SELECT quantidade FROM public.uso_diario WHERE usuario_id = %s AND acao = %s", (usuario_id, acao)
        ).fetchone()
    return linha[0] if linha else 0


def test_limite_por_conta_bloqueia_e_nao_conta_a_tentativa_barrada(usuarios):
    a, b = usuarios
    acao = f"teste-{uuid.uuid4().hex}"
    uso = UsoDiario(DATABASE_URL, por_conta=2, total=100)
    uso.consumir(a, acao)
    uso.consumir(a, acao)
    with pytest.raises(LimiteDiarioExcedido, match="limite de 2 consultas por dia"):
        uso.consumir(a, acao)
    assert _uso_de(a, acao) == 2
    uso.consumir(b, acao)  # a outra conta tem o próprio limite


def test_limite_total_soma_todas_as_contas(usuarios):
    a, b = usuarios
    acao = f"teste-{uuid.uuid4().hex}"
    uso = UsoDiario(DATABASE_URL, por_conta=10, total=3)
    uso.consumir(a, acao)
    uso.consumir(a, acao)
    uso.consumir(b, acao)
    with pytest.raises(LimiteDiarioExcedido, match="limite de consultas de hoje"):
        uso.consumir(b, acao)
    assert _uso_de(b, acao) == 1


def test_banco_fora_do_ar_nao_bloqueia():
    UsoDiario("postgresql://ninguem@127.0.0.1:1/nada?connect_timeout=1", por_conta=0, total=0).consumir(uuid.uuid4(), "query")
