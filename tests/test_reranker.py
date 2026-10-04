"""
Testes do Reranker (query/search/reranker.py).

Unit test puro — o FlashRank real (Ranker) é substituído por um fake injetado
via o parâmetro `ranker` (mesmo padrão de QueryEnricher(client=...)): nunca
baixa/carrega o modelo ONNX real em teste. Cobre só a lógica própria deste
módulo — uma chamada ao Ranker POR passagem, em paralelo, remontando a lista
na ordem de entrada — não a qualidade do re-ranking em si (isso é
responsabilidade do FlashRank).
"""
from __future__ import annotations

from query.search.reranker import Reranker, _MAX_PASSAGE_CHARS


class _FakeFlashRankRanker:
    """Substitui flashrank.Ranker — cada chamada a rerank() recebe exatamente
    1 passagem (é assim que Reranker.rerank_scores chama, ver o módulo), e
    devolve o score pelo TEXTO (não por índice — cada chamada não sabe a
    posição original da passagem no lote)."""

    def __init__(self, score_por_texto: dict[str, float] | None = None):
        self._score_por_texto = score_por_texto or {}
        self.textos_recebidos: list[str] = []

    def rerank(self, request):
        assert len(request.passages) == 1
        texto = request.passages[0]["text"]
        self.textos_recebidos.append(texto)
        return [{"id": 0, "text": texto, "score": self._score_por_texto.get(texto, 0.0)}]


def test_rerank_scores_preserva_ordem_de_entrada():
    fake = _FakeFlashRankRanker({"a": 0.2, "b": 0.9, "c": 0.5})
    reranker = Reranker(ranker=fake)

    scores = reranker.rerank_scores("query", ["a", "b", "c"])

    assert scores == [0.2, 0.9, 0.5]


def test_rerank_scores_lista_vazia():
    reranker = Reranker(ranker=_FakeFlashRankRanker())
    assert reranker.rerank_scores("query", []) == []


def test_rerank_scores_trunca_passagem_gigante():
    """Regressão: uma única ementa-outlier gigante (existem casos >60 mil
    caracteres na base real) não deve ir inteira pro cross-encoder — a
    atenção escala ~O(n²) com o tamanho, e isso travava uma thread inteira do
    pool enquanto as outras já tinham terminado (ver _MAX_PASSAGE_CHARS)."""
    fake = _FakeFlashRankRanker()
    reranker = Reranker(ranker=fake)

    passagem_gigante = "x" * 50_000
    reranker.rerank_scores("query", [passagem_gigante])

    assert len(fake.textos_recebidos[0]) == _MAX_PASSAGE_CHARS
