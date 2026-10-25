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
    import threading
    import time

    class _GravarFalha(_FakeStore):
        def gravar(self, *a, **k):
            raise RuntimeError("banco caiu")

    class _Lento(_FakeClassificador):
        def classificar(self, acordao, ementa):
            self.chamadas.append(acordao)
            time.sleep(0.02)
            return _classif()

    itens = [_item(i) for i in range(200)]
    clf = _Lento()
    with pytest.raises(RuntimeError):
        cli.classificar_pendentes(_GravarFalha(itens), clf, itens, "s", max_workers=2)
    # Sem cancel_futures a fila inteira (200) seguiria rodando em segundo plano.
    time.sleep(0.5)
    assert len(clf.chamadas) < 20


def test_item_lento_nao_atrasa_gravacao_dos_rapidos():
    import threading
    import time

    liberar = threading.Event()
    estado = {"lento_terminou": False, "gravou_antes": None}

    class _Misto(_FakeClassificador):
        def classificar(self, acordao, ementa):
            if acordao == "texto 0":
                liberar.wait(timeout=5)
                estado["lento_terminou"] = True
            return _classif()

    class _Store(_FakeStore):
        def gravar(self, *a, **k):
            if estado["gravou_antes"] is None:
                estado["gravou_antes"] = not estado["lento_terminou"]
                liberar.set()
            super().gravar(*a, **k)

    itens = [_item(i) for i in range(4)]
    assert cli.classificar_pendentes(_Store(itens), _Misto(), itens, "s", max_workers=4) == (4, 0)
    assert estado["gravou_antes"] is True


def test_modelo_latest_e_recusado_no_cli(monkeypatch, capsys):
    monkeypatch.setenv("TYPESAFE_MODEL", "jev-latest")
    assert cli.main(["classificar", "--sim"], store=_FakeStore([_item(1)])) == 2
    assert "latest" in capsys.readouterr().err
    assert cli.main(["aplicar"], store=_StoreAplicar([])) == 2


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


from scraper.provimento_jev_db import LinhaClassificada


# --- aplicar ---

def _la(i, resultado, atual, conf=0.9):
    return LinhaClassificada(f"doc-{i}", resultado, "reclamante", "reclamante", conf, "", atual)


class _StoreAplicar:
    def __init__(self, linhas):
        self._linhas = linhas
        self.chamadas: list = []

    def linhas(self, modelo, perguntas_sha):
        return self._linhas

    def aplicar(self, mudancas):
        self.chamadas.append(mudancas)
        return len(mudancas)


def test_mudancas_respeita_confianca():
    linhas = [_la(1, "provido", "NEGADO", 0.79), _la(2, "provido", "NEGADO", 0.8)]
    assert cli.mudancas(linhas, 0.8) == [("doc-2", "NEGADO", "APROVADO")]


def test_mudancas_ignora_iguais():
    assert cli.mudancas([_la(1, "nao_provido", "NEGADO")], 0.0) == []


def test_aplicar_sem_confirmar_nao_escreve(capsys):
    store = _StoreAplicar([_la(1, "provido", "NEGADO"), _la(2, "provido", "NEGADO", 0.5)])
    assert cli.main(["aplicar"], store=store) == 0
    assert store.chamadas == []
    out = capsys.readouterr().out
    assert "NEGADO → APROVADO: 1" in out
    assert "abaixo do limite e mudariam: 1" in out
    assert "abaixo do limite sem mudança: 0" in out


def test_aplicar_separa_abaixo_do_limite(capsys):
    store = _StoreAplicar([
        _la(1, "provido", "NEGADO", 0.5),       # abaixo e mudaria
        _la(2, "nao_provido", "NEGADO", 0.5),   # abaixo e sem mudança
        _la(3, "nao_provido", "NEGADO", 0.9),
    ])
    assert cli.main(["aplicar"], store=store) == 0
    out = capsys.readouterr().out
    assert "abaixo do limite e mudariam: 1" in out
    assert "abaixo do limite sem mudança: 1" in out


def test_aplicar_com_confirmar_escreve(capsys):
    store = _StoreAplicar([_la(1, "provido", "NEGADO")])
    assert cli.main(["aplicar", "--confirmar"], store=store) == 0
    assert store.chamadas == [[("doc-1", "APROVADO")]]
    assert "reclassify.py" in capsys.readouterr().out


def test_aplicar_sem_linhas_avisa(capsys):
    assert cli.main(["aplicar"], store=_StoreAplicar([])) == 1


@pytest.mark.parametrize("valor", ["-0.1", "1.5", "abc"])
def test_confianca_min_fora_de_0_1(valor):
    with pytest.raises(SystemExit):
        cli.main(["aplicar", "--confianca-min", valor], store=_StoreAplicar([]))


# ---- sincronizar ----
import json  # noqa: E402

from qdrant_client import QdrantClient, models  # noqa: E402

from indexing.lexical.bm25_builder import PROVIMENTOS_FILENAME  # noqa: E402
from indexing.vector_store.qdrant_store import (  # noqa: E402
    COLLECTION_COMPLETO,
    COLLECTION_EMENTA,
    QdrantStore,
)

DOC_A = "aaaaaaaa-0000-0000-0000-000000000001"
DOC_B = "bbbbbbbb-0000-0000-0000-000000000002"
DOC_X = "xxxxxxxx-0000-0000-0000-000000000003"  # só no índice: órfão


class _StoreSync:
    def provimentos_documentos(self):
        return {DOC_A: "APROVADO", DOC_B: "NEGADO"}


def _qdrant_memoria() -> QdrantStore:
    client = QdrantClient(":memory:")
    vec = [1.0, 0.0, 0.0, 0.0]
    for nome in (COLLECTION_COMPLETO, COLLECTION_EMENTA):
        client.create_collection(
            nome, vectors_config=models.VectorParams(size=4, distance=models.Distance.COSINE)
        )
    client.upsert(COLLECTION_COMPLETO, points=[
        models.PointStruct(id=i, vector=vec, payload={"documento_id": d, "provimento": "NAO_APLICAVEL"})
        for i, d in [(1, DOC_A), (2, DOC_A), (3, DOC_B)]
    ])
    client.upsert(COLLECTION_EMENTA, points=[
        models.PointStruct(id=d, vector=vec, payload={"documento_id": d, "provimento": "NAO_APLICAVEL"})
        for d in (DOC_A, DOC_B)
    ])
    return QdrantStore(client)


def _indice(tmp_path):
    (tmp_path / "chunk_ids.json").write_text(
        json.dumps([f"{DOC_A}:0", f"{DOC_A}:1", f"{DOC_B}:0", f"{DOC_X}:0"])
    )
    return tmp_path


def _payloads(qs, colecao):
    pontos, _ = qs._client.scroll(colecao, limit=100, with_payload=True)
    return sorted((p.payload["documento_id"], p.payload["provimento"]) for p in pontos)


def test_provimentos_dos_chunks():
    lista, orfaos = cli.provimentos_dos_chunks(
        [f"{DOC_A}:0", f"{DOC_B}:3", f"{DOC_X}:0"], {DOC_A: "APROVADO", DOC_B: "NEGADO"}
    )
    assert lista == ["APROVADO", "NEGADO", "NAO_APLICAVEL"]
    assert orfaos == 1


def test_sincronizar_atualiza_qdrant_e_bm25(tmp_path, capsys):
    qs, indice = _qdrant_memoria(), _indice(tmp_path)
    rc = cli.main(["sincronizar", "--indice-bm25", str(indice)], store=_StoreSync(), qdrant=qs)
    assert rc == 0
    assert json.loads((indice / PROVIMENTOS_FILENAME).read_text()) == [
        "APROVADO", "APROVADO", "NEGADO", "NAO_APLICAVEL"
    ]
    esperado = sorted([(DOC_A, "APROVADO"), (DOC_B, "NEGADO")])
    assert _payloads(qs, COLLECTION_EMENTA) == esperado
    assert sorted(set(_payloads(qs, COLLECTION_COMPLETO))) == esperado
    saida = capsys.readouterr().out
    assert "órfãos (documento ausente, NAO_APLICAVEL): 1" in saida and "reinicie" in saida.lower()


def test_sincronizar_idempotente(tmp_path):
    qs, indice = _qdrant_memoria(), _indice(tmp_path)
    args = ["sincronizar", "--indice-bm25", str(indice)]
    cli.main(args, store=_StoreSync(), qdrant=qs)
    estado = (
        (indice / PROVIMENTOS_FILENAME).read_text(),
        _payloads(qs, COLLECTION_COMPLETO), _payloads(qs, COLLECTION_EMENTA),
    )
    cli.main(args, store=_StoreSync(), qdrant=qs)
    assert estado == (
        (indice / PROVIMENTOS_FILENAME).read_text(),
        _payloads(qs, COLLECTION_COMPLETO), _payloads(qs, COLLECTION_EMENTA),
    )


def test_sincronizar_so_qdrant_e_so_bm25(tmp_path):
    qs, indice = _qdrant_memoria(), _indice(tmp_path)
    cli.main(["sincronizar", "--so-bm25", "--indice-bm25", str(indice)], store=_StoreSync(), qdrant=qs)
    assert (indice / PROVIMENTOS_FILENAME).exists()
    assert {p for _, p in _payloads(qs, COLLECTION_EMENTA)} == {"NAO_APLICAVEL"}
    (indice / PROVIMENTOS_FILENAME).unlink()
    cli.main(["sincronizar", "--so-qdrant", "--indice-bm25", str(indice)], store=_StoreSync(), qdrant=qs)
    assert not (indice / PROVIMENTOS_FILENAME).exists()
    assert {p for _, p in _payloads(qs, COLLECTION_EMENTA)} == {"APROVADO", "NEGADO"}


def test_sincronizar_nao_cria_cliente_jev(tmp_path, monkeypatch):
    def _proibido(*a, **k):
        raise AssertionError("sincronizar não pode criar cliente do Jev")

    monkeypatch.setattr(cli, "ClassificadorJev", _proibido)
    qs, indice = _qdrant_memoria(), _indice(tmp_path)
    assert cli.main(["sincronizar", "--indice-bm25", str(indice)], store=_StoreSync(), qdrant=qs) == 0
