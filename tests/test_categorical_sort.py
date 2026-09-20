"""
Testes do Categorical Sort / Hierarchical Ranker (query/search/categorical_sort.py).

Puro — sem mocks. Constrói DocumentoJuridico mínimos para exercitar a ordenação.
"""
from datetime import date

import pytest

from query.search.categorical_sort import ordenar
from scraper.schema import DocumentoJuridico, Provimento, TipoDocumento


def _doc(tipo: TipoDocumento, hierarquia: int, data: date | None = None) -> DocumentoJuridico:
    return DocumentoJuridico(
        id_documento="x",
        tipo_documento=tipo,
        hierarquia_categoria=hierarquia,
        data_julgamento=data,
        provimento=Provimento.NAO_APLICAVEL,
    )


def test_ordenar_hierarquia_e_criterio_primario():
    sumula = _doc(TipoDocumento.SUMULA, 1)
    acordao = _doc(TipoDocumento.ACORDAO, 4)
    # o acórdão tem score MAIOR, mas a súmula deve vir primeiro mesmo assim.
    resultados = [("acordao-id", acordao, 99.0), ("sumula-id", sumula, 1.0)]

    ordenados = ordenar(resultados, por="relevancia")

    assert [doc_id for doc_id, _, _ in ordenados] == ["sumula-id", "acordao-id"]


def test_ordenar_por_relevancia_dentro_da_mesma_categoria():
    a = _doc(TipoDocumento.ACORDAO, 4)
    b = _doc(TipoDocumento.ACORDAO, 4)
    resultados = [("baixo", a, 0.5), ("alto", b, 0.9)]

    ordenados = ordenar(resultados, por="relevancia")

    assert [doc_id for doc_id, _, _ in ordenados] == ["alto", "baixo"]


def test_ordenar_por_data_dentro_da_mesma_categoria():
    recente = _doc(TipoDocumento.ACORDAO, 4, date(2026, 1, 1))
    antigo = _doc(TipoDocumento.ACORDAO, 4, date(2020, 1, 1))
    resultados = [("antigo", antigo, 1.0), ("recente", recente, 1.0)]

    ordenados = ordenar(resultados, por="data")

    assert [doc_id for doc_id, _, _ in ordenados] == ["recente", "antigo"]


def test_ordenar_por_data_none_vai_para_o_fim():
    com_data = _doc(TipoDocumento.ACORDAO, 4, date(2020, 1, 1))
    sem_data = _doc(TipoDocumento.ACORDAO, 4, None)
    resultados = [("sem-data", sem_data, 1.0), ("com-data", com_data, 1.0)]

    ordenados = ordenar(resultados, por="data")

    assert [doc_id for doc_id, _, _ in ordenados] == ["com-data", "sem-data"]


def test_ordenar_preserva_o_documento_id_atraves_da_ordenacao():
    doc = _doc(TipoDocumento.SUMULA, 1)
    resultados = [("uuid-especifico", doc, 1.0)]

    ordenados = ordenar(resultados)

    assert ordenados[0][0] == "uuid-especifico"


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
