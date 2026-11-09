import uuid

import pytest

from avaliacao.eval import avaliar
from avaliacao.store import Tese


def _tese(split="dev", origem="sintetica", tema="t") -> Tese:
    return Tese(id=uuid.uuid4(), estrutura={"k": 1}, origem=origem, tema=tema, split=split)


def test_eval_agrega_por_split_e_origem():
    t1 = _tese(split="dev", origem="sintetica")
    t2 = _tese(split="dev", origem="real")
    rankings = {str(t1.id): ["a", "b"], str(t2.id): ["b", "a"]}
    rotulos = {
        t1.id: ({"a": 3, "b": 1}, {"a": "fortalece", "b": "neutro"}),
        t2.id: ({"a": 3, "b": 1}, {"a": "fortalece", "b": "neutro"}),
    }
    # buscar_ids recebe a estrutura; aqui a identifica a tese pela ordem de chamada
    chamadas = iter([rankings[str(t1.id)], rankings[str(t2.id)]])

    resultado = avaliar([t1, t2], lambda estrutura: next(chamadas), lambda tid: rotulos[tid])

    # t1 ranking ideal => ndcg 1.0; t2 invertido => < 1.0
    por_tese = {p["tese_id"]: p for p in resultado["por_tese"]}
    assert por_tese[str(t1.id)]["ndcg_10"] == 1.0
    assert por_tese[str(t2.id)]["ndcg_10"] < 1.0
    assert por_tese[str(t1.id)]["recall_20"] == 1.0
    assert por_tese[str(t1.id)]["fortalece_10"] == 1.0
    assert por_tese[str(t1.id)]["nao_julgados_10"] == 0.0

    dev = resultado["por_split"]["dev"]
    assert dev["n_teses"] == 2
    esperado = (por_tese[str(t1.id)]["ndcg_10"] + por_tese[str(t2.id)]["ndcg_10"]) / 2
    assert dev["medias"]["ndcg_10"] == pytest.approx(esperado)
    assert dev["excluidas"]["ndcg_10"] == 0

    assert resultado["por_origem"]["sintetica"]["medias"]["ndcg_10"] == 1.0
    assert resultado["por_origem"]["real"]["n_teses"] == 1
    assert resultado["por_origem"]["real"]["medias"]["ndcg_10"] == por_tese[str(t2.id)]["ndcg_10"]


def test_eval_ignora_teses_sem_relevantes():
    boa = _tese()
    sem_relevantes = _tese()
    rotulos = {
        boa.id: ({"a": 3}, {"a": "fortalece"}),
        sem_relevantes.id: ({"a": 1}, {"a": "neutro"}),
    }

    resultado = avaliar([boa, sem_relevantes], lambda e: ["a"], lambda tid: rotulos[tid])

    dev = resultado["por_split"]["dev"]
    assert dev["excluidas"]["recall_20"] == 1
    assert dev["medias"]["recall_20"] == 1.0  # só a tese boa entra na média
    assert dev["excluidas"]["nao_julgados_10"] == 0


def test_eval_sem_teses():
    resultado = avaliar([], lambda e: [], lambda tid: ({}, {}))
    assert resultado == {"por_tese": [], "por_split": {}, "por_origem": {}, "teses_com_erro": []}


def test_eval_tese_com_busca_que_falha_nao_derruba(capsys):
    from query.enrichment.schema import EstruturaArgumentativa

    boa, ruim_valor, ruim_pydantic = _tese(), _tese(), _tese()
    rotulos = {boa.id: ({"a": 3}, {"a": "fortalece"})}

    def _buscar(estrutura, _ordem=iter([None, "valor", "pydantic"])):
        caso = next(_ordem)
        if caso == "valor":
            raise ValueError("busca quebrou")
        if caso == "pydantic":
            EstruturaArgumentativa(pedido_principal=["não é str"])
        return ["a"]

    resultado = avaliar([boa, ruim_valor, ruim_pydantic], _buscar, lambda tid: rotulos[tid])

    assert resultado["teses_com_erro"] == [str(ruim_valor.id), str(ruim_pydantic.id)]
    err = capsys.readouterr().err
    assert str(ruim_valor.id) in err and str(ruim_pydantic.id) in err
    dev = resultado["por_split"]["dev"]
    assert dev["n_teses"] == 3
    assert dev["medias"]["ndcg_10"] == 1.0  # só a tese boa entra na média
    assert all(dev["excluidas"][m] == 2 for m in ("ndcg_10", "recall_20", "fortalece_10", "nao_julgados_10"))
    com_erro = {p["tese_id"]: p for p in resultado["por_tese"]}[str(ruim_valor.id)]
    assert com_erro["ndcg_10"] is None and "busca quebrou" in com_erro["erro"]

