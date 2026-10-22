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
    """(logit_sim, logit_nao) por item do lote, no primeiro passo do decoder.
    `entrada` traz listas de ids; a conversão para tensor fica aqui."""
    import torch

    tensores = {k: torch.tensor(v, dtype=torch.long) for k, v in entrada.items()}
    with torch.inference_mode():
        decoder = torch.full((tensores["input_ids"].shape[0], 1), model.config.decoder_start_token_id)
        logits = model(**tensores, decoder_input_ids=decoder).logits[:, 0, :]
    return [(float(l[id_sim]), float(l[id_nao])) for l in logits]


def _sigmoide(x: float) -> float:
    if x >= 0:
        return 1.0 / (1.0 + math.exp(-x))
    e = math.exp(x)
    return e / (1.0 + e)


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
        for token, id_ in ((TOKEN_SIM, self._id_sim), (TOKEN_NAO, self._id_nao)):
            if id_ is None or id_ == tokenizer.unk_token_id:
                raise RuntimeError(f"Token {token!r} ausente do vocabulário do tokenizer")
        if self._id_sim == self._id_nao:
            raise RuntimeError("Tokens Sim/Não com o mesmo id")
        self._eos = tokenizer.eos_token_id
        self._cabeca = self._ids("Pergunta:")
        self._meio = self._ids("Documento:")
        self._sufixo = self._ids(" Relevante:")

    def _ids(self, texto: str) -> list[int]:
        return list(self._tokenizer(texto, add_special_tokens=False)["input_ids"])

    def _montar(self, query: str, passagem: str) -> dict[str, list[list[int]]]:
        """Prompt do card com o sufixo " Relevante:" e o eos sempre no fim: só
        o documento (e, se preciso, a query) é truncado, nunca o sufixo."""
        fixos = len(self._cabeca) + len(self._meio) + len(self._sufixo) + 1  # +eos
        livre = max(self._max_tokens - fixos, 0)
        ids_query = self._ids(query)
        if len(ids_query) > livre:  # query sozinha estoura: fica com metade do espaço
            ids_query = ids_query[: livre // 2]
        ids_doc = self._ids(passagem[:_MAX_PASSAGE_CHARS])[: livre - len(ids_query)]
        ids = self._cabeca + ids_query + self._meio + ids_doc + self._sufixo + [self._eos]
        return {"input_ids": [ids], "attention_mask": [[1] * len(ids)]}

    def _pontuar(self, query: str, passagem: str) -> float:
        entrada = self._montar(query, passagem)
        sim, nao = self._calcular_logits(self._model, entrada, self._id_sim, self._id_nao)[0]
        return _sigmoide(sim - nao)

    def rerank_scores(self, query: str, passagens: list[str]) -> list[float]:
        """P(Sim) contra Não (softmax entre os dois logits, como no card), na
        ordem de entrada. Uma passagem por chamada: sem padding de lote."""
        return [self._pontuar(query, p) for p in passagens]
