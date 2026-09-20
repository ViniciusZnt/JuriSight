"""
Testes do Result Formatter (query/search/result_formatter.py).

Puro — sem mocks.
"""
import pytest

from query.search.result_formatter import DocumentoDetalhe, format_results
from scraper.schema import DocumentoJuridico, Provimento, TipoDocumento


def _doc(**kwargs) -> DocumentoJuridico:
    base = dict(
        id_documento="x",
        tipo_documento=TipoDocumento.ACORDAO,
        hierarquia_categoria=4,
        numero_processo="RR-1234-56.2021.5.03.0000",
        tribunal="TST",
        turma="3ª Turma",
        relator="Min. Fulano",
        ementa="Ementa de exemplo.",
        provimento=Provimento.APROVADO,
        link_original="https://jurisprudencia.tst.jus.br/x",
    )
    base.update(kwargs)
    return DocumentoJuridico(**base)


def test_format_results_carrega_id_e_score():
    doc = _doc()
    cards = format_results([("uuid-1", doc, 0.42)])
    assert cards[0].id == "uuid-1"
    assert cards[0].score_rrf == 0.42


def test_format_results_preserva_a_ordem_de_entrada():
    doc = _doc()
    resultados = [("primeiro", doc, 0.9), ("segundo", doc, 0.1)]
    cards = format_results(resultados)
    assert [c.id for c in cards] == ["primeiro", "segundo"]


def test_format_results_projeta_campos_de_exibicao():
    doc = _doc(ementa="Ementa específica", relator="Min. Beltrano")
    cards = format_results([("uuid-1", doc, 0.5)])
    card = cards[0]
    assert card.ementa == "Ementa específica"
    assert card.relator == "Min. Beltrano"
    assert card.provimento == Provimento.APROVADO
    assert card.tipo_documento == TipoDocumento.ACORDAO


def test_documento_detalhe_adiciona_id_ao_documento_completo():
    doc = _doc()
    detalhe = DocumentoDetalhe(id="uuid-1", **doc.model_dump())
    assert detalhe.id == "uuid-1"
    assert detalhe.ementa == doc.ementa


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
