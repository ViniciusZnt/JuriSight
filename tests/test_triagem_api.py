"""Testes de POST /triagem (query/api/app.py + query/search/triagem*.py), com OpenAI e cache falsos."""
from __future__ import annotations

import uuid

import httpx
import openai
import psycopg
import pytest
from fastapi.testclient import TestClient

from query.api.app import app, get_current_user, get_doc_retriever, get_openai, get_triagem_cache, get_uso_diario
from query.api.auth_routes import get_usuario_store
from query.api.uso_diario import LimiteDiarioExcedido
from query.enrichment.schema import EstruturaArgumentativa
from query.search.triagem import ItemTriagem, TriagemGerada, chave_da_triagem
from tests.fakes import FakeOpenAI, documento_fake, usuario_fake

IDS = [str(uuid.uuid4()) for _ in range(2)]
TESE = {"tese_central": "calor acima do limite de tolerância"}
CORPO = {"estrutura": TESE, "ids": IDS}


class _FakeRetriever:
    def __init__(self):
        self.pedidos: list[list[str]] = []

    def fetch(self, ids, completo=True):
        self.pedidos.append(list(ids))
        return {i: documento_fake(ementa=f"EMENTA {i}") for i in ids}


class _FakeCache:
    def __init__(self, salvas=None, erro=False):
        self.salvas, self._erro = dict(salvas or {}), erro

    def ler_varios(self, chaves):
        if self._erro:
            raise psycopg.OperationalError("banco fora")
        return {c: self.salvas[c] for c in chaves if c in self.salvas}

    def gravar_varios(self, itens):
        if self._erro:
            raise psycopg.OperationalError("banco fora")
        self.salvas.update(itens)


class _FakeUso:
    def __init__(self, limite=10):
        self.limite, self.acoes = limite, []

    def consumir(self, usuario_id, acao):
        if len(self.acoes) >= self.limite:
            raise LimiteDiarioExcedido("Você atingiu o limite de uso da IA de hoje.")
        self.acoes.append(acao)


def _itens(*notas):
    return TriagemGerada(itens=[ItemTriagem(numero=n, motivo=f"m{n}", nota=nota, pedido_da_tese="deferiu",
                                            fatos_da_premissa=True) for n, nota in enumerate(notas, start=1)])


def _salva(doc_id, nota=3):
    return {chave_da_triagem(EstruturaArgumentativa(**TESE), doc_id): {"nota": nota, "posicao": "negou", "motivo": "c"}}


@pytest.fixture
def usar():
    estado = {}

    def _usar(fake, cache=None, uso=None):
        estado.update(retriever=_FakeRetriever(), cache=cache or _FakeCache(), uso=uso or _FakeUso())
        app.dependency_overrides[get_current_user] = lambda: usuario_fake()
        app.dependency_overrides[get_doc_retriever] = lambda: estado["retriever"]
        app.dependency_overrides[get_openai] = lambda: fake
        app.dependency_overrides[get_triagem_cache] = lambda: estado["cache"]
        app.dependency_overrides[get_uso_diario] = lambda: estado["uso"]
        return estado

    yield _usar
    app.dependency_overrides.clear()


client = TestClient(app)


def test_avalia_e_devolve_por_id_e_grava_no_cache(usar):
    estado = usar(FakeOpenAI(_itens(3, 1)))
    resp = client.post("/triagem", json=CORPO)
    assert resp.status_code == 200
    assert resp.json() == {"avaliacoes": [
        {"id": IDS[0], "nota": 3, "posicao": "deferiu", "motivo": "m1"},
        {"id": IDS[1], "nota": 1, "posicao": "deferiu", "motivo": "m2"}]}
    assert len(estado["cache"].salvas) == 2


def test_so_os_ids_sem_cache_vao_a_openai(usar):
    fake = FakeOpenAI(_itens(2))
    estado = usar(fake, cache=_FakeCache(_salva(IDS[0])))
    corpo = client.post("/triagem", json=CORPO).json()
    assert estado["retriever"].pedidos == [[IDS[1]]]
    assert f"EMENTA {IDS[1]}" in fake.chamadas[0]["messages"][1]["content"]
    assert f"EMENTA {IDS[0]}" not in fake.chamadas[0]["messages"][1]["content"]
    assert [a["id"] for a in corpo["avaliacoes"]] == IDS
    assert corpo["avaliacoes"][0] == {"id": IDS[0], "nota": 3, "posicao": "negou", "motivo": "c"}


def test_tudo_em_cache_nao_chama_a_openai_nem_conta_limite(usar):
    fake = FakeOpenAI(_itens())
    estado = usar(fake, cache=_FakeCache({**_salva(IDS[0]), **_salva(IDS[1], 0)}))
    assert len(client.post("/triagem", json=CORPO).json()["avaliacoes"]) == 2
    assert fake.chamadas == [] and estado["uso"].acoes == []


def test_apenas_cache_nunca_chama_a_openai(usar):
    fake = FakeOpenAI(_itens(3, 3))
    estado = usar(fake, cache=_FakeCache(_salva(IDS[0])))
    corpo = client.post("/triagem", json={**CORPO, "apenas_cache": True}).json()
    assert [a["id"] for a in corpo["avaliacoes"]] == [IDS[0]]
    assert fake.chamadas == [] and estado["uso"].acoes == []


def test_lote_que_chama_a_openai_conta_um_uso_de_triagem(usar):
    estado = usar(FakeOpenAI(_itens(3, 3)))
    client.post("/triagem", json=CORPO)
    assert estado["uso"].acoes == ["triagem"]


def test_limite_estourado_429_sem_chamar_a_openai(usar):
    fake = FakeOpenAI(_itens(3, 3))
    usar(fake, uso=_FakeUso(limite=0))
    resp = client.post("/triagem", json=CORPO)
    assert resp.status_code == 429 and "limite" in resp.json()["detail"]
    assert fake.chamadas == []


def test_openai_fora_vira_503_com_mensagem(usar):
    erro = openai.APIConnectionError(request=httpx.Request("POST", "https://api.openai.com"))
    usar(FakeOpenAI(erro=erro))
    resp = client.post("/triagem", json=CORPO)
    assert resp.status_code == 503 and resp.json()["detail"] == "Avaliação por IA indisponível agora."


def test_cache_fora_do_ar_avalia_mesmo_assim(usar):
    fake = FakeOpenAI(_itens(2, 2))
    usar(fake, cache=_FakeCache(erro=True))
    resp = client.post("/triagem", json=CORPO)
    assert resp.status_code == 200 and len(resp.json()["avaliacoes"]) == 2


def test_mais_de_10_ids_422(usar):
    usar(FakeOpenAI(_itens()))
    corpo = {"estrutura": TESE, "ids": [str(uuid.uuid4()) for _ in range(11)]}
    assert client.post("/triagem", json=corpo).status_code == 422


def test_estrutura_sem_tese_422(usar):
    fake = FakeOpenAI(_itens())
    usar(fake)
    resp = client.post("/triagem", json={"estrutura": {"tribunais": ["TRT12"]}, "ids": IDS})
    assert resp.status_code == 422 and fake.chamadas == []


def test_sem_sessao_401():
    app.dependency_overrides.clear()
    app.dependency_overrides[get_usuario_store] = lambda: None
    try:
        assert client.post("/triagem", json=CORPO).status_code == 401
    finally:
        app.dependency_overrides.clear()
