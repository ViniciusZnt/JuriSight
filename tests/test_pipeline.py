"""
Testes de query/search/pipeline.py::buscar — o pipeline do /query chamado
direto, sem HTTP. Nenhuma infra real: hybrid/retriever são fakes.
"""
import pytest

from query.enrichment.schema import EstruturaArgumentativa
from query.search.pipeline import N_CANDIDATOS_COM_FILTRO, buscar
from scraper.schema import Provimento
from tests.fakes import FakeDocRetriever, documento_fake


class _FakeHybrid:
    def __init__(self, resultados: list[tuple[str, float]]):
        self._resultados = resultados
        self.calls: list[dict] = []
        self.ids: list[list[str] | None] = []

    def search(self, query, n_results, where=None, *, bm25_query=None, provimento=None, documento_ids=None):
        self.calls.append({"n_results": n_results, "provimento": provimento})
        self.ids.append(documento_ids)
        return self._resultados[:n_results]


def test_buscar_mantem_ordem_do_rrf_e_corta_em_n_resultados():
    ids = [f"a{i}" for i in range(60)]
    docs = {i: documento_fake(id_documento=i) for i in ids}
    hybrid = _FakeHybrid([(i, 1.0 / (n + 1)) for n, i in enumerate(ids)])

    cards = buscar(EstruturaArgumentativa(tese_central="tese fake"), hybrid=hybrid,
                   retriever=FakeDocRetriever(docs), n_resultados=50)

    assert [c.id for c in cards] == ids[:50]
    assert hybrid.calls[0]["n_results"] == 50


def test_buscar_estrutura_vazia_levanta_value_error():
    with pytest.raises(ValueError):
        buscar(EstruturaArgumentativa(), hybrid=_FakeHybrid([]), retriever=FakeDocRetriever({}), n_resultados=50)


def test_buscar_devolve_score_rrf_cru():
    docs = {i: documento_fake(id_documento=i) for i in ("a", "b")}
    cards = buscar(EstruturaArgumentativa(tese_central="t"), hybrid=_FakeHybrid([("a", 0.9), ("b", 0.5)]),
                   retriever=FakeDocRetriever(docs), n_resultados=50)
    assert [c.score_rrf for c in cards] == [0.9, 0.5]


def _buscar_com(hybrid, docs, **kwargs):
    return buscar(
        EstruturaArgumentativa(tese_central="tese fake"),
        hybrid=hybrid,
        retriever=FakeDocRetriever(docs),
        n_resultados=50,
        **kwargs,
    )


def test_buscar_so_provimento_usa_pool_n_resultados():
    docs = {"a": documento_fake(id_documento="a")}
    hybrid = _FakeHybrid([("a", 1.0)])

    _buscar_com(hybrid, docs, provimento=Provimento.APROVADO)

    assert hybrid.calls == [{"n_results": 50, "provimento": "APROVADO"}]


def test_buscar_com_periodo_usa_pool_120_e_corta_depois_do_filtro():
    from datetime import date

    docs = {"a": documento_fake(id_documento="a", data_julgamento=date(2022, 1, 1))}
    hybrid = _FakeHybrid([("a", 1.0)])

    _buscar_com(hybrid, docs, provimento=Provimento.APROVADO, data_inicio=date(2021, 1, 1))
    _buscar_com(hybrid, docs, data_fim=date(2023, 1, 1))

    assert [c["n_results"] for c in hybrid.calls] == [N_CANDIDATOS_COM_FILTRO] * 2 == [120, 120]
    assert hybrid.calls[0]["provimento"] == "APROVADO"
    assert hybrid.calls[1]["provimento"] is None


def test_buscar_sem_filtro_nao_passa_provimento_e_usa_pool_n_resultados():
    hybrid = _FakeHybrid([("a", 1.0)])

    _buscar_com(hybrid, {"a": documento_fake(id_documento="a")})

    assert hybrid.calls == [{"n_results": 50, "provimento": None}]


def test_buscar_com_ids_usa_pool_normal():
    hybrid = _FakeHybrid([("a", 1.0)])

    _buscar_com(hybrid, {"a": documento_fake(id_documento="a")}, documento_ids=["a", "b"])

    assert hybrid.calls[0]["n_results"] == 50
    assert hybrid.ids == [["a", "b"]]


def test_buscar_com_lista_vazia_nao_busca():
    hybrid = _FakeHybrid([("a", 1.0)])

    assert _buscar_com(hybrid, {"a": documento_fake(id_documento="a")}, documento_ids=[]) == []
    assert hybrid.calls == []


def test_buscar_marca_canais_nos_cards_quando_pedido():
    class _HybridComCanais(_FakeHybrid):
        def search(self, query, n_results, where=None, *, bm25_query=None, provimento=None, documento_ids=None, canais=None):
            canais.update({"a0": ["semantica", "termos"], "a1": ["termos"]})
            return super().search(query, n_results)

    docs = {i: documento_fake(id_documento=i) for i in ("a0", "a1")}
    cards = buscar(
        EstruturaArgumentativa(tese_central="t"),
        hybrid=_HybridComCanais([("a0", 1.0), ("a1", 0.5)]),
        retriever=FakeDocRetriever(docs),
        n_resultados=50,
        marcar_canais=True,
    )
    assert {c.id: c.canais for c in cards} == {"a0": ["semantica", "termos"], "a1": ["termos"]}


def test_buscar_sem_marcar_canais_nao_passa_o_kwarg():
    docs = {"a0": documento_fake(id_documento="a0")}
    cards = buscar(EstruturaArgumentativa(tese_central="t"), hybrid=_FakeHybrid([("a0", 1.0)]),
                   retriever=FakeDocRetriever(docs), n_resultados=50)
    assert cards[0].canais == []


def test_buscar_com_periodo_corta_em_n_resultados_depois_do_filtro():
    from datetime import date

    ids = [f"a{i}" for i in range(100)]
    docs = {i: documento_fake(id_documento=i, data_julgamento=date(2022, 1, 1)) for i in ids}
    cards = buscar(EstruturaArgumentativa(tese_central="t"), hybrid=_FakeHybrid([(i, 1.0) for i in ids]),
                   retriever=FakeDocRetriever(docs), n_resultados=50, data_inicio=date(2021, 1, 1))
    assert len(cards) == 50
