import numpy as np

from query.search.reranker_onnx import CrossEncoderOnnx


class _Enc:
    def __init__(self, n):
        self.ids = list(range(n))
        self.attention_mask = [1] * n
        self.type_ids = [0] * n


class _TokenizerFalso:
    def __init__(self):
        self.pares = []

    def encode(self, query, passagem):
        self.pares.append((query, passagem))
        return _Enc(len(passagem) % 7 + 1)


class _Entrada:
    def __init__(self, name):
        self.name = name


class _SessaoFalsa:
    def __init__(self, entradas=("input_ids", "attention_mask", "token_type_ids")):
        self._entradas = entradas
        self.recebidas = []

    def get_inputs(self):
        return [_Entrada(n) for n in self._entradas]

    def run(self, _saidas, feed):
        self.recebidas.append(set(feed))
        # score = comprimento da sequência (identifica a passagem)
        n = feed["input_ids"].shape[1]
        return [np.array([[float(n)]], dtype=np.float32)]


def _montar(entradas=("input_ids", "attention_mask", "token_type_ids")):
    sessao, tok = _SessaoFalsa(entradas), _TokenizerFalso()
    return CrossEncoderOnnx("repo", "x.onnx", sessao=sessao, tokenizer=tok), sessao, tok


def test_scores_na_ordem_de_entrada():
    modelo, _, _ = _montar()
    passagens = ["a" * 3, "b" * 1, "c" * 5, "d" * 6]
    assert modelo.rerank_scores("q", passagens) == [4.0, 2.0, 6.0, 7.0]


def test_passagem_cortada_em_1200():
    modelo, _, tok = _montar()
    modelo.rerank_scores("q", ["x" * 5000])
    assert len(tok.pares[0][1]) == 1200


def test_so_entradas_declaradas_pela_sessao():
    modelo, sessao, _ = _montar(("input_ids", "attention_mask"))
    modelo.rerank_scores("q", ["abc"])
    assert sessao.recebidas == [{"input_ids", "attention_mask"}]


def test_lista_vazia():
    modelo, _, _ = _montar()
    assert modelo.rerank_scores("q", []) == []


def test_saida_unidimensional():
    modelo, sessao, _ = _montar()
    sessao.run = lambda _s, feed: [np.array([1.5], dtype=np.float32)]
    assert modelo.rerank_scores("q", ["abc"]) == [1.5]
