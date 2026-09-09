"""
Testes do Doc Retriever (query/search/doc_retriever.py).

`DocRetriever.fetch()` fala com um PostgreSQL real via psycopg — sem injeção de
conexão, então não dá para testá-lo fim-a-fim sem infraestrutura (mesmo padrão
do resto do repo: nenhum teste de código de ingestão bate num banco real). O que
É puro e testável sem infra é `_row_para_documento` — a função que mapeia uma
linha do `_SELECT_BY_IDS` para um `DocumentoJuridico` — e é exatamente aí que
mora o risco real: um índice de coluna errado nessa função quebra silenciosamente
em produção sem nenhum teste pegar.
"""
import pytest

from query.search.doc_retriever import DocRetriever, _row_para_documento
from scraper.schema import Provimento, TipoDocumento

# Uma linha completa, na MESMA ordem de colunas de _SELECT_BY_IDS.
_ROW_COMPLETA = (
    "11111111-1111-1111-1111-111111111111",  # 0  id (UUID, não entra no schema)
    "TST-RR-100-44.2021.5.01.0019",           # 1  id_documento
    "ACORDAO",                                 # 2  tipo_documento
    4,                                          # 3  hierarquia_categoria
    None,                                       # 4  data_filtro
    "TST-RR-100-44.2021.5.01.0019",           # 5  numero_processo
    "TST",                                      # 6  tribunal
    "Recurso de Revista",                       # 7  classe_processo
    "RR",                                       # 8  sigla_classe
    "Min. Alberto Bresciani",                   # 9  relator
    "3ª Turma",                                 # 10 turma
    "Gab. Min. Bresciani",                      # 11 gabinete
    None,                                       # 12 data_julgamento
    None,                                       # 13 data_juntada
    "cabeçalho",                                 # 14 cabecalho
    "ementa de exemplo",                        # 15 ementa
    "relatório",                                 # 16 relatorio
    "fundamentação",                             # 17 fundamentacao
    "acórdão",                                   # 18 acordao
    "votos",                                     # 19 votos
    True,                                        # 20 possui_ementa
    ["NR-15", "CLT art. 192"],                  # 21 referencia_legislativa
    "APROVADO",                                  # 22 provimento
    "https://jurisprudencia.tst.jus.br/x",      # 23 link_original
)


def test_row_para_documento_mapeia_todos_os_campos_na_ordem_certa():
    doc = _row_para_documento(_ROW_COMPLETA)

    assert doc.id_documento == "TST-RR-100-44.2021.5.01.0019"
    assert doc.tipo_documento == TipoDocumento.ACORDAO
    assert doc.hierarquia_categoria == 4
    assert doc.numero_processo == "TST-RR-100-44.2021.5.01.0019"
    assert doc.tribunal == "TST"
    assert doc.classe_processo == "Recurso de Revista"
    assert doc.sigla_classe == "RR"
    assert doc.relator == "Min. Alberto Bresciani"
    assert doc.turma == "3ª Turma"
    assert doc.gabinete == "Gab. Min. Bresciani"
    assert doc.cabecalho == "cabeçalho"
    assert doc.ementa == "ementa de exemplo"
    assert doc.relatorio == "relatório"
    assert doc.fundamentacao == "fundamentação"
    assert doc.acordao == "acórdão"
    assert doc.votos == "votos"
    assert doc.possui_ementa is True
    assert doc.referencia_legislativa == ["NR-15", "CLT art. 192"]
    assert doc.provimento == Provimento.APROVADO
    assert doc.link_original == "https://jurisprudencia.tst.jus.br/x"


def test_row_para_documento_colunas_texto_nulas_viram_string_vazia():
    row = list(_ROW_COMPLETA)
    for indice_texto in (5, 6, 7, 8, 9, 10, 11, 14, 15, 16, 17, 18, 19):
        row[indice_texto] = None
    doc = _row_para_documento(tuple(row))

    assert doc.numero_processo == ""
    assert doc.tribunal == ""
    assert doc.relator == ""
    assert doc.ementa == ""
    assert doc.acordao == ""


def test_row_para_documento_possui_ementa_none_vira_false():
    row = list(_ROW_COMPLETA)
    row[20] = None
    doc = _row_para_documento(tuple(row))
    assert doc.possui_ementa is False


def test_row_para_documento_referencia_legislativa_none_vira_lista_vazia():
    row = list(_ROW_COMPLETA)
    row[21] = None
    doc = _row_para_documento(tuple(row))
    assert doc.referencia_legislativa == []


def test_row_para_documento_preserva_datas_quando_presentes():
    from datetime import date

    row = list(_ROW_COMPLETA)
    row[12] = date(2025, 4, 27)  # data_julgamento
    row[13] = date(2025, 4, 28)  # data_juntada
    doc = _row_para_documento(tuple(row))

    assert doc.data_julgamento == date(2025, 4, 27)
    assert doc.data_juntada == date(2025, 4, 28)


def test_row_para_documento_provimento_negado():
    row = list(_ROW_COMPLETA)
    row[22] = "NEGADO"
    doc = _row_para_documento(tuple(row))
    assert doc.provimento == Provimento.NEGADO


def test_row_para_documento_sumula_hierarquia_um():
    row = list(_ROW_COMPLETA)
    row[2] = "SUMULA"
    row[3] = 1
    doc = _row_para_documento(tuple(row))
    assert doc.tipo_documento == TipoDocumento.SUMULA
    assert doc.hierarquia_categoria == 1


@pytest.mark.parametrize("tipo,hierarquia", [("OJ", 2), ("PRECEDENTE", 3)])
def test_row_para_documento_tipos_documento_restantes(tipo, hierarquia):
    row = list(_ROW_COMPLETA)
    row[2] = tipo
    row[3] = hierarquia
    doc = _row_para_documento(tuple(row))
    assert doc.tipo_documento == TipoDocumento(tipo)
    assert doc.hierarquia_categoria == hierarquia


@pytest.mark.parametrize("provimento", ["PARCIAL", "NAO_APLICAVEL"])
def test_row_para_documento_provimentos_restantes(provimento):
    row = list(_ROW_COMPLETA)
    row[22] = provimento
    doc = _row_para_documento(tuple(row))
    assert doc.provimento == Provimento(provimento)


# --------------------------------------------------------------------------- #
# DocRetriever.fetch — só o caminho que não toca o banco (lista vazia)         #
# --------------------------------------------------------------------------- #

def test_fetch_lista_vazia_nao_abre_conexao():
    retriever = DocRetriever("postgresql://usuario-invalido-de-proposito")
    assert retriever.fetch([]) == {}


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
