"""
Testes de POST /enrich, POST /query, GET /document/{id} e GET /health
(query/api/app.py).

Nenhuma infra real é usada: hybrid/doc_retriever/enricher são substituídos via
app.dependency_overrides (por isso o TestClient NÃO é usado como context manager
— o lifespan real, que conectaria a Postgres/Chroma/Ollama, nunca precisa rodar).
pdf_extractor.extract_text é monkeypatchado quando o teste precisa controlar o
resultado da extração sem depender de um PDF de verdade.

/enrich, /query e /document/{id} agora exigem sessão (get_current_user, ver
query/api/auth_routes.py) — como este arquivo testa a lógica de negócio, não
autenticação (isso é tests/test_auth_routes.py), a autouse fixture abaixo
substitui get_current_user por um usuário fake em TODO teste, sem precisar
repetir isso em cada um.
"""
import uuid
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

import query.api.app as api_app
from auth.store import Usuario
from query.api.app import app, get_current_user, get_doc_retriever, get_enricher, get_hybrid, get_reranker, get_uso_diario
from query.api.auth_routes import get_usuario_store
from query.api.filtros_routes import get_filtro_store
from query.api.uso_diario import LimiteDiarioExcedido
from query.enrichment.pdf_extractor import PDFSemTextoError
from query.enrichment.query_enrichment import Extracao, _montar_conteudo
from query.enrichment.schema import EstruturaArgumentativa
from query.filtros.dispositivos import rotulo
from query.filtros.store import ContagemFiltros, FiltroIndisponivel, SugestaoDispositivo
from query.search.result_formatter import ResultCard
from scraper.schema import DocumentoJuridico, Provimento, TipoDocumento

_USUARIO_FAKE = Usuario(
    id=uuid.uuid4(),
    email="teste@example.com",
    hashed_password="hash-nao-usado-neste-teste",
    nome="Usuário de Teste",
    is_active=True,
    criado_em=datetime.now(timezone.utc),
)


class _FakeHybrid:
    def __init__(self, resultados: list[tuple[str, float]]):
        self._resultados = resultados
        self.calls: list[dict] = []

    def search(self, query, n_results, where=None, *, bm25_query=None, provimento=None, documento_ids=None, canais=None):
        self.calls.append(
            {"query": query, "n_results": n_results, "bm25_query": bm25_query, "provimento": provimento,
             "documento_ids": documento_ids}
        )
        achados = [r for r in self._resultados if documento_ids is None or r[0] in documento_ids]
        if canais is not None:
            canais.update({doc_id: ["semantica"] for doc_id, _ in achados})
        return achados[:n_results]


class _FakeReranker:
    """Passthrough: devolve scores estritamente decrescentes na MESMA ordem de
    entrada, então o sort por score em query/api/app.py não muda a ordem que
    já veio do (fake) RRF — os testes abaixo continuam testando a lógica de
    filtro/hierarquia/paginação sem precisar saber de re-ranking."""

    def rerank_scores(self, query: str, passagens: list[str]) -> list[float]:
        return [1.0 - i * 0.01 for i in range(len(passagens))]


class _FakeDocRetriever:
    def __init__(self, docs: dict[str, DocumentoJuridico]):
        self._docs = docs

    def fetch(self, ids):
        return {i: self._docs[i] for i in ids if i in self._docs}


class _FakeEnricher:
    def __init__(self, estrutura: EstruturaArgumentativa | None = None, sugeridas: list[str] | None = None,
                 dispositivos: list[str] | None = None):
        self.estrutura = estrutura or EstruturaArgumentativa(tese_central="tese fake")
        self.sugeridas = sugeridas or []
        self.dispositivos = dispositivos or []
        self.calls: list[tuple] = []

    def resumir_bloco(self, texto: str) -> str:
        return texto[:20]

    def condensar(self, resumos: list[str]) -> str:
        return " ".join(resumos)

    def extrair(self, texto_caso, intencao=None):
        self.calls.append((texto_caso, intencao))
        _montar_conteudo(texto_caso, intencao)  # levanta ValueError se ambos vazios
        return Extracao(self.estrutura, self.sugeridas, self.dispositivos)


def _doc(**kwargs) -> DocumentoJuridico:
    base = dict(
        id_documento="x",
        tipo_documento=TipoDocumento.ACORDAO,
        hierarquia_categoria=4,
        numero_processo="RR-1-2021",
        tribunal="TST",
        relator="Min. Fulano",
        ementa="Ementa.",
        provimento=Provimento.APROVADO,
    )
    base.update(kwargs)
    return DocumentoJuridico(**base)


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture(autouse=True)
def _usuario_autenticado():
    """Simula uma sessão válida em toda rota — estes testes cobrem a lógica de
    negócio de /enrich, /query, /document/{id}, não autenticação em si."""
    app.dependency_overrides[get_current_user] = lambda: _USUARIO_FAKE
    yield
    app.dependency_overrides.clear()


@pytest.fixture(autouse=True)
def _reranker_passthrough():
    """O reranker real (query/search/reranker.py) baixa/carrega um modelo ONNX
    — nunca deve rodar em teste. Os testes de /query abaixo testam filtro/
    hierarquia/paginação, não a qualidade do re-ranking em si (isso é
    tests/test_reranker.py)."""
    app.dependency_overrides[get_reranker] = lambda: _FakeReranker()
    yield


# --------------------------------------------------------------------------- #
# GET /health                                                                  #
# --------------------------------------------------------------------------- #

def test_health(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


# --------------------------------------------------------------------------- #
# Autenticação exigida (regressão — prova que get_current_user está mesmo      #
# aplicado, não só a fixture autouse escondendo isso)                         #
# --------------------------------------------------------------------------- #

@pytest.fixture(autouse=True)
def _usuario_store_dummy():
    """get_current_user declara `store: UsuarioStore = Depends(get_usuario_store)`
    — o FastAPI resolve isso ANTES de rodar o corpo da função, mesmo quando o
    corpo nunca chega a usar `store` (cookie ausente já levanta 401 antes). Sem
    isto, os testes _sem_sessao abaixo dariam 500 (AttributeError) em vez de
    401, só porque o lifespan real (que preenche app.state.usuario_store) não
    roda neste arquivo — não é um bug do endpoint, é só o app real precisar de
    um valor onde este teste não faz nenhuma chamada ao Postgres."""
    app.dependency_overrides[get_usuario_store] = lambda: None
    yield


def test_enrich_sem_sessao_401(client):
    app.dependency_overrides.pop(get_current_user, None)  # desliga o override desta fixture
    resp = client.post("/enrich", data={"intencao": "teste"})
    assert resp.status_code == 401


def test_query_sem_sessao_401(client):
    app.dependency_overrides.pop(get_current_user, None)
    resp = client.post("/query", json={"estrutura": EstruturaArgumentativa(tese_central="x").model_dump()})
    assert resp.status_code == 401


def test_document_sem_sessao_401(client):
    app.dependency_overrides.pop(get_current_user, None)
    resp = client.get("/document/qualquer-id")
    assert resp.status_code == 401


def test_health_nao_exige_sessao(client):
    # /health é a única rota pública de propósito (liveness) — sem override
    # nenhum, ainda deve responder 200.
    app.dependency_overrides.pop(get_current_user, None)
    resp = client.get("/health")
    assert resp.status_code == 200


# --------------------------------------------------------------------------- #
# POST /enrich                                                                 #
# --------------------------------------------------------------------------- #

def test_enrich_sem_pdf_com_intencao_fa01(client):
    fake_enricher = _FakeEnricher()
    app.dependency_overrides[get_enricher] = lambda: fake_enricher

    resp = client.post("/enrich", data={"intencao": "adicional de insalubridade"})

    assert resp.status_code == 200
    body = resp.json()
    assert body["pdf_extraido"] is None
    assert body["aviso"] is None
    assert fake_enricher.calls == [(None, "adicional de insalubridade")]


class _UsoEsgotado:
    def __init__(self):
        self.acoes = []

    def consumir(self, usuario_id, acao):
        self.acoes.append(acao)
        raise LimiteDiarioExcedido("Você atingiu o limite de 30 consultas por dia. Ele renova à meia-noite.")


@pytest.mark.parametrize("rota,kwargs", [
    ("/enrich", {"data": {"intencao": "adicional de insalubridade"}}),
    ("/query", {"json": {"estrutura": {"tese_central": "ruído"}}}),
])
def test_limite_diario_esgotado_vira_429_antes_de_gastar(client, rota, kwargs):
    fake_enricher, uso = _FakeEnricher(), _UsoEsgotado()
    app.dependency_overrides[get_enricher] = lambda: fake_enricher
    app.dependency_overrides[get_uso_diario] = lambda: uso
    resp = client.post(rota, **kwargs)
    assert resp.status_code == 429
    assert resp.json()["detail"].startswith("Você atingiu o limite de 30 consultas por dia")
    assert uso.acoes == [rota.strip("/")] and fake_enricher.calls == []


def test_enrich_pdf_extraido_com_sucesso(client, monkeypatch):
    monkeypatch.setattr(api_app.pdf_extractor, "extract_text", lambda pdf_bytes: "texto do processo")
    fake_enricher = _FakeEnricher()
    app.dependency_overrides[get_enricher] = lambda: fake_enricher

    resp = client.post("/enrich", files={"pdf": ("caso.pdf", b"conteudo", "application/pdf")})

    assert resp.status_code == 200
    body = resp.json()
    assert body["pdf_extraido"] is True
    assert body["aviso"] is None
    assert fake_enricher.calls == [("texto do processo", None)]


def test_enrich_fa02_com_intencao_prossegue_200(client, monkeypatch):
    def _falha(pdf_bytes):
        raise PDFSemTextoError("sem texto")

    monkeypatch.setattr(api_app.pdf_extractor, "extract_text", _falha)
    fake_enricher = _FakeEnricher()
    app.dependency_overrides[get_enricher] = lambda: fake_enricher

    resp = client.post(
        "/enrich",
        files={"pdf": ("scan.pdf", b"conteudo", "application/pdf")},
        data={"intencao": "adicional de insalubridade"},
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["pdf_extraido"] is False
    assert body["aviso"] is not None
    assert fake_enricher.calls == [(None, "adicional de insalubridade")]


def test_enrich_fa02_sem_intencao_422(client, monkeypatch):
    def _falha(pdf_bytes):
        raise PDFSemTextoError("sem texto")

    monkeypatch.setattr(api_app.pdf_extractor, "extract_text", _falha)
    app.dependency_overrides[get_enricher] = lambda: _FakeEnricher()

    resp = client.post("/enrich", files={"pdf": ("scan.pdf", b"conteudo", "application/pdf")})

    assert resp.status_code == 422


def test_enrich_pdf_acima_do_limite_413_sem_chamar_o_llm(client, monkeypatch):
    fake_enricher = _FakeEnricher()
    app.dependency_overrides[get_enricher] = lambda: fake_enricher
    monkeypatch.setattr(api_app, "MAX_PDF_MB", 1)

    resp = client.post("/enrich", files={"pdf": ("caso.pdf", b"x" * (1024 * 1024 + 1), "application/pdf")})

    assert resp.status_code == 413
    assert "limite de 1 MB" in resp.json()["detail"]
    assert fake_enricher.calls == []


def test_enrich_pdf_no_limite_exato_passa_do_corte(client, monkeypatch):
    app.dependency_overrides[get_enricher] = lambda: _FakeEnricher()
    monkeypatch.setattr(api_app, "MAX_PDF_MB", 1)

    # exatamente no limite não é recusado por tamanho (cai no 400 de PDF inválido, como antes)
    resp = client.post("/enrich", files={"pdf": ("caso.pdf", b"x" * (1024 * 1024), "application/pdf")})

    assert resp.status_code == 400


def test_enrich_pdf_corrompido_400(client):
    app.dependency_overrides[get_enricher] = lambda: _FakeEnricher()

    # bytes que não são um PDF de verdade — pdfplumber real levanta ao tentar abrir.
    resp = client.post("/enrich", files={"pdf": ("caso.pdf", b"isto nao e um pdf", "application/pdf")})

    assert resp.status_code == 400


# --------------------------------------------------------------------------- #
# _normalizar_scores (helper do re-ranking)                                   #
# --------------------------------------------------------------------------- #

def test_normalizar_scores_espalha_entre_0_e_1():
    assert api_app._normalizar_scores([0.97, 0.98, 0.999]) == [0.0, pytest.approx((0.98 - 0.97) / (0.999 - 0.97)), 1.0]


def test_normalizar_scores_vazio():
    assert api_app._normalizar_scores([]) == []


def test_normalizar_scores_sem_variacao_nao_divide_por_zero():
    assert api_app._normalizar_scores([0.5]) == [1.0]
    assert api_app._normalizar_scores([0.5, 0.5, 0.5]) == [1.0, 1.0, 1.0]


# --------------------------------------------------------------------------- #
# POST /query                                                                  #
# --------------------------------------------------------------------------- #

def test_query_fim_a_fim_ordena_e_formata(client):
    docs = {"a-id": _doc(), "b-id": _doc()}

    app.dependency_overrides[get_hybrid] = lambda: _FakeHybrid([("a-id", 9.0), ("b-id", 1.0)])
    app.dependency_overrides[get_doc_retriever] = lambda: _FakeDocRetriever(docs)

    resp = client.post("/query", json={"estrutura": {"tese_central": "insalubridade"}})

    assert resp.status_code == 200
    body = resp.json()
    # a ordem final é a do reranker (o fake mantém a ordem de entrada).
    assert [card["id"] for card in body] == ["a-id", "b-id"]
    assert body[0]["canais"] == ["semantica"]


def test_query_explicacao_devolve_texto_semantico_e_termos(client):
    resp = client.post("/query/explicacao", json={"estrutura": {
        "tese_central": "A gestante tem estabilidade.", "pedido_principal": "reintegração",
        "dispositivos": ["b_ii_art_10_adct"], "expressoes": ["estabilidade da gestante"]}})

    assert resp.status_code == 200
    assert resp.json() == {
        "semantica": "A gestante tem estabilidade.",
        "termos": ["reintegração", "ADCT art. 10, II, b", "estabilidade da gestante"],
    }


def test_query_explicacao_estrutura_vazia_422(client):
    assert client.post("/query/explicacao", json={"estrutura": {}}).status_code == 422


def test_query_explicacao_sem_sessao_401(client):
    app.dependency_overrides.pop(get_current_user, None)
    assert client.post("/query/explicacao", json={"estrutura": {"tese_central": "x"}}).status_code == 401


def test_query_estrutura_vazia_422(client):
    app.dependency_overrides[get_hybrid] = lambda: _FakeHybrid([])
    app.dependency_overrides[get_doc_retriever] = lambda: _FakeDocRetriever({})

    resp = client.post("/query", json={"estrutura": {}})

    assert resp.status_code == 422


def test_query_filtro_provimento_reduz_resultados_e_filtra_nos_canais(client):
    favoravel = _doc(provimento=Provimento.APROVADO)
    desfavoravel = _doc(provimento=Provimento.NEGADO)
    docs = {"favoravel": favoravel, "desfavoravel": desfavoravel}

    fake_hybrid = _FakeHybrid([("favoravel", 2.0), ("desfavoravel", 1.0)])
    app.dependency_overrides[get_hybrid] = lambda: fake_hybrid
    app.dependency_overrides[get_doc_retriever] = lambda: _FakeDocRetriever(docs)

    resp = client.post(
        "/query",
        json={"estrutura": {"tese_central": "insalubridade"}, "provimento": "APROVADO"},
    )

    assert resp.status_code == 200
    body = resp.json()
    assert [card["id"] for card in body] == ["favoravel"]
    # provimento filtrado dentro dos canais: pool normal, e o valor chega ao hybrid
    assert fake_hybrid.calls[0]["n_results"] == api_app.N_CANDIDATOS_PARA_RERANK
    assert fake_hybrid.calls[0]["provimento"] == "APROVADO"


def test_query_sem_filtro_usa_pool_de_rerank(client):
    """Sem filtro, o pool pedido ao hybrid search é N_CANDIDATOS_PARA_RERANK
    (maior que N_RESULTS_FINAL) — o re-ranking precisa de mais candidatos que
    o corte final pra ter o que escolher (ver query/api/app.py::query)."""
    doc = _doc()
    fake_hybrid = _FakeHybrid([("doc-1", 1.0)])
    app.dependency_overrides[get_hybrid] = lambda: fake_hybrid
    app.dependency_overrides[get_doc_retriever] = lambda: _FakeDocRetriever({"doc-1": doc})

    client.post("/query", json={"estrutura": {"tese_central": "insalubridade"}})

    assert fake_hybrid.calls[0]["n_results"] == api_app.N_CANDIDATOS_PARA_RERANK


def test_query_reranking_promove_candidato_mal_rankeado_pelo_rrf(client):
    """O re-ranking (query/search/reranker.py) reordena por relevância real —
    um candidato que o RRF rankeou por último pode terminar primeiro, se o
    cross-encoder achar que ele é o mais relevante pro conteúdo da tese."""
    mesma_hierarquia = {"a": _doc(), "b": _doc(), "c": _doc()}  # todos ACORDAO (default)

    app.dependency_overrides[get_hybrid] = lambda: _FakeHybrid(
        [("a", 3.0), ("b", 2.0), ("c", 1.0)]  # RRF: a > b > c
    )
    app.dependency_overrides[get_doc_retriever] = lambda: _FakeDocRetriever(mesma_hierarquia)

    class _RerankerInverteOrdem:
        def rerank_scores(self, query, passagens):
            return list(range(len(passagens)))  # cresce com a posição -> inverte a ordem do RRF

    app.dependency_overrides[get_reranker] = lambda: _RerankerInverteOrdem()

    resp = client.post("/query", json={"estrutura": {"tese_central": "insalubridade"}})

    assert [card["id"] for card in resp.json()] == ["c", "b", "a"]


# --------------------------------------------------------------------------- #
# GET /document/{id}                                                           #
# --------------------------------------------------------------------------- #

def test_get_document_encontrado(client):
    doc = _doc()
    app.dependency_overrides[get_doc_retriever] = lambda: _FakeDocRetriever({"uuid-1": doc})

    resp = client.get("/document/uuid-1")

    assert resp.status_code == 200
    assert resp.json()["id"] == "uuid-1"
    assert resp.json()["ementa"] == "Ementa."


def test_get_document_nao_encontrado_404(client):
    app.dependency_overrides[get_doc_retriever] = lambda: _FakeDocRetriever({})

    resp = client.get("/document/nao-existe")

    assert resp.status_code == 404


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))


# --------------------------------------------------------------------------- #
# Classificação do Jev anexada aos cards                                       #
# --------------------------------------------------------------------------- #

import psycopg  # noqa: E402

from query.api.provimento_routes import get_provimento_store  # noqa: E402

_DETALHE = {
    "resultado": "nao_provido", "recorrente": "reclamada", "favorece": "reclamante",
    "probabilidades": {"resultado": {"nao_provido": 0.9, "provido": 0.1}},
    "confianca_resultado": 0.9, "confianca_recorrente": 0.8, "confianca_favorece": 0.7,
    "modelo": "jev-1.13.0",
}


class _FakeProvimentoStore:
    def __init__(self, falha: bool = False):
        self.falha = falha

    def detalhes(self, ids):
        if self.falha:
            raise psycopg.OperationalError("banco fora")
        return {i: _DETALHE for i in ids if i == "a-id"}


def _instalar_busca():
    docs = {"a-id": _doc(), "b-id": _doc()}
    app.dependency_overrides[get_hybrid] = lambda: _FakeHybrid([("a-id", 9.0), ("b-id", 1.0)])
    app.dependency_overrides[get_doc_retriever] = lambda: _FakeDocRetriever(docs)


def test_query_anexa_classificacao(client):
    _instalar_busca()
    app.dependency_overrides[get_provimento_store] = lambda: _FakeProvimentoStore()
    body = client.post("/query", json={"estrutura": {"tese_central": "insalubridade"}}).json()
    por_id = {c["id"]: c for c in body}
    assert por_id["a-id"]["classificacao_provimento"]["favorece"] == "reclamante"
    assert por_id["b-id"]["classificacao_provimento"] is None


def test_query_sem_classificacao_quando_store_falha(client):
    _instalar_busca()
    app.dependency_overrides[get_provimento_store] = lambda: _FakeProvimentoStore(falha=True)
    resp = client.post("/query", json={"estrutura": {"tese_central": "insalubridade"}})
    assert resp.status_code == 200
    assert all(c["classificacao_provimento"] is None for c in resp.json())


def test_document_anexa_classificacao(client):
    _instalar_busca()
    app.dependency_overrides[get_provimento_store] = lambda: _FakeProvimentoStore()
    body = client.get("/document/a-id").json()
    assert body["classificacao_provimento"]["recorrente"] == "reclamada"


# --------------------------------------------------------------------------- #
# Filtro restrito: /query com faixas, /query/livre e /enrich                  #
# --------------------------------------------------------------------------- #

class _FakeFiltroStore:
    def __init__(self, elegiveis=("a-id",), existentes=("art_192_clt",), indisponivel=False):
        self._elegiveis, self._existentes, self._indisponivel = list(elegiveis), set(existentes), indisponivel
        self.calls: list[tuple] = []

    def _check(self):
        if self._indisponivel:
            raise FiltroIndisponivel("sem preparo")

    def elegiveis(self, dispositivos, expressoes):
        self._check()
        self.calls.append(("elegiveis", dispositivos, expressoes))
        return self._elegiveis

    def existentes(self, codigos):
        self._check()
        return {c for c in codigos if c in self._existentes}

    def contar(self, dispositivos, expressoes):
        self._check()
        totais = {"dano moral coletivo": 137, "ação civil pública": 0, "termo raro": 3}
        return ContagemFiltros(
            total=0,
            dispositivos=[SugestaoDispositivo(c, rotulo(c), 40 if c in self._existentes else 0) for c in dispositivos],
            expressoes=[(e, totais.get(e, 5)) for e in expressoes],
        )


class _UsoContador:
    def __init__(self):
        self.acoes = []

    def consumir(self, usuario_id, acao):
        self.acoes.append(acao)


_FILTRO = {"estrutura": {"tese_central": "insalubridade", "dispositivos": ["art_192_clt"]}}


def _busca_fake():
    hybrid = _FakeHybrid([("a-id", 9.0), ("b-id", 1.0)])
    app.dependency_overrides[get_hybrid] = lambda: hybrid
    app.dependency_overrides[get_doc_retriever] = lambda: _FakeDocRetriever({"a-id": _doc(), "b-id": _doc()})
    return hybrid


def test_query_com_filtro_passa_elegiveis_e_marca_restrita(client, monkeypatch):
    _busca_fake()
    store = _FakeFiltroStore(elegiveis=["a-id"])
    app.dependency_overrides[get_filtro_store] = lambda: store
    vistos = {}
    real = api_app.buscar
    monkeypatch.setattr(api_app, "buscar", lambda *a, **k: vistos.update(k) or real(*a, **k))

    resp = client.post("/query", json=_FILTRO)

    assert resp.status_code == 200
    assert vistos["documento_ids"] == ["a-id"]
    assert [(c["id"], c["faixa"]) for c in resp.json()] == [("a-id", "restrita")]
    assert store.calls == [("elegiveis", ["art_192_clt"], [])]


def test_query_com_filtro_nunca_marca_restrita_card_fora_dos_elegiveis(client, monkeypatch):
    _busca_fake()
    app.dependency_overrides[get_filtro_store] = lambda: _FakeFiltroStore(elegiveis=["a-id"])
    real = api_app.buscar
    monkeypatch.setattr(api_app, "buscar", lambda *a, **k: real(*a, **{**k, "documento_ids": None}))  # busca "esquece" o filtro

    resp = client.post("/query", json=_FILTRO)

    assert [(c["id"], c["faixa"]) for c in resp.json()] == [("a-id", "restrita")]


@pytest.mark.parametrize("rota", ["/query", "/query/livre"])
@pytest.mark.parametrize("estrutura", [
    {"dispositivos": [f"art_{i}_clt" for i in range(21)]},
    {"expressoes": [f"expressao {i}" for i in range(21)]},
    {"expressoes": ["x" * 201]},
    {"dispositivos": ["x" * 201]},
])
def test_query_filtros_acima_do_limite_422(client, rota, estrutura):
    hybrid = _busca_fake()
    app.dependency_overrides[get_filtro_store] = lambda: _FakeFiltroStore()
    resp = client.post(rota, json={"estrutura": {"tese_central": "x", **estrutura}})
    assert resp.status_code == 422
    assert hybrid.calls == []


def test_query_com_filtro_sem_elegiveis_devolve_lista_vazia_sem_buscar(client):
    hybrid = _busca_fake()
    app.dependency_overrides[get_filtro_store] = lambda: _FakeFiltroStore(elegiveis=[])

    resp = client.post("/query", json=_FILTRO)

    assert resp.status_code == 200 and resp.json() == []
    assert hybrid.calls == []


def test_query_com_codigo_inexistente_devolve_200_vazio(client):
    hybrid = _busca_fake()
    app.dependency_overrides[get_filtro_store] = lambda: _FakeFiltroStore(elegiveis=[])

    resp = client.post("/query", json={"estrutura": {"tese_central": "x", "dispositivos": ["art_999_xyz"]}})

    assert resp.status_code == 200 and resp.json() == []
    assert hybrid.calls == []


def test_query_com_filtro_sem_store_503(client):
    _busca_fake()
    app.dependency_overrides[get_filtro_store] = lambda: None
    resp = client.post("/query", json=_FILTRO)
    assert resp.status_code == 503
    assert resp.json()["detail"] == "O filtro restrito está indisponível no momento."


def test_query_com_filtro_e_tabelas_ausentes_503(client):
    _busca_fake()
    app.dependency_overrides[get_filtro_store] = lambda: _FakeFiltroStore(indisponivel=True)
    assert client.post("/query", json=_FILTRO).status_code == 503


def test_query_sem_filtro_sem_store_funciona(client):
    _busca_fake()
    app.dependency_overrides[get_filtro_store] = lambda: None
    resp = client.post("/query", json={"estrutura": {"tese_central": "insalubridade"}})
    assert resp.status_code == 200
    assert [(c["id"], c["faixa"]) for c in resp.json()] == [("a-id", "livre"), ("b-id", "livre")]


def test_query_livre_ignora_filtro_e_nao_consome_limite(client):
    hybrid = _busca_fake()
    store, uso = _FakeFiltroStore(elegiveis=["a-id"]), _UsoContador()
    app.dependency_overrides[get_filtro_store] = lambda: store
    app.dependency_overrides[get_uso_diario] = lambda: uso

    resp = client.post("/query/livre", json=_FILTRO)

    assert resp.status_code == 200
    assert [(c["id"], c["faixa"]) for c in resp.json()] == [("a-id", "livre"), ("b-id", "livre")]
    assert store.calls == [] and uso.acoes == []
    assert "art. 192" in hybrid.calls[0]["bm25_query"]  # só no texto do BM25


def test_query_livre_sem_sessao_401(client):
    app.dependency_overrides.pop(get_current_user, None)
    assert client.post("/query/livre", json=_FILTRO).status_code == 401


def test_enrich_norma_citada_no_texto_vira_filtro_ativo(client):
    est = EstruturaArgumentativa(tese_central="t", normas=["CLT art. 192", "NR-15"])
    app.dependency_overrides[get_enricher] = lambda: _FakeEnricher(est)
    app.dependency_overrides[get_filtro_store] = lambda: _FakeFiltroStore()

    body = client.post("/enrich", data={"intencao": "Pede o adicional com base na NR-15 e no art. 192 da CLT."}).json()

    assert body["estrutura"]["dispositivos"] == ["art_192_clt"]
    assert body["dispositivos_ia"] == ["art_192_clt"]
    assert body["estrutura"]["normas"] == ["NR-15"]
    assert body["dispositivos_sugeridos"] == []


def test_enrich_norma_que_a_ia_deduziu_so_vira_sugestao(client):
    """O modelo pequeno põe em `normas` artigos que não estão no texto (e às vezes errados):
    eles não podem virar filtro ativo, só sugestão clicável, e saem do texto da busca livre."""
    est = EstruturaArgumentativa(tese_central="t", normas=["CLT art. 192", "NR-15"])
    app.dependency_overrides[get_enricher] = lambda: _FakeEnricher(est)
    app.dependency_overrides[get_filtro_store] = lambda: _FakeFiltroStore()

    body = client.post("/enrich", data={"intencao": "O trabalhador exposto a ruído quer o adicional."}).json()

    assert body["estrutura"]["dispositivos"] == [] and body["dispositivos_ia"] == []
    assert body["estrutura"]["normas"] == []
    assert body["dispositivos_sugeridos"] == [{"codigo": "art_192_clt", "rotulo": "CLT art. 192", "total": 40}]


def test_enrich_descarta_sugestoes_com_menos_de_5_decisoes(client):
    app.dependency_overrides[get_enricher] = lambda: _FakeEnricher(sugeridas=["dano moral coletivo", "termo raro"])
    app.dependency_overrides[get_filtro_store] = lambda: _FakeFiltroStore()

    body = client.post("/enrich", data={"intencao": "x"}).json()

    assert [e["texto"] for e in body["expressoes_sugeridas"]] == ["dano moral coletivo"]


def test_enrich_sugere_so_expressoes_que_existem_no_acervo(client):
    est = EstruturaArgumentativa(tese_central="t")
    app.dependency_overrides[get_enricher] = lambda: _FakeEnricher(est, ["dano moral coletivo", "ação civil pública"])
    app.dependency_overrides[get_filtro_store] = lambda: _FakeFiltroStore()

    body = client.post("/enrich", data={"intencao": "x"}).json()

    assert body["expressoes_sugeridas"] == [{"texto": "dano moral coletivo", "total": 137}]
    assert body["estrutura"]["expressoes"] == []  # sugestão não filtra até o advogado escolher


def test_enrich_sugere_dispositivos_que_existem_e_ainda_nao_estao_no_filtro(client):
    est = EstruturaArgumentativa(tese_central="t", normas=["CLT art. 192"])
    sugeridos = ["CLT art. 192", "Súmula 85 do TST", "CLT art. 9999", "art. 62"]  # repetido, existente, inexistente, sem lei
    app.dependency_overrides[get_enricher] = lambda: _FakeEnricher(est, dispositivos=sugeridos)
    app.dependency_overrides[get_filtro_store] = lambda: _FakeFiltroStore(existentes=("art_192_clt", "sumula_85_tst"))

    body = client.post("/enrich", data={"intencao": "Pede o adicional do art. 192 da CLT."}).json()

    assert body["estrutura"]["dispositivos"] == ["art_192_clt"]  # citado no texto: já ativo
    assert body["dispositivos_sugeridos"] == [{"codigo": "sumula_85_tst", "rotulo": "Súmula 85 do TST", "total": 40}]


def test_enrich_sem_store_nao_sugere_expressoes(client):
    app.dependency_overrides[get_enricher] = lambda: _FakeEnricher(sugeridas=["dano moral coletivo"])
    app.dependency_overrides[get_filtro_store] = lambda: _FakeFiltroStore(indisponivel=True)

    body = client.post("/enrich", data={"intencao": "x"}).json()

    assert body["expressoes_sugeridas"] == [] and body["dispositivos_sugeridos"] == []


def test_enrich_segue_sem_converter_quando_store_falha(client):
    est = EstruturaArgumentativa(tese_central="t", normas=["CLT art. 192"])
    app.dependency_overrides[get_enricher] = lambda: _FakeEnricher(est)
    app.dependency_overrides[get_filtro_store] = lambda: _FakeFiltroStore(indisponivel=True)

    body = client.post("/enrich", data={"intencao": "Pede o adicional do art. 192 da CLT."}).json()

    assert body["estrutura"]["normas"] == ["CLT art. 192"]
    assert body["estrutura"]["dispositivos"] == [] and body["dispositivos_ia"] == []


class _FiltroStoreBancoFora(_FakeFiltroStore):
    def existentes(self, codigos):
        raise psycopg.OperationalError("conexão recusada")


def test_enrich_segue_sem_converter_quando_banco_falha(client):
    est = EstruturaArgumentativa(tese_central="t", normas=["CLT art. 192"])
    app.dependency_overrides[get_enricher] = lambda: _FakeEnricher(est)
    app.dependency_overrides[get_filtro_store] = lambda: _FiltroStoreBancoFora()

    resp = client.post("/enrich", data={"intencao": "Pede o adicional do art. 192 da CLT."})

    assert resp.status_code == 200
    assert resp.json()["estrutura"]["normas"] == ["CLT art. 192"] and resp.json()["dispositivos_ia"] == []


def test_estrutura_e_card_antigos_validam():
    e = EstruturaArgumentativa.model_validate({"tese_central": "x", "normas": ["NR-15"]})
    assert e.dispositivos == [] and e.expressoes == []
    assert "dispositivos" not in e.model_dump(mode="json", exclude_defaults=True)  # chave do cache da resposta
    card = ResultCard.model_validate({
        "id": "a", "tipo_documento": "ACORDAO", "hierarquia_categoria": 4, "numero_processo": "RR-1",
        "tribunal": "TST", "turma": "", "relator": "R", "data_julgamento": None, "ementa": "e",
        "provimento": "APROVADO", "link_original": None, "score_rrf": 0.5,
    })
    assert card.faixa == "livre"
