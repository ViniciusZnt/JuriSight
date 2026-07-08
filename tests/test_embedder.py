"""
Testes do Poly-Vector Embedder (processing/embeddings/poly_vector.py).

O cliente Ollama é mockado — os testes validam a LÓGICA do embedder (batch,
validação de dimensão, fallback do sac_summary vazio) sem depender de um servidor
no ar. Um teste de integração real vive fora daqui (rodado à mão com o Ollama up).
"""
import pytest

from scraper.schema import Provimento, TipoDocumento
from processing.chunking.sac_chunker import Chunk
from processing.embeddings.poly_vector import EMBED_DIM, PolyVectorEmbedder


class _FakeOllama:
    """Cliente Ollama falso: devolve vetores de dimensão fixa e registra as chamadas."""

    def __init__(self, dim: int = EMBED_DIM):
        self.dim = dim
        self.calls: list[list[str]] = []

    def embed(self, model: str, input: list[str]):
        self.calls.append(list(input))
        # vetor determinístico por texto (comprimento = self.dim)
        return {"embeddings": [[float(len(t))] * self.dim for t in input]}


def _embedder(fake: _FakeOllama) -> PolyVectorEmbedder:
    emb = PolyVectorEmbedder()
    emb._client = fake          # injeta o mock no lugar do cliente real
    return emb


def _chunk(texto: str, sac_summary: str) -> Chunk:
    return Chunk(
        documento_id="uuid",
        texto=texto,
        texto_bruto=texto,
        sac_summary=sac_summary,
        posicao=0,
        tipo_documento=TipoDocumento.ACORDAO.value,
        provimento=Provimento.APROVADO.value,
    )


# --------------------------------------------------------------------------- #
# embed_batch                                                                  #
# --------------------------------------------------------------------------- #

def test_embed_batch_retorna_um_vetor_por_texto():
    emb = _embedder(_FakeOllama())
    vs = emb.embed_batch(["a", "bb", "ccc"])
    assert len(vs) == 3
    assert all(len(v) == EMBED_DIM for v in vs)


def test_embed_batch_lista_vazia():
    emb = _embedder(_FakeOllama())
    assert emb.embed_batch([]) == []


def test_embed_batch_dimensao_errada_falha():
    emb = _embedder(_FakeOllama(dim=512))     # modelo devolvendo dim errada
    with pytest.raises(RuntimeError, match="Dimensão"):
        emb.embed_batch(["x"])


def test_embed_batch_contagem_divergente_falha():
    fake = _FakeOllama()
    fake.embed = lambda model, input: {"embeddings": [[0.0] * EMBED_DIM]}  # 1 vetor p/ N textos
    emb = _embedder(fake)
    with pytest.raises(RuntimeError, match="vetores para"):
        emb.embed_batch(["a", "b"])


# --------------------------------------------------------------------------- #
# embed_text                                                                   #
# --------------------------------------------------------------------------- #

def test_embed_text_vazio_levanta():
    emb = _embedder(_FakeOllama())
    with pytest.raises(ValueError):
        emb.embed_text("")
    with pytest.raises(ValueError):
        emb.embed_text("   ")


def test_embed_text_unico():
    emb = _embedder(_FakeOllama())
    v = emb.embed_text("teste")
    assert len(v) == EMBED_DIM


# --------------------------------------------------------------------------- #
# embed_chunk                                                                  #
# --------------------------------------------------------------------------- #

def test_embed_chunk_usa_texto_e_sac_summary():
    fake = _FakeOllama()
    emb = _embedder(fake)
    ch = _chunk(texto="janela com prefixo", sac_summary="a ementa")
    completo, ementa = emb.embed_chunk(ch)
    assert len(completo) == EMBED_DIM and len(ementa) == EMBED_DIM
    # um único round-trip, com os dois textos na ordem certa
    assert fake.calls == [["janela com prefixo", "a ementa"]]


def test_embed_chunk_sac_vazio_cai_para_texto():
    fake = _FakeOllama()
    emb = _embedder(fake)
    ch = _chunk(texto="conteudo da sumula", sac_summary="")   # súmula: sem prefixo
    completo, ementa = emb.embed_chunk(ch)
    # ambos os inputs viram o próprio texto → vetores coincidem
    assert fake.calls == [["conteudo da sumula", "conteudo da sumula"]]
    assert completo == ementa


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
