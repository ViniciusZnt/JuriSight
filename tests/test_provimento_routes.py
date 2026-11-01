"""Testes de POST /provimento/{documento_id}/correcao (query/api/provimento_routes.py)."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from auth.store import Usuario
from query.api.app import app, get_current_user
from query.api.auth_routes import get_usuario_store
from query.api.provimento_routes import get_provimento_store
from scraper.provimento_jev_db import DocumentoNaoEncontrado

_USUARIO = Usuario(
    id=uuid.uuid4(), email="a@example.com", hashed_password="x",
    nome="A", is_active=True, criado_em=datetime.now(timezone.utc),
)
DOC = str(uuid.uuid4())
CORPO = {"resultado": "provido", "recorrente": "reclamante", "favorece": "reclamante", "comentario": "texto"}


class _FakeStore:
    def __init__(self, erro: Exception | None = None):
        self.erro = erro
        self.chamadas: list[tuple] = []

    def salvar_correcao(self, *args):
        if self.erro:
            raise self.erro
        self.chamadas.append(args)
        return datetime(2026, 10, 25, tzinfo=timezone.utc)


@pytest.fixture
def store():
    s = _FakeStore()
    app.dependency_overrides[get_current_user] = lambda: _USUARIO
    app.dependency_overrides[get_provimento_store] = lambda: s
    yield s
    app.dependency_overrides.clear()


client = TestClient(app)


def test_correcao_grava(store):
    resp = client.post(f"/provimento/{DOC}/correcao", json=CORPO)
    assert resp.status_code == 200
    assert store.chamadas == [(DOC, str(_USUARIO.id), "provido", "reclamante", "reclamante", "texto")]
    assert resp.json()["documento_id"] == DOC


def test_correcao_valor_invalido(store):
    assert client.post(f"/provimento/{DOC}/correcao", json={**CORPO, "resultado": "ganhou"}).status_code == 422


def test_correcao_comentario_longo(store):
    assert client.post(f"/provimento/{DOC}/correcao", json={**CORPO, "comentario": "x" * 1001}).status_code == 422


def test_correcao_documento_inexistente(store):
    store.erro = DocumentoNaoEncontrado(DOC)
    assert client.post(f"/provimento/{DOC}/correcao", json=CORPO).status_code == 404


def test_correcao_uuid_malformado(store):
    assert client.post("/provimento/abc/correcao", json=CORPO).status_code == 404


def test_correcao_sem_sessao():
    app.dependency_overrides.clear()
    app.dependency_overrides[get_usuario_store] = lambda: None  # sem cookie, nem chega a consultar
    assert client.post(f"/provimento/{DOC}/correcao", json=CORPO).status_code == 401
    app.dependency_overrides.clear()
