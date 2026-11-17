"""Limite diário por ação (query/api/uso_diario.py) e GET /uso, sem banco."""
from __future__ import annotations

import psycopg
from fastapi.testclient import TestClient

from query.api.app import app, get_current_user, get_uso_diario
from query.api.auth_routes import get_usuario_store
from query.api.uso_diario import UsoDiario
from tests.fakes import usuario_fake

client = TestClient(app)


def _limpar_env(monkeypatch):
    for v in ("LIMITE_DIARIO_TRIAGEM_POR_CONTA", "LIMITE_DIARIO_TRIAGEM_TOTAL"):
        monkeypatch.delenv(v, raising=False)


def test_triagem_tem_5x_o_limite_e_aceita_override(monkeypatch):
    _limpar_env(monkeypatch)
    uso = UsoDiario("postgresql://x", por_conta=30, total=300)
    assert uso.limites("query") == (30, 300)
    assert uso.limites("triagem") == (150, 1500)
    monkeypatch.setenv("LIMITE_DIARIO_TRIAGEM_POR_CONTA", "40")
    assert UsoDiario("postgresql://x", por_conta=30, total=300).limites("triagem") == (40, 1500)


class _FakeUso:
    def __init__(self, do_dia=None, erro=False):
        self._do_dia, self._erro = do_dia or {}, erro

    def limites(self, acao):
        return (150, 1500) if acao == "triagem" else (30, 300)

    def do_dia(self, usuario_id):
        if self._erro:
            raise psycopg.OperationalError("banco fora")
        return self._do_dia


def _com(uso):
    app.dependency_overrides[get_current_user] = lambda: usuario_fake()
    app.dependency_overrides[get_uso_diario] = lambda: uso


def test_uso_devolve_as_4_acoes_na_ordem_com_usado_e_limite():
    _com(_FakeUso({"query": 3, "teste-x": 9}))
    try:
        assert client.get("/uso").json() == {"acoes": [
            {"acao": "enrich", "usado": 0, "limite": 30}, {"acao": "query", "usado": 3, "limite": 30},
            {"acao": "triagem", "usado": 0, "limite": 150}, {"acao": "resposta", "usado": 0, "limite": 30}]}
    finally:
        app.dependency_overrides.clear()


def test_uso_com_banco_fora_503():
    _com(_FakeUso(erro=True))
    try:
        assert client.get("/uso").status_code == 503
    finally:
        app.dependency_overrides.clear()


def test_uso_sem_contador_configurado_503():
    _com(None)
    try:
        assert client.get("/uso").status_code == 503
    finally:
        app.dependency_overrides.clear()


def test_uso_sem_sessao_401():
    app.dependency_overrides[get_usuario_store] = lambda: None
    try:
        assert client.get("/uso").status_code == 401
    finally:
        app.dependency_overrides.clear()
