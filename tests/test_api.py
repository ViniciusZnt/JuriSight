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
from datetime import date, datetime, timezone

import pytest
from fastapi.testclient import TestClient

import query.api.app as api_app
from auth.store import Usuario
from query.api.app import app, get_current_user, get_doc_retriever, get_enricher, get_hybrid
from query.api.auth_routes import get_usuario_store
from query.enrichment.pdf_extractor import PDFSemTextoError
from query.enrichment.query_enrichment import _montar_conteudo
from query.enrichment.schema import EstruturaArgumentativa
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

    def search(self, query, n_results, where=None, *, bm25_query=None):
        self.calls.append({"query": query, "n_results": n_results, "bm25_query": bm25_query})
        return self._resultados[:n_results]


class _FakeDocRetriever:
    def __init__(self, docs: dict[str, DocumentoJuridico]):
        self._docs = docs

    def fetch(self, ids):
        return {i: self._docs[i] for i in ids if i in self._docs}


class _FakeEnricher:
    def __init__(self, estrutura: EstruturaArgumentativa | None = None):
        self.estrutura = estrutura or EstruturaArgumentativa(tese_central="tese fake")
        self.calls: list[tuple] = []

    def resumir_bloco(self, texto: str) -> str:
        return texto[:20]

    def condensar(self, resumos: list[str]) -> str:
        return " ".join(resumos)

    def extract_estrutura(self, texto_caso, intencao=None):
        self.calls.append((texto_caso, intencao))
        _montar_conteudo(texto_caso, intencao)  # levanta ValueError se ambos vazios
        return self.estrutura


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


def test_enrich_pdf_corrompido_400(client):
    app.dependency_overrides[get_enricher] = lambda: _FakeEnricher()

    # bytes que não são um PDF de verdade — pdfplumber real levanta ao tentar abrir.
    resp = client.post("/enrich", files={"pdf": ("caso.pdf", b"isto nao e um pdf", "application/pdf")})

    assert resp.status_code == 400


# --------------------------------------------------------------------------- #
# POST /query                                                                  #
# --------------------------------------------------------------------------- #

def test_query_fim_a_fim_ordena_e_formata(client):
    sumula = _doc(tipo_documento=TipoDocumento.SUMULA, hierarquia_categoria=1)
    acordao = _doc(tipo_documento=TipoDocumento.ACORDAO, hierarquia_categoria=4)
    docs = {"sumula-id": sumula, "acordao-id": acordao}

    app.dependency_overrides[get_hybrid] = lambda: _FakeHybrid(
        [("acordao-id", 9.0), ("sumula-id", 1.0)]
    )
    app.dependency_overrides[get_doc_retriever] = lambda: _FakeDocRetriever(docs)

    resp = client.post("/query", json={"estrutura": {"tese_central": "insalubridade"}})

    assert resp.status_code == 200
    body = resp.json()
    # a súmula tem hierarquia_categoria menor -> vem primeiro, mesmo com score menor.
    assert [card["id"] for card in body] == ["sumula-id", "acordao-id"]


def test_query_estrutura_vazia_422(client):
    app.dependency_overrides[get_hybrid] = lambda: _FakeHybrid([])
    app.dependency_overrides[get_doc_retriever] = lambda: _FakeDocRetriever({})

    resp = client.post("/query", json={"estrutura": {}})

    assert resp.status_code == 422


def test_query_filtro_provimento_reduz_resultados_e_pede_pool_maior(client):
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
    assert fake_hybrid.calls[0]["n_results"] == api_app.N_CANDIDATOS_COM_FILTRO


def test_query_sem_filtro_usa_pool_padrao(client):
    doc = _doc()
    fake_hybrid = _FakeHybrid([("doc-1", 1.0)])
    app.dependency_overrides[get_hybrid] = lambda: fake_hybrid
    app.dependency_overrides[get_doc_retriever] = lambda: _FakeDocRetriever({"doc-1": doc})

    client.post("/query", json={"estrutura": {"tese_central": "insalubridade"}})

    assert fake_hybrid.calls[0]["n_results"] == api_app.N_RESULTS_FINAL


def test_query_ordenar_por_data(client):
    recente = _doc(data_julgamento=date(2026, 1, 1))
    antigo = _doc(data_julgamento=date(2020, 1, 1))
    docs = {"antigo": antigo, "recente": recente}

    app.dependency_overrides[get_hybrid] = lambda: _FakeHybrid([("antigo", 2.0), ("recente", 1.0)])
    app.dependency_overrides[get_doc_retriever] = lambda: _FakeDocRetriever(docs)

    resp = client.post(
        "/query",
        json={"estrutura": {"tese_central": "insalubridade"}, "ordenar_por": "data"},
    )

    assert [card["id"] for card in resp.json()] == ["recente", "antigo"]


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
