"""Testes de FiltroStore.contar sem banco (query/filtros/store.py): quais consultas saem e como voltam."""
from query.filtros.expressoes import tsquery_da_expressao
from query.filtros.store import FiltroStore

_DANO = tsquery_da_expressao("dano moral")
_HORAS = tsquery_da_expressao("horas extras")


class _Store(FiltroStore):
    def __init__(self):
        super().__init__("postgresql://nao-usado")
        self.consultas = []

    def _consultar(self, sql, params):
        self.consultas.append((sql, params))
        if "public.dispositivo " in sql:
            return [("art_192_clt", 42)]
        if params == [_DANO]:
            return [(10,)]
        if params == [_HORAS]:
            return [(20,)]
        return [(3,)]  # total com todos os filtros


def _contagens(store):
    return [c for c in store.consultas if "documento_tsv" in c[0]]


def test_contar_total_e_cada_item():
    store = _Store()
    c = store.contar(["art_192_clt"], ["dano moral", "horas extras"])
    assert c.total == 3
    assert [(d.codigo, d.total) for d in c.dispositivos] == [("art_192_clt", 42)]
    assert c.expressoes == [("dano moral", 10), ("horas extras", 20)]
    assert len(_contagens(store)) == 3


def test_contar_uma_expressao_nao_conta_duas_vezes():
    store = _Store()
    c = store.contar([], ["dano moral"])
    assert c.total == 10 and c.expressoes == [("dano moral", 10)]
    assert len(_contagens(store)) == 1


def test_contar_expressao_repetida_ou_vazia():
    store = _Store()
    c = store.contar([], ["dano moral", "Danos Morais", "&|!"])
    assert c.expressoes == [("dano moral", 10), ("Danos Morais", 10), ("&|!", 0)]
    assert c.total == 10
    assert len(_contagens(store)) == 1


def test_contar_sem_filtro():
    store = _Store()
    assert store.contar([], []).total == 0
    assert _contagens(store) == []
