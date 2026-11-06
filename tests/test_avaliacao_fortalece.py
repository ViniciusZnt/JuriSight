"""Fortalece@k: quantos do top-k são relevantes e apoiam a tese."""
import uuid

from avaliacao.benchmark import avaliar_runs, calcular_contrastes
from avaliacao.metricas import fortalece_at_k

GANHOS = {"a": 3, "b": 2, "c": 2, "d": 1, "e": 0}
STANCES = {"a": "fortalece", "b": "enfraquece", "c": "neutro", "d": "fortalece", "e": "neutro"}


def test_conta_so_relevante_que_fortalece_sobre_k():
    assert fortalece_at_k(["a", "b", "c", "d", "e"], GANHOS, STANCES, 10) == 0.1


def test_nota_1_com_fortalece_nao_conta():
    assert fortalece_at_k(["d"], GANHOS, STANCES, 10) == 0.0


def test_so_olha_o_top_k():
    assert fortalece_at_k(["b", "a"], GANHOS, STANCES, 1) == 0.0


def test_sem_relevante_julgado_e_none():
    assert fortalece_at_k(["d"], {"d": 1}, {"d": "fortalece"}, 10) is None


def test_relatorio_traz_a_media_de_fortalece():
    t1, t2 = str(uuid.uuid4()), str(uuid.uuid4())

    def linha(tese_id, ids):
        return {"tese_id": tese_id, "origem": "advogado", "tema": "x", "split": "dev",
                "candidatos": ids, "top10_bm25": [], "top10_denso": [],
                "sistemas": {"S2": {"ids": ids, "latencia_s": 1.0}}}

    runs = {"data": "x", "commit": "c", "sistemas": ["S2"], "modelos": {},
            "teses": [linha(t1, ["a", "b"]), linha(t2, ["b"])]}
    rel = avaliar_runs(runs, lambda tid: (GANHOS, STANCES))
    # T1: 1 de 10 fortalece (a); T2: 0 de 10 (b enfraquece). Média = 0,05.
    assert rel["por_sistema"]["S2"]["medias"]["fortalece_10"] == 0.05


def test_s7_e_comparado_com_a_producao():
    ids = [str(uuid.uuid4()) for _ in range(4)]
    ndcg = {"S3": dict(zip(ids, (0.1, 0.2, 0.3, 0.4))), "S7": dict(zip(ids, (0.2, 0.2, 0.5, 0.5)))}
    contrastes, _, _ = calcular_contrastes(ndcg)
    assert [(c["tratamento"], c["controle"]) for c in contrastes] == [("S7", "S3")]
    assert contrastes[0]["diferenca_media"] == 0.1
