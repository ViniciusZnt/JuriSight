"""Testes de query/search/triagem.py (nota 0-3 e posição por ementa), com OpenAI falso."""
from __future__ import annotations

from query.enrichment.schema import EstruturaArgumentativa
from query.search.triagem import (
    Avaliacao,
    ItemTriagem,
    TriagemGerada,
    avaliar_lote,
    chave_da_triagem,
    tese_para_ia,
)
from tests.fakes import FakeOpenAI, documento_fake

EST = EstruturaArgumentativa(tese_central="calor acima do limite de tolerância")


def _item(numero, nota, pedido="deferiu", fatos=True, motivo=None):
    return ItemTriagem(numero=numero, motivo=motivo or f"m{numero}", nota=nota,
                       pedido_da_tese=pedido, fatos_da_premissa=fatos)


def _fake(*itens):
    return FakeOpenAI(TriagemGerada(itens=list(itens)))


def test_cada_item_vira_avaliacao_pelo_id_e_posicao_segue_a_premissa():
    fake = _fake(_item(1, 3), _item(2, 2, "negou", fatos=False))
    r = avaliar_lote(EST, {"a": documento_fake(), "b": documento_fake()}, fake)
    assert r["a"] == Avaliacao(nota=3, posicao="deferiu", motivo="m1")
    assert r["b"] == Avaliacao(nota=2, posicao="fato_diferente", motivo="m2")


def test_negou_com_os_mesmos_fatos_fica_negou():
    r = avaliar_lote(EST, {"a": documento_fake()}, _fake(_item(1, 2, "negou", fatos=True)))
    assert r["a"].posicao == "negou"


def test_numero_repetido_ou_fora_e_nota_invalida_sao_descartados():
    fake = _fake(_item(1, 2), _item(1, 0), _item(3, 3), _item(2, 5))
    r = avaliar_lote(EST, {"a": documento_fake(), "b": documento_fake()}, fake)
    assert set(r) == {"a"} and r["a"].nota == 2


def test_ao_modelo_vao_so_campos_da_tese_e_ementa_cortada_com_cabecalho(monkeypatch):
    monkeypatch.delenv("OPENAI_TRIAGEM_MODEL", raising=False)
    est = EstruturaArgumentativa(tese_central="calor", tribunais=["TRT12"], expressoes=["calor intenso"],
                                 dispositivos=["art_192_clt"], fase="conhecimento")
    fake = _fake()
    doc = documento_fake(ementa="A" * 1300 + "FIM", tribunal="TRT12", turma="1ª Turma", sigla_classe="ROT")
    avaliar_lote(est, {"a": doc}, fake)
    chamada = fake.chamadas[0]
    user = chamada["messages"][1]["content"]
    assert "tribunais" not in user and "expressoes" not in user and "dispositivos" not in user
    assert "conhecimento" not in user and "calor" in user
    assert "#1 (ROT, TRT12, 1ª Turma" in user and "FIM" in user and user.count("A") < 1300
    assert chamada["response_format"] is TriagemGerada and chamada["timeout"] == 20
    assert chamada["model"] == "gpt-4o-mini"


def test_recusa_do_modelo_devolve_vazio():
    assert avaliar_lote(EST, {"a": documento_fake()}, FakeOpenAI(None)) == {}


def test_lote_vazio_nao_chama_a_openai():
    fake = _fake()
    assert avaliar_lote(EST, {}, fake) == {} and fake.chamadas == []


def test_tese_para_ia_so_tem_campos_da_tese():
    est = EstruturaArgumentativa(pedido_principal="adicional", tese_central="t", tribunais=["TRT4"], normas=["NR-15"])
    assert tese_para_ia(est) == {"pedido_principal": "adicional", "normas": ["NR-15"], "tese_central": "t"}


def test_chave_muda_com_tese_doc_e_modelo_mas_nao_com_filtros(monkeypatch):
    monkeypatch.delenv("OPENAI_TRIAGEM_MODEL", raising=False)
    base = chave_da_triagem(EstruturaArgumentativa(tese_central="calor"), "a")
    assert base == chave_da_triagem(EstruturaArgumentativa(tese_central="calor", tribunais=["TRT4"]), "a")
    assert base != chave_da_triagem(EstruturaArgumentativa(tese_central="ruído"), "a")
    assert base != chave_da_triagem(EstruturaArgumentativa(tese_central="calor"), "b")
    monkeypatch.setenv("OPENAI_TRIAGEM_MODEL", "outro")
    assert base != chave_da_triagem(EstruturaArgumentativa(tese_central="calor"), "a")
