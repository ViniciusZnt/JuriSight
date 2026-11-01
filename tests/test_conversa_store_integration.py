"""
Testes de integração de conversations/store.py contra um Postgres DE VERDADE.

Existe especificamente porque ConversaStore.add_versao() monta o JSON da
versão via `jsonb_build_object(...)` dentro do próprio SQL — um fake em
memória (o `_FakeConversaStore` usado em tests/test_conversa_routes.py) não
executa SQL de verdade, então não detectaria um erro só o Postgres real
levanta. Foi exatamente assim que um bug real escapou dos testes mockados:
`jsonb_build_object` com um parâmetro NULL sem cast explícito (ex.:
`file_name`/`pdf_extraido`/`aviso`, todos `None` quando a busca não envolveu
PDF — o caso comum) falha com `IndeterminateDatatype` ("could not determine
data type of parameter"), porque o Postgres não consegue inferir o tipo de um
NULL puro passado pra uma função `anyelement`. Corrigido com `%s::tipo`
explícito em cada parâmetro — este teste garante que não volta.

Requer DATABASE_URL apontando para um Postgres no ar; roda
`auth.db.ensure_schema()` + `conversations.db.ensure_schema()` antes de cada
teste (idempotente) e limpa via o usuário de teste (ON DELETE CASCADE
derruba a conversa junto — não precisa limpar `conversas` à parte).

Pulado automaticamente se DATABASE_URL não estiver definida ou o Postgres não
responder — mesmo espírito de tests/test_auth_store_integration.py.
"""
from __future__ import annotations

import os
import uuid

import psycopg
import pytest

from auth.db import ensure_schema as ensure_auth_schema
from auth.store import UsuarioStore
from conversations.db import ensure_schema as ensure_conversas_schema
from conversations.store import ConversaStore

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
    ensure_conversas_schema(DATABASE_URL)


@pytest.fixture
def usuario_id():
    """Usuário de teste descartável — ON DELETE CASCADE limpa a(s) conversa(s)
    criada(s) por ele junto, sem precisar de limpeza separada em `conversas`."""
    email = f"conversa-integ-{uuid.uuid4().hex}@teste-integracao.invalid"
    usuario = UsuarioStore(DATABASE_URL).create(email=email, hashed_password="hash-fake-de-teste", nome=None)
    yield usuario.id
    conn = psycopg.connect(DATABASE_URL)
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM auth.usuarios WHERE id = %s", (usuario.id,))
        conn.commit()
    finally:
        conn.close()


@pytest.fixture
def store() -> ConversaStore:
    return ConversaStore(DATABASE_URL)


def test_add_versao_com_campos_none_nao_quebra(store: ConversaStore, usuario_id):
    """Regressão: busca sem PDF (o caso comum) manda file_name/pdf_extraido/
    aviso = None — isso derrubava a query inteira com IndeterminateDatatype
    antes do fix de cast explícito (ver docstring do módulo)."""
    conversa = store.create(usuario_id, "Teste integração — campos None")

    atualizada = store.add_versao(
        conversa.id,
        usuario_id,
        estrutura={"tese_central": "tese sem pdf"},
        has_file=False,
        file_name=None,
        pdf_extraido=None,
        aviso=None,
        resultados=None,
    )

    assert len(atualizada.versoes) == 1
    v = atualizada.versoes[0]
    assert v["numero"] == 1
    assert v["file_name"] is None
    assert v["pdf_extraido"] is None
    assert v["aviso"] is None
    assert v["resultados"] is None
    assert v["estrutura"]["tese_central"] == "tese sem pdf"


def test_add_versao_acumula_numeracao_sequencial(store: ConversaStore, usuario_id):
    conversa = store.create(usuario_id, "Teste integração — numeração")

    store.add_versao(
        conversa.id, usuario_id, estrutura={"tese_central": "v1"},
        has_file=False, file_name=None, pdf_extraido=None, aviso=None, resultados=None,
    )
    atualizada = store.add_versao(
        conversa.id, usuario_id, estrutura={"tese_central": "v2"},
        has_file=True, file_name="processo.pdf", pdf_extraido=True, aviso=None,
        resultados=[{"id": "d1"}],
    )

    assert [v["numero"] for v in atualizada.versoes] == [1, 2]
    assert atualizada.versoes[1]["file_name"] == "processo.pdf"
    assert atualizada.versoes[1]["resultados"] == [{"id": "d1"}]
