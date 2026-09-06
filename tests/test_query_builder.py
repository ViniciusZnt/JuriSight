"""
Testes do Query Builder (query/enrichment/query_builder.py).

Puramente determinístico — sem mocks, sem LLM.
"""
import pytest

from query.enrichment.query_builder import build_bm25_query, build_frase_tese
from query.enrichment.schema import EstruturaArgumentativa


def _estrutura(**kwargs) -> EstruturaArgumentativa:
    base = dict(
        pedido_principal="adicional de insalubridade grau máximo",
        agente_nocivo=["benzeno"],
        violacoes=["ausência de EPI eficaz"],
        normas=["NR-15", "CLT art. 192"],
        empresa_ciente=True,
        setor="metalurgia",
        cargo="operador de prensa",
        tese_central="A empresa tinha ciência do risco e não forneceu proteção adequada.",
    )
    base.update(kwargs)
    return EstruturaArgumentativa(**base)


# --------------------------------------------------------------------------- #
# build_bm25_query                                                             #
# --------------------------------------------------------------------------- #

def test_build_bm25_query_inclui_termos_exatos():
    q = build_bm25_query(_estrutura())
    assert "adicional de insalubridade grau máximo" in q
    assert "benzeno" in q
    assert "ausência de EPI eficaz" in q
    assert "NR-15" in q and "CLT art. 192" in q


def test_build_bm25_query_exclui_tese_central_e_setor_cargo():
    q = build_bm25_query(_estrutura())
    assert "tinha ciência do risco" not in q
    assert "metalurgia" not in q
    assert "operador de prensa" not in q


def test_build_bm25_query_estrutura_vazia_devolve_string_vazia():
    assert build_bm25_query(EstruturaArgumentativa()) == ""


# --------------------------------------------------------------------------- #
# build_frase_tese                                                             #
# --------------------------------------------------------------------------- #

def test_build_frase_tese_usa_tese_central_quando_presente():
    frase = build_frase_tese(_estrutura())
    assert frase == "A empresa tinha ciência do risco e não forneceu proteção adequada."


def test_build_frase_tese_cai_para_pedido_e_violacoes_sem_tese_central():
    estrutura = _estrutura(tese_central="")
    frase = build_frase_tese(estrutura)
    assert "adicional de insalubridade grau máximo" in frase
    assert "ausência de EPI eficaz" in frase


def test_build_frase_tese_levanta_erro_quando_tudo_vazio():
    with pytest.raises(ValueError):
        build_frase_tese(EstruturaArgumentativa())


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
