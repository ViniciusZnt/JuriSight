"""
Testes de GET/POST /conversas, PATCH /conversas/{id}, POST /conversas/{id}/versoes
e DELETE /conversas/{id} (query/api/conversa_routes.py).

Mesmo espírito de tests/test_api.py: usa o `app` real de query/api/app.py (o
conversa_router já está montado lá), com get_current_user e get_conversa_store
substituídos via dependency_overrides — nenhuma infra real.

_FakeConversaStore replica o invariante de segurança do ConversaStore real: toda
operação filtra por (id, usuario_id) — é o que os testes de isolamento entre
usuários abaixo verificam. Também replica a numeração sequencial de versões
(jsonb_array_length(versoes) + 1 no store real).
"""
from __future__ import annotations

import uuid
from dataclasses import replace
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from conversations.store import Conversa, ConversaNaoEncontradaError
from query.api.app import app, get_current_user
from query.api.conversa_routes import get_conversa_store
from query.enrichment.schema import EstruturaArgumentativa
from query.search.result_formatter import ResultCard
from scraper.schema import Provimento, TipoDocumento
from tests.fakes import usuario_fake

_USUARIO_A = usuario_fake()
_USUARIO_B = usuario_fake("b@example.com", "B")


class _FakeConversaStore:
    """Dict em memória, mesma interface pública do ConversaStore — e o mesmo
    invariante de segurança: toda leitura/escrita checa usuario_id."""

    def __init__(self) -> None:
        self._por_id: dict[uuid.UUID, Conversa] = {}

    def create(self, usuario_id, titulo) -> Conversa:
        now = datetime.now(timezone.utc)
        c = Conversa(id=uuid.uuid4(), usuario_id=usuario_id, titulo=titulo, criado_em=now, atualizado_em=now, versoes=[])
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

    def add_versao(self, conversa_id, usuario_id, *, estrutura, has_file, file_name, pdf_extraido, aviso, resultados) -> Conversa:
        c = self._get_or_raise(conversa_id, usuario_id)
        versao = {
            "numero": len(c.versoes) + 1,
            "estrutura": estrutura, "has_file": has_file, "file_name": file_name,
            "pdf_extraido": pdf_extraido, "aviso": aviso, "resultados": resultados,
            "criado_em": datetime.now(timezone.utc).isoformat(),
        }
        novo = replace(c, versoes=[*c.versoes, versao])
        self._por_id[conversa_id] = novo
        return novo

    def atualizar_versao(self, conversa_id, usuario_id, numero, campos) -> Conversa:
        c = self._get_or_raise(conversa_id, usuario_id)
        if not 1 <= numero <= len(c.versoes):
            raise ConversaNaoEncontradaError(conversa_id)
        versoes = [dict(v) for v in c.versoes]
        versoes[numero - 1].update(campos)
        novo = replace(c, versoes=versoes)
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


def _estrutura_dict(tese: str = "tese de teste") -> dict:
    return EstruturaArgumentativa(tese_central=tese).model_dump(mode="json")


def _resultado_dict(id_: str = "d1") -> dict:
    return ResultCard(
        id=id_, tipo_documento=TipoDocumento.ACORDAO.value, hierarquia_categoria=4,
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
    assert body["versoes"] == []

    resp = client.get("/conversas")
    assert resp.status_code == 200
    assert [c["id"] for c in resp.json()] == [body["id"]]


def test_renomear(client):
    criada = client.post("/conversas", json={"titulo": "Original"}).json()
    resp = client.patch(f"/conversas/{criada['id']}", json={"titulo": "Renomeada"})
    assert resp.status_code == 200
    assert resp.json()["titulo"] == "Renomeada"


def test_adicionar_versoes_acumula_nao_sobrescreve(client):
    """O ponto central do versionamento: cada busca vira uma versão NOVA
    (V1, V2, ...), nenhuma substitui a anterior — é o que dá o histórico
    navegável no dropdown do frontend."""
    criada = client.post("/conversas", json={"titulo": "P"}).json()

    resp = client.post(
        f"/conversas/{criada['id']}/versoes",
        json={"estrutura": _estrutura_dict("tese v1"), "has_file": False, "resultados": [_resultado_dict("d1")]},
    )
    assert resp.status_code == 201
    assert len(resp.json()["versoes"]) == 1
    assert resp.json()["versoes"][0]["numero"] == 1
    assert resp.json()["versoes"][0]["estrutura"]["tese_central"] == "tese v1"

    # "Refinar consulta": busca de novo na MESMA conversa.
    resp = client.post(
        f"/conversas/{criada['id']}/versoes",
        json={"estrutura": _estrutura_dict("tese v2"), "has_file": False, "resultados": [_resultado_dict("d2")]},
    )
    assert resp.status_code == 201
    versoes = resp.json()["versoes"]
    assert len(versoes) == 2  # V1 continua lá
    assert versoes[0]["numero"] == 1 and versoes[0]["estrutura"]["tese_central"] == "tese v1"
    assert versoes[1]["numero"] == 2 and versoes[1]["estrutura"]["tese_central"] == "tese v2"

    # Persistiu de verdade — relendo a lista mostra as duas versões.
    resp = client.get("/conversas")
    assert len(resp.json()[0]["versoes"]) == 2


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
    assert client_b.post(
        f"/conversas/{criada['id']}/versoes",
        json={"estrutura": _estrutura_dict(), "has_file": False},
    ).status_code == 404


def test_conversa_inexistente_404(client):
    resp = client.patch(f"/conversas/{uuid.uuid4()}", json={"titulo": "x"})
    assert resp.status_code == 404
    assert resp.json() == {"detail": "Conversa não encontrada."}
    assert client.get("/conversas").status_code == 200  # sanity: rota de leitura não quebra


def test_id_malformado_404(client):
    resp = client.patch("/conversas/nao-eh-uuid", json={"titulo": "x"})
    assert resp.status_code == 404
    assert resp.json() == {"detail": "Conversa não encontrada."}


# --------------------------------------------------------------------------- #
# PATCH /conversas/{id}/versoes/{numero} — voto "É relevante"                  #
# --------------------------------------------------------------------------- #

def _com_versoes(client, n=2) -> str:
    criada = client.post("/conversas", json={"titulo": "P"}).json()
    for i in range(n):
        client.post(f"/conversas/{criada['id']}/versoes",
                    json={"estrutura": _estrutura_dict(f"v{i + 1}"), "has_file": False, "resultados": [_resultado_dict()]})
    return criada["id"]


def test_patch_versao_grava_relevantes_e_devolve_conversa(client):
    cid = _com_versoes(client)
    ids = [str(uuid.uuid4()), str(uuid.uuid4())]
    resp = client.patch(f"/conversas/{cid}/versoes/2", json={"relevantes_usuario": ids})
    assert resp.status_code == 200
    versoes = resp.json()["versoes"]
    assert versoes[1]["relevantes_usuario"] == ids
    assert versoes[0]["relevantes_usuario"] == []
    assert versoes[1]["estrutura"]["tese_central"] == "v2"


def test_versao_antiga_sem_campo_vem_com_lista_vazia(client):
    cid = _com_versoes(client, 1)
    assert client.get("/conversas").json()[0]["versoes"][0]["relevantes_usuario"] == []
    assert cid


def test_patch_versao_inexistente_404(client):
    cid = _com_versoes(client, 1)
    assert client.patch(f"/conversas/{cid}/versoes/3", json={"relevantes_usuario": []}).status_code == 404


def test_patch_versao_de_outro_usuario_404(client):
    cid = _com_versoes(client, 1)
    app.dependency_overrides[get_current_user] = lambda: _USUARIO_B
    resp = TestClient(app).patch(f"/conversas/{cid}/versoes/1", json={"relevantes_usuario": []})
    assert resp.status_code == 404


def test_patch_mais_de_50_ids_422(client):
    cid = _com_versoes(client, 1)
    ids = [str(uuid.uuid4()) for _ in range(51)]
    assert client.patch(f"/conversas/{cid}/versoes/1", json={"relevantes_usuario": ids}).status_code == 422


def test_patch_versao_grava_resposta_ids_sem_tocar_relevantes(client):
    cid = _com_versoes(client, 1)
    rel, resp = [str(uuid.uuid4())], [str(uuid.uuid4()), str(uuid.uuid4())]
    client.patch(f"/conversas/{cid}/versoes/1", json={"relevantes_usuario": rel})
    v = client.patch(f"/conversas/{cid}/versoes/1", json={"resposta_ids": resp}).json()["versoes"][0]
    assert v["resposta_ids"] == resp and v["relevantes_usuario"] == rel


def test_patch_versao_sem_campo_422(client):
    cid = _com_versoes(client, 1)
    assert client.patch(f"/conversas/{cid}/versoes/1", json={}).status_code == 422


def test_patch_mais_de_25_resposta_ids_422(client):
    cid = _com_versoes(client, 1)
    ids = [str(uuid.uuid4()) for _ in range(26)]
    assert client.patch(f"/conversas/{cid}/versoes/1", json={"resposta_ids": ids}).status_code == 422
