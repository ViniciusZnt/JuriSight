"""Testes do classificador de provimento com o Jev, com cliente falso (sem rede)."""
from types import SimpleNamespace

import pytest

from scraper.provimento_jev import (
    FAVORECE,
    PERGUNTAS_PROVIMENTO,
    RECORRENTES,
    RESULTADOS,
    ClassificacaoProvimento,
    ClassificadorJev,
    favorece_por_regra,
    montar_estado,
    para_provimento,
)
from scraper.schema import Provimento


class _FakeClient:
    def __init__(self):
        self.chamadas = []

    def system_one(self, state, questions, *, model=None, **kw):
        self.chamadas.append({"state": state, "questions": questions, "model": model})
        return SimpleNamespace(
            answers={
                "resultado": SimpleNamespace(
                    choice="provido", probabilities={"provido": 0.9, "nao_provido": 0.1}, confidence=0.9
                ),
                "recorrente": SimpleNamespace(
                    choice="reclamante", probabilities={"reclamante": 0.8, "reclamada": 0.2}, confidence=0.8
                ),
                "favorece": SimpleNamespace(
                    choice="reclamante", probabilities={"reclamante": 0.7, "reclamada": 0.3}, confidence=0.7
                ),
            }
        )


def test_classificar_converte_resposta():
    client = _FakeClient()
    c = ClassificadorJev(client=client).classificar("texto do acórdão", "ementa")
    assert c == ClassificacaoProvimento(
        resultado="provido",
        recorrente="reclamante",
        favorece="reclamante",
        probs={
            "resultado": {"provido": 0.9, "nao_provido": 0.1},
            "recorrente": {"reclamante": 0.8, "reclamada": 0.2},
            "favorece": {"reclamante": 0.7, "reclamada": 0.3},
        },
        confianca_resultado=0.9,
        confianca_recorrente=0.8,
        confianca_favorece=0.7,
    )
    assert client.chamadas[0]["model"] == "jev-1.13.0"
    assert client.chamadas[0]["questions"] is PERGUNTAS_PROVIMENTO


def test_estado_trunca():
    estado = montar_estado("x" * 5000 + "FIM", "e" * 2000)
    assert len(estado["acordao"]["dispositivo"]) == 4000
    assert estado["acordao"]["dispositivo"].endswith("FIM")
    assert len(estado["acordao"]["ementa"]) == 1500
    assert montar_estado("abc", None)["acordao"]["ementa"] == ""


@pytest.mark.parametrize("texto", [None, "", "   "])
def test_acordao_vazio_nao_chama_jev(texto):
    client = _FakeClient()
    with pytest.raises(ValueError):
        ClassificadorJev(client=client).classificar(texto, "ementa")
    assert client.chamadas == []


@pytest.mark.parametrize(
    "resultado,esperado",
    [
        ("provido", Provimento.APROVADO),
        ("parcialmente_provido", Provimento.PARCIAL),
        ("nao_provido", Provimento.NEGADO),
        ("nao_conhecido", Provimento.NEGADO),
        ("sem_recurso", Provimento.NAO_APLICAVEL),
    ],
)
def test_para_provimento(resultado, esperado):
    assert para_provimento(resultado) == esperado


@pytest.mark.parametrize(
    "resultado,recorrente,esperado",
    [
        ("provido", "reclamante", "reclamante"),
        ("parcialmente_provido", "reclamante", "ambos_em_parte"),
        ("nao_provido", "reclamante", "reclamada"),
        ("nao_conhecido", "reclamante", "reclamada"),
        ("provido", "reclamada", "reclamada"),
        ("parcialmente_provido", "reclamada", "ambos_em_parte"),
        ("nao_provido", "reclamada", "reclamante"),
        ("nao_conhecido", "reclamada", "reclamante"),
        ("provido", "ambos", None),
        ("nao_provido", "indefinido", None),
        ("sem_recurso", "reclamante", None),
    ],
)
def test_favorece_por_regra(resultado, recorrente, esperado):
    assert favorece_por_regra(resultado, recorrente) == esperado


def test_perguntas_tem_os_rotulos():
    assert set(PERGUNTAS_PROVIMENTO["resultado"].criteria) == set(RESULTADOS)
    assert set(PERGUNTAS_PROVIMENTO["recorrente"].criteria) == set(RECORRENTES)
    assert set(PERGUNTAS_PROVIMENTO["favorece"].criteria) == set(FAVORECE)


def test_modelo_latest_e_recusado(monkeypatch):
    with pytest.raises(ValueError, match="jev-1.13.0"):
        ClassificadorJev(client=_FakeClient(), model="jev-latest")
    monkeypatch.setenv("TYPESAFE_MODEL", "jev-latest")
    with pytest.raises(ValueError, match="latest"):
        ClassificadorJev(client=_FakeClient())
