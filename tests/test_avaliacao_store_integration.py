"""
Testes de integração de avaliacao/store.py contra um Postgres DE VERDADE.

Cada teste cria suas teses (UUIDs próprios) e as apaga ao final — as FKs com
ON DELETE CASCADE derrubam pares, julgamentos e amostra junto.

Pulado automaticamente se DATABASE_URL não estiver definida ou o Postgres não
responder (mesmo espírito de tests/test_conversa_store_integration.py).
"""
from __future__ import annotations

import os
import uuid

import psycopg
import pytest

from avaliacao.db import ensure_schema
from avaliacao.store import AvaliacaoStore, Julgamento

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


@pytest.fixture(autouse=True)
def _schema_pronto():
    ensure_schema(DATABASE_URL)


@pytest.fixture
def store() -> AvaliacaoStore:
    return AvaliacaoStore(DATABASE_URL)


@pytest.fixture
def teses_criadas():
    """Lista a ser preenchida pelos testes; apaga as teses (e, em cascata,
    pares/julgamentos/amostra) ao final."""
    ids: list[uuid.UUID] = []
    yield ids
    if not ids:
        return
    conn = psycopg.connect(DATABASE_URL)
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM avaliacao.teses WHERE id = ANY(%s)", (ids,))
        conn.commit()
    finally:
        conn.close()


def _tese(store, teses_criadas, tema="horas extras", split="dev", origem="sintetica", doc_origem=None):
    t = store.criar_tese({"pedido_principal": f"p-{uuid.uuid4().hex[:6]}"}, origem, tema, split, doc_origem)
    teses_criadas.append(t.id)
    return t


def _doc(prefixo="d") -> str:
    return f"{prefixo}-{uuid.uuid4().hex}"


def test_round_trip_tese_par_julgamento(store, teses_criadas):
    tese = _tese(store, teses_criadas, doc_origem="origem-1")
    assert tese.estrutura["pedido_principal"].startswith("p-")
    assert (tese.origem, tese.tema, tese.split, tese.documento_origem_id) == (
        "sintetica", "horas extras", "dev", "origem-1",
    )
    assert tese.id in {t.id for t in store.listar_teses()}
    assert tese.id in {t.id for t in store.listar_teses(split="dev")}
    assert tese.id not in {t.id for t in store.listar_teses(split="teste")}

    doc = _doc()
    (par,) = store.adicionar_pares(tese.id, {doc: ["bm25"]})
    assert par.tese_id == tese.id and par.documento_id == doc and par.corredores == ["bm25"]
    assert [p.id for p in store.pares_da_tese(tese.id)] == [par.id]

    j = Julgamento(
        par_id=par.id, juiz="jev:jev-1.13.0", rodada=1, relevancia=2, stance="fortalece",
        relevancia_probs={"0": 0.1, "1": 0.2, "2": 0.6, "3": 0.1},
        stance_probs={"fortalece": 0.7, "enfraquece": 0.1, "neutro": 0.2},
        confianca_rel=0.6, confianca_stance=0.7,
    )
    store.gravar_julgamento(j)
    (lido,) = [x for x in store.julgamentos("jev:") if x.par_id == par.id]
    assert lido.juiz == "jev:jev-1.13.0" and lido.rodada == 1
    assert (lido.relevancia, lido.stance) == (2, "fortalece")
    assert lido.relevancia_probs == j.relevancia_probs
    assert lido.stance_probs == j.stance_probs
    assert lido.confianca_rel == pytest.approx(0.6)
    assert lido.confianca_stance == pytest.approx(0.7)
    assert all(x.par_id != par.id for x in store.julgamentos("humano:"))

    # upsert por (par, juiz, rodada): regravar substitui, não duplica
    store.gravar_julgamento(Julgamento(par.id, "jev:jev-1.13.0", 1, 3, "neutro"))
    (relido,) = [x for x in store.julgamentos("jev:") if x.par_id == par.id]
    assert (relido.relevancia, relido.stance) == (3, "neutro")
    assert relido.relevancia_probs is None and relido.confianca_rel is None


def test_adicionar_pares_une_corredores(store, teses_criadas):
    tese = _tese(store, teses_criadas)
    doc = _doc()
    store.adicionar_pares(tese.id, {doc: ["bm25"]})
    pares = store.adicionar_pares(tese.id, {doc: ["pipeline"], _doc("outro"): ["vetorial"]})

    por_doc = {p.documento_id: p for p in pares}
    assert por_doc[doc].corredores == ["bm25", "pipeline"]
    assert len(store.pares_da_tese(tese.id)) == 2  # sem duplicar o par


def test_rotulos_finais_so_humanos(store, teses_criadas):
    tese = _tese(store, teses_criadas)
    d1, d2, d3 = _doc(), _doc(), _doc()
    pares = {p.documento_id: p for p in store.adicionar_pares(tese.id, {d1: ["bm25"], d2: ["bm25"], d3: ["bm25"]})}

    for d, rel, st in [(d1, 1, "neutro"), (d2, 2, "fortalece"), (d3, 3, "enfraquece")]:
        store.gravar_julgamento(Julgamento(pares[d].id, "jev:m", 1, rel, st))
    # humano só no d1; julgamentos antigos do Jev não contam
    store.gravar_julgamento(Julgamento(pares[d1].id, "humano:a@x.invalid", 1, 3, "fortalece"))

    rel, stance = store.rotulos_finais(tese.id)
    assert rel == {d1: 3}
    assert stance == {d1: "fortalece"}


def test_fila_segue_ordem_e_progresso(store, teses_criadas):
    tese = _tese(store, teses_criadas, tema="rescisão")
    docs = [_doc() for _ in range(3)]
    pares = store.adicionar_pares(tese.id, {d: ["bm25"] for d in docs})
    ordem_id = sorted(p.id for p in pares)  # desempate por id
    metade = {ordem_id[0]: "incerta", ordem_id[1]: "sorteada", ordem_id[2]: "sorteada"}
    # a fila é global: com pares reais na amostra a ordem não é isolável
    if store.amostra():
        pytest.skip("amostra real presente no banco; ordem da fila não é isolável")
    store.definir_amostra(metade)
    assert {k: v for k, v in store.amostra().items() if k in metade} == metade

    juiz = f"humano:{uuid.uuid4().hex[:6]}@x.invalid"
    ja_feitos, total_inicial = store.progresso(juiz)
    assert ja_feitos == 0

    esperado = [ordem_id[1], ordem_id[2], ordem_id[0]]  # sorteadas primeiro, depois a incerta
    for i, par_id in enumerate(esperado):
        proximo = store.proximo_da_fila(juiz)
        assert proximo is not None
        par, t = proximo
        assert par.id == par_id and t.id == tese.id
        store.gravar_julgamento(Julgamento(par_id, juiz, 1, 1, "neutro"))
        assert store.progresso(juiz) == (i + 1, total_inicial)

    assert store.proximo_da_fila(juiz) is None


def test_rotulo_humano_mais_recente_do_mesmo_juiz_prevalece(store, teses_criadas):
    tese = _tese(store, teses_criadas)
    doc = _doc()
    (par,) = store.adicionar_pares(tese.id, {doc: ["bm25"]})
    store.gravar_julgamento(Julgamento(par.id, "humano:a@x.invalid", 1, 1, "neutro"))
    store.gravar_julgamento(Julgamento(par.id, "humano:a@x.invalid", 2, 3, "enfraquece"))
    rel, stance = store.rotulos_finais(tese.id)
    assert rel == {doc: 3} and stance == {doc: "enfraquece"}


def test_dois_humanos_aplicam_a_regra(store, teses_criadas):
    tese = _tese(store, teses_criadas)
    d1, d2 = _doc(), _doc()
    pares = {p.documento_id: p for p in store.adicionar_pares(tese.id, {d1: ["bm25"], d2: ["bm25"]})}
    for d, (ra, rb) in {d1: (1, 2), d2: (3, 3)}.items():
        store.gravar_julgamento(Julgamento(pares[d].id, "humano:a@x.invalid", 1, ra, "neutro" if ra < 2 else "fortalece"))
        store.gravar_julgamento(Julgamento(pares[d].id, "humano:b@x.invalid", 1, rb, "fortalece"))
    rel, _ = store.rotulos_finais(tese.id)
    assert rel == {d1: 1, d2: 3}


def test_pendente_fica_fora(store, teses_criadas):
    tese = _tese(store, teses_criadas)
    d1, d2 = _doc(), _doc()
    pares = {p.documento_id: p for p in store.adicionar_pares(tese.id, {d1: ["bm25"], d2: ["bm25"]})}
    store.gravar_julgamento(Julgamento(pares[d1].id, "humano:a@x.invalid", 1, 0, "neutro"))
    store.gravar_julgamento(Julgamento(pares[d1].id, "humano:b@x.invalid", 1, 3, "fortalece"))
    store.gravar_julgamento(Julgamento(pares[d2].id, "humano:a@x.invalid", 1, 2, "fortalece"))

    rel, stance = store.rotulos_finais(tese.id)
    assert rel == {d2: 2} and stance == {d2: "fortalece"}
    assert (tese.id, pares[d1].id) in store.pendentes()

    # o adjudicador resolve (e-mail em qualquer caixa)
    store.gravar_julgamento(Julgamento(pares[d1].id, "humano:b@x.invalid", 2, 3, "fortalece"))
    store.gravar_julgamento(Julgamento(pares[d1].id, "humano:c@x.invalid", 2, 1, "neutro"))  # rodada 2
    rel, _ = store.rotulos_finais(tese.id, adjudicador=" C@X.invalid")
    assert rel[d1] == 1
    assert (tese.id, pares[d1].id) not in store.pendentes(adjudicador="c@x.invalid")


def test_pendentes_detalhe_e_adjudicador_na_rodada_1(store, teses_criadas):
    tese = _tese(store, teses_criadas)
    d1, d2 = _doc(), _doc()
    pares = {p.documento_id: p for p in store.adicionar_pares(tese.id, {d1: ["bm25"], d2: ["bm25"]})}
    store.gravar_julgamento(Julgamento(pares[d1].id, "humano:a@x.invalid", 1, 0, "neutro"))
    store.gravar_julgamento(Julgamento(pares[d1].id, "humano:b@x.invalid", 1, 3, "fortalece"))
    # d2: a adjudicadora também avaliou na rodada 1, diferença de 1: vale a menor
    store.gravar_julgamento(Julgamento(pares[d2].id, "humano:a@x.invalid", 1, 2, "fortalece"))
    store.gravar_julgamento(Julgamento(pares[d2].id, "humano:c@x.invalid", 1, 1, "neutro"))

    det = [d for d in store.pendentes_detalhe("c@x.invalid") if d["par_id"] == pares[d1].id]
    assert len(det) == 1 and det[0]["documento_id"] == d1 and det[0]["tese_id"] == tese.id
    assert sorted((j["juiz"], j["nota"], j["stance"]) for j in det[0]["julgamentos"]) == [
        ("humano:a@x.invalid", 0, "neutro"), ("humano:b@x.invalid", 3, "fortalece")]
    assert not any(d["par_id"] == pares[d2].id for d in store.pendentes_detalhe("c@x.invalid"))
    rel, _ = store.rotulos_finais(tese.id, "c@x.invalid")
    assert rel == {d2: 1}
