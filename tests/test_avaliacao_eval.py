import uuid

import pytest

from avaliacao.eval import (
    avaliar,
    concordancia_reteste,
    kappas_calibracao,
    limite_confianca,
    nome_juiz_atual,
)
from avaliacao.store import Julgamento, Tese


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


def _j(par_id, juiz, rodada, rel, stance, conf_rel=None, conf_stance=None):
    return Julgamento(
        par_id=par_id, juiz=juiz, rodada=rodada, relevancia=rel, stance=stance,
        confianca_rel=conf_rel, confianca_stance=conf_stance,
    )


def test_reteste_concordancia_perfeita():
    nome = nome_juiz_atual()
    dados = [(0, "neutro"), (1, "enfraquece"), (2, "fortalece"), (3, "fortalece")]
    julgamentos = []
    for rel, stance in dados:
        par = uuid.uuid4()
        julgamentos += [_j(par, nome, 1, rel, stance), _j(par, nome, 2, rel, stance)]

    r = concordancia_reteste(julgamentos)

    assert r["n"] == 4
    assert r["kappa_relevancia"] == pytest.approx(1.0)
    assert r["kappa_stance"] == pytest.approx(1.0)
    assert r["concordancia_exata"] == 1.0


def test_reteste_rejeita_mais_de_um_juiz():
    par = uuid.uuid4()
    with pytest.raises(ValueError):
        concordancia_reteste([_j(par, "jev:a", 1, 1, "neutro"), _j(par, "jev:b", 2, 1, "neutro")])


def test_reteste_sem_pares_completos():
    par = uuid.uuid4()
    r = concordancia_reteste([_j(par, nome_juiz_atual(), 1, 1, "neutro")])
    assert r == {"n": 0, "kappa_relevancia": None, "kappa_stance": None, "concordancia_exata": None}


class FakeStore:
    def __init__(self, amostra, julgamentos):
        self._amostra = amostra
        self._julgamentos = julgamentos

    def amostra(self):
        return self._amostra

    def julgamentos(self, juiz_prefixo=None):
        if juiz_prefixo is None:
            return list(self._julgamentos)
        return [j for j in self._julgamentos if j.juiz.startswith(juiz_prefixo)]


def test_kappa_calibracao_usa_so_sorteada():
    nome = nome_juiz_atual()
    amostra, julgs = {}, []
    # 4 pares sorteados em que humano e Jev concordam totalmente.
    for rel, stance in [(0, "neutro"), (1, "enfraquece"), (2, "fortalece"), (3, "fortalece")]:
        par = uuid.uuid4()
        amostra[par] = "sorteada"
        julgs += [_j(par, "humano:a@x.com", 1, rel, stance), _j(par, nome, 1, rel, stance)]
    # 1 par 'incerta' em que discordam totalmente: não pode entrar nos kappas.
    par_incerta = uuid.uuid4()
    amostra[par_incerta] = "incerta"
    julgs += [
        _j(par_incerta, "humano:a@x.com", 1, 0, "enfraquece"),
        _j(par_incerta, nome, 1, 3, "fortalece", 0.9, 0.9),
    ]
    # Jev rodada 2 e par sorteado sem humano: ignorados.
    par_sem_humano = uuid.uuid4()
    amostra[par_sem_humano] = "sorteada"
    julgs.append(_j(par_sem_humano, nome, 1, 2, "neutro"))

    r = kappas_calibracao(FakeStore(amostra, julgs))

    assert r["n_sorteada"] == 4
    assert r["kappa_relevancia"] == pytest.approx(1.0)
    assert r["kappa_stance"] == pytest.approx(1.0)
    assert r["aprovado"] is True
    # só 1 incerta, errada: nenhum limite atinge 0,8
    assert r["limite_confianca"] is None
    assert r["n_acima_limite"] == 0


def test_kappa_calibracao_usa_humano_mais_recente_e_reprova():
    nome = nome_juiz_atual()
    amostra, julgs = {}, []
    for rel, stance in [(0, "neutro"), (1, "enfraquece"), (2, "fortalece"), (3, "fortalece")]:
        par = uuid.uuid4()
        amostra[par] = "sorteada"
        # humano antigo discorda, o mais recente (último na lista) concorda
        julgs += [
            _j(par, "humano:velho@x.com", 1, 3 - rel, "neutro"),
            _j(par, "humano:novo@x.com", 1, rel, stance),
            _j(par, nome, 1, rel, stance),
        ]
    assert kappas_calibracao(FakeStore(amostra, julgs))["aprovado"] is True

    # Sem Jev concordando: reprovado.
    amostra2, julgs2 = {}, []
    for rel in (0, 1, 2, 3):
        par = uuid.uuid4()
        amostra2[par] = "sorteada"
        julgs2 += [_j(par, "humano:a@x.com", 1, rel, "fortalece"), _j(par, nome, 1, 3 - rel, "neutro")]
    assert kappas_calibracao(FakeStore(amostra2, julgs2))["aprovado"] is False


def test_kappa_calibracao_sem_dados_nao_aprova():
    r = kappas_calibracao(FakeStore({}, []))
    assert r["n_sorteada"] == 0
    assert r["kappa_relevancia"] is None
    assert r["aprovado"] is False


def test_limite_confianca():
    # nenhum limite atinge 0,8
    assert limite_confianca([(0.9, False), (0.5, False)]) == (None, 0)
    assert limite_confianca([]) == (None, 0)
    # limite intermediário: >=0.7 tem 3 acertos em 3; >=0.4 tem 3/4 (0,75) e 0.2 tem 3/5
    itens = [(0.9, True), (0.8, True), (0.7, True), (0.4, False), (0.2, False)]
    assert limite_confianca(itens) == (0.7, 3)
    # alvo exato (4/5 = 0,8) conta
    itens3 = [(0.9, True), (0.8, True), (0.7, True), (0.6, True), (0.5, False)]
    assert limite_confianca(itens3) == (0.5, 5)
