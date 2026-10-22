"""Classifica o provimento de um acórdão com o Jev (TypeSafe System One).

Três perguntas: resultado do recurso, quem recorreu e a quem a decisão favorece."""
from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass

from typesafe_sdk import Choice, TypeSafeClient

from scraper.schema import Provimento

MODELO_PADRAO = "jev-1.13.0"
TAMANHO_DISPOSITIVO = 4000
TAMANHO_EMENTA = 1500
TOKENS_POR_ACORDAO = 1600

RESULTADOS = ("provido", "parcialmente_provido", "nao_provido", "nao_conhecido", "sem_recurso")
RECORRENTES = ("reclamante", "reclamada", "ambos", "outro", "indefinido")
FAVORECE = ("reclamante", "reclamada", "ambos_em_parte", "indefinido")

PERGUNTAS_PROVIMENTO: dict[str, Choice] = {
    "resultado": Choice(
        instructions=(
            "Qual foi o resultado do recurso julgado neste acórdão (`acordao`)? "
            "Se houver mais de um recurso, escolha parcialmente_provido só quando pelo "
            "menos um deles foi provido, no todo ou em parte; se nenhum foi provido e pelo "
            "menos um foi conhecido, escolha nao_provido. Embargos de declaração acolhidos "
            "apenas para prestar esclarecimentos, sem efeito modificativo, contam como "
            "nao_provido."
        ),
        criteria={
            "provido": "O recurso foi provido (aceito) integralmente.",
            "parcialmente_provido": (
                "O recurso foi provido em parte, ou há mais de um recurso e pelo menos um deles "
                "foi provido, no todo ou em parte."
            ),
            "nao_provido": (
                "O recurso foi conhecido, mas o provimento foi negado. Também quando há mais de "
                "um recurso e nenhum foi provido, ou quando embargos de declaração foram acolhidos "
                "só para esclarecer, sem efeito modificativo."
            ),
            "nao_conhecido": (
                "O recurso não foi conhecido (não foi admitido para julgamento do mérito)."
            ),
            "sem_recurso": (
                "O texto não julga um recurso (por exemplo, incidente, ação originária ou homologação)."
            ),
        },
    ),
    "recorrente": Choice(
        instructions="Quem interpôs o recurso julgado neste acórdão (`acordao`)?",
        criteria={
            "reclamante": "O trabalhador (reclamante, autor).",
            "reclamada": "A empresa ou o empregador (reclamada, ré).",
            "ambos": "Reclamante e reclamada recorreram.",
            "outro": "Outra parte (Ministério Público do Trabalho, União, terceiro).",
            "indefinido": "O texto não permite saber quem recorreu.",
        },
    ),
    "favorece": Choice(
        instructions=(
            "Considerando o resultado final deste acórdão (`acordao`), a decisão favorece "
            "o trabalhador (reclamante) ou a empresa (reclamada)? Atenção a quem recorreu: "
            "negar provimento ao recurso da reclamada favorece o reclamante, e negar "
            "provimento ao recurso do reclamante favorece a reclamada. Recurso provido só "
            "em parte significa que cada parte ganhou em algum ponto."
        ),
        criteria={
            "reclamante": "O resultado favorece o trabalhador.",
            "reclamada": "O resultado favorece a empresa.",
            "ambos_em_parte": "Cada parte ganhou em algum ponto.",
            "indefinido": "O texto não permite saber a quem o resultado favorece.",
        },
    ),
}


def sha_perguntas(perguntas: dict) -> str:
    """sha256 das perguntas do Jev (instruções e critérios).

    Serializa cada pergunta com `model_dump(mode="json")` e `json.dumps(sort_keys=True)`,
    então só muda quando o texto das perguntas muda."""
    dump = {nome: p.model_dump(mode="json") for nome, p in perguntas.items()}
    texto = json.dumps(dump, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(texto.encode("utf-8")).hexdigest()


def perguntas_sha() -> str:
    return sha_perguntas(PERGUNTAS_PROVIMENTO)


def montar_estado(acordao: str, ementa: str | None) -> dict:
    # O dispositivo fica no fim do acórdão, por isso os últimos caracteres.
    return {
        "acordao": {
            "ementa": (ementa or "")[:TAMANHO_EMENTA],
            "dispositivo": acordao[-TAMANHO_DISPOSITIVO:],
        }
    }


@dataclass(frozen=True)
class ClassificacaoProvimento:
    resultado: str
    recorrente: str
    favorece: str
    probs: dict[str, dict[str, float]]
    confianca_resultado: float
    confianca_recorrente: float
    confianca_favorece: float


def validar_modelo(modelo: str) -> str:
    """Recusa aliases móveis: o modelo precisa ficar fixo para a comparação valer."""
    if modelo.endswith("-latest"):
        raise ValueError(
            f"Modelo {modelo!r} termina em '-latest'; fixe a versão (ex.: {MODELO_PADRAO})."
        )
    return modelo


class ClassificadorJev:
    def __init__(self, client: TypeSafeClient | None = None, model: str | None = None):
        self.client = client or TypeSafeClient()
        self.model = validar_modelo(model or os.getenv("TYPESAFE_MODEL", MODELO_PADRAO))

    def classificar(self, acordao: str | None, ementa: str | None) -> ClassificacaoProvimento:
        if not acordao or not acordao.strip():
            raise ValueError("acórdão vazio")
        resposta = self.client.system_one(
            state=montar_estado(acordao, ementa),
            questions=PERGUNTAS_PROVIMENTO,
            model=self.model,
        )
        r = resposta.answers["resultado"]
        c = resposta.answers["recorrente"]
        f = resposta.answers["favorece"]

        def _probs(resp) -> dict[str, float]:
            # O SDK real pode devolver chaves int; no banco (JSONB) viram str.
            return {str(k): v for k, v in resp.probabilities.items()}

        return ClassificacaoProvimento(
            resultado=r.choice,
            recorrente=c.choice,
            favorece=f.choice,
            probs={"resultado": _probs(r), "recorrente": _probs(c), "favorece": _probs(f)},
            confianca_resultado=r.confidence,
            confianca_recorrente=c.confidence,
            confianca_favorece=f.confidence,
        )


_MAPA_PROVIMENTO = {
    "provido": Provimento.APROVADO,
    "parcialmente_provido": Provimento.PARCIAL,
    "nao_provido": Provimento.NEGADO,
    "nao_conhecido": Provimento.NEGADO,
    "sem_recurso": Provimento.NAO_APLICAVEL,
}


def para_provimento(resultado: str) -> Provimento:
    return _MAPA_PROVIMENTO[resultado]


def favorece_por_regra(resultado: str, recorrente: str) -> str | None:
    """Deriva `favorece` de (resultado, recorrente) quando é inequívoco; senão None."""
    if recorrente not in ("reclamante", "reclamada") or resultado not in RESULTADOS:
        return None
    if resultado == "sem_recurso":
        return None
    if resultado == "parcialmente_provido":
        return "ambos_em_parte"
    outro = "reclamada" if recorrente == "reclamante" else "reclamante"
    return recorrente if resultado == "provido" else outro
