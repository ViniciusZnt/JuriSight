import pytest
"""Testes do CLI de construção do conjunto-ouro (fakes; sem OpenAI nem banco)."""
import uuid
from types import SimpleNamespace

from avaliacao.construir import etapa_fila, precisa_de_pool, reais_novas
from avaliacao.store import Par, Tese


def _tese(estrutura=None, tema="insalubridade", origem="sintetica"):
    return Tese(uuid.uuid4(), estrutura or {"pedido_principal": "x"}, origem, tema, "dev", None)


class _StoreFalso:
    """Teses, pares e fila em memória; reproduz só o que `etapa_fila` usa."""

    def __init__(self, teses, pares, fila=None):
        self._teses, self._pares = teses, pares
        self.fila: dict = dict(fila or {})

    def listar_teses(self, split=None):
        return self._teses

    def pares_da_tese(self, tese_id):
        return [p for p in self._pares if p.tese_id == tese_id]

    def amostra(self):
        return dict(self.fila)

    def definir_amostra(self, par_ids):
        self.fila.update(par_ids)


def test_etapa_fila_poe_todos_os_pares_e_e_idempotente():
    tese = _tese()
    pares = [Par(uuid.uuid4(), tese.id, f"doc{i}", ["bm25"]) for i in range(3)]
    store = _StoreFalso([tese], pares, fila={pares[0].id: "incerta"})

    etapa_fila(store)
    etapa_fila(store)

    assert set(store.fila) == {p.id for p in pares}
    assert store.fila[pares[0].id] == "incerta"  # quem já estava na fila não muda
    assert store.fila[pares[1].id] == "sorteada"


def test_tese_com_pool_antigo_precisa_de_pool_novo():
    p = lambda corredores: Par(uuid.uuid4(), uuid.uuid4(), "d", corredores)  # noqa: E731
    assert precisa_de_pool([])
    assert precisa_de_pool([p(["passo_zero"])])
    assert precisa_de_pool([p(["bm25", "vetorial", "pipeline"])])  # pool antigo
    assert not precisa_de_pool([p(["passo_zero"]), p(["hibrido", "bm25"])])
    assert not precisa_de_pool([p(["hibrido"])])


def test_reais_novas_ignora_as_ja_gravadas_e_respeita_o_limite():
    existente = {"pedido_principal": "a", "normas": ["x"]}
    mesma_outra_ordem = {"normas": ["x"], "pedido_principal": "a"}
    b, c = {"pedido_principal": "b"}, {"pedido_principal": "c"}

    assert reais_novas([mesma_outra_ordem, b, c], [existente], limite=10) == [b, c]
    assert reais_novas([mesma_outra_ordem, b, c], [existente], limite=1) == [b]
    assert reais_novas([b], [], limite=0) == []


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


def _rodar_sinteticas(monkeypatch, teses):
    """Roda _completar_sinteticas com fakes; devolve os `exemplos` passados a gerar_tese."""
    from types import SimpleNamespace

    from avaliacao import construir, geracao, temas

    visto = []
    acordao = SimpleNamespace(id_documento="d1", provimento="APROVADO")
    monkeypatch.setattr(geracao, "sortear_acordaos", lambda url, n, seed: [acordao])
    monkeypatch.setattr(construir, "uuids_origem", lambda url, docs: {"d1": "u1"})

    def fake_gerar(doc, lado, client=None, exemplos=None):
        visto.append(exemplos)
        return SimpleNamespace(model_dump=lambda: {"pedido_principal": "x"})

    monkeypatch.setattr(geracao, "gerar_tese", fake_gerar)
    monkeypatch.setattr(temas, "atribuir_tema", lambda e, client=None: "outro")
    store = SimpleNamespace(listar_teses=lambda: teses, criar_tese=lambda *a, **k: None)
    construir._completar_sinteticas(store, SimpleNamespace(database_url="db"), None, len(teses) + 1, 42, {"outro": "dev"})
    return visto


def test_sinteticas_recebem_texto_original_dos_advogados(monkeypatch):
    import uuid

    from avaliacao.store import Tese

    adv = Tese(uuid.uuid4(), {"_texto_original": "texto do advogado"}, "advogado", "outro", "dev", "u0")
    assert _rodar_sinteticas(monkeypatch, [adv]) == [["texto do advogado"]]


def test_sinteticas_sem_advogados_passam_none(monkeypatch):
    assert _rodar_sinteticas(monkeypatch, []) == [None]


def test_doc_e_help_descrevem_o_pool_novo(capsys):
    from avaliacao import construir

    assert "híbrido" in construir.__doc__ and "vetorial e pipeline" not in construir.__doc__
    with pytest.raises(SystemExit):
        construir.main(["--help"])
    assert "híbrido" in capsys.readouterr().out
