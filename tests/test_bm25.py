"""
Testes do BM25 Builder (indexing/lexical/bm25_builder.py).

Unit tests puros — sem Ollama nem DB. Cobrem a tokenização, o ciclo
build→save→load→search e os casos-limite (corpus vazio, indexar texto_bruto).
"""
import pytest

from scraper.schema import Provimento, TipoDocumento
from processing.chunking.sac_chunker import Chunk
from indexing.lexical.bm25_builder import BM25Builder, _tokenize


def _chunk(documento_id: str, posicao: int, texto_bruto: str, sac_summary: str = "resumo") -> Chunk:
    return Chunk(
        documento_id=documento_id,
        texto=f"{sac_summary}\n\n{texto_bruto}",
        texto_bruto=texto_bruto,
        sac_summary=sac_summary,
        posicao=posicao,
        tipo_documento=TipoDocumento.ACORDAO.value,
        provimento=Provimento.APROVADO.value,
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
