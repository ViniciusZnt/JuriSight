"""Testes de GET /filtros/dispositivos e POST /filtros/contagem (query/api/filtros_routes.py)."""
import uuid
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from auth.store import Usuario
from query.api.app import app, get_current_user
from query.api.auth_routes import get_usuario_store
from query.api.filtros_routes import get_filtro_store
from query.filtros.store import ContagemFiltros, SugestaoDispositivo

_USUARIO = Usuario(id=uuid.uuid4(), email="t@example.com", hashed_password="x", nome="T", is_active=True,
                   criado_em=datetime.now(timezone.utc))


class _Store:
    def __init__(self):
        self.contagens = []

    def sugerir(self, texto, limite=10):
        return [SugestaoDispositivo("art_192_clt", "CLT art. 192", 42)]

    def contar(self, dispositivos, expressoes):
        self.contagens.append((dispositivos, expressoes))
        return ContagemFiltros(7, [SugestaoDispositivo("art_192_clt", "CLT art. 192", 42)], [(e, 3) for e in expressoes])


@pytest.fixture
def client():
    app.dependency_overrides[get_current_user] = lambda: _USUARIO
    app.dependency_overrides[get_usuario_store] = lambda: None
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_filtros_sugestoes(client):
    app.dependency_overrides[get_filtro_store] = lambda: _Store()
    resp = client.get("/filtros/dispositivos", params={"q": "clt 192"})
    assert resp.status_code == 200
    assert resp.json() == [{"codigo": "art_192_clt", "rotulo": "CLT art. 192", "total": 42}]


def test_filtros_contagem(client):
    app.dependency_overrides[get_filtro_store] = lambda: _Store()
    resp = client.post("/filtros/contagem", json={"dispositivos": ["art_192_clt"], "expressoes": ["adicional noturno"]})
    assert resp.status_code == 200
    assert resp.json() == {
        "total": 7,
        "dispositivos": [{"codigo": "art_192_clt", "rotulo": "CLT art. 192", "total": 42}],
        "expressoes": [{"texto": "adicional noturno", "total": 3}],
    }


def test_filtros_contagem_expressao_so_com_simbolos_nao_quebra(client):
    app.dependency_overrides[get_filtro_store] = lambda: _Store()
    assert client.post("/filtros/contagem", json={"dispositivos": [], "expressoes": ["&|!"]}).status_code == 200


def test_filtros_sugestoes_401_sem_sessao(client):
    app.dependency_overrides.pop(get_current_user)
    assert client.get("/filtros/dispositivos", params={"q": "x"}).status_code == 401
    assert client.post("/filtros/contagem", json={}).status_code == 401


@pytest.mark.parametrize("chamada", [
    lambda c: c.get("/filtros/dispositivos", params={"q": "x"}),
    lambda c: c.post("/filtros/contagem", json={}),
])
def test_filtros_503_sem_store(client, chamada):
    app.dependency_overrides[get_filtro_store] = lambda: None
    resp = chamada(client)
    assert resp.status_code == 503
    assert "query.filtros.preparar" in resp.json()["detail"]
