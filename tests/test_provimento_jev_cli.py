"""Testes do subcomando `classificar` (store e classificador falsos)."""
from __future__ import annotations

import pytest
from typesafe_sdk import TypeSafeError

from scraper import provimento_jev_cli as cli
from scraper.provimento_jev import ClassificacaoProvimento
from scraper.provimento_jev_db import ItemPendente


def _item(i: int) -> ItemPendente:
    return ItemPendente(f"doc-{i}", f"texto {i}", "ementa", "")


def _classif() -> ClassificacaoProvimento:
    return ClassificacaoProvimento("provido", "reclamante", "reclamante", {}, 0.9, 0.9, 0.9)


class _FakeStore:
    def __init__(self, itens):
        self.itens = itens
        self.gravados: list[str] = []

    def pendentes(self, modelo, perguntas_sha, limite=None, apos_id=None, documento_ids=None):
        r = [i for i in self.itens if i.documento_id not in self.gravados]
        if apos_id is not None:
            r = [i for i in r if i.documento_id > apos_id]
        return r[:limite] if limite is not None else r

    def contar_pendentes(self, modelo, perguntas_sha, documento_ids=None):
        return len(self.pendentes(modelo, perguntas_sha))

    def contar_sem_texto(self):
        return 0

    def gravar(self, documento_id, c, provimento_regex, modelo, perguntas_sha):
        self.gravados.append(documento_id)


class _FakeClassificador:
    model = "jev-teste"

    def __init__(self, falhar_uma_vez=()):
        self.falhar_uma_vez = set(falhar_uma_vez)
        self.chamadas: list[str] = []

    def classificar(self, acordao, ementa):
        self.chamadas.append(acordao)
        if acordao in self.falhar_uma_vez:
            self.falhar_uma_vez.discard(acordao)
            raise TypeSafeError("falha simulada")
        return _classif()


def test_classificar_retoma_sem_repetir():
    itens = [_item(1), _item(2), _item(3)]
    store = _FakeStore(itens)
    clf = _FakeClassificador(falhar_uma_vez={"texto 2"})
    assert cli.classificar_pendentes(store, clf, store.pendentes("m", "s"), "s") == (2, 1)
    assert cli.classificar_pendentes(store, clf, store.pendentes("m", "s"), "s") == (1, 0)
    assert sorted(store.gravados) == ["doc-1", "doc-2", "doc-3"]
    assert len(clf.chamadas) == 4


def test_falha_nao_para_o_lote():
    store = _FakeStore([_item(1), _item(2), _item(3)])
    clf = _FakeClassificador(falhar_uma_vez={"texto 1"})
    ok, falhas = cli.classificar_pendentes(store, clf, store.pendentes("m", "s"), "s")
    assert (ok, falhas) == (2, 1)
    assert sorted(store.gravados) == ["doc-2", "doc-3"]


def test_acordao_vazio_conta_como_falha():
    class _Vazio(_FakeClassificador):
        def classificar(self, acordao, ementa):
            raise ValueError("acórdão vazio")

    store = _FakeStore([_item(1)])
    assert cli.classificar_pendentes(store, _Vazio(), store.itens, "s") == (0, 1)


def test_cancelado_nao_chama_jev(monkeypatch):
    store = _FakeStore([_item(1), _item(2)])
    clf = _FakeClassificador()
    monkeypatch.setattr(cli, "confirmar", lambda pergunta: False)
    assert cli.main(["classificar"], store=store, classificador=clf) == 1
    assert clf.chamadas == []


def test_lotes_com_cursor_nao_repetem_item_que_sempre_falha():
    class _SempreFalha(_FakeClassificador):
        def classificar(self, acordao, ementa):
            self.chamadas.append(acordao)
            if acordao == "texto 2":
                raise TypeSafeError("sempre")
            return _classif()

    store = _FakeStore([_item(i) for i in range(1, 6)])
    clf = _SempreFalha()
    assert cli.main(["classificar", "--sim", "--lote", "2"], store=store, classificador=clf) == 1
    assert clf.chamadas.count("texto 2") == 1
    assert len(store.gravados) == 4


def test_limite_e_teto_de_tentativas():
    store = _FakeStore([_item(i) for i in range(1, 8)])
    clf = _FakeClassificador()
    assert cli.main(["classificar", "--sim", "--limite", "3", "--lote", "2"],
                    store=store, classificador=clf) == 0
    assert len(clf.chamadas) == 3


def test_cancelado_nao_instancia_cliente_real(monkeypatch):
    instancias = []

    class _Contador:
        def __init__(self):
            instancias.append(1)
            self.model = "x"

    monkeypatch.setattr(cli, "ClassificadorJev", _Contador)
    monkeypatch.setattr(cli, "confirmar", lambda pergunta: False)
    store = _FakeStore([_item(1)])
    assert cli.main(["classificar"], store=store) == 1
    assert instancias == []


def test_excecao_em_gravar_cancela_chamadas_pendentes():
    import time

    import pytest

    class _GravarFalha(_FakeStore):
        def gravar(self, *a, **k):
            raise RuntimeError("banco caiu")

    class _Lento(_FakeClassificador):
        def classificar(self, acordao, ementa):
            self.chamadas.append(acordao)
            time.sleep(0.05)
            return _classif()

    itens = [_item(i) for i in range(50)]
    clf = _Lento()
    with pytest.raises(RuntimeError):
        cli.classificar_pendentes(_GravarFalha(itens), clf, itens, "s", max_workers=2)
    assert len(clf.chamadas) < 25


@pytest.mark.parametrize("flag", ["--lote", "--limite"])
@pytest.mark.parametrize("valor", ["0", "-1"])
def test_lote_e_limite_positivos(flag, valor):
    with pytest.raises(SystemExit) as e:
        cli.main(["classificar", flag, valor], store=_FakeStore([]), classificador=_FakeClassificador())
    assert e.value.code == 2


def test_estimativa_usa_min_com_limite(capsys):
    store = _FakeStore([_item(i) for i in range(1, 8)])
    clf = _FakeClassificador()
    assert cli.main(["classificar", "--sim", "--limite", "3"], store=store, classificador=clf) == 0
    saida = capsys.readouterr().out
    assert "Pendentes: 3" in saida
    assert "4,800 tokens" in saida
    assert "3 tentados (ok=3, falhas=0)" in saida
