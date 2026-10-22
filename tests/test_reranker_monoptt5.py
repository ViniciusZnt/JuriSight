"""MonoPTT5 com modelo e tokenizer falsos (sem torch)."""
import math

from query.search.reranker import _MAX_PASSAGE_CHARS
from query.search.reranker_monoptt5 import PROMPT, MonoPTT5


class _Tok:
    def __init__(self):
        self.textos = []

    def __call__(self, texto, **kw):
        self.textos.append(texto)
        return {"texto": texto}

    def convert_tokens_to_ids(self, token):
        return {"▁Sim": 7, "▁Não": 3}[token]


class _Modelo:
    """Passagens com 'bom' no prompt ganham logit maior para 'Sim'."""

    def eval(self):
        return self


def _logits_falsos(modelo, entrada, id_sim, id_nao):
    bom = "bom" in entrada["texto"]
    return [(2.0, 0.0) if bom else (0.0, 2.0)]  # (logit_sim, logit_nao)


def _mono(tok=None):
    return MonoPTT5(model=_Modelo(), tokenizer=tok or _Tok(), calcular_logits=_logits_falsos)


def test_ordem_preservada_e_probabilidade():
    scores = _mono().rerank_scores("q", ["ruim", "bom", "ruim"])
    esperado_bom = 1 / (1 + math.exp(-2.0))
    assert scores[1] == esperado_bom or abs(scores[1] - esperado_bom) < 1e-9
    assert scores[0] == scores[2] < 0.5 < scores[1]


def test_prompt_no_formato_do_card():
    tok = _Tok()
    _mono(tok).rerank_scores("minha query", ["texto x"])
    assert tok.textos == ["Pergunta: minha query Documento: texto x Relevante:"]
    assert PROMPT == "Pergunta: {query} Documento: {text} Relevante:"


def test_passagem_cortada():
    tok = _Tok()
    _mono(tok).rerank_scores("q", ["Ж" * (_MAX_PASSAGE_CHARS + 500)])
    assert tok.textos[0].count("Ж") == _MAX_PASSAGE_CHARS


def test_lista_vazia():
    assert _mono().rerank_scores("q", []) == []


def test_sem_torch_orienta_o_grupo_benchmark(monkeypatch):
    import sys

    import pytest

    monkeypatch.setitem(sys.modules, "torch", None)
    with pytest.raises(RuntimeError, match="uv sync --group benchmark"):
        MonoPTT5()
