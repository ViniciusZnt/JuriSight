"""monoPTT5 (unicamp-dl/monoptt5-base) em PyTorch CPU — sistema S6 do benchmark.

Prompt e tokens conforme o model card: "Pergunta: {query} Documento: {text}
Relevante:", com "▁Sim"/"▁Não" como tokens positivo/negativo. Requer o grupo
opcional `benchmark` (uv sync --group benchmark). Mesma interface
`rerank_scores` do Reranker.
"""
from __future__ import annotations

import math

from query.search.reranker import _MAX_PASSAGE_CHARS

PROMPT = "Pergunta: {query} Documento: {text} Relevante:"
TOKEN_SIM = "▁Sim"
TOKEN_NAO = "▁Não"


def _carregar(modelo: str):
    try:
        import torch  # noqa: F401
        from transformers import AutoTokenizer, T5ForConditionalGeneration
    except ImportError as e:
        raise RuntimeError("monoPTT5 requer torch e transformers: rode `uv sync --group benchmark`") from e
    tokenizer = AutoTokenizer.from_pretrained(modelo)
    return T5ForConditionalGeneration.from_pretrained(modelo).eval(), tokenizer


def _logits_torch(model, entrada, id_sim: int, id_nao: int) -> list[tuple[float, float]]:
    """(logit_sim, logit_nao) por item do lote, no primeiro passo do decoder."""
    import torch

    with torch.inference_mode():
        decoder = torch.full((entrada["input_ids"].shape[0], 1), model.config.decoder_start_token_id)
        logits = model(**entrada, decoder_input_ids=decoder).logits[:, 0, :]
    return [(float(l[id_sim]), float(l[id_nao])) for l in logits]


class MonoPTT5:
    def __init__(self, modelo: str = "unicamp-dl/monoptt5-base", max_tokens: int = 512,
                 model=None, tokenizer=None, calcular_logits=_logits_torch) -> None:
        """Input: modelo — repo no Hugging Face; max_tokens — teto do prompt;
        model/tokenizer/calcular_logits — injetáveis em teste (sem torch)."""
        if model is None or tokenizer is None:
            model, tokenizer = _carregar(modelo)
        self._model = model
        self._tokenizer = tokenizer
        self._max_tokens = max_tokens
        self._calcular_logits = calcular_logits
        self._id_sim = tokenizer.convert_tokens_to_ids(TOKEN_SIM)
        self._id_nao = tokenizer.convert_tokens_to_ids(TOKEN_NAO)

    def _pontuar(self, query: str, passagem: str) -> float:
        prompt = PROMPT.format(query=query, text=passagem[:_MAX_PASSAGE_CHARS])
        entrada = self._tokenizer(prompt, return_tensors="pt", truncation=True, max_length=self._max_tokens)
        sim, nao = self._calcular_logits(self._model, entrada, self._id_sim, self._id_nao)[0]
        return 1.0 / (1.0 + math.exp(nao - sim))

    def rerank_scores(self, query: str, passagens: list[str]) -> list[float]:
        """P(Sim) contra Não (softmax entre os dois logits, como no card), na
        ordem de entrada. Uma passagem por chamada: sem padding de lote."""
        return [self._pontuar(query, p) for p in passagens]
