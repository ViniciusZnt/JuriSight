"""
Reranker — reordena os candidatos da busca híbrida por cross-encoder, depois do RRF.

O RRF funde os RANKS de cada canal mas não lê o conteúdo. O cross-encoder recebe
tese e ementa JUNTAS e pontua a relevância de verdade, só sobre o pool que já
sobreviveu à primeira fase.

Via FlashRank (ONNX puro, sem PyTorch) com o modelo multilíngue
`ms-marco-MultiBERT-L-12` (~150MB, cobre português). Sem PyTorch porque a máquina é
limitada em RAM (ver README §Escalabilidade).
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

from flashrank import Ranker, RerankRequest

# Multilíngue: os modelos só-inglês do FlashRank (o default) não pontuam ementa em português.
MODEL_NAME = "ms-marco-MultiBERT-L-12"

# Uma chamada por passagem, em paralelo: pedir 50 passagens num só RerankRequest era
# muito mais lento (custo super-linear no batching da lib), e o onnxruntime libera o GIL.
# Mais de 8 workers não ajudou nesta CPU.
_MAX_WORKERS = 8

# Teto por passagem: existem ementas com mais de 60 mil caracteres, a atenção cresce ~O(n²)
# e uma só segurava o lote inteiro. A tese de um acórdão cabe nos primeiros ~1200.
_MAX_PASSAGE_CHARS = 1200


class Reranker:
    """Wrapper fino sobre o FlashRank — isola o resto do código da lib
    específica usada (mesmo espírito de QdrantStore sobre o QdrantClient)."""

    def __init__(self, cache_dir: str = "./data/index/reranker_cache", ranker: Ranker | None = None) -> None:
        """Carrega o modelo (baixa na primeira vez). `ranker` é injetável em teste."""
        self._ranker = ranker or Ranker(model_name=MODEL_NAME, cache_dir=cache_dir)
        # Criado uma vez: antes eram 8 threads criadas e destruídas a cada busca.
        self._executor = ThreadPoolExecutor(max_workers=_MAX_WORKERS)

    def rerank_scores(self, query: str, passagens: list[str]) -> list[float]:
        """Pontua cada passagem contra a query, na MESMA ordem de entrada (quem chama reordena).
        Lista vazia se `passagens` for vazia."""
        if not passagens:
            return []

        def pontuar_uma(passagem: str) -> float:
            texto = passagem[:_MAX_PASSAGE_CHARS]
            resultado = self._ranker.rerank(RerankRequest(query=query, passages=[{"id": 0, "text": texto}]))
            return float(resultado[0]["score"])

        return list(self._executor.map(pontuar_uma, passagens))
