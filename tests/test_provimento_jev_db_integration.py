"""
Testes de integração de scraper/provimento_jev_db.py contra um Postgres real.

Cada teste cria os seus documentos (id_documento = "TESTE-PJ-<uuid>") e os
apaga no fim; a FK com cascade remove a linha de provimento_jev. Sempre usa
`documento_ids` para nunca varrer o acervo.
"""
from __future__ import annotations

import os
import uuid

import psycopg
import pytest

from scraper.provimento_jev import ClassificacaoProvimento
from scraper.provimento_jev_db import ProvimentoJevStore, ensure_schema

DATABASE_URL = os.getenv("DATABASE_URL")


def _postgres_disponivel() -> bool:
    if not DATABASE_URL:
        return False
    try:
        psycopg.connect(DATABASE_URL, connect_timeout=2).close()
        return True
    except psycopg.OperationalError:
        return False


pytestmark = pytest.mark.skipif(
    not _postgres_disponivel(),
    reason="Requer DATABASE_URL apontando para um Postgres real e acessível.",
)

MODELO, SHA = "jev-1.13.0", "sha1"


@pytest.fixture(autouse=True)
def _schema_pronto():
    ensure_schema(DATABASE_URL)


@pytest.fixture
def store() -> ProvimentoJevStore:
    return ProvimentoJevStore(DATABASE_URL)


@pytest.fixture
def criar_doc():
    ids: list[str] = []

    def _criar(acordao="texto do acórdão", ementa="ementa", provimento="NEGADO") -> str:
        with psycopg.connect(DATABASE_URL) as conn:
            row = conn.execute(
                "INSERT INTO documentos (id_documento, tipo_documento, acordao, ementa, "
                "provimento, scraped_at) VALUES (%s, 'ACORDAO', %s, %s, %s, NOW()) RETURNING id",
                ("TESTE-PJ-" + uuid.uuid4().hex, acordao, ementa, provimento),
            ).fetchone()
        ids.append(str(row[0]))
        return str(row[0])

    yield _criar
    if ids:
        with psycopg.connect(DATABASE_URL) as conn:
            conn.execute("DELETE FROM documentos WHERE id = ANY(%s::uuid[])", (ids,))


def _classif(resultado="nao_provido") -> ClassificacaoProvimento:
    return ClassificacaoProvimento(
        resultado=resultado, recorrente="reclamada", favorece="reclamante",
        probs={"resultado": {resultado: 0.9}}, confianca_resultado=0.9,
        confianca_recorrente=0.8, confianca_favorece=0.7,
    )


def test_gravar_e_ler(store, criar_doc):
    doc = criar_doc()
    store.gravar(doc, _classif(), "NEGADO", MODELO, SHA)
    linhas = [l for l in store.linhas(MODELO, SHA) if l.documento_id == doc]
    assert len(linhas) == 1
    l = linhas[0]
    assert (l.resultado, l.recorrente, l.favorece) == ("nao_provido", "reclamada", "reclamante")
    assert l.provimento_regex == "NEGADO"
    assert l.provimento_atual == "NEGADO"
    assert l.confianca_resultado == pytest.approx(0.9)


def _linha_bruta(doc):
    with psycopg.connect(DATABASE_URL) as conn:
        return conn.execute(
            "SELECT criado_em, modelo, perguntas_sha, probs, resultado "
            "FROM provimento_jev WHERE documento_id = %s", (doc,)
        ).fetchone()


def test_gravar_faz_upsert(store, criar_doc):
    doc = criar_doc()
    store.gravar(doc, _classif("nao_provido"), "NEGADO", MODELO, SHA)
    antes = _linha_bruta(doc)
    novo = ClassificacaoProvimento(
        resultado="provido", recorrente="reclamada", favorece="reclamante",
        probs={"resultado": {"provido": 0.95}}, confianca_resultado=0.95,
        confianca_recorrente=0.8, confianca_favorece=0.7,
    )
    store.gravar(doc, novo, "NEGADO", "jev-outro", "sha9")
    depois = _linha_bruta(doc)
    assert depois[0] > antes[0]
    assert depois[1:3] == ("jev-outro", "sha9")
    assert depois[3] == {"resultado": {"provido": 0.95}}
    assert depois[4] == "provido"
    assert [l.resultado for l in store.linhas("jev-outro", "sha9") if l.documento_id == doc] == ["provido"]
    assert [l for l in store.linhas(MODELO, SHA) if l.documento_id == doc] == []
    assert [i.documento_id for i in store.pendentes(MODELO, SHA, documento_ids=[doc])] == [doc]


def test_pendentes_ignora_feito(store, criar_doc):
    doc = criar_doc()
    assert [i.documento_id for i in store.pendentes(MODELO, SHA, documento_ids=[doc])] == [doc]
    store.gravar(doc, _classif(), "NEGADO", MODELO, SHA)
    assert store.pendentes(MODELO, SHA, documento_ids=[doc]) == []


def test_pendentes_volta_com_outro_sha(store, criar_doc):
    doc = criar_doc()
    store.gravar(doc, _classif(), "NEGADO", MODELO, SHA)
    assert len(store.pendentes(MODELO, "sha2", documento_ids=[doc])) == 1
    assert len(store.pendentes("outro-modelo", SHA, documento_ids=[doc])) == 1


def test_pendentes_ignora_acordao_vazio(store, criar_doc):
    doc = criar_doc(acordao="   ")
    assert store.pendentes(MODELO, SHA, documento_ids=[doc]) == []
    assert store.contar_sem_texto() >= 1


def test_pendentes_trunca_texto_e_pagina(store, criar_doc):
    a = criar_doc(acordao="x" * 5000 + "FIM", ementa="e" * 2000)
    b = criar_doc()
    ordenados = sorted([a, b])
    itens = store.pendentes(MODELO, SHA, documento_ids=[a, b])
    assert [i.documento_id for i in itens] == ordenados
    item_a = next(i for i in itens if i.documento_id == a)
    assert len(item_a.acordao) == 4000 and item_a.acordao.endswith("FIM")
    assert len(item_a.ementa) == 1500
    assert item_a.provimento_regex == "NEGADO"
    assert [i.documento_id for i in store.pendentes(MODELO, SHA, documento_ids=[a, b], limite=1)] == ordenados[:1]
    apos = store.pendentes(MODELO, SHA, documento_ids=[a, b], apos_id=ordenados[0])
    assert [i.documento_id for i in apos] == ordenados[1:]


def test_contar_pendentes_reflete_gravacao(store, criar_doc):
    doc = criar_doc()
    assert store.contar_pendentes(MODELO, SHA, documento_ids=[doc]) == 1
    store.gravar(doc, _classif(), "NEGADO", MODELO, SHA)
    assert store.contar_pendentes(MODELO, SHA, documento_ids=[doc]) == 0


def test_contar_pendentes_paridade_com_pendentes(store, criar_doc):
    ids = [criar_doc(), criar_doc(acordao="   "), criar_doc(acordao="\n\t\n"), criar_doc()]
    assert store.contar_pendentes(MODELO, SHA, documento_ids=ids) == len(
        store.pendentes(MODELO, SHA, documento_ids=ids)
    ) == 2


def test_acordao_so_com_quebras_de_linha_nao_e_pendente(store, criar_doc):
    doc = criar_doc(acordao="\n\t\r\n")
    assert store.pendentes(MODELO, SHA, documento_ids=[doc]) == []
    assert store.contar_sem_texto() >= 1


def test_trechos(store, criar_doc):
    doc = criar_doc(acordao="a" * 3000 + "FIM")
    t = store.trechos([doc], tamanho=100)
    assert set(t) == {doc}
    link, trecho = t[doc]
    assert link is None and len(trecho) == 100 and trecho.endswith("FIM")


def test_aplicar_muda_provimento(store, criar_doc):
    doc = criar_doc()
    assert store.aplicar([(doc, "PARCIAL")]) == 1
    with psycopg.connect(DATABASE_URL) as conn:
        assert conn.execute("SELECT provimento FROM documentos WHERE id = %s", (doc,)).fetchone()[0] == "PARCIAL"
    assert store.aplicar([(doc, "PARCIAL")]) == 0


def test_cascade(store, criar_doc):
    doc = criar_doc()
    store.gravar(doc, _classif(), "NEGADO", MODELO, SHA)
    with psycopg.connect(DATABASE_URL) as conn:
        conn.execute("DELETE FROM documentos WHERE id = %s", (doc,))
        n = conn.execute("SELECT count(*) FROM provimento_jev WHERE documento_id = %s", (doc,)).fetchone()[0]
    assert n == 0


def test_regex_preservada_apos_aplicar(store, criar_doc):
    doc = criar_doc()
    store.gravar(doc, _classif(), "NEGADO", MODELO, SHA)
    store.aplicar([(doc, "PARCIAL")])
    # Simula `pendentes` lendo documentos.provimento (já com o valor do Jev).
    store.gravar(doc, _classif(), "PARCIAL", "outro-modelo", "outro-sha")
    linhas = store.linhas("outro-modelo", "outro-sha")
    assert [l.provimento_regex for l in linhas if l.documento_id == doc] == ["NEGADO"]


def test_provimentos_documentos(store, criar_doc):
    a = criar_doc(provimento="APROVADO")
    b = criar_doc(provimento=None)
    r = store.provimentos_documentos()
    assert r[a] == "APROVADO"
    assert r[b] == "NAO_APLICAVEL"
