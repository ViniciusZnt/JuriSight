"""Testes de POST /resposta (query/api/app.py + query/search/resposta.py), com OpenAI falso."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from types import SimpleNamespace

import httpx
import openai
import pytest
from fastapi.testclient import TestClient

from auth.store import Usuario
from query.api.app import app, get_current_user, get_doc_retriever, get_openai
from query.api.auth_routes import get_usuario_store
from query.search.resposta import Frase, RespostaGerada
from scraper.schema import DocumentoJuridico, Provimento, TipoDocumento

_USUARIO = Usuario(
    id=uuid.uuid4(), email="a@example.com", hashed_password="x",
    nome="A", is_active=True, criado_em=datetime.now(timezone.utc),
)
IDS = [str(uuid.uuid4()) for _ in range(3)]
CORPO = {"estrutura": {"tese_central": "ruído acima da NR-15 sem EPI eficaz"}, "ids": IDS}


def _doc(ementa: str) -> DocumentoJuridico:
    return DocumentoJuridico(
        id_documento=ementa, tipo_documento=TipoDocumento.ACORDAO, hierarquia_categoria=4,
        tribunal="TRT2", turma="11ª Turma", sigla_classe="RORSum", ementa=ementa,
        provimento=Provimento.APROVADO,
    )


class _FakeRetriever:
    def fetch(self, ids):
        return {i: _doc(f"EMENTA {n}") for n, i in enumerate(IDS, start=1) if i in ids}


class _FakeOpenAI:
    def __init__(self, frases=None, erro: Exception | None = None):
        self.chamadas: list[dict] = []
        self.chat = SimpleNamespace(completions=SimpleNamespace(parse=self._parse))
        self._parsed = RespostaGerada(desfechos=[], frases=frases or [])
        self._erro = erro

    def _parse(self, **kwargs):
        self.chamadas.append(kwargs)
        if self._erro:
            raise self._erro
        msg = SimpleNamespace(parsed=self._parsed, refusal=None)
        return SimpleNamespace(choices=[SimpleNamespace(message=msg)])


@pytest.fixture
def usar():
    def _usar(fake):
        app.dependency_overrides[get_current_user] = lambda: _USUARIO
        app.dependency_overrides[get_doc_retriever] = lambda: _FakeRetriever()
        app.dependency_overrides[get_openai] = lambda: fake
        return fake
    yield _usar
    app.dependency_overrides.clear()


client = TestClient(app)


def test_frases_validas_passam_e_ementas_vem_do_banco_numeradas(usar, monkeypatch):
    monkeypatch.delenv("OPENAI_GEN_MODEL", raising=False)
    monkeypatch.delenv("OPENAI_GEN_TEMPERATURE", raising=False)
    fake = usar(_FakeOpenAI([Frase(texto="Sim, quando a perícia confirma.", citacoes=[1, 3, 1]),
                             Frase(texto="As contrárias negaram por EPI eficaz.", citacoes=[2])]))
    resp = client.post("/resposta", json=CORPO)
    assert resp.status_code == 200
    assert resp.json() == {"frases": [
        {"texto": "Sim, quando a perícia confirma.", "citacoes": [1, 3]},
        {"texto": "As contrárias negaram por EPI eficaz.", "citacoes": [2]},
    ]}
    kw = fake.chamadas[0]
    assert kw["model"] == "gpt-4o-mini" and kw["temperature"] == 0 and kw["timeout"] == 20
    assert kw["response_format"] is RespostaGerada
    usuario = kw["messages"][1]["content"]
    assert "#1 (RORSum, TRT2, 11ª Turma)\nEMENTA 1" in usuario and "#3 (RORSum" in usuario
    assert "ruído acima da NR-15" in usuario


def test_frase_sem_citacao_ou_indice_invalido_some(usar):
    usar(_FakeOpenAI([Frase(texto="Sem citação.", citacoes=[]),
                      Frase(texto="Fora do intervalo.", citacoes=[1, 4]),
                      Frase(texto="Zero.", citacoes=[0]),
                      Frase(texto="Válida.", citacoes=[2])]))
    assert client.post("/resposta", json=CORPO).json() == {"frases": [{"texto": "Válida.", "citacoes": [2]}]}


def test_nenhuma_frase_valida_devolve_lista_vazia(usar):
    usar(_FakeOpenAI([Frase(texto="Sem citação.", citacoes=[])]))
    resp = client.post("/resposta", json=CORPO)
    assert resp.status_code == 200 and resp.json() == {"frases": []}


def test_erro_da_openai_vira_503(usar):
    erro = openai.APITimeoutError(request=httpx.Request("POST", "https://api.openai.com"))
    usar(_FakeOpenAI(erro=erro))
    resp = client.post("/resposta", json=CORPO)
    assert resp.status_code == 503
    assert "indisponível" in resp.json()["detail"]


def test_mais_de_20_ids_422(usar):
    usar(_FakeOpenAI())
    corpo = {**CORPO, "ids": [str(uuid.uuid4()) for _ in range(21)]}
    assert client.post("/resposta", json=corpo).status_code == 422


def test_sem_sessao_401():
    app.dependency_overrides.clear()
    app.dependency_overrides[get_usuario_store] = lambda: None
    assert client.post("/resposta", json=CORPO).status_code == 401
    app.dependency_overrides.clear()


def test_ementa_longa_vai_com_comeco_e_fim(usar):
    from query.search.resposta import _trecho
    longa = "INÍCIO " + "x" * 5000 + " RECURSO PROVIDO."
    trecho = _trecho(longa)
    assert trecho.startswith("INÍCIO") and trecho.endswith("RECURSO PROVIDO.") and len(trecho) < 2100
