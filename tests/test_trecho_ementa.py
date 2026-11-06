"""Trecho da ementa enviado ao reranker do S7: início + "Tese de julgamento"."""
from types import SimpleNamespace

from avaliacao import sistemas
from avaliacao.sistemas import construir_rerankers, rodar_sistema
from query.enrichment.schema import EstruturaArgumentativa
from query.search.trecho_ementa import RerankerComTese, trecho_para_rerank
from tests.test_pipeline import _doc

INICIO = "I. CASO EM EXAME " + "x" * 1500 + " Recurso desprovido. "
TESE = "Tese de julgamento: 1. Frigorífico expõe a risco biológico."
CITADOS = " Dispositivos relevantes citados: NR-15, Anexo 14."


def test_ementa_curta_nao_muda():
    assert trecho_para_rerank("Ementa curta. Tese de julgamento: X.", limite=1200) == (
        "Ementa curta. Tese de julgamento: X.")


def test_ementa_longa_sem_tese_nao_muda():
    longa = "y" * 3000
    assert trecho_para_rerank(longa, limite=1200) == longa


def test_ementa_longa_junta_inicio_e_tese_sem_passar_do_limite():
    trecho = trecho_para_rerank(INICIO + TESE + CITADOS, limite=1200)
    assert trecho.startswith("I. CASO EM EXAME")
    assert trecho.endswith(TESE)
    assert len(trecho) <= 1200


def test_tese_para_antes_da_jurisprudencia_citada():
    for fim in (" Jurisprudência relevante citada : TST, Súmula 438.",
                " Jurisprudência citada : STF, MS 33702.",
                " Dispositivos citados: CF/88, art. 37.",
                " Dispositivos legais citados : CF/88, art. 37, II e § 2º."):
        assert trecho_para_rerank(INICIO + TESE + fim, limite=1200).endswith(TESE)


def test_tese_ate_o_fim_quando_nao_ha_citacoes():
    assert trecho_para_rerank(INICIO + TESE, limite=1200).endswith(TESE)


def test_marcador_em_maiusculas_e_plural():
    tese = "TESES DE JULGAMENTO: 1. Acidente gera dano."
    assert trecho_para_rerank(INICIO + tese, limite=1200).endswith(tese)


def test_tese_que_ja_cabe_no_inicio_nao_muda():
    ementa = "Início. " + TESE + CITADOS + " " + "z" * 2000
    assert trecho_para_rerank(ementa, limite=1200) == ementa


def test_tese_que_comeca_cedo_e_passa_do_limite_nao_se_repete():
    ementa = "Início. Tese de julgamento: " + "w" * 3000
    trecho = trecho_para_rerank(ementa, limite=1200)
    assert trecho.startswith("Início. Tese de julgamento")
    assert trecho.count("Tese de julgamento") == 1
    assert len(trecho) <= 1200


def test_tese_enorme_ainda_mantem_o_inicio():
    tese = "Tese de julgamento: " + "w" * 3000
    trecho = trecho_para_rerank(INICIO + tese, limite=1200)
    assert trecho.startswith("I. CASO EM EXAME")
    assert "Tese de julgamento" in trecho
    assert len(trecho) <= 1200


class _RerankerQueGuarda:
    def __init__(self):
        self.chamadas = []

    def rerank_scores(self, query, passagens):
        self.chamadas.append((query, passagens))
        return [float(i) for i in range(len(passagens))]


def test_reranker_com_tese_troca_so_a_passagem_e_preserva_a_ordem():
    interno = _RerankerQueGuarda()
    scores = RerankerComTese(interno, limite=1200).rerank_scores("q", [INICIO + TESE, "curta"])
    assert scores == [0.0, 1.0]
    query, passagens = interno.chamadas[0]
    assert query == "q"
    assert passagens[0].endswith(TESE) and len(passagens[0]) <= 1200
    assert passagens[1] == "curta"


class _Hybrid:
    def search(self, query, n, where=None, *, bm25_query=None):
        return [("longo", 1.0), ("curto", 0.5)]


def test_s7_reordena_com_o_trecho_novo(monkeypatch):
    docs = {"longo": _doc(id_documento="longo", ementa=INICIO + TESE),
            "curto": _doc(id_documento="curto", ementa="curta")}
    deps = SimpleNamespace(hybrid=_Hybrid(), retriever=SimpleNamespace(fetch=lambda ids: docs))

    class _PrefereTese:
        def rerank_scores(self, query, passagens):
            return [1.0 if TESE in p else 0.0 for p in passagens]

    rerankers = {"S7": RerankerComTese(_PrefereTese(), limite=1200)}
    ids = rodar_sistema("S7", EstruturaArgumentativa(tese_central="t"), deps, rerankers)
    assert ids == ["longo", "curto"]


def test_construir_s7_envolve_o_reranker_de_producao(monkeypatch):
    import query.search.reranker as mod

    interno = _RerankerQueGuarda()
    monkeypatch.setattr(mod, "Reranker", lambda: interno)
    s7 = construir_rerankers(["S7"])["S7"]
    s7.rerank_scores("q", [INICIO + TESE])
    assert interno.chamadas[0][1][0].endswith(TESE)
    assert "S7" in sistemas.SISTEMAS
