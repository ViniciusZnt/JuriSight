"""
Testes de integração de query/filtros/store.py contra o Postgres local (corpus real).
Pulado se DATABASE_URL não estiver definida, o Postgres não responder ou o preparo
(`python -m query.filtros.preparar`) ainda não tiver rodado. Os testes só leem o banco; o que roda
o preparo (reescreve as tabelas, leva minutos e trava a leitura) só roda com JURISIGHT_TESTAR_PREPARO=1.
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
    with psycopg.connect(DATABASE_URL) as conn:
        prontas = conn.execute("SELECT to_regclass('public.documento_tsv') IS NOT NULL "
                               "AND to_regclass('public.dispositivo') IS NOT NULL").fetchone()[0]
    if not prontas:
        pytest.skip("Rode `python -m query.filtros.preparar` antes.")
    return FiltroStore(DATABASE_URL)


@pytest.mark.skipif(os.getenv("JURISIGHT_TESTAR_PREPARO") != "1",
                    reason="Reescreve as tabelas do banco (minutos); ligue com JURISIGHT_TESTAR_PREPARO=1.")
def test_preparar_e_idempotente():
    preparar(DATABASE_URL)
    preparar(DATABASE_URL)
    assert FiltroStore(DATABASE_URL).existentes(["art_15_clt"]) == {"art_15_clt"}


def test_frase_com_hifen_casa_como_no_texto(store):
    # "auxílio-doença" e "auxilio doenca" valem o mesmo; a contagem bate com uma regex no texto
    with psycopg.connect(DATABASE_URL) as conn:
        regex = conn.execute(
            r"""SELECT count(*) FROM documentos WHERE lower(public.jurisight_unaccent(
                 coalesce(ementa,'') || ' ' || coalesce(fundamentacao,''))) ~ %s""",
            [r"\mconcess(ao|oes|aos)[^a-z0-9]+(do|dos)[^a-z0-9]+auxilios?[^a-z0-9]+doencas?\M"]).fetchone()[0]
    assert store.contar([], ["concessão do auxílio-doença"]).total == regex > 0


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


def test_tribunal_e_fase_filtram_pelo_acervo(store):
    ids = store.elegiveis([], [], ["TRT4"], "conhecimento")
    assert ids
    with psycopg.connect(DATABASE_URL) as conn:
        linhas = conn.execute("SELECT tribunal, sigla_classe FROM documentos WHERE id::text = ANY(%s)", [ids]).fetchall()
    assert {t for t, _ in linhas} == {"TRT4"}
    assert {c for _, c in linhas} <= {"ROT", "RORSum", "RO", "RemNecRO", "RemNecTrab", "AIRO"}


def test_contar_so_com_tribunal(store):
    with psycopg.connect(DATABASE_URL) as conn:
        esperado = conn.execute("SELECT count(*) FROM documentos WHERE tribunal='TRT4'").fetchone()[0]
    assert store.contar([], [], ["TRT4"], None).total == esperado > 0


def test_tribunal_inexistente_nao_acha_nada(store):
    assert store.elegiveis(["art_10_adct"], [], ["TRT99"], None) == []


def test_tribunais_com_total(store):
    lista = dict(store.tribunais())
    assert lista["TRT2"] == 13073
    nomes = [t for t, _ in store.tribunais()]
    assert nomes.index("TRT2") < nomes.index("TRT10") < nomes.index("TRT24")


def test_nr_tema_e_sv_filtraveis(store):
    nr = store.sugerir("nr 15")[0]
    assert nr.codigo == "nr_15" and 2500 <= nr.total <= 3500
    assert "tema_1046" in [s.codigo for s in store.sugerir("tema 1046")]
    ids = store.elegiveis(["nr_15"], ["adicional de insalubridade"])
    assert ids
    with psycopg.connect(DATABASE_URL) as conn:
        ruins = conn.execute(
            r"""SELECT count(*) FROM documentos WHERE id = ANY(%s::uuid[]) AND NOT
                (coalesce(ementa,'') || ' ' || coalesce(fundamentacao,'') ~* '(?<![a-z])(nrs?|normas?\s+regulamentadoras?)[\s-]*(n[º°.]?\s*)?([0-9.]+\s*(,|e)\s*)*0*15(?![0-9])')""",
            (ids,)).fetchone()[0]
    assert ruins == 0
