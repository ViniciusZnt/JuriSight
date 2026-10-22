import uuid
from types import SimpleNamespace

import pytest

from avaliacao.benchmark import (
    _benjamini_hochberg,
    _holm,
    avaliar_runs,
    calcular_contrastes,
    pares_de_avaliadores,
)

T1, T2, T3, T4, T5, T6 = (str(uuid.uuid4()) for _ in range(6))
GANHOS = {"a": 3, "b": 2, "c": 0, "d": 2}


def _linha(tese_id, sistemas, candidatos=("a", "b", "c"), bm25=("a",), denso=("d",)):
    return {
        "tese_id": tese_id, "origem": "sintetica", "tema": "t", "split": "dev",
        "candidatos": list(candidatos), "top10_bm25": list(bm25), "top10_denso": list(denso),
        "sistemas": {s: {"ids": ids, "latencia_s": lat} for s, (ids, lat) in sistemas.items()},
    }


def _runs(linhas, sistemas):
    return {"data": "x", "commit": "abc", "sistemas": sistemas, "modelos": {}, "teses": linhas}


def _rotulos(por_tese):
    return lambda tid: (por_tese.get(str(tid), {}), {})


def test_medias_por_sistema_e_excluidas():
    runs = _runs([
        _linha(T1, {"S2": (["a", "d", "b"], 1.0)}),
        _linha(T2, {"S2": (["b", "a"], 3.0)}),
        _linha(T3, {"S2": (["a"], 2.0)}),  # nota 1: sem relevante (>=2), sai de MRR/P/MAP/Recall
    ], ["S2"])
    rotulos = _rotulos({T1: GANHOS, T2: GANHOS, T3: {"a": 1, "z": 0}})
    rel = avaliar_runs(runs, rotulos)
    s2 = rel["por_sistema"]["S2"]
    assert s2["n_teses"] == 3
    assert s2["excluidas"]["ndcg_10"] == 0  # nDCG existe com nota 1
    assert s2["excluidas"]["mrr_10"] == 1
    t1, t2, t3 = (t["sistemas"]["S2"]["ndcg_10"] for t in rel["por_tese"])
    assert t1 == pytest.approx(1.0) and t2 < 1.0
    assert s2["medias"]["ndcg_10"] == pytest.approx((t1 + t2 + t3) / 3)
    assert s2["medias"]["mrr_10"] == pytest.approx(1.0)
    assert s2["latencia_mediana_s"] == 2.0
    assert s2["latencia_p95_s"] == pytest.approx(2.9)


def test_contraste_com_diferenca_clara():
    ndcg = {
        "S2": {f"t{i}": 0.30 + 0.01 * (i % 3) for i in range(8)},
        "S3": {f"t{i}": 0.60 + 0.02 * (i % 4) for i in range(8)},
    }
    contrastes, avisos = calcular_contrastes(ndcg)
    c = contrastes[0]
    assert (c["tratamento"], c["controle"]) == ("S3", "S2")
    assert c["n_teses"] == 8 and c["diferenca_media"] > 0.25
    assert c["ic95"][0] > 0
    assert c["p_t_holm"] < 0.05 and c["p_wilcoxon_bh"] < 0.05
    assert len(contrastes) == 1 and avisos  # os demais dependem de sistemas ausentes


def test_contraste_com_diferencas_nulas_nao_quebra():
    ndcg = {"S2": {f"t{i}": 0.5 for i in range(5)}, "S3": {f"t{i}": 0.5 for i in range(5)}}
    c = calcular_contrastes(ndcg)[0][0]
    assert c["diferenca_media"] == 0
    assert c["p_t"] is None and c["p_wilcoxon"] is None
    assert c["p_t_holm"] is None and c["p_wilcoxon_bh"] is None


def test_contraste_so_usa_teses_com_os_dois_valores():
    ndcg = {"S2": {"a": 0.1, "b": None, "c": 0.2}, "S3": {"a": 0.3, "b": 0.5, "c": 0.4}}
    c = calcular_contrastes(ndcg)[0][0]
    assert c["n_teses"] == 2
    assert c["diferenca_media"] == pytest.approx(0.2)
    um = calcular_contrastes({"S2": {"a": 0.1}, "S3": {"a": 0.3}})[0][0]
    assert um["p_t"] is None and um["ic95"] is None


def test_contrastes_de_sistema_ausente_sao_omitidos_com_aviso():
    runs = _runs([_linha(T1, {s: (["a", "b"], 1.0) for s in ("S0", "S1", "S2", "S3")})], ["S0", "S1", "S2", "S3"])
    rel = avaliar_runs(runs, _rotulos({T1: GANHOS}))
    pares = {(c["tratamento"], c["controle"]) for c in rel["contrastes"]}
    assert pares == {("S3", "S2"), ("S0", "S2"), ("S1", "S2")}
    assert any("S4" in a for a in rel["avisos"])


def test_holm_e_bh():
    ps = [0.01, 0.04, 0.03]
    assert _holm(ps) == pytest.approx([0.03, 0.06, 0.06])
    assert _benjamini_hochberg(ps) == pytest.approx([0.03, 0.04, 0.04])


def test_teto_perdidos_e_judged():
    # candidatos a,b,c; d (nota 2) está no top-10 do denso mas fora dos 30
    runs = _runs([_linha(T1, {"S2": (["c", "x", "a"], 1.0)})], ["S2"])
    rel = avaliar_runs(runs, _rotulos({T1: GANHOS}))
    assert rel["perdidos"]["total"] == 1
    assert rel["perdidos"]["por_tese"][0]["documentos"] == ["d"]
    # teto: melhor ordem entre a,b,c (d fora) vs ideal com d
    assert 0 < rel["teto"]["ndcg_10_medio"] < 1
    # judged: c e a julgados, x não -> 2/3; x conta como 0 no nDCG
    assert rel["por_sistema"]["S2"]["medias"]["judged_10"] == pytest.approx(2 / 3)


def test_sem_rotulos_metricas_none():
    rel = avaliar_runs(_runs([_linha(T1, {"S2": (["a"], 1.0)})], ["S2"]), _rotulos({}))
    m = rel["por_sistema"]["S2"]["medias"]
    assert m["ndcg_10"] is None and m["judged_10"] is None
    assert rel["teto"]["ndcg_10_medio"] is None


def _j(par, juiz, rel):
    return SimpleNamespace(par_id=par, juiz=juiz, relevancia=rel)


def test_concordancia_sem_adjudicador_e_mais_recente():
    p1, p2, p3 = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    julgs = [
        _j(p1, "humano:ana@x.com", 0), _j(p1, "humano:ana@x.com", 3),  # vale a mais recente
        _j(p1, "humano:bia@x.com", 2),
        _j(p1, "humano:adj@x.com", 1),  # adjudicador fora
        _j(p2, "humano:ana@x.com", 1), _j(p2, "humano:adj@x.com", 0),  # só um avaliador: fora
        _j(p3, "humano:ana@x.com", 1), _j(p3, "humano:bia@x.com", 1), _j(p3, "humano:caio@x.com", 3),
        _j(p3, "llm:jev", 0),
    ]
    assert pares_de_avaliadores(julgs, " ADJ@x.com ") == [(3, 2), (1, 1)]
    rel = avaliar_runs(_runs([], []), _rotulos({}), julgamentos=julgs, pendentes=[(1, 2)], adjudicador="adj@x.com")
    assert rel["concordancia"]["n_pares"] == 2
    assert rel["concordancia"]["alfa_krippendorff"] is not None
    assert rel["pendentes"] == 1
