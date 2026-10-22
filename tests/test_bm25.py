"""
Testes do BM25 Builder (indexing/lexical/bm25_builder.py).

Unit tests puros — sem Ollama nem DB. Cobrem a tokenização, o ciclo
build→save→load→search e os casos-limite (corpus vazio, indexar texto_bruto).
"""
import json
import logging

import pytest

from scraper.schema import Provimento, TipoDocumento
from processing.chunking.sac_chunker import Chunk
from indexing.lexical.bm25_builder import (
    PROVIMENTOS_FILENAME,
    BM25Builder,
    _tokenize,
    gravar_provimentos,
)


def _chunk(
    documento_id: str,
    posicao: int,
    texto_bruto: str,
    sac_summary: str = "resumo",
    provimento: str = Provimento.APROVADO.value,
) -> Chunk:
    return Chunk(
        documento_id=documento_id,
        texto=f"{sac_summary}\n\n{texto_bruto}",
        texto_bruto=texto_bruto,
        sac_summary=sac_summary,
        posicao=posicao,
        tipo_documento=TipoDocumento.ACORDAO.value,
        provimento=provimento,
    )


# --------------------------------------------------------------------------- #
# _tokenize                                                                    #
# --------------------------------------------------------------------------- #

def test_tokenize_minusculas_e_sem_acento():
    assert _tokenize("Exposição") == ["exposicao"]


def test_tokenize_quebra_termos_juridicos():
    # "e" e "a" são stopwords → removidas; siglas e números ficam.
    assert _tokenize("NR-15 e a CLT art. 193") == ["nr", "15", "clt", "art", "193"]


def test_tokenize_remove_stopwords():
    assert _tokenize("o trabalhador foi exposto ao benzeno") == ["trabalhador", "exposto", "benzeno"]


def test_tokenize_preserva_nao():
    # "nao" é mantido de propósito (negação relevante na busca).
    assert "nao" in _tokenize("nao provido o recurso")


def test_tokenize_vazio():
    assert _tokenize("") == []
    assert _tokenize("  ...  ") == []


# --------------------------------------------------------------------------- #
# build → save → load → search                                                #
# --------------------------------------------------------------------------- #

def test_ciclo_completo_recupera_chunk_certo(tmp_path):
    chunks = [
        _chunk("d1", 0, "Adicional de insalubridade por exposicao a benzeno acima da NR-15."),
        _chunk("d2", 0, "Horas extras e intervalo intrajornada suprimido de bancario."),
        _chunk("d3", 0, "Periculosidade por inflamaveis, CLT art. 193 e Sumula 447."),
    ]
    path = tmp_path / "bm25.pkl"
    b = BM25Builder(index_path=path)
    b.add(chunks)
    b.build_and_save()
    assert path.exists()

    loaded = BM25Builder.load(path)
    assert loaded.search("benzeno NR-15", n=1)[0][0] == "d1:0"
    assert loaded.search("horas extras", n=1)[0][0] == "d2:0"
    assert loaded.search("CLT art 193 periculosidade", n=1)[0][0] == "d3:0"


def test_search_respeita_n(tmp_path):
    chunks = [_chunk("d", i, f"texto termo{i} comum") for i in range(5)]
    path = tmp_path / "bm25.pkl"
    b = BM25Builder(index_path=path)
    b.add(chunks)
    b.build_and_save()
    loaded = BM25Builder.load(path)
    assert len(loaded.search("comum", n=3)) == 3


# --------------------------------------------------------------------------- #
# Provimento por chunk e filtro                                                #
# --------------------------------------------------------------------------- #

def _indice_com_provimentos(tmp_path):
    chunks = [
        _chunk("d1", 0, "benzeno insalubridade", provimento=Provimento.NEGADO.value),
        _chunk("d2", 0, "benzeno insalubridade grau maximo", provimento=Provimento.APROVADO.value),
        _chunk("d3", 0, "benzeno periculosidade", provimento=Provimento.NEGADO.value),
        _chunk("d4", 0, "horas extras", provimento=Provimento.PARCIAL.value),
    ]
    path = tmp_path / "idx"
    b = BM25Builder(index_path=path)
    b.add(chunks)
    b.build_and_save()
    return path


def test_build_grava_provimentos(tmp_path):
    path = _indice_com_provimentos(tmp_path)
    provs = json.loads((path / PROVIMENTOS_FILENAME).read_text())
    ids = json.loads((path / "chunk_ids.json").read_text())
    assert ids == ["d1:0", "d2:0", "d3:0", "d4:0"]
    assert provs == ["NEGADO", "APROVADO", "NEGADO", "PARCIAL"]


def test_search_com_filtro_so_traz_o_provimento(tmp_path):
    loaded = BM25Builder.load(_indice_com_provimentos(tmp_path))
    # sem filtro o comportamento antigo se mantém: completa o top-n com score 0
    assert len(loaded.search("benzeno", n=10)) == 4
    res = loaded.search("benzeno", n=10, provimento="APROVADO")
    assert [c for c, _ in res] == ["d2:0"]


def test_search_com_filtro_descarta_score_zero(tmp_path):
    loaded = BM25Builder.load(_indice_com_provimentos(tmp_path))
    res = loaded.search("benzeno", n=4, provimento="PARCIAL")
    assert res == []  # d4 é PARCIAL mas não tem o termo
    res = loaded.search("extras", n=4, provimento="PARCIAL")
    assert [c for c, _ in res] == ["d4:0"]


def test_search_provimento_sem_chunks_devolve_vazio(tmp_path):
    loaded = BM25Builder.load(_indice_com_provimentos(tmp_path))
    assert loaded.search("benzeno", n=5, provimento="NAO_APLICAVEL") == []


def test_search_sem_filtro_inalterada(tmp_path):
    loaded = BM25Builder.load(_indice_com_provimentos(tmp_path))
    sem = loaded.search("benzeno", n=3)
    assert loaded.search("benzeno", n=3, provimento=None) == sem
    assert {c for c, _ in sem} == {"d1:0", "d3:0", "d2:0"}


def test_search_sem_arquivo_ignora_filtro(tmp_path, caplog):
    path = _indice_com_provimentos(tmp_path)
    (path / PROVIMENTOS_FILENAME).unlink()
    loaded = BM25Builder.load(path)
    esperado = loaded.search("benzeno", n=10)
    with caplog.at_level(logging.WARNING):
        assert loaded.search("benzeno", n=10, provimento="APROVADO") == esperado
        assert loaded.search("benzeno", n=10, provimento="APROVADO") == esperado
    assert len([r for r in caplog.records if r.levelno == logging.WARNING]) == 1


def test_load_rejeita_provimentos_desalinhados(tmp_path):
    path = _indice_com_provimentos(tmp_path)
    gravar_provimentos(path, ["APROVADO"])
    with pytest.raises(ValueError, match="sincronizar"):
        BM25Builder.load(path)


def test_gravar_provimentos_atomico(tmp_path):
    gravar_provimentos(tmp_path, ["A", "B"])
    assert json.loads((tmp_path / PROVIMENTOS_FILENAME).read_text()) == ["A", "B"]
    assert not list(tmp_path.glob("*.tmp"))


# --------------------------------------------------------------------------- #
# Casos-limite                                                                 #
# --------------------------------------------------------------------------- #

def test_build_corpus_vazio_levanta(tmp_path):
    b = BM25Builder(index_path=tmp_path / "bm25.pkl")
    with pytest.raises(ValueError):
        b.build_and_save()


def test_indexa_texto_bruto_e_nao_texto():
    """BM25 tokeniza texto_bruto (janela crua), não texto (com prefixo SAC)."""
    chunk = _chunk("d1", 0, texto_bruto="janela crua", sac_summary="resumo prefixo")
    b = BM25Builder()
    b.add([chunk])
    # o corpus tem os tokens da JANELA; os do prefixo SAC ficam de fora.
    assert b._corpus_tokens == [["janela", "crua"]]
    assert "resumo" not in b._corpus_tokens[0]
    assert b._chunk_ids == ["d1:0"]


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
