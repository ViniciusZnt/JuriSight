"""
Testes de integração de query/filtros/store.py contra o Postgres local (corpus real).
Pulado se DATABASE_URL não estiver definida ou o Postgres não responder.
Requer `python -m query.filtros.preparar` já rodado (o primeiro teste também roda).
"""
from __future__ import annotations

import os

import psycopg
import pytest

from query.filtros.preparar import preparar
from query.filtros.store import FiltroStore

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


@pytest.fixture(scope="module")
def store():
    preparar(DATABASE_URL)
    return FiltroStore(DATABASE_URL)


def test_preparar_e_idempotente(store):
    preparar(DATABASE_URL)
    preparar(DATABASE_URL)


def test_niveis_entram_na_tabela(store):
    c = store.contar(["art_10_adct"], []).total
    assert c >= store.contar(["b_ii_art_10_adct"], []).total > 0


def test_sugerir_por_tokens_em_qualquer_ordem(store):
    a = [s.codigo for s in store.sugerir("clt 791")]
    b = [s.codigo for s in store.sugerir("791 clt")]
    assert "art_791_clt" in a and a == b
    assert len(store.sugerir("art", limite=10)) == 10
    assert store.sugerir("") == []


def test_sugerir_prefixo_no_ultimo_token(store):
    assert store.sugerir("clt art 79")[0].codigo == "art_791_clt"


def test_expressao_singular_plural_e_acento(store):
    a = store.contar([], ["dano moral coletivo"]).total
    b = store.contar([], ["Danos Morais Coletivos"]).total
    assert a == b and a >= 100


def test_elegiveis_cumprem_todos_os_filtros(store):
    ids = store.elegiveis(["art_186_ccb"], ["dano moral coletivo"])
    assert 0 < len(ids) == store.contar(["art_186_ccb"], ["dano moral coletivo"]).total
    with psycopg.connect(DATABASE_URL) as conn:
        ruins = conn.execute(
            """SELECT count(*) FROM documentos WHERE id = ANY(%s::uuid[]) AND NOT (
                 EXISTS (SELECT 1 FROM unnest(referencia_legislativa) r WHERE r = 'art_186_ccb' OR r LIKE '%%\\_art_186_ccb')
                 AND coalesce(ementa,'') || ' ' || coalesce(fundamentacao,'') ~* 'danos? mora(l|is) coletivos?')""",
            (ids,)).fetchone()[0]
    assert ruins == 0


def test_codigo_inexistente_da_zero(store):
    assert store.elegiveis(["art_99999_clt"], []) == []


def test_sem_filtro_valido_da_zero(store):
    assert store.elegiveis([], []) == []
    assert store.contar([], []).total == 0


def test_existentes(store):
    assert store.existentes(["art_15_clt", "art_99999_clt"]) == {"art_15_clt"}
