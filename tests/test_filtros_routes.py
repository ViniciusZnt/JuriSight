"""Testes de GET /filtros/dispositivos e POST /filtros/contagem (query/api/filtros_routes.py)."""
import pytest
from fastapi.testclient import TestClient

from query.api.app import app, get_current_user
from query.api.auth_routes import get_usuario_store
from query.api.filtros_routes import get_filtro_store
from query.filtros.store import ContagemFiltros, SugestaoDispositivo
from tests.fakes import usuario_fake

_USUARIO = usuario_fake("t@example.com", "T")


class _Store:
    def __init__(self):
        self.contagens = []

    def sugerir(self, texto, limite=10):
        return [SugestaoDispositivo("art_192_clt", "CLT art. 192", 42)]

    def tribunais(self):
        return [("TRT4", 4634), ("TRT2", 13073)]

    def contar(self, dispositivos, expressoes, tribunais=(), fase=None):
        self.contagens.append((dispositivos, expressoes, list(tribunais), fase))
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
    assert resp.json()["detail"] == "O filtro restrito está indisponível no momento."  # sem comando de servidor


def test_filtros_sem_store_valida_antes_de_dar_503(client):
    app.dependency_overrides[get_filtro_store] = lambda: None
    assert client.post("/filtros/contagem", json={"dispositivos": "x"}).status_code == 422
    assert client.get("/filtros/dispositivos", params={"q": "x" * 300}).status_code == 422
    resp = client.post("/filtros/contagem", json={"dispositivos": ["a"]})
    assert resp.status_code == 503
    assert resp.json()["detail"] == "O filtro restrito está indisponível no momento."


@pytest.mark.parametrize("body", [
    {"expressoes": ["x" * 201]},
    {"dispositivos": ["x" * 201]},
    {"expressoes": ["x"] * 21},
])
def test_filtros_contagem_acima_do_limite_422(client, body):
    app.dependency_overrides[get_filtro_store] = lambda: _Store()
    assert client.post("/filtros/contagem", json=body).status_code == 422


def test_filtros_sugestoes_texto_longo_422(client):
    app.dependency_overrides[get_filtro_store] = lambda: _Store()
    assert client.get("/filtros/dispositivos", params={"q": "x" * 201}).status_code == 422


def test_filtros_tribunais(client):
    app.dependency_overrides[get_filtro_store] = lambda: _Store()
    resp = client.get("/filtros/tribunais")
    assert resp.status_code == 200
    assert resp.json() == [{"tribunal": "TRT4", "rotulo": "TRT-4", "total": 4634},
                           {"tribunal": "TRT2", "rotulo": "TRT-2", "total": 13073}]


def test_filtros_tribunais_sem_sessao_401(client):
    app.dependency_overrides.pop(get_current_user)
    assert client.get("/filtros/tribunais").status_code == 401


def test_filtros_tribunais_sem_store_503(client):
    app.dependency_overrides[get_filtro_store] = lambda: None
    resp = client.get("/filtros/tribunais")
    assert resp.status_code == 503
    assert resp.json()["detail"] == "O filtro restrito está indisponível no momento."


def test_contagem_repassa_tribunais_e_fase(client):
    store = _Store()
    app.dependency_overrides[get_filtro_store] = lambda: store
    resp = client.post("/filtros/contagem", json={"tribunais": ["TRT4"], "fase": "execucao"})
    assert resp.status_code == 200
    assert store.contagens == [([], [], ["TRT4"], "execucao")]


def test_contagem_mais_de_25_tribunais_422(client):
    app.dependency_overrides[get_filtro_store] = lambda: _Store()
    assert client.post("/filtros/contagem", json={"tribunais": [f"TRT{i}" for i in range(26)]}).status_code == 422
