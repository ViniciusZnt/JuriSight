"""Testes do CLI de construção do conjunto-ouro (fakes; sem Jev, OpenAI nem banco)."""
import uuid
from types import SimpleNamespace

from typesafe_sdk import TypeSafeError

from avaliacao.amostra import ItemAmostra
from avaliacao.construir import (
    etapa_julgamento,
    itens_da_amostra,
    precisa_de_pool,
    reais_novas,
)
from avaliacao.juiz import perguntas_sha
from avaliacao.store import Julgamento, Par, Tese


def _tese(estrutura=None, tema="insalubridade", origem="sintetica"):
    return Tese(uuid.uuid4(), estrutura or {"pedido_principal": "x"}, origem, tema, "dev", None)


class _StoreFalso:
    """Guarda julgamentos em memória; reproduz só o que `etapa_julgamento` usa."""

    def __init__(self, teses, pares):
        self._teses, self._pares = teses, pares
        self.gravados: list[Julgamento] = []

    def listar_teses(self, split=None):
        return self._teses

    def pares_sem_julgamento(self, juiz, rodada):
        feitos = {(j.par_id, j.juiz, j.rodada) for j in self.gravados}
        return [p for p in self._pares if (p.id, juiz, rodada) not in feitos]

    def gravar_julgamento(self, j):
        self.gravados.append(j)


class _JuizFalso:
    nome = "jev:fake"

    def __init__(self, falha_no_par=None):
        self.chamadas = 0
        self.falha_no_par = falha_no_par

    def julgar(self, tese, documento, rodada, par_id):
        self.chamadas += 1
        if par_id == self.falha_no_par:
            self.falha_no_par = None  # falha só na primeira vez
            raise TypeSafeError("falha simulada")
        return Julgamento(par_id=par_id, juiz=self.nome, rodada=rodada, relevancia=2, stance="neutro")


def test_construir_retoma_sem_rejulgar():
    tese = _tese()
    pares = [Par(uuid.uuid4(), tese.id, f"doc{i}", ["bm25"]) for i in range(3)]
    store = _StoreFalso([tese], pares)
    juiz = _JuizFalso(falha_no_par=pares[1].id)
    carregar_doc = lambda doc_id: SimpleNamespace(id_documento=doc_id)  # noqa: E731

    falhas_1 = etapa_julgamento(store, juiz, carregar_doc, rodadas=1)
    falhas_2 = etapa_julgamento(store, juiz, carregar_doc, rodadas=1)

    assert (falhas_1, falhas_2) == (1, 0)
    assert juiz.chamadas == 4  # 3 + 1 retry do que falhou
    for par in pares:
        assert [j.rodada for j in store.gravados if j.par_id == par.id] == [1]


def test_precisa_de_pool_so_com_corredor_real():
    p = lambda corredores: Par(uuid.uuid4(), uuid.uuid4(), "d", corredores)  # noqa: E731
    assert precisa_de_pool([])
    assert precisa_de_pool([p(["passo_zero"])])  # tese do passo 0: só tem o corredor de teste
    assert not precisa_de_pool([p(["passo_zero"]), p(["bm25", "pipeline"])])
    assert not precisa_de_pool([p(["vetorial"])])


def test_itens_da_amostra_usa_menor_confianca_e_none_vira_zero():
    tese = _tese(tema="dano moral", origem="real")
    a, b, c, d = (Par(uuid.uuid4(), tese.id, f"d{i}", []) for i in range(4))

    def j(par, rodada=1, juiz="jev:m", rel_c=0.9, st_c=0.8):
        return Julgamento(par.id, juiz, rodada, 3, "fortalece", confianca_rel=rel_c, confianca_stance=st_c)

    julgamentos = [
        j(a, rel_c=0.9, st_c=0.6),
        j(b, rel_c=None, st_c=0.9),  # None conta como 0.0
        j(c, rodada=2),  # rodada 2 não entra
        j(d, juiz="jev:outro"),  # outro modelo não entra
    ]
    itens = itens_da_amostra([tese], [a, b, c, d], julgamentos, "jev:m")

    assert sorted(itens, key=lambda i: str(i.par_id)) == sorted(
        [
            ItemAmostra(a.id, "dano moral", "real", 3, "fortalece", 0.6),
            ItemAmostra(b.id, "dano moral", "real", 3, "fortalece", 0.0),
        ],
        key=lambda i: str(i.par_id),
    )


def test_reais_novas_ignora_as_ja_gravadas_e_respeita_o_limite():
    existente = {"pedido_principal": "a", "normas": ["x"]}
    mesma_outra_ordem = {"normas": ["x"], "pedido_principal": "a"}
    b, c = {"pedido_principal": "b"}, {"pedido_principal": "c"}

    assert reais_novas([mesma_outra_ordem, b, c], [existente], limite=10) == [b, c]
    assert reais_novas([mesma_outra_ordem, b, c], [existente], limite=1) == [b]
    assert reais_novas([b], [], limite=0) == []


def test_perguntas_sha_e_estavel():
    sha = perguntas_sha()
    assert sha == perguntas_sha()
    assert len(sha) == 64 and set(sha) <= set("0123456789abcdef")


def test_candidatos_sinteticos_alternam_lados_e_pulam_usados():
    from avaliacao.construir import candidatos_sinteticos

    def acordao(id_, provimento):
        return SimpleNamespace(id_documento=id_, provimento=provimento)

    docs = [acordao("f1", "APROVADO"), acordao("f2", "PARCIAL"), acordao("f3", "APROVADO"),
            acordao("c1", "NEGADO"), acordao("c2", "NEGADO"), acordao("sem_uuid", "NEGADO")]
    uuids = {"f1": "u-f1", "f2": "u-f2", "f3": "u-f3", "c1": "u-c1", "c2": "u-c2"}

    resultado = candidatos_sinteticos(docs, uuids, usados={"u-f2"})

    assert [(a.id_documento, lado) for a, _, lado in resultado] == [
        ("f1", "favoravel"), ("c1", "contrario"), ("f3", "favoravel"), ("c2", "contrario"),
    ]
