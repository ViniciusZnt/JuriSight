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

    def search(self, query, n_results, where=None, *, bm25_query=None):
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


def test_buscar_ordena_hierarquia_e_corta_em_20():
    docs = {f"a{i}": _doc(id_documento=f"a{i}") for i in range(25)}
    docs["s1"] = _doc(id_documento="s1", tipo_documento=TipoDocumento.SUMULA, hierarquia_categoria=1)
    # A súmula fica no meio do ranking (dentro do corte de 20) — só a hierarquia
    # a põe em primeiro lugar.
    ids = [f"a{i}" for i in range(5)] + ["s1"] + [f"a{i}" for i in range(5, 25)]
    hybrid = _FakeHybrid([(i, 1.0 / (n + 1)) for n, i in enumerate(ids)])

    resultado = buscar(
        EstruturaArgumentativa(tese_central="tese fake"),
        hybrid=hybrid,
        retriever=_FakeDocRetriever(docs),
        reranker=_FakeReranker(),
    )

    assert len(resultado) == N_RESULTS_FINAL == 20
    assert resultado[0].tipo_documento == TipoDocumento.SUMULA


def test_buscar_estrutura_vazia_levanta_value_error():
    with pytest.raises(ValueError):
        buscar(
            EstruturaArgumentativa(),
            hybrid=_FakeHybrid([]),
            retriever=_FakeDocRetriever({}),
            reranker=_FakeReranker(),
        )
