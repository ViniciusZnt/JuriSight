"""MonoPTT5 com modelo e tokenizer falsos (sem torch)."""
import pytest

from query.search.reranker import _MAX_PASSAGE_CHARS
from query.search.reranker_monoptt5 import PROMPT, MonoPTT5

EOS, UNK = 1, 2


class _Tok:
    """Um id por caractere (ord); como o sentencepiece, põe um espaço no início
    de cada trecho que não comece por espaço."""

    eos_token_id = EOS
    unk_token_id = UNK

    def __call__(self, texto, add_special_tokens=False, **kw):
        assert add_special_tokens is False
        if not texto.startswith(" "):
            texto = " " + texto
        return {"input_ids": [ord(c) for c in texto]}

    def convert_tokens_to_ids(self, token):
        return {"▁Sim": 7, "▁Não": 3}.get(token, UNK)


class _Modelo:
    def eval(self):
        return self


def _texto(entrada):
    ids = entrada["input_ids"][0]
    assert ids[-1] == EOS
    return "".join(chr(i) for i in ids[:-1])


def _logits_falsos(modelo, entrada, id_sim, id_nao):
    assert len(entrada["input_ids"][0]) == len(entrada["attention_mask"][0])
    return [(2.0, 0.0) if "bom" in _texto(entrada) else (0.0, 2.0)]


def _mono(tok=None, logits=_logits_falsos, **kw):
    return MonoPTT5(model=_Modelo(), tokenizer=tok or _Tok(), calcular_logits=logits, **kw)


def test_ordem_preservada_e_probabilidade():
    scores = _mono().rerank_scores("q", ["ruim", "bom", "ruim"])
    assert scores[1] == pytest.approx(1 / (1 + 2.718281828459045**-2))
    assert scores[0] == scores[2] < 0.5 < scores[1]


def test_prompt_no_formato_do_card():
    vistos = []

    def logits(m, entrada, a, b):
        vistos.append(_texto(entrada))
        return [(0.0, 0.0)]

    _mono(logits=logits).rerank_scores("minha query", ["texto x"])
    assert vistos[0].strip() == "Pergunta: minha query Documento: texto x Relevante:"
    assert PROMPT == "Pergunta: {query} Documento: {text} Relevante:"


def test_passagem_cortada_em_caracteres():
    vistos = []

    def logits(m, entrada, a, b):
        vistos.append(_texto(entrada))
        return [(0.0, 0.0)]

    _mono(logits=logits, max_tokens=5000).rerank_scores("q", ["Ж" * (_MAX_PASSAGE_CHARS + 500)])
    assert vistos[0].count("Ж") == _MAX_PASSAGE_CHARS


@pytest.mark.parametrize("query", ["q", "Q" * 2000])
def test_sufixo_sobrevive_a_truncagem(query):
    vistos = []

    def logits(m, entrada, a, b):
        vistos.append(entrada["input_ids"][0])
        return [(0.0, 0.0)]

    _mono(logits=logits, max_tokens=100).rerank_scores(query, ["d" * 1000])
    ids = vistos[0]
    assert len(ids) <= 100
    assert ids[-1] == EOS
    assert "".join(chr(i) for i in ids[-12:-1]) == " Relevante:"


def test_lista_vazia():
    assert _mono().rerank_scores("q", []) == []


def test_token_ausente_levanta():
    class SemSim(_Tok):
        def convert_tokens_to_ids(self, token):
            return UNK if token == "▁Sim" else 3

    with pytest.raises(RuntimeError, match="▁Sim"):
        _mono(SemSim())


def test_ids_iguais_levanta():
    class Iguais(_Tok):
        def convert_tokens_to_ids(self, token):
            return 5

    with pytest.raises(RuntimeError):
        _mono(Iguais())


def test_sem_torch_orienta_o_grupo_benchmark(monkeypatch):
    import sys

    monkeypatch.setitem(sys.modules, "torch", None)
    with pytest.raises(RuntimeError, match="uv sync --group benchmark"):
        MonoPTT5()
