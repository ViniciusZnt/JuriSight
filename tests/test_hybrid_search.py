"""
Testes do Hybrid Search (query/search/hybrid_search.py).

Embedder, Chroma e BM25 são substituídos por fakes — os testes validam a fusão
RRF e o roteamento das strings query/bm25_query para os canais certos, sem
ChromaDB/OpenAI/rank-bm25 reais.
"""
import pytest

from query.search.hybrid_search import HybridSearch, reciprocal_rank_fusion


class _FakeEmbedder:
    def __init__(self):
        self.calls: list[str] = []

    def embed_text(self, text: str):
        self.calls.append(text)
        return [0.0]


class _FakeChroma:
    def __init__(self, hits_completo=None, hits_ementa=None):
        self._hits_completo = hits_completo or []
        self._hits_ementa = hits_ementa or []
        self.calls: list[dict] = []

    def query(self, embedding, n_results, where, collection):
        self.calls.append({"collection": collection, "n_results": n_results, "where": where})
        hits = self._hits_completo if "completo" in collection else self._hits_ementa
        return hits


class _FakeBM25:
    def __init__(self, hits=None):
        self._hits = hits or []
        self.calls: list[tuple[str, int]] = []

    def search(self, query: str, n: int):
        self.calls.append((query, n))
        return self._hits


def _hit(documento_id: str) -> dict:
    return {"id": documento_id, "documento_id": documento_id, "distance": 0.1, "metadata": {}}


# --------------------------------------------------------------------------- #
# reciprocal_rank_fusion                                                       #
# --------------------------------------------------------------------------- #

def test_rrf_documento_no_topo_de_todos_os_rankings_vence():
    fundidos = reciprocal_rank_fusion([["a", "b"], ["a", "c"], ["a", "d"]])
    assert fundidos[0][0] == "a"


def test_rrf_lista_vazia():
    assert reciprocal_rank_fusion([]) == []


# --------------------------------------------------------------------------- #
# HybridSearch.search — roteamento de query vs bm25_query                     #
# --------------------------------------------------------------------------- #

def test_search_usa_query_para_embedding_e_bm25_quando_bm25_query_ausente():
    embedder, chroma, bm25 = _FakeEmbedder(), _FakeChroma(), _FakeBM25()
    hybrid = HybridSearch(embedder, chroma, bm25)

    hybrid.search("frase única")

    assert embedder.calls == ["frase única"]
    assert bm25.calls[0][0] == "frase única"


def test_search_usa_bm25_query_distinta_quando_fornecida():
    embedder, chroma, bm25 = _FakeEmbedder(), _FakeChroma(), _FakeBM25()
    hybrid = HybridSearch(embedder, chroma, bm25)

    hybrid.search("frase-tese para embedding", bm25_query="NR-15 benzeno")

    assert embedder.calls == ["frase-tese para embedding"]
    assert bm25.calls[0][0] == "NR-15 benzeno"


def test_search_funde_os_tres_canais():
    embedder = _FakeEmbedder()
    chroma = _FakeChroma(
        hits_completo=[_hit("doc-1"), _hit("doc-2")],
        hits_ementa=[_hit("doc-1")],
    )
    bm25 = _FakeBM25(hits=[("doc-1:0", 5.0), ("doc-3:0", 3.0)])
    hybrid = HybridSearch(embedder, chroma, bm25)

    resultados = hybrid.search("tese", n_results=10)

    ids = [doc_id for doc_id, _ in resultados]
    assert "doc-1" in ids  # aparece nos 3 canais, deve estar no topo
    assert ids[0] == "doc-1"
    assert set(ids) == {"doc-1", "doc-2", "doc-3"}


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
