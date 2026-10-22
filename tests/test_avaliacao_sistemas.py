"""Testes dos sistemas S0-S3 do benchmark (fakes; sem Qdrant/BM25/banco)."""
from types import SimpleNamespace

import pytest

from avaliacao import sistemas
from avaliacao.sistemas import candidatos_hibrido, rodar_sistema, top_denso
from query.enrichment.schema import EstruturaArgumentativa
from tests.test_pipeline import _doc


class _Bm25:
    def search(self, texto, n):
        return [(f"b{i}:0", 1.0) for i in range(n)]


class _Hybrid:
    def __init__(self, ids):
        self.bm25 = _Bm25()
        self._ids = ids

    def search(self, query, n, where=None, *, bm25_query=None):
        return [(i, 1.0 / (k + 1)) for k, i in enumerate(self._ids)][:n]


class _Retriever:
    def __init__(self, ids):
        self._docs = {i: _doc(id_documento=i) for i in ids}

    def fetch(self, ids):
        return {i: self._docs[i] for i in ids if i in self._docs}


class _Reranker:
    """Inverte a ordem de entrada."""

    def __init__(self):
        self.chamadas = 0

    def rerank_scores(self, query, passagens):
        self.chamadas += 1
        return [float(i) for i in range(len(passagens))]


ESTRUTURA = EstruturaArgumentativa(tese_central="tese fake")


def _deps(ids, achados=None):
    return SimpleNamespace(
        hybrid=_Hybrid(ids), retriever=_Retriever(achados if achados is not None else ids)
    )


def test_rodar_sistema_s2_s3():
    ids = [f"a{i}" for i in range(25)]
    deps = _deps(ids)
    rr = _Reranker()

    assert rodar_sistema("S2", ESTRUTURA, deps, {}) == ids[:20]
    assert rr.chamadas == 0

    s3 = rodar_sistema("S3", ESTRUTURA, deps, {"S3": rr})
    assert rr.chamadas == 1
    assert s3 == list(reversed(ids[:25]))[:20]


def test_rodar_sistema_s0_usa_bm25_k20():
    ids = rodar_sistema("S0", ESTRUTURA, _deps([]), {})
    assert ids == [f"b{i}" for i in range(20)]


def test_rodar_sistema_sem_reranker_falha():
    with pytest.raises(KeyError, match="S4"):
        rodar_sistema("S4", ESTRUTURA, _deps(["a0"]), {})


def test_sistema_desconhecido_falha():
    with pytest.raises(KeyError):
        rodar_sistema("S9", ESTRUTURA, _deps(["a0"]), {})


def test_candidatos_hibrido_so_os_que_o_retriever_acha():
    deps = _deps(["a0", "a1", "a2"], achados=["a0", "a2"])
    assert candidatos_hibrido(ESTRUTURA, hybrid=deps.hybrid, retriever=deps.retriever) == ["a0", "a2"]


def test_top_denso_funde_colecoes_por_rrf():
    from indexing.vector_store.qdrant_store import COLLECTION_COMPLETO, COLLECTION_EMENTA

    por_colecao = {COLLECTION_COMPLETO: ["a", "x"], COLLECTION_EMENTA: ["b", "x"]}
    store = SimpleNamespace(
        query=lambda vetor, n_results=20, collection=None: [
            {"documento_id": d} for d in por_colecao[collection]
        ][:n_results]
    )
    hybrid = SimpleNamespace(embedder=SimpleNamespace(embed_text=lambda t: [0.1]), store=store)
    estrutura = EstruturaArgumentativa(tese_central="EPI não elide a insalubridade.")
    # x está nas duas coleções: o RRF o põe na frente de a e b.
    assert top_denso(hybrid, estrutura, 1) == ["x"]


def test_construir_rerankers_nome_desconhecido():
    import pytest
    from avaliacao.sistemas import construir_rerankers

    with pytest.raises(ValueError):
        construir_rerankers(["S9"])
    assert construir_rerankers([]) == {}
