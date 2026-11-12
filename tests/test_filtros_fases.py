"""Testes de query/filtros/fases.py: fase do processo pela classe e quando a busca é restrita."""
from query.enrichment.schema import EstruturaArgumentativa
from query.filtros.fases import CLASSES, condicao_fase, tem_filtro_restrito


def test_execucao_cobre_ap_e_aiap():
    sql, params = condicao_fase("execucao")
    assert "x.sigla_classe" in sql and params == [["AP", "AIAP"]]


def test_conhecimento_cobre_as_classes_de_conhecimento():
    assert condicao_fase("conhecimento")[1] == [list(CLASSES["conhecimento"])]
    assert "ROT" in CLASSES["conhecimento"]


def test_outras_exclui_conhecimento_e_execucao_e_inclui_nulo():
    sql, params = condicao_fase("outras")
    assert "IS NULL" in sql and "NOT" in sql
    assert "ROT" in params[0] and "AP" in params[0]


def test_tem_filtro_restrito():
    assert not tem_filtro_restrito(EstruturaArgumentativa())
    assert tem_filtro_restrito(EstruturaArgumentativa(tribunais=["TRT4"]))
    assert tem_filtro_restrito(EstruturaArgumentativa(fase="execucao"))
    assert tem_filtro_restrito(EstruturaArgumentativa(dispositivos=["art_1_clt"]))
    assert tem_filtro_restrito(EstruturaArgumentativa(expressoes=["x"]))
