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
import psycopg

from query.api.app import app, get_current_user, get_doc_retriever, get_openai, get_resposta_cache
from query.api.auth_routes import get_usuario_store
from query.enrichment.schema import EstruturaArgumentativa
from query.search.resposta import Citada, Desfecho, Fundamento, RespostaGerada, chave_da_resposta
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


def _gerada(**campos) -> RespostaGerada:
    """Resposta do modelo com as partes vazias, exceto as dadas."""
    vazia = Citada(citacoes=[], texto="")
    base = dict(desfechos=[], resposta=vazia, fundamentos=[], base_legal="", prova=vazia,
                negaram_por_outros_fatos=vazia, negaram_pelo_direito=vazia)
    return RespostaGerada(**{**base, **campos})


def _c(texto: str, citacoes: list[int]) -> Citada:
    return Citada(citacoes=citacoes, texto=texto)


def _fund(texto: str, citacoes: list[int], precedente: str = "") -> Fundamento:
    return Fundamento(quem_decidiu="TRT2", precedente_de_outro_ramo=precedente, citacoes=citacoes, texto=texto)


def _d(numero: int, pedido: str, fatos_da_premissa: bool = True) -> Desfecho:
    return Desfecho(numero=numero, motivo="m", pedido_da_tese=pedido, fatos_da_premissa=fatos_da_premissa)


class _FakeOpenAI:
    def __init__(self, gerada: RespostaGerada | None = None, erro: Exception | None = None):
        self.chamadas: list[dict] = []
        self.chat = SimpleNamespace(completions=SimpleNamespace(parse=self._parse))
        self._parsed = gerada or _gerada()
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


def test_partes_viram_frases_na_ordem_e_ementas_vem_do_banco_numeradas(usar, monkeypatch):
    monkeypatch.delenv("OPENAI_GEN_MODEL", raising=False)
    monkeypatch.delenv("OPENAI_GEN_TEMPERATURE", raising=False)
    fake = usar(_FakeOpenAI(_gerada(
        desfechos=[_d(1, "deferiu"), _d(2, "negou"), _d(3, "negou", fatos_da_premissa=False)],
        resposta=_c("Sim, quando a perícia confirma.", [1, 3, 1]),
        fundamentos=[_fund("A 11ª Turma do TRT2 entende assim.", [1])],
        base_legal="CLT, art. 189.",
        prova=_c("Para o pedido, é preciso provar: perícia.", [1]),
        negaram_por_outros_fatos=_c("As que negaram partiram de EPI eficaz.", [3]),
        negaram_pelo_direito=_c("As decisões contrárias negaram porque…", [2]),
    )))
    resp = client.post("/resposta", json=CORPO)
    assert resp.status_code == 200
    assert resp.json() == {
        "frases": [
            {"tipo": "resposta", "texto": "Sim, quando a perícia confirma.", "citacoes": [1, 3]},
            {"tipo": "fundamento", "texto": "A 11ª Turma do TRT2 entende assim.", "citacoes": [1]},
            {"tipo": "base_legal", "texto": "CLT, art. 189.", "citacoes": []},
            {"tipo": "prova", "texto": "Para o pedido, é preciso provar: perícia.", "citacoes": [1]},
            {"tipo": "divergencia", "texto": "As decisões contrárias negaram porque…", "citacoes": [2]},
            {"tipo": "divergencia", "texto": "As que negaram partiram de EPI eficaz.", "citacoes": [3]},
        ],
        "posicoes": [
            {"numero": 1, "posicao": "deferiu"}, {"numero": 2, "posicao": "negou"},
            {"numero": 3, "posicao": "fato_diferente"},
        ],
    }
    kw = fake.chamadas[0]
    assert kw["model"] == "gpt-4o-mini" and kw["temperature"] == 0 and kw["timeout"] == 30
    assert kw["response_format"] is RespostaGerada
    usuario = kw["messages"][1]["content"]
    assert "#1 (RORSum, TRT2, 11ª Turma)\nEMENTA 1" in usuario and "#3 (RORSum" in usuario
    assert "ruído acima da NR-15" in usuario


def test_frase_sem_citacao_ou_indice_invalido_some(usar):
    usar(_FakeOpenAI(_gerada(
        resposta=_c("Sem citação.", []),
        fundamentos=[_fund("Fora do intervalo, TRT2.", [1, 4]), _fund("Zero, TRT2.", [0]), _fund("Válida, TRT2.", [2])],
        prova=_c("Prova sem citação.", []),
    )))
    assert client.post("/resposta", json=CORPO).json() == {
        "frases": [{"tipo": "fundamento", "texto": "Válida, TRT2.", "citacoes": [2]}], "posicoes": [],
    }


def test_divergencia_so_cita_decisao_com_o_desfecho_certo(usar):
    """Quem negou por fato diferente não entra como "contrária", e vice-versa; sem citação certa, a frase sai."""
    usar(_FakeOpenAI(_gerada(
        desfechos=[_d(1, "deferiu"), _d(2, "negou", fatos_da_premissa=False), _d(3, "negou")],
        negaram_pelo_direito=_c("As decisões contrárias negaram porque EPI eficaz.", [2]),
        negaram_por_outros_fatos=_c("As que negaram partiram de EPI eficaz.", [2, 3, 1]),
    )))
    assert client.post("/resposta", json=CORPO).json()["frases"] == [
        {"tipo": "divergencia", "texto": "As que negaram partiram de EPI eficaz.", "citacoes": [2]},
    ]


def test_fundamento_sem_analogia_ou_de_outro_tribunal_some(usar):
    usar(_FakeOpenAI(_gerada(fundamentos=[
        _fund("O TRT2 aplica a tese do STF: EPI não elimina.", [1], precedente="Tema 555, aposentadoria especial"),
        _fund("O TRT2 aplica por analogia a tese do STF sobre aposentadoria especial.", [1], precedente="Tema 555"),
        _fund("O TRT12 entende assim.", [2]),  # a decisão #2 é do TRT2
    ])))
    assert client.post("/resposta", json=CORPO).json()["frases"] == [
        {"tipo": "fundamento", "texto": "O TRT2 aplica por analogia a tese do STF sobre aposentadoria especial.", "citacoes": [1]},
    ]


def test_posicoes_validas_vao_ao_cliente_sem_o_motivo(usar):
    usar(_FakeOpenAI(_gerada(desfechos=[_d(2, "negou", fatos_da_premissa=False), _d(1, "deferiu"),
                                        _d(1, "negou"), _d(9, "negou")])))
    assert client.post("/resposta", json=CORPO).json()["posicoes"] == [
        {"numero": 1, "posicao": "deferiu"}, {"numero": 2, "posicao": "fato_diferente"},
    ]


def test_nenhuma_frase_valida_devolve_lista_vazia(usar):
    usar(_FakeOpenAI(_gerada(resposta=_c("Sem citação.", []))))
    resp = client.post("/resposta", json=CORPO)
    assert resp.status_code == 200 and resp.json() == {"frases": [], "posicoes": []}


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


class _FakeCache:
    def __init__(self, salvas: dict | None = None, erro: bool = False):
        self.salvas = dict(salvas or {})
        self._erro = erro

    def ler(self, chave):
        if self._erro:
            raise psycopg.OperationalError("banco fora")
        return self.salvas.get(chave)

    def gravar(self, chave, resposta):
        if self._erro:
            raise psycopg.OperationalError("banco fora")
        self.salvas[chave] = resposta


_UMA_FRASE = dict(desfechos=[_d(1, "deferiu")], resposta=_c("Sim, quando a perícia confirma.", [1]))


def test_resposta_gerada_vai_para_o_cache_e_a_segunda_vez_nao_chama_a_openai(usar):
    fake = usar(_FakeOpenAI(_gerada(**_UMA_FRASE)))
    cache = _FakeCache()
    app.dependency_overrides[get_resposta_cache] = lambda: cache
    primeira = client.post("/resposta", json=CORPO)
    segunda = client.post("/resposta", json=CORPO)
    assert primeira.status_code == segunda.status_code == 200
    assert primeira.json() == segunda.json()
    assert len(fake.chamadas) == 1 and len(cache.salvas) == 1


def test_resposta_vazia_nao_vai_para_o_cache(usar):
    usar(_FakeOpenAI(_gerada()))
    cache = _FakeCache()
    app.dependency_overrides[get_resposta_cache] = lambda: cache
    assert client.post("/resposta", json=CORPO).json()["frases"] == []
    assert cache.salvas == {}


def test_cache_fora_do_ar_nao_derruba_a_resposta(usar):
    fake = usar(_FakeOpenAI(_gerada(**_UMA_FRASE)))
    app.dependency_overrides[get_resposta_cache] = lambda: _FakeCache(erro=True)
    resp = client.post("/resposta", json=CORPO)
    assert resp.status_code == 200 and resp.json()["frases"][0]["citacoes"] == [1]
    assert len(fake.chamadas) == 1


def test_chave_muda_com_a_lista_a_tese_e_o_modelo(monkeypatch):
    monkeypatch.delenv("OPENAI_GEN_MODEL", raising=False)
    tese = EstruturaArgumentativa(tese_central="ruído")
    base = chave_da_resposta(tese, IDS)
    assert base == chave_da_resposta(EstruturaArgumentativa(tese_central="ruído"), list(IDS))
    assert base != chave_da_resposta(tese, IDS[::-1])
    assert base != chave_da_resposta(EstruturaArgumentativa(tese_central="calor"), IDS)
    monkeypatch.setenv("OPENAI_GEN_MODEL", "outro-modelo")
    assert base != chave_da_resposta(tese, IDS)
