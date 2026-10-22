"""Cross-encoders ONNX (gte-multilingual-reranker e bge-reranker-v2-m3) via
onnxruntime + tokenizers, sem PyTorch — mesma interface `rerank_scores` do
Reranker (FlashRank), para o benchmark de rerankers (sistemas S4 e S5)."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

import numpy as np

from query.search.reranker import _MAX_PASSAGE_CHARS, _MAX_WORKERS

GTE = ("onnx-community/gte-multilingual-reranker-base", "onnx/model_int8.onnx")
BGE = ("onnx-community/bge-reranker-v2-m3-ONNX", "onnx/model_int8.onnx")
CACHE_DIR = "data/index/reranker_cache"


def _carregar(repo_id: str, arquivo_onnx: str, max_tokens: int):
    """Baixa (ou usa o cache) e devolve (sessão onnx, tokenizer, tokenizer de fallback)."""
    import onnxruntime as ort
    from huggingface_hub import hf_hub_download
    from tokenizers import Tokenizer

    caminho_onnx = hf_hub_download(repo_id, arquivo_onnx, cache_dir=CACHE_DIR)
    caminho_tok = hf_hub_download(repo_id, "tokenizer.json", cache_dir=CACHE_DIR)
    sessao = ort.InferenceSession(caminho_onnx, providers=["CPUExecutionProvider"])

    def tokenizer(estrategia: str):
        tok = Tokenizer.from_file(caminho_tok)
        tok.enable_truncation(max_length=max_tokens, strategy=estrategia)
        return tok

    return sessao, tokenizer("only_second"), tokenizer("longest_first")


class CrossEncoderOnnx:
    def __init__(self, repo_id: str, arquivo_onnx: str, max_tokens: int = 512, sessao=None, tokenizer=None) -> None:
        """Input: repo_id/arquivo_onnx — modelo no Hugging Face; max_tokens —
        teto do par (query, passagem); sessao/tokenizer — injetáveis em teste."""
        self._fallback = None
        if sessao is None or tokenizer is None:
            sessao, tokenizer, self._fallback = _carregar(repo_id, arquivo_onnx, max_tokens)
        self._sessao = sessao
        self._tokenizer = tokenizer
        self._entradas = {i.name for i in sessao.get_inputs()}

    def _codificar(self, query: str, passagem: str):
        try:
            return self._tokenizer.encode(query, passagem)
        except Exception:
            # only_second falha quando a query sozinha já passa do limite: aí
            # corta os dois lados.
            if self._fallback is None:
                raise
            return self._fallback.encode(query, passagem)

    def _pontuar_uma(self, query: str, passagem: str) -> float:
        enc = self._codificar(query, passagem[:_MAX_PASSAGE_CHARS])
        todas = {
            "input_ids": enc.ids,
            "attention_mask": enc.attention_mask,
            "token_type_ids": enc.type_ids,
        }
        feed = {k: np.array([v], dtype=np.int64) for k, v in todas.items() if k in self._entradas}
        saida = self._sessao.run(None, feed)[0]
        return float(np.asarray(saida).reshape(-1)[0])

    def rerank_scores(self, query: str, passagens: list[str]) -> list[float]:
        """Logit por passagem, na ordem de entrada. Uma passagem por chamada,
        em threads: o padding do lote explode a latência (ver reranker.py)."""
        if not passagens:
            return []
        with ThreadPoolExecutor(max_workers=_MAX_WORKERS) as executor:
            return list(executor.map(lambda p: self._pontuar_uma(query, p), passagens))
