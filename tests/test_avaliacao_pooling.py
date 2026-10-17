"""Testes do pooling de 3 corredores (fakes; sem Qdrant/BM25/banco)."""
from types import SimpleNamespace

import pytest

from avaliacao import pooling
from avaliacao.pooling import montar_pool
from query.enrichment.schema import EstruturaArgumentativa
from query.search.hybrid_search import CANDIDATOS_POR_CANAL
from scraper.schema import DocumentoJuridico


class _FakeBM25:
    def __init__(self, chunk_ids):
        self.chunk_ids = chunk_ids
        self.chamadas = []

    def search(self, texto, n=10):
        self.chamadas.append((texto, n))
        return [(cid, 1.0) for cid in self.chunk_ids][:n]


class _FakeEmbedder:
    def __init__(self):
        self.textos = []

    def embed_text(self, texto):
        self.textos.append(texto)
        return [0.1, 0.2]


class _FakeStore:
    def __init__(self, por_colecao):
        self.por_colecao = por_colecao
        self.chamadas = []

    def query(self, embedding, n_results=20, where=None, collection=None):
        self.chamadas.append((collection, n_results))
        return [{"documento_id": d} for d in self.por_colecao[collection]][:n_results]


class _FakeRetriever:
    def __init__(self, vazios=(), ausentes=()):
        self.vazios = set(vazios)
        self.ausentes = set(ausentes)
        self.chamadas = []

    def fetch(self, ids):
        self.chamadas.append(list(ids))
        out = {}
        for i in ids:
            if i in self.ausentes:
                continue
            ementa = "" if i in self.vazios else f"ementa {i}"
            out[i] = DocumentoJuridico.model_construct(id_documento=i, ementa=ementa, fundamentacao="")
        return out


def _estrutura():
    return EstruturaArgumentativa(
        pedido_principal="adicional de insalubridade",
        violacoes=["EPI sem fiscalização"],
        tese_central="EPI não elide a insalubridade sem fiscalização.",
    )


def _hybrid(bm25_chunks, completo, ementa):
    from indexing.vector_store.qdrant_store import COLLECTION_COMPLETO, COLLECTION_EMENTA

    return SimpleNamespace(
        bm25=_FakeBM25(bm25_chunks),
        embedder=_FakeEmbedder(),
        store=_FakeStore({COLLECTION_COMPLETO: completo, COLLECTION_EMENTA: ementa}),
    )


@pytest.fixture
def pipeline_ids(monkeypatch):
    def _definir(ids):
        monkeypatch.setattr(
            pooling, "buscar", lambda estrutura, **kw: [SimpleNamespace(id=i) for i in ids]
        )

    return _definir


def test_pool_une_corredores_e_colapsa_chunks(pipeline_ids):
    pipeline_ids(["d3"])
    hybrid = _hybrid(["d1:0", "d1:1", "d2:0"], ["d1", "d4"], ["d1"])
    pool = montar_pool(
        _estrutura(), hybrid=hybrid, retriever=_FakeRetriever(), reranker=None, k=5
    )
    assert pool == {
        "d1": ["bm25", "vetorial"],
        "d2": ["bm25"],
        "d4": ["vetorial"],
        "d3": ["pipeline"],
    }
    assert len(hybrid.bm25.chamadas) == 1
    assert hybrid.bm25.chamadas[0] == (
        "adicional de insalubridade EPI sem fiscalização",
        5 * CANDIDATOS_POR_CANAL,
    )
    assert hybrid.embedder.textos == ["EPI não elide a insalubridade sem fiscalização."]


def test_corredores_na_ordem_fixa(pipeline_ids):
    pipeline_ids(["d1"])
    hybrid = _hybrid(["d1:0"], ["d1"], ["d1"])
    pool = montar_pool(_estrutura(), hybrid=hybrid, retriever=_FakeRetriever(), reranker=None, k=3)
    assert pool == {"d1": ["bm25", "vetorial", "pipeline"]}


def test_cada_corredor_limitado_a_k(pipeline_ids):
    pipeline_ids([f"p{i}" for i in range(10)])
    # 6 chunks do mesmo doc primeiro: só colapsam para 1 documento, não gastam o k.
    chunks = [f"b0:{i}" for i in range(6)] + [f"b{i}:0" for i in range(1, 10)]
    hybrid = _hybrid(chunks, [f"v{i}" for i in range(10)], [f"e{i}" for i in range(10)])
    pool = montar_pool(_estrutura(), hybrid=hybrid, retriever=_FakeRetriever(), reranker=None, k=3)

    por_corredor = {"bm25": [], "vetorial": [], "pipeline": []}
    for doc, corredores in pool.items():
        for c in corredores:
            por_corredor[c].append(doc)
    assert por_corredor["bm25"] == ["b0", "b1", "b2"]
    assert por_corredor["pipeline"] == ["p0", "p1", "p2"]
    assert len(por_corredor["vetorial"]) == 3
    assert all(d.startswith(("v", "e")) for d in por_corredor["vetorial"])


def test_vetorial_funde_colecoes_por_rrf(pipeline_ids):
    pipeline_ids([])
    # x aparece nas duas coleções: o RRF o põe na frente de a e b.
    hybrid = _hybrid([], ["a", "x"], ["b", "x"])
    pool = montar_pool(_estrutura(), hybrid=hybrid, retriever=_FakeRetriever(), reranker=None, k=1)
    assert pool == {"x": ["vetorial"]}


def test_pool_descarta_documento_sem_texto(pipeline_ids):
    pipeline_ids(["d3", "d5"])
    hybrid = _hybrid(["d1:0", "d2:0"], ["d1"], [])
    retriever = _FakeRetriever(vazios={"d1"}, ausentes={"d5"})
    pool = montar_pool(_estrutura(), hybrid=hybrid, retriever=retriever, reranker=None, k=5)
    assert set(pool) == {"d2", "d3"}
    assert len(retriever.chamadas) == 1  # um único fetch sobre a união


def test_estrutura_vazia_propaga_value_error(pipeline_ids):
    pipeline_ids([])
    hybrid = _hybrid([], [], [])
    with pytest.raises(ValueError):
        montar_pool(
            EstruturaArgumentativa(), hybrid=hybrid, retriever=_FakeRetriever(), reranker=None
        )
