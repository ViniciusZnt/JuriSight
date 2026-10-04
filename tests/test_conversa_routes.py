"""
Testes de GET/POST /conversas, PATCH /conversas/{id}, PUT /conversas/{id}/snapshot
e DELETE /conversas/{id} (query/api/conversa_routes.py).

Mesmo espírito de tests/test_api.py: usa o `app` real de query/api/app.py (o
conversa_router já está montado lá), com get_current_user e get_conversa_store
substituídos via dependency_overrides — nenhuma infra real.

_FakeConversaStore replica o invariante de segurança do ConversaStore real: toda
operação filtra por (id, usuario_id) — é o que os testes de isolamento entre
usuários abaixo verificam.
"""
from __future__ import annotations

import uuid
from dataclasses import replace
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from auth.store import Usuario
from conversations.store import Conversa, ConversaNaoEncontradaError
from query.api.app import app, get_current_user
from query.api.conversa_routes import get_conversa_store
from query.enrichment.schema import EstruturaArgumentativa
from query.search.result_formatter import ResultCard
from scraper.schema import Provimento, TipoDocumento

_USUARIO_A = Usuario(
    id=uuid.uuid4(), email="a@example.com", hashed_password="x",
    nome="A", is_active=True, criado_em=datetime.now(timezone.utc),
)
_USUARIO_B = Usuario(
    id=uuid.uuid4(), email="b@example.com", hashed_password="x",
    nome="B", is_active=True, criado_em=datetime.now(timezone.utc),
)


class _FakeConversaStore:
    """Dict em memória, mesma interface pública do ConversaStore — e o mesmo
    invariante de segurança: toda leitura/escrita checa usuario_id."""

    def __init__(self) -> None:
        self._por_id: dict[uuid.UUID, Conversa] = {}

    def create(self, usuario_id, titulo) -> Conversa:
        now = datetime.now(timezone.utc)
        c = Conversa(
            id=uuid.uuid4(), usuario_id=usuario_id, titulo=titulo,
            criado_em=now, atualizado_em=now, estrutura=None,
            has_file=None, file_name=None, pdf_extraido=None, aviso=None, resultados=None,
        )
        self._por_id[c.id] = c
        return c

    def list_by_usuario(self, usuario_id) -> list[Conversa]:
        return sorted(
            (c for c in self._por_id.values() if c.usuario_id == usuario_id),
            key=lambda c: c.criado_em, reverse=True,
        )

    def _get_or_raise(self, conversa_id, usuario_id) -> Conversa:
        c = self._por_id.get(conversa_id)
        if c is None or c.usuario_id != usuario_id:
            raise ConversaNaoEncontradaError(conversa_id)
        return c

    def rename(self, conversa_id, usuario_id, titulo) -> Conversa:
        c = self._get_or_raise(conversa_id, usuario_id)
        novo = replace(c, titulo=titulo)
        self._por_id[conversa_id] = novo
        return novo

    def set_snapshot(self, conversa_id, usuario_id, *, estrutura, has_file, file_name, pdf_extraido, aviso, resultados) -> Conversa:
        c = self._get_or_raise(conversa_id, usuario_id)
        novo = replace(
            c, estrutura=estrutura, has_file=has_file, file_name=file_name,
            pdf_extraido=pdf_extraido, aviso=aviso, resultados=resultados,
        )
        self._por_id[conversa_id] = novo
        return novo

    def delete(self, conversa_id, usuario_id) -> None:
        self._get_or_raise(conversa_id, usuario_id)
        del self._por_id[conversa_id]


@pytest.fixture
def store() -> _FakeConversaStore:
    return _FakeConversaStore()


@pytest.fixture
def client(store: _FakeConversaStore):
    app.dependency_overrides[get_current_user] = lambda: _USUARIO_A
    app.dependency_overrides[get_conversa_store] = lambda: store
    yield TestClient(app)
    app.dependency_overrides.clear()


def _estrutura_dict() -> dict:
    return EstruturaArgumentativa(tese_central="tese de teste").model_dump(mode="json")


def _resultado_dict() -> dict:
    return ResultCard(
        id="d1", tipo_documento=TipoDocumento.ACORDAO.value, hierarquia_categoria=4,
        numero_processo="RR-1-2021", tribunal="TST", turma="2ª Turma", relator="Min. Fulano",
        data_julgamento=None, ementa="Ementa.", provimento=Provimento.APROVADO.value,
        link_original=None, score_rrf=0.5,
    ).model_dump(mode="json")


# --------------------------------------------------------------------------- #
# Ciclo básico                                                                 #
# --------------------------------------------------------------------------- #

def test_criar_e_listar(client):
    resp = client.post("/conversas", json={"titulo": "Minha pesquisa"})
    assert resp.status_code == 201
    body = resp.json()
    assert body["titulo"] == "Minha pesquisa"
    assert body["estrutura"] is None and body["resultados"] is None

    resp = client.get("/conversas")
    assert resp.status_code == 200
    assert [c["id"] for c in resp.json()] == [body["id"]]


def test_renomear(client):
    criada = client.post("/conversas", json={"titulo": "Original"}).json()
    resp = client.patch(f"/conversas/{criada['id']}", json={"titulo": "Renomeada"})
    assert resp.status_code == 200
    assert resp.json()["titulo"] == "Renomeada"


def test_salvar_snapshot_e_reler(client):
    criada = client.post("/conversas", json={"titulo": "P"}).json()

    resp = client.put(
        f"/conversas/{criada['id']}/snapshot",
        json={"estrutura": _estrutura_dict(), "has_file": False, "resultados": None},
    )
    assert resp.status_code == 200
    assert resp.json()["estrutura"]["tese_central"] == "tese de teste"
    assert resp.json()["resultados"] is None

    # Refaz a busca na mesma conversa (RF: cada re-busca sobrescreve o snapshot).
    resp = client.put(
        f"/conversas/{criada['id']}/snapshot",
        json={"estrutura": _estrutura_dict(), "has_file": False, "resultados": [_resultado_dict()]},
    )
    assert resp.status_code == 200
    assert len(resp.json()["resultados"]) == 1

    resp = client.get("/conversas")
    assert len(resp.json()[0]["resultados"]) == 1


def test_apagar(client):
    criada = client.post("/conversas", json={"titulo": "P"}).json()
    resp = client.delete(f"/conversas/{criada['id']}")
    assert resp.status_code == 204
    assert client.get("/conversas").json() == []


# --------------------------------------------------------------------------- #
# Isolamento entre usuários (regressão de segurança)                           #
# --------------------------------------------------------------------------- #

def test_usuario_nao_ve_conversa_de_outro(client, store):
    criada = client.post("/conversas", json={"titulo": "Da usuária A"}).json()

    app.dependency_overrides[get_current_user] = lambda: _USUARIO_B
    client_b = TestClient(app)

    assert client_b.get("/conversas").json() == []
    assert client_b.patch(f"/conversas/{criada['id']}", json={"titulo": "Hackeado"}).status_code == 404
    assert client_b.delete(f"/conversas/{criada['id']}").status_code == 404
    assert client_b.put(
        f"/conversas/{criada['id']}/snapshot",
        json={"estrutura": _estrutura_dict(), "has_file": False},
    ).status_code == 404


def test_conversa_inexistente_404(client):
    assert client.patch(f"/conversas/{uuid.uuid4()}", json={"titulo": "x"}).status_code == 404
    assert client.get("/conversas").status_code == 200  # sanity: rota de leitura não quebra


def test_id_malformado_404(client):
    assert client.patch("/conversas/nao-eh-uuid", json={"titulo": "x"}).status_code == 404
