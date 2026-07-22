"""
Testes do Poly-Vector Embedder (processing/embeddings/poly_vector.py).

O cliente OpenAI é mockado — os testes validam a LÓGICA do embedder (batch,
validação de dimensão, fallback do sac_summary vazio) sem chamar a API. Um teste
de integração real vive fora daqui (rodado à mão com a OPENAI_API_KEY setada).
"""
import pytest

from scraper.schema import Provimento, TipoDocumento
from processing.chunking.sac_chunker import Chunk
from processing.embeddings.poly_vector import EMBED_DIM, PolyVectorEmbedder


class _FakeItem:
    def __init__(self, index: int, embedding: list[float]):
        self.index = index
        self.embedding = embedding


class _FakeResponse:
    def __init__(self, data: list[_FakeItem]):
        self.data = data


class _FakeEmbeddings:
    def __init__(self, parent: "_FakeOpenAI"):
        self._parent = parent

    def create(self, model: str, input: list[str]):
        self._parent.calls.append(list(input))
        # vetor determinístico por texto (comprimento = self._parent.dim)
        return _FakeResponse(
            [_FakeItem(i, [float(len(t))] * self._parent.dim) for i, t in enumerate(input)]
        )


class _FakeOpenAI:
    """Cliente OpenAI falso: expõe .embeddings.create e registra as chamadas."""

    def __init__(self, dim: int = EMBED_DIM):
        self.dim = dim
        self.calls: list[list[str]] = []
        self.embeddings = _FakeEmbeddings(self)


def _embedder(fake: _FakeOpenAI) -> PolyVectorEmbedder:
    return PolyVectorEmbedder(client=fake)  # injeta o mock no lugar do cliente real


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
    emb = _embedder(_FakeOpenAI())
    vs = emb.embed_batch(["a", "bb", "ccc"])
    assert len(vs) == 3
    assert all(len(v) == EMBED_DIM for v in vs)


def test_embed_batch_lista_vazia():
    emb = _embedder(_FakeOpenAI())
    assert emb.embed_batch([]) == []


def test_embed_batch_reordena_por_index():
    """A API pode devolver fora de ordem; o embedder reordena por .index."""
    fake = _FakeOpenAI()
    fake.embeddings.create = lambda model, input: _FakeResponse(
        [_FakeItem(1, [2.0] * EMBED_DIM), _FakeItem(0, [1.0] * EMBED_DIM)]
    )
    vs = _embedder(fake).embed_batch(["primeiro", "segundo"])
    assert vs[0][0] == 1.0 and vs[1][0] == 2.0   # index 0 antes de index 1


def test_embed_batch_dimensao_errada_falha():
    emb = _embedder(_FakeOpenAI(dim=512))     # API devolvendo dim errada
    with pytest.raises(RuntimeError, match="Dimensão"):
        emb.embed_batch(["x"])


# --------------------------------------------------------------------------- #
# embed_text                                                                   #
# --------------------------------------------------------------------------- #

def test_embed_text_vazio_levanta():
    emb = _embedder(_FakeOpenAI())
    with pytest.raises(ValueError):
        emb.embed_text("")
    with pytest.raises(ValueError):
        emb.embed_text("   ")


def test_embed_text_unico():
    emb = _embedder(_FakeOpenAI())
    v = emb.embed_text("teste")
    assert len(v) == EMBED_DIM


# --------------------------------------------------------------------------- #
# embed_chunk                                                                  #
# --------------------------------------------------------------------------- #

def test_embed_chunk_usa_texto_e_sac_summary():
    fake = _FakeOpenAI()
    emb = _embedder(fake)
    ch = _chunk(texto="janela com prefixo", sac_summary="a ementa")
    completo, ementa = emb.embed_chunk(ch)
    assert len(completo) == EMBED_DIM and len(ementa) == EMBED_DIM
    # um único round-trip, com os dois textos na ordem certa
    assert fake.calls == [["janela com prefixo", "a ementa"]]


def test_embed_chunk_sac_vazio_cai_para_texto():
    fake = _FakeOpenAI()
    emb = _embedder(fake)
    ch = _chunk(texto="conteudo da sumula", sac_summary="")   # súmula: sem prefixo
    completo, ementa = emb.embed_chunk(ch)
    # ambos os inputs viram o próprio texto → vetores coincidem
    assert fake.calls == [["conteudo da sumula", "conteudo da sumula"]]
    assert completo == ementa


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
