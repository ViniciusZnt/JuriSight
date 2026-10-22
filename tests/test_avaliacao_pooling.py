"""Testes do pooling (híbrido + BM25 + denso) (fakes; sem Qdrant/BM25/banco)."""
from types import SimpleNamespace

import pytest

from avaliacao import pooling
from avaliacao.pooling import montar_pool
from query.enrichment.schema import EstruturaArgumentativa
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


def _hybrid(bm25_chunks, completo, ementa, hibrido=()):
    from indexing.vector_store.qdrant_store import COLLECTION_COMPLETO, COLLECTION_EMENTA

    h = SimpleNamespace(
        bm25=_FakeBM25(bm25_chunks),
        embedder=_FakeEmbedder(),
        store=_FakeStore({COLLECTION_COMPLETO: completo, COLLECTION_EMENTA: ementa}),
        chamadas_search=[],
    )

    def search(frase, n, bm25_query=None):
        h.chamadas_search.append((frase, n, bm25_query))
        return [(d, 1.0 / (i + 1)) for i, d in enumerate(hibrido)][:n]

    h.search = search
    return h


def test_pool_une_os_tres_corredores():
    hibrido = [f"h{i}" for i in range(30)]
    hybrid = _hybrid(
        [f"b{i}:0" for i in range(10)], [f"v{i}" for i in range(10)], [], hibrido=hibrido
    )
    pool = montar_pool(_estrutura(), hybrid=hybrid, retriever=_FakeRetriever())
    assert pooling.CORREDORES == ("hibrido", "bm25", "vetorial")
    por_corredor = {c: [] for c in pooling.CORREDORES}
    for doc, corredores in pool.items():
        for c in corredores:
            por_corredor[c].append(doc)
    assert len(por_corredor["hibrido"]) == 30
    assert len(por_corredor["bm25"]) == 10
    assert len(por_corredor["vetorial"]) == 10
    assert hybrid.chamadas_search[0][1] == 30


def test_corredores_na_ordem_fixa_e_colapsa_chunks():
    hybrid = _hybrid(["d1:0", "d1:1", "d2:0"], ["d1", "d4"], ["d1"], hibrido=["d1", "d3"])
    pool = montar_pool(_estrutura(), hybrid=hybrid, retriever=_FakeRetriever(), n_hibrido=5, k=5)
    assert pool == {
        "d1": ["hibrido", "bm25", "vetorial"],
        "d3": ["hibrido"],
        "d2": ["bm25"],
        "d4": ["vetorial"],
    }
    assert hybrid.embedder.textos[0] == "EPI não elide a insalubridade sem fiscalização."


def test_bm25_e_denso_limitados_a_k():
    chunks = [f"b0:{i}" for i in range(6)] + [f"b{i}:0" for i in range(1, 10)]
    hybrid = _hybrid(chunks, [f"v{i}" for i in range(10)], [f"e{i}" for i in range(10)])
    pool = montar_pool(_estrutura(), hybrid=hybrid, retriever=_FakeRetriever(), k=3)
    bm25 = [d for d, c in pool.items() if "bm25" in c]
    vet = [d for d, c in pool.items() if "vetorial" in c]
    assert bm25 == ["b0", "b1", "b2"]
    assert len(vet) == 3


def test_pool_descarta_documento_sem_texto():
    hybrid = _hybrid(["d1:0", "d2:0"], ["d1"], [], hibrido=["d3", "d5"])
    retriever = _FakeRetriever(vazios={"d1"}, ausentes={"d5"})
    pool = montar_pool(_estrutura(), hybrid=hybrid, retriever=retriever, k=5)
    assert set(pool) == {"d2", "d3"}
    assert len(retriever.chamadas) == 2  # fetch do híbrido + um único fetch sobre a união
    assert set(retriever.chamadas[1]) == {"d3", "d1", "d2"}


def test_estrutura_vazia_propaga_value_error():
    hybrid = _hybrid([], [], [])
    with pytest.raises(ValueError):
        montar_pool(EstruturaArgumentativa(), hybrid=hybrid, retriever=_FakeRetriever())
