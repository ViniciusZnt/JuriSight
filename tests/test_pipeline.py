"""
Testes de query/search/pipeline.py::buscar — o pipeline do /query chamado
direto, sem HTTP. Nenhuma infra real: hybrid/retriever/reranker são fakes.
"""
import pytest

from query.enrichment.schema import EstruturaArgumentativa
from query.search.pipeline import N_RESULTS_FINAL, buscar
from scraper.schema import DocumentoJuridico, Provimento, TipoDocumento


class _FakeHybrid:
    def __init__(self, resultados: list[tuple[str, float]]):
        self._resultados = resultados
        self.calls: list[dict] = []

    def search(self, query, n_results, where=None, *, bm25_query=None, provimento=None):
        self.calls.append({"n_results": n_results, "provimento": provimento})
        return self._resultados[:n_results]


class _FakeReranker:
    """Passthrough: scores estritamente decrescentes na ordem de entrada."""

    def rerank_scores(self, query: str, passagens: list[str]) -> list[float]:
        return [1.0 - i * 0.01 for i in range(len(passagens))]


class _FakeDocRetriever:
    def __init__(self, docs: dict[str, DocumentoJuridico]):
        self._docs = docs

    def fetch(self, ids):
        return {i: self._docs[i] for i in ids if i in self._docs}


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


def test_buscar_mantem_ordem_do_reranker_e_corta_em_20():
    docs = {f"a{i}": _doc(id_documento=f"a{i}") for i in range(25)}
    ids = [f"a{i}" for i in range(25)]
    hybrid = _FakeHybrid([(i, 1.0 / (n + 1)) for n, i in enumerate(ids)])

    resultado = buscar(
        EstruturaArgumentativa(tese_central="tese fake"),
        hybrid=hybrid,
        retriever=_FakeDocRetriever(docs),
        reranker=_FakeReranker(),
    )

    assert len(resultado) == N_RESULTS_FINAL == 20
    assert [card.id for card in resultado] == ids[:20]


def test_buscar_estrutura_vazia_levanta_value_error():
    with pytest.raises(ValueError):
        buscar(
            EstruturaArgumentativa(),
            hybrid=_FakeHybrid([]),
            retriever=_FakeDocRetriever({}),
            reranker=_FakeReranker(),
        )


def _buscar_com(hybrid, docs, **kwargs):
    return buscar(
        EstruturaArgumentativa(tese_central="tese fake"),
        hybrid=hybrid,
        retriever=_FakeDocRetriever(docs),
        reranker=_FakeReranker(),
        **kwargs,
    )


def test_buscar_so_provimento_usa_pool_30():
    docs = {"a": _doc(id_documento="a")}
    hybrid = _FakeHybrid([("a", 1.0)])

    _buscar_com(hybrid, docs, provimento=Provimento.APROVADO)

    assert hybrid.calls == [{"n_results": 30, "provimento": "APROVADO"}]


def test_buscar_com_periodo_usa_pool_80():
    from datetime import date

    docs = {"a": _doc(id_documento="a", data_julgamento=date(2022, 1, 1))}
    hybrid = _FakeHybrid([("a", 1.0)])

    _buscar_com(hybrid, docs, provimento=Provimento.APROVADO, data_inicio=date(2021, 1, 1))
    _buscar_com(hybrid, docs, data_fim=date(2023, 1, 1))

    assert [c["n_results"] for c in hybrid.calls] == [80, 80]
    assert hybrid.calls[0]["provimento"] == "APROVADO"
    assert hybrid.calls[1]["provimento"] is None


def test_buscar_sem_filtro_nao_passa_provimento_e_usa_pool_30():
    hybrid = _FakeHybrid([("a", 1.0)])

    _buscar_com(hybrid, {"a": _doc(id_documento="a")})

    assert hybrid.calls == [{"n_results": 30, "provimento": None}]


def test_buscar_sem_filtrar_nos_canais_comportamento_antigo():
    docs = {
        "a": _doc(id_documento="a", provimento=Provimento.NEGADO),
        "b": _doc(id_documento="b", provimento=Provimento.APROVADO),
    }
    hybrid = _FakeHybrid([("a", 2.0), ("b", 1.0)])

    resultado = _buscar_com(
        hybrid, docs, provimento=Provimento.APROVADO, filtrar_nos_canais=False
    )

    assert hybrid.calls == [{"n_results": 80, "provimento": None}]
    assert [c.id for c in resultado] == ["b"]
