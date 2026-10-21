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


# --- comparar / conferir ---------------------------------------------------

import csv

from scraper.provimento_jev_db import LinhaClassificada


def _lc(i, resultado, recorrente="reclamante", favorece="reclamante", regex="", conf=0.9):
    return LinhaClassificada(f"doc-{i}", resultado, recorrente, favorece, conf, regex, "")


def test_resumo_matriz_e_concordancia():
    linhas = [
        _lc(1, "provido", regex="APROVADO"),
        _lc(2, "nao_provido", regex="APROVADO"),
        _lc(3, "parcialmente_provido", regex="PARCIAL"),
    ]
    r = cli.resumo(linhas)
    assert r["n"] == 3
    assert r["matriz"] == {"APROVADO": {"APROVADO": 1, "NEGADO": 1}, "PARCIAL": {"PARCIAL": 1}}
    assert r["concordancia"] == pytest.approx(2 / 3)
    assert r["distribuicao"]["resultado"] == {"provido": 1, "nao_provido": 1, "parcialmente_provido": 1}


def test_coerencia_favorece():
    linhas = [
        _lc(1, "provido", "reclamante", "reclamante"),  # coerente
        _lc(2, "provido", "reclamante", "reclamada"),  # incoerente
        _lc(3, "provido", "outro", "reclamante"),  # regra não opina
    ]
    assert cli.resumo(linhas)["coerencia_favorece"] == {"n": 2, "concordam": 0.5}


def test_divergencias_deterministicas():
    linhas = [_lc(i, "provido", regex="APROVADO" if i % 2 else "NEGADO") for i in range(40)]
    a = cli.divergencias(linhas, 5, seed=42)
    b = cli.divergencias(list(reversed(linhas)), 5, seed=42)
    assert [l.documento_id for l in a] == [l.documento_id for l in b]
    assert len(a) == 5
    assert all(l.provimento_regex == "NEGADO" for l in a)


class _StoreComparar:
    def __init__(self, linhas):
        self._linhas = linhas

    def linhas(self, modelo, perguntas_sha):
        return self._linhas

    def trechos(self, ids, tamanho=1500):
        return {i: ("http://x", f"trecho {i}") for i in ids}


def test_csv_conferido_nao_e_sobrescrito(tmp_path):
    caminho = tmp_path / "d.csv"
    store = _StoreComparar([_lc(1, "provido", regex="NEGADO")])
    assert cli.main(["comparar", "--csv", str(caminho)], store=store) == 0
    with open(caminho, encoding="utf-8-sig", newline="") as f:
        linhas = list(csv.DictReader(f))
    assert linhas[0]["trecho_dispositivo"] == "trecho doc-1"
    assert linhas[0]["quem_acertou"] == ""
    linhas[0]["quem_acertou"] = "jev"
    with open(caminho, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(linhas[0]))
        w.writeheader()
        w.writerows(linhas)
    antes = caminho.read_bytes()
    assert cli.csv_conferido(caminho)
    assert cli.main(["comparar", "--csv", str(caminho)], store=store) == 1
    assert caminho.read_bytes() == antes


def test_comparar_sem_linhas_avisa(tmp_path, capsys):
    assert cli.main(["comparar", "--csv", str(tmp_path / "d.csv")], store=_StoreComparar([])) == 1
    assert "classificar" in capsys.readouterr().out


def test_resumo_conferencia(tmp_path, capsys):
    caminho = tmp_path / "c.csv"
    with open(caminho, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["documento_id", "quem_acertou"])
        w.writeheader()
        for i, v in enumerate(["jev", "jev", "regex", "ambos", "nenhum", "", "talvez"]):
            w.writerow({"documento_id": i, "quem_acertou": v})
    assert cli.resumo_conferencia(caminho) == {"jev": 2, "regex": 1, "ambos": 1, "nenhum": 1}
    assert "talvez" in capsys.readouterr().err


def test_conferir_csv_inexistente(tmp_path, capsys):
    assert cli.main(["conferir", "--csv", str(tmp_path / "nada.csv")], store=None) == 2
