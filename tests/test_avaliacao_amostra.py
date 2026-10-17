import uuid

from avaliacao.amostra import ItemAmostra, escolher_amostra


def _item(i, tema="t1", origem="real", relevancia=2, stance="neutro", confianca=0.9):
    return ItemAmostra(uuid.UUID(int=i), tema, origem, relevancia, stance, confianca)


def _itens_variados(n=60):
    temas = ["t1", "t2", "t3"]
    stances = ["fortalece", "enfraquece", "neutro"]
    return [
        _item(i, tema=temas[i % 3], relevancia=i % 4, stance=stances[(i // 3) % 3],
              confianca=(i % 10) / 10)
        for i in range(1, n + 1)
    ]


def test_tamanhos_e_disjuncao():
    itens = _itens_variados(60)
    r = escolher_amostra(itens, n_sorteada=10, n_incerta=7, seed=1)
    sorteada = {p for p, v in r.items() if v == "sorteada"}
    incerta = {p for p, v in r.items() if v == "incerta"}
    assert len(sorteada) == 10
    assert len(incerta) == 7
    assert not sorteada & incerta
    assert set(r.values()) == {"sorteada", "incerta"}


def test_obrigatorios_entram_na_sorteada():
    itens = _itens_variados(40)
    obrig = {itens[0].par_id, itens[5].par_id, itens[9].par_id}
    r = escolher_amostra(itens, n_sorteada=8, n_incerta=5, seed=3, obrigatorios=obrig)
    assert all(r[p] == "sorteada" for p in obrig)
    assert sum(1 for v in r.values() if v == "sorteada") == 8


def test_obrigatorios_alem_do_n_nao_sao_descartados():
    itens = _itens_variados(20)
    obrig = {i.par_id for i in itens[:6]}
    r = escolher_amostra(itens, n_sorteada=4, n_incerta=3, seed=3, obrigatorios=obrig)
    assert all(r[p] == "sorteada" for p in obrig)
    assert sum(1 for v in r.values() if v == "sorteada") == 6


def test_obrigatorios_ausentes_sao_ignorados():
    itens = _itens_variados(10)
    fantasma = uuid.UUID(int=9999)
    r = escolher_amostra(itens, n_sorteada=3, n_incerta=2, seed=3, obrigatorios={fantasma})
    assert fantasma not in r
    assert sum(1 for v in r.values() if v == "sorteada") == 3


def test_estratos_raros_representados():
    comuns = [_item(i, tema="t1", relevancia=2, stance="neutro") for i in range(1, 50)]
    raro = _item(100, tema="t9", relevancia=3, stance="enfraquece", origem="sintetica")
    for seed in range(5):
        r = escolher_amostra(comuns + [raro], n_sorteada=60 // 5, n_incerta=0, seed=seed)
        # 1 estrato comum + 1 raro: round-robin pega o raro logo na 1a volta
        assert r[raro.par_id] == "sorteada"


def test_incerta_pega_menor_confianca():
    itens = [_item(i, tema=f"t{i}", confianca=i / 100) for i in range(1, 21)]
    r = escolher_amostra(itens, n_sorteada=5, n_incerta=4, seed=7)
    sorteada = {p for p, v in r.items() if v == "sorteada"}
    restantes = sorted((i for i in itens if i.par_id not in sorteada), key=lambda i: i.confianca)
    esperadas = {i.par_id for i in restantes[:4]}
    assert {p for p, v in r.items() if v == "incerta"} == esperadas


def test_deterministico_pela_seed():
    itens = _itens_variados(60)
    a = escolher_amostra(itens, n_sorteada=10, n_incerta=10, seed=42)
    b = escolher_amostra(list(reversed(itens)), n_sorteada=10, n_incerta=10, seed=42)
    assert a == b
    c = escolher_amostra(itens, n_sorteada=10, n_incerta=10, seed=43)
    assert c != a


def test_menos_itens_que_o_pedido():
    itens = _itens_variados(12)
    r = escolher_amostra(itens, n_sorteada=75, n_incerta=75, seed=1)
    assert set(r) == {i.par_id for i in itens}
    assert all(v == "sorteada" for v in r.values())


def test_lista_vazia():
    assert escolher_amostra([], seed=1) == {}
