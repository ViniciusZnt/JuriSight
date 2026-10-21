"""Testes de geração de teses, tema, teses reais e split (sem rede, sem OpenAI real)."""
import json
import os
import uuid
from types import SimpleNamespace

import psycopg
import pytest

from avaliacao.geracao import (
    deduplicar_estruturas,
    gerar_tese,
    sortear_split,
    sortear_acordaos,
    teses_reais,
)
from query.enrichment.schema import EstruturaArgumentativa
from scraper.schema import DocumentoJuridico, TipoDocumento

TESE_JSON = {
    "pedido_principal": "adicional de insalubridade",
    "agente_nocivo": ["ruído"],
    "violacoes": ["EPI sem fiscalização"],
    "normas": ["NR-15"],
    "empresa_ciente": True,
    "setor": "indústria",
    "cargo": "operador",
    "tese_central": "O fornecimento de EPI não elide a insalubridade sem fiscalização.",
}


def _doc():
    return DocumentoJuridico.model_construct(
        id_documento="d1",
        tipo_documento=TipoDocumento.ACORDAO,
        hierarquia_categoria=3,
        ementa="INSALUBRIDADE. EPI. Ementa de teste.",
    )


class _FakeOpenAI:
    def __init__(self, parsed):
        self.chamadas = []
        self.chat = SimpleNamespace(completions=SimpleNamespace(parse=self._parse))
        self._parsed = parsed

    def _parse(self, **kwargs):
        self.chamadas.append(kwargs)
        msg = SimpleNamespace(parsed=self._parsed, refusal=None)
        return SimpleNamespace(choices=[SimpleNamespace(message=msg)])


@pytest.mark.parametrize("lado", ["favoravel", "contrario"])
def test_gerar_tese_valida_schema(lado, monkeypatch):
    monkeypatch.delenv("OPENAI_GEN_MODEL", raising=False)
    fake = _FakeOpenAI(EstruturaArgumentativa(**TESE_JSON))
    tese = gerar_tese(_doc(), lado, client=fake)
    assert isinstance(tese, EstruturaArgumentativa)
    assert tese.pedido_principal == "adicional de insalubridade"
    kw = fake.chamadas[0]
    assert kw["response_format"] is EstruturaArgumentativa
    assert kw["temperature"] == 0.7
    assert kw["model"] == "gpt-4o-mini"
    prompt = " ".join(m["content"] for m in kw["messages"]).upper()
    assert ("FAVORÁVEL" if lado == "favoravel" else "CONTRÁRIA") in prompt
    assert "INSALUBRIDADE. EPI." in prompt


def test_gerar_tese_modelo_do_ambiente(monkeypatch):
    monkeypatch.setenv("OPENAI_GEN_MODEL", "gpt-x")
    fake = _FakeOpenAI(EstruturaArgumentativa(**TESE_JSON))
    gerar_tese(_doc(), "favoravel", client=fake)
    assert fake.chamadas[0]["model"] == "gpt-x"


def test_gerar_tese_lado_invalido():
    with pytest.raises(ValueError):
        gerar_tese(_doc(), "talvez", client=_FakeOpenAI(None))


def test_gerar_tese_recusa_do_modelo():
    fake = _FakeOpenAI(None)
    with pytest.raises(RuntimeError):
        gerar_tese(_doc(), "favoravel", client=fake)


def test_atribuir_tema_devolve_tema_da_lista(monkeypatch):
    from avaliacao.temas import TEMAS, _Tema, atribuir_tema

    monkeypatch.delenv("OPENAI_GEN_MODEL", raising=False)
    fake = _FakeOpenAI(_Tema(tema="dano moral"))
    assert atribuir_tema(TESE_JSON, client=fake) == "dano moral"
    kw = fake.chamadas[0]
    assert kw["response_format"] is _Tema
    assert kw["model"] == "gpt-4o-mini"
    assert all(t in kw["messages"][0]["content"] for t in TEMAS)
    assert "adicional de insalubridade" in kw["messages"][1]["content"]


def test_atribuir_tema_recusa_vira_outro():
    from avaliacao.temas import atribuir_tema

    assert atribuir_tema(TESE_JSON, client=_FakeOpenAI(None)) == "outro"


def test_split_deterministico_e_cobre_os_dois_lados():
    temas = ["a", "b", "c", "d", "e", "f", "g"]
    s1 = sortear_split(temas, seed=42)
    assert s1 == sortear_split(list(reversed(temas)), seed=42)
    assert set(s1) == set(temas)
    assert set(s1.values()) == {"dev", "teste"}
    assert sum(v == "teste" for v in s1.values()) == round(0.4 * 7)
    assert sorted(sortear_split(["a", "b"], seed=1).values()) == ["dev", "teste"]
    # fração extrema ainda deixa um tema de cada lado
    assert set(sortear_split(["a", "b", "c"], seed=1, fracao_teste=0.0).values()) == {"dev", "teste"}
    assert set(sortear_split(["a", "b", "c"], seed=1, fracao_teste=1.0).values()) == {"dev", "teste"}
    assert sortear_split(["a"], seed=1) == {"a": "dev"}
    assert sortear_split([], seed=1) == {}


def test_deduplicar_estruturas():
    a = {"pedido_principal": "x", "normas": ["n"]}
    a_reordenada = {"normas": ["n"], "pedido_principal": "x"}
    b = {"pedido_principal": "y"}
    assert deduplicar_estruturas([a, b, a_reordenada, b]) == [a, b]
    assert deduplicar_estruturas([a, {}, None, "lixo"]) == [a]


@pytest.mark.skipif(not os.getenv("DATABASE_URL"), reason="sem DATABASE_URL")
def test_teses_reais_integracao():
    teses = teses_reais(os.environ["DATABASE_URL"])
    assert isinstance(teses, list)
    assert len({json.dumps(t, sort_keys=True) for t in teses}) == len(teses)


@pytest.mark.skipif(not os.getenv("DATABASE_URL"), reason="sem DATABASE_URL")
def test_teses_reais_ignora_contas_example_com():
    from auth.db import ensure_schema as ensure_auth_schema
    from auth.store import UsuarioStore
    from conversations.db import ensure_schema as ensure_conversas_schema
    from conversations.store import ConversaStore

    url = os.environ["DATABASE_URL"]
    ensure_auth_schema(url)
    ensure_conversas_schema(url)
    sufixo = uuid.uuid4().hex
    usuarios = UsuarioStore(url)
    conversas = ConversaStore(url)
    criados = []
    try:
        for email, marca in (
            (f"e2e-{sufixo}@Example.com", f"tese-example-{sufixo}"),
            (f"real-{sufixo}@teste-integracao.invalid", f"tese-real-{sufixo}"),
        ):
            u = usuarios.create(email=email, hashed_password="hash-fake", nome=None)
            criados.append(u.id)
            c = conversas.create(u.id, "t")
            conversas.add_versao(
                c.id, u.id, estrutura={"tese_central": marca}, has_file=False,
                file_name=None, pdf_extraido=None, aviso=None, resultados=None,
            )

        centrais = {t.get("tese_central") for t in teses_reais(url)}

        assert f"tese-real-{sufixo}" in centrais
        assert f"tese-example-{sufixo}" not in centrais
    finally:
        with psycopg.connect(url) as conn:
            conn.execute("DELETE FROM auth.usuarios WHERE id = ANY(%s)", (criados,))


@pytest.mark.skipif(not os.getenv("DATABASE_URL"), reason="sem DATABASE_URL")
def test_sortear_acordaos_integracao():
    url = os.environ["DATABASE_URL"]
    docs = sortear_acordaos(url, n=6, seed=42)
    assert len(docs) <= 6
    assert all(d.tipo_documento == TipoDocumento.ACORDAO and d.possui_ementa for d in docs)
    assert [d.id_documento for d in docs] == [d.id_documento for d in sortear_acordaos(url, n=6, seed=42)]
