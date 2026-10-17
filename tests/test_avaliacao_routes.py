"""
Testes de GET /avaliacao/fila e POST /avaliacao/pares/{par_id}/rotulo
(query/api/avaliacao_routes.py).

Mesmo padrão de tests/test_conversa_routes.py: `app` real, com get_current_user,
get_avaliacao_store e get_avaliacao_doc_retriever substituídos — sem infra real.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from auth.store import Usuario
from avaliacao.juiz import TAMANHO_FUNDAMENTACAO
from avaliacao.store import Julgamento, Par, Tese
from query.api.app import app, get_current_user
from query.api.avaliacao_routes import get_avaliacao_doc_retriever, get_avaliacao_store
from query.enrichment.schema import EstruturaArgumentativa
from scraper.schema import DocumentoJuridico, TipoDocumento

_USUARIO = Usuario(
    id=uuid.uuid4(), email="  Especialista@Example.com ", hashed_password="x",
    nome="E", is_active=True, criado_em=datetime.now(timezone.utc),
)
_JUIZ = "humano:especialista@example.com"

_PAR_ID = uuid.uuid4()
_TESE = Tese(
    id=uuid.uuid4(),
    estrutura=EstruturaArgumentativa(tese_central="Horas extras são devidas.").model_dump(mode="json"),
    origem="gerada", tema="horas extras", split="dev",
)
_PAR = Par(id=_PAR_ID, tese_id=_TESE.id, documento_id="doc-1", corredores=["bm25", "vetorial"])


def _documento(fundamentacao: str = "Fundamentação do acórdão.") -> DocumentoJuridico:
    return DocumentoJuridico(
        id_documento="doc-1", tipo_documento=TipoDocumento.ACORDAO, hierarquia_categoria=4,
        numero_processo="RR-1-2021", tribunal="TST", ementa="Ementa do acórdão.",
        fundamentacao=fundamentacao, link_original="https://example.com/doc-1",
    )


class _FakeAvaliacaoStore:
    def __init__(self, fila: tuple[Par, Tese] | None = (_PAR, _TESE)) -> None:
        self.fila = fila
        self.metades = {_PAR_ID: "sorteada"}
        self.gravados: list[Julgamento] = []
        self.juizes_consultados: list[str] = []

    def proximo_da_fila(self, juiz: str):
        self.juizes_consultados.append(juiz)
        return self.fila

    def progresso(self, juiz: str) -> tuple[int, int]:
        return 3, 150

    def amostra(self) -> dict[uuid.UUID, str]:
        return self.metades

    def gravar_julgamento(self, j: Julgamento) -> None:
        self.gravados.append(j)


class _FakeRetriever:
    def __init__(self, docs: dict[str, DocumentoJuridico]) -> None:
        self.docs = docs

    def fetch(self, ids: list[str]) -> dict[str, DocumentoJuridico]:
        return {i: self.docs[i] for i in ids if i in self.docs}


@pytest.fixture(autouse=True)
def _emails(monkeypatch):
    monkeypatch.setenv("AVALIACAO_EMAILS", "outra@example.com, ESPECIALISTA@example.com ,")


@pytest.fixture
def store() -> _FakeAvaliacaoStore:
    return _FakeAvaliacaoStore()


@pytest.fixture
def retriever() -> _FakeRetriever:
    return _FakeRetriever({"doc-1": _documento()})


@pytest.fixture
def client(store, retriever):
    app.dependency_overrides[get_current_user] = lambda: _USUARIO
    app.dependency_overrides[get_avaliacao_store] = lambda: store
    app.dependency_overrides[get_avaliacao_doc_retriever] = lambda: retriever
    yield TestClient(app)
    app.dependency_overrides.clear()


# --------------------------------------------------------------------------- #
# GET /avaliacao/fila                                                          #
# --------------------------------------------------------------------------- #

def test_fila_retorna_par_sem_nota_do_jev(client, store):
    resp = client.get("/avaliacao/fila")
    assert resp.status_code == 200
    body = resp.json()
    assert set(body) == {"par", "feitos", "total"}
    assert (body["feitos"], body["total"]) == (3, 150)
    assert set(body["par"]) == {"id", "tese", "documento"}
    assert set(body["par"]["documento"]) == {
        "id", "ementa", "fundamentacao_inicio", "link_original", "numero_processo", "tribunal",
    }
    assert body["par"]["id"] == str(_PAR_ID)
    assert body["par"]["tese"]["tese_central"] == "Horas extras são devidas."
    assert body["par"]["documento"]["id"] == "doc-1"
    assert body["par"]["documento"]["ementa"] == "Ementa do acórdão."
    assert store.juizes_consultados == [_JUIZ]


def test_fila_trunca_fundamentacao_no_mesmo_trecho_do_jev(client, retriever):
    retriever.docs["doc-1"] = _documento("x" * (TAMANHO_FUNDAMENTACAO + 500))
    doc = client.get("/avaliacao/fila").json()["par"]["documento"]
    assert len(doc["fundamentacao_inicio"]) == TAMANHO_FUNDAMENTACAO


def test_fila_documento_nao_encontrado_nao_quebra(client, retriever):
    retriever.docs.clear()
    resp = client.get("/avaliacao/fila")
    assert resp.status_code == 200
    assert resp.json()["par"]["documento"] == {
        "id": "doc-1", "ementa": None, "fundamentacao_inicio": None,
        "link_original": None, "numero_processo": None, "tribunal": None,
    }


def test_fila_vazia_retorna_par_null(client, store):
    store.fila = None
    resp = client.get("/avaliacao/fila")
    assert resp.status_code == 200
    assert resp.json() == {"par": None, "feitos": 3, "total": 150}


# --------------------------------------------------------------------------- #
# Acesso                                                                       #
# --------------------------------------------------------------------------- #

def test_email_fora_da_lista_403(client, monkeypatch):
    monkeypatch.setenv("AVALIACAO_EMAILS", "outra@example.com")
    resp = client.get("/avaliacao/fila")
    assert resp.status_code == 403
    assert resp.json()["detail"] == "Acesso restrito à avaliação."
    resp = client.post(f"/avaliacao/pares/{_PAR_ID}/rotulo", json={"relevancia": 1, "stance": "neutro"})
    assert resp.status_code == 403


@pytest.mark.parametrize("valor", ["", " , ,"])
def test_lista_vazia_ninguem_tem_acesso(client, monkeypatch, valor):
    monkeypatch.setenv("AVALIACAO_EMAILS", valor)
    assert client.get("/avaliacao/fila").status_code == 403


def test_lista_ausente_ninguem_tem_acesso(client, monkeypatch):
    monkeypatch.delenv("AVALIACAO_EMAILS", raising=False)
    assert client.get("/avaliacao/fila").status_code == 403


# --------------------------------------------------------------------------- #
# POST /avaliacao/pares/{par_id}/rotulo                                        #
# --------------------------------------------------------------------------- #

def test_rotulo_grava_julgamento_humano(client, store):
    resp = client.post(f"/avaliacao/pares/{_PAR_ID}/rotulo", json={"relevancia": 2, "stance": "fortalece"})
    assert resp.status_code == 204
    assert store.gravados == [
        Julgamento(par_id=_PAR_ID, juiz=_JUIZ, rodada=1, relevancia=2, stance="fortalece")
    ]


@pytest.mark.parametrize("body", [
    {"relevancia": 4, "stance": "neutro"},
    {"relevancia": -1, "stance": "neutro"},
    {"relevancia": 1, "stance": "talvez"},
    {"relevancia": 1},
])
def test_rotulo_invalido_422(client, store, body):
    resp = client.post(f"/avaliacao/pares/{_PAR_ID}/rotulo", json=body)
    assert resp.status_code == 422
    assert store.gravados == []


@pytest.mark.parametrize("par_id", [str(uuid.uuid4()), "nao-e-uuid"])
def test_par_fora_da_amostra_404(client, store, par_id):
    resp = client.post(f"/avaliacao/pares/{par_id}/rotulo", json={"relevancia": 1, "stance": "neutro"})
    assert resp.status_code == 404
    assert resp.json()["detail"] == "Par fora da amostra."
    assert store.gravados == []
