"""Testes dos sistemas S0-S2 do benchmark (fakes; sem Qdrant/BM25/banco)."""
from types import SimpleNamespace

import pytest

from avaliacao import sistemas
from avaliacao.sistemas import candidatos_hibrido, rodar_sistema, top_denso
from query.enrichment.schema import EstruturaArgumentativa
from tests.fakes import documento_fake


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
        self._docs = {i: documento_fake(id_documento=i) for i in ids}

    def fetch(self, ids, completo=True):
        return {i: self._docs[i] for i in ids if i in self._docs}


ESTRUTURA = EstruturaArgumentativa(tese_central="tese fake")


def _deps(ids, achados=None):
    return SimpleNamespace(
        hybrid=_Hybrid(ids), retriever=_Retriever(achados if achados is not None else ids)
    )


def test_rodar_sistema_s2_busca_50_e_devolve_top20_na_ordem_do_rrf():
    ids = [f"a{i}" for i in range(60)]
    assert rodar_sistema("S2", ESTRUTURA, _deps(ids)) == ids[:20]


def test_rodar_sistema_s0_usa_bm25_k20():
    ids = rodar_sistema("S0", ESTRUTURA, _deps([]))
    assert ids == [f"b{i}" for i in range(20)]


def test_sistema_desconhecido_falha():
    with pytest.raises(KeyError):
        rodar_sistema("S3", ESTRUTURA, _deps(["a0"]))


def test_candidatos_hibrido_so_os_que_o_retriever_acha():
    deps = _deps(["a0", "a1", "a2"], achados=["a0", "a2"])
    assert candidatos_hibrido(ESTRUTURA, hybrid=deps.hybrid, retriever=deps.retriever) == ["a0", "a2"]


def test_candidatos_hibrido_pede_50_por_padrao():
    ids = [f"a{i}" for i in range(60)]
    deps = _deps(ids)
    assert len(candidatos_hibrido(ESTRUTURA, hybrid=deps.hybrid, retriever=deps.retriever)) == 50


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


class _Bm25Chunks:
    """Muitos chunks por documento: 7 chunks para cada doc, nas posições 0..."""

    def search(self, texto, n):
        return [(f"d{i // 7}:{i % 7}", 1.0) for i in range(n)]


def _hybrid_profundidade():
    from indexing.vector_store.qdrant_store import COLLECTION_COMPLETO, COLLECTION_EMENTA

    def query(vetor, n_results=20, collection=None):
        base = "c" if collection == COLLECTION_COMPLETO else "e"
        return [{"documento_id": f"{base}{i // 2}"} for i in range(n_results)]  # 2 chunks por doc

    return SimpleNamespace(
        bm25=_Bm25Chunks(), embedder=SimpleNamespace(embed_text=lambda t: [0.1]),
        store=SimpleNamespace(query=query),
    )


def test_top10_e_prefixo_do_top20_bm25_e_denso():
    hybrid = _hybrid_profundidade()
    est = EstruturaArgumentativa(tese_central="tese")
    assert sistemas.top_bm25(hybrid, est, 10) == sistemas.top_bm25(hybrid, est, 20)[:10]
    assert sistemas.top_denso(hybrid, est, 10) == sistemas.top_denso(hybrid, est, 20)[:10]
    assert len(sistemas.top_bm25(hybrid, est, 20)) == 15  # 100 chunks / 7 por doc: profundidade fixa


# --- S7: S2 + triagem por IA ------------------------------------------------------------------

from query.search.triagem import Avaliacao  # noqa: E402


def _av(nota):
    return Avaliacao(nota=nota, posicao="deferiu", motivo="m")


def test_ordenar_por_triagem_nota_desc_desempate_pela_entrada_e_sem_nota_no_fim():
    av = {"b": _av(3), "c": _av(3), "a": _av(1)}
    assert sistemas.ordenar_por_triagem(["a", "b", "c", "d"], av) == ["b", "c", "a", "d"]


class _CacheMemoria:
    def __init__(self):
        self.salvas = {}

    def ler_varios(self, chaves):
        return {c: self.salvas[c] for c in chaves if c in self.salvas}

    def gravar_varios(self, itens):
        self.salvas.update(itens)


def test_s7_avalia_os_50_em_lotes_de_10_usando_o_cache_e_devolve_top20(monkeypatch):
    ids = [f"a{i}" for i in range(60)]
    lotes = []

    def avaliar_lote(estrutura, decisoes, client):
        lotes.append(list(decisoes))
        # as 10 últimas dos 50 viram nota 3, o resto nota 1
        return {i: _av(3 if int(i[1:]) >= 40 else 1) for i in decisoes}

    monkeypatch.setattr(sistemas, "avaliar_lote", avaliar_lote)
    deps = _deps(ids)
    deps.openai, deps.triagem_cache = object(), _CacheMemoria()

    top = rodar_sistema("S7", ESTRUTURA, deps)
    assert [len(lote) for lote in lotes] == [10] * 5
    assert top[:10] == [f"a{i}" for i in range(40, 50)] and len(top) == 20

    lotes.clear()
    assert rodar_sistema("S7", ESTRUTURA, deps) == top
    assert lotes == []  # 2ª vez: tudo do cache
