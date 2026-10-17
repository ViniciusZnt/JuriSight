"""Testes do juiz Jev e da atribuição de tema, com cliente falso (sem rede)."""
import os
import uuid
from types import SimpleNamespace

import httpx
import pytest
from typesafe_sdk import TypeSafeRateLimitError

from avaliacao.juiz import PERGUNTAS, JuizJev, julgar_lote, montar_estado
from avaliacao.store import Julgamento
from avaliacao.temas import TEMAS, atribuir_tema
from scraper.schema import DocumentoJuridico, TipoDocumento

TESE = {
    "pedido_principal": "adicional de insalubridade",
    "agente_nocivo": ["ruído"],
    "violacoes": ["fornecimento de EPI sem fiscalização do uso"],
    "normas": ["NR-15", "Súmula 289 do TST"],
    "tese_central": "O mero fornecimento de EPI não elide a insalubridade sem prova de uso efetivo.",
}


def _doc(ementa="Ementa X", fundamentacao="Fundamentação Y", id_="d1"):
    # model_construct: o banco pode devolver NULL em campos que o schema tipa como str.
    return DocumentoJuridico.model_construct(
        id_documento=id_,
        tipo_documento=TipoDocumento.ACORDAO,
        hierarquia_categoria=3,
        ementa=ementa,
        fundamentacao=fundamentacao,
    )


class _FakeClient:
    def __init__(self, answers=None, falhar_em=None):
        self.chamadas = []
        self.answers = answers
        self.falhar_em = falhar_em

    def system_one(self, state, questions, *, model=None, **kw):
        self.chamadas.append({"state": state, "questions": questions, "model": model})
        if self.falhar_em is not None and state["acordao"]["ementa"] == self.falhar_em:
            raise TypeSafeRateLimitError(429, {}, httpx.Headers(), "limite")
        return SimpleNamespace(answers=self.answers or _answers_padrao())


def _answers_padrao():
    return {
        "relevancia": SimpleNamespace(
            probabilities={"0": 0.1, "1": 0.1, "2": 0.7, "3": 0.1},
            confidence=0.7,
            score=1.8,
        ),
        "stance": SimpleNamespace(
            choice="enfraquece",
            probabilities={"fortalece": 0.1, "enfraquece": 0.8, "neutro": 0.1},
            confidence=0.8,
        ),
    }


def test_julgar_converte_resposta():
    client = _FakeClient()
    juiz = JuizJev(client=client, model="jev-1.13.0")
    par_id = uuid.uuid4()
    j = juiz.julgar(TESE, _doc(), rodada=1, par_id=par_id)
    assert j == Julgamento(
        par_id=par_id,
        juiz="jev:jev-1.13.0",
        rodada=1,
        relevancia=2,
        stance="enfraquece",
        relevancia_probs={"0": 0.1, "1": 0.1, "2": 0.7, "3": 0.1},
        stance_probs={"fortalece": 0.1, "enfraquece": 0.8, "neutro": 0.1},
        confianca_rel=0.7,
        confianca_stance=0.8,
    )
    assert client.chamadas[0]["questions"] is PERGUNTAS
    assert client.chamadas[0]["model"] == "jev-1.13.0"


def test_chaves_int_das_probabilidades_viram_str():
    answers = _answers_padrao()
    answers["relevancia"].probabilities = {0: 0.0, 1: 0.1, 2: 0.2, 3: 0.7}
    juiz = JuizJev(client=_FakeClient(answers=answers), model="jev-1.13.0")
    j = juiz.julgar(TESE, _doc(), rodada=1, par_id=uuid.uuid4())
    assert j.relevancia == 3
    assert j.relevancia_probs == {"0": 0.0, "1": 0.1, "2": 0.2, "3": 0.7}


def test_estado_com_campos_ausentes():
    doc = _doc(ementa=None, fundamentacao="a" * 5000)
    estado = montar_estado(TESE, doc)
    assert estado["tese"] == TESE
    assert estado["acordao"]["ementa"] == ""
    assert len(estado["acordao"]["fundamentacao_inicio"]) == 3000


def test_modelo_fixado_por_env(monkeypatch):
    monkeypatch.setenv("TYPESAFE_MODEL", "jev-x")
    client = _FakeClient()
    juiz = JuizJev(client=client)
    assert juiz.nome == "jev:jev-x"
    juiz.julgar(TESE, _doc(), rodada=1, par_id=uuid.uuid4())
    assert client.chamadas[0]["model"] == "jev-x"


def test_perguntas_tem_niveis_e_opcoes_do_spec():
    assert len(PERGUNTAS["relevancia"].criteria) == 4
    assert set(PERGUNTAS["stance"].criteria) == {"fortalece", "enfraquece", "neutro"}


def test_julgar_lote_pula_falha_e_segue():
    itens = [(uuid.uuid4(), TESE, _doc(ementa=f"e{i}", id_=f"d{i}")) for i in range(5)]
    juiz = JuizJev(client=_FakeClient(falhar_em="e2"), model="jev-1.13.0")
    vistos = []
    ok = julgar_lote(juiz, itens, rodada=1, ao_julgar=vistos.append, max_workers=2)
    assert ok == 4
    assert len(vistos) == 4
    assert {j.par_id for j in vistos} == {i[0] for i in itens if i[2].ementa != "e2"}


def test_julgar_lote_grava_sem_esperar_item_lento():
    import threading

    lento_id, rapido_id = uuid.uuid4(), uuid.uuid4()
    fast_gravado = threading.Event()
    thread_principal = threading.current_thread()

    class _JuizLento:
        nome = "jev:fake"

        def julgar(self, tese, documento, rodada, par_id):
            if par_id == lento_id:
                # só termina depois que o item rápido foi gravado (ou estoura o prazo)
                fast_gravado.wait(timeout=5)
            return Julgamento(par_id=par_id, juiz=self.nome, rodada=rodada, relevancia=1, stance="neutro")

    gravados = []

    def _grava(j):
        assert threading.current_thread() is thread_principal
        gravados.append(j.par_id)
        if j.par_id == rapido_id:
            fast_gravado.set()

    itens = [(lento_id, TESE, _doc(id_="d0")), (rapido_id, TESE, _doc(id_="d1"))]
    ok = julgar_lote(_JuizLento(), itens, rodada=1, ao_julgar=_grava, max_workers=2)

    assert ok == 2
    assert gravados == [rapido_id, lento_id]


def test_atribuir_tema_retorna_item_da_lista():
    client = _FakeClient(
        answers={
            "tema": SimpleNamespace(
                choice="insalubridade", probabilities={}, confidence=0.9
            )
        }
    )
    assert atribuir_tema(TESE, client=client, model="jev-1.13.0") == "insalubridade"
    assert client.chamadas[0]["state"] == {"tese": TESE}
    assert set(client.chamadas[0]["questions"]["tema"].criteria) == set(TEMAS)


def test_atribuir_tema_fora_da_lista_vira_outro():
    client = _FakeClient(
        answers={"tema": SimpleNamespace(choice="xyz", probabilities={}, confidence=0.1)}
    )
    assert atribuir_tema(TESE, client=client, model="jev-1.13.0") == "outro"


@pytest.mark.skipif(not os.getenv("TYPESAFE_API_KEY"), reason="sem TYPESAFE_API_KEY")
def test_jev_real_responde_em_portugues():
    doc = _doc(
        ementa=(
            "RECURSO DE REVISTA. ADICIONAL DE INSALUBRIDADE. RUÍDO. FORNECIMENTO DE EPI. "
            "O simples fornecimento de equipamento de proteção individual não afasta o "
            "direito ao adicional quando não comprovada a fiscalização do uso efetivo "
            "e a eliminação do agente nocivo. Recurso de revista conhecido e provido."
        ),
        fundamentacao=(
            "A reclamada limitou-se a juntar fichas de entrega de protetores auriculares, "
            "sem demonstrar fiscalização do uso nem a neutralização do ruído acima do "
            "limite de tolerância. Aplica-se a Súmula 289 do TST."
        ),
    )
    j = JuizJev().julgar(TESE, doc, rodada=1, par_id=uuid.uuid4())
    print("JEV_REAL", j)
    assert 0 <= j.relevancia <= 3
    assert j.stance in {"fortalece", "enfraquece", "neutro"}
