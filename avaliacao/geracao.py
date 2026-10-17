"""
Teses do harness de avaliação: sintéticas (geradas por LLM a partir de acórdãos
reais, estilo Promptagator), reais (conversas salvas) e split dev/teste por tema.
"""
from __future__ import annotations

import itertools
import json
import os
import random
import uuid
from typing import Literal

import psycopg
from openai import OpenAI

from avaliacao.juiz import Juiz
from query.enrichment.schema import EstruturaArgumentativa
from query.search.doc_retriever import COLUNAS_DOCUMENTO, _row_para_documento
from scraper.schema import DocumentoJuridico

MODELO_GERACAO_PADRAO = "gpt-4o-mini"
LIMIAR_FILTRO = 0.5

_SQL_SORTEIO = f"""
SELECT {COLUNAS_DOCUMENTO}
FROM documentos
WHERE tipo_documento = 'ACORDAO' AND possui_ementa AND provimento = ANY(%s)
ORDER BY md5(id::text || %s)
LIMIT %s
"""

_SQL_TESES_REAIS = """
SELECT c.versoes
FROM public.conversas c
JOIN auth.usuarios u ON u.id = c.usuario_id
WHERE lower(u.email) NOT LIKE '%@example.com'
ORDER BY c.criado_em, c.id
"""

_PROMPT_SISTEMA = (
    "Você é um advogado trabalhista brasileiro. A partir da ementa de um acórdão, "
    "você escreve a tese que um advogado levaria à busca de jurisprudência, "
    "preenchendo os campos da estrutura argumentativa. Use as suas próprias palavras: "
    "não copie a ementa literalmente. Deixe vazio (ou nulo) o que a ementa não permitir inferir."
)

_LADOS = {
    "favoravel": "FAVORÁVEL",
    "contrario": "CONTRÁRIA",
}


def sortear_acordaos(database_url: str, n: int, seed: int) -> list[DocumentoJuridico]:
    """Sorteia n acórdãos com ementa, metade com provimento a favor do reclamante
    (APROVADO/PARCIAL) e metade NEGADO. Se n é ímpar, o extra vai para a primeira
    metade. Determinístico para a mesma seed.
    """
    n_favor = (n + 1) // 2
    n_contra = n // 2
    docs: list[DocumentoJuridico] = []
    with psycopg.connect(database_url) as conn, conn.cursor() as cur:
        for provimentos, qtd in ((["APROVADO", "PARCIAL"], n_favor), (["NEGADO"], n_contra)):
            cur.execute(_SQL_SORTEIO, (provimentos, str(seed), qtd))
            docs.extend(_row_para_documento(row) for row in cur.fetchall())
    return docs


def candidatos_sinteticos(acordaos, uuids: dict[str, str], usados: set[str]):
    """(acórdão, uuid, lado) ainda sem tese, alternando favorável e contrário.

    O lado vem do provimento: NEGADO -> "contrario"; APROVADO/PARCIAL -> "favoravel"."""
    por_lado: dict[str, list] = {"favoravel": [], "contrario": []}
    for a in acordaos:
        uid = uuids.get(a.id_documento)
        if uid is None or uid in usados:
            continue
        lado = "contrario" if getattr(a.provimento, "value", a.provimento) == "NEGADO" else "favoravel"
        por_lado[lado].append((a, uid, lado))
    alternados = itertools.zip_longest(por_lado["favoravel"], por_lado["contrario"])
    return [c for par in alternados for c in par if c is not None]


def gerar_tese(
    documento: DocumentoJuridico,
    lado: Literal["favoravel", "contrario"],
    client: OpenAI | None = None,
) -> EstruturaArgumentativa:
    """Gera a tese de um advogado para quem o acórdão é favorável ou contrário."""
    if lado not in _LADOS:
        raise ValueError(f"lado inválido: {lado!r} (esperado 'favoravel' ou 'contrario')")
    client = client or OpenAI()
    modelo = os.getenv("OPENAI_GEN_MODEL", MODELO_GERACAO_PADRAO)
    usuario = (
        f"Ementa do acórdão:\n{documento.ementa}\n\n"
        f"Escreva a tese de um advogado para quem esta decisão é {_LADOS[lado]}."
    )
    resposta = client.chat.completions.parse(
        model=modelo,
        messages=[
            {"role": "system", "content": _PROMPT_SISTEMA},
            {"role": "user", "content": usuario},
        ],
        response_format=EstruturaArgumentativa,
        temperature=0.7,
    )
    tese = resposta.choices[0].message.parsed
    if tese is None:
        raise RuntimeError("o modelo não devolveu uma tese válida (recusa ou saída inválida)")
    return tese


def passa_filtro(juiz: Juiz, tese: dict, documento: DocumentoJuridico) -> bool:
    """Filtro de qualidade da tese sintética: P(relevância >= 2) do acórdão de origem.

    A chamada não é persistida (par_id descartável, rodada 0).
    """
    julgamento = juiz.julgar(tese, documento, rodada=0, par_id=uuid.uuid4())
    probs = julgamento.relevancia_probs or {}
    return probs.get("2", 0) + probs.get("3", 0) >= LIMIAR_FILTRO


def deduplicar_estruturas(estruturas: list[dict]) -> list[dict]:
    """Remove estruturas repetidas (comparando o JSON canônico) e ignora vazias/não-dict."""
    vistas: set[str] = set()
    unicas: list[dict] = []
    for e in estruturas:
        if not isinstance(e, dict) or not e:
            continue
        chave = json.dumps(e, sort_keys=True)
        if chave not in vistas:
            vistas.add(chave)
            unicas.append(e)
    return unicas


def teses_reais(database_url: str) -> list[dict]:
    """Estruturas de todas as versões das conversas salvas, sem repetição.

    Conversas de contas `@example.com` (usadas nos testes E2E) ficam de fora."""
    with psycopg.connect(database_url) as conn, conn.cursor() as cur:
        cur.execute(_SQL_TESES_REAIS)
        linhas = cur.fetchall()
    estruturas = [
        versao.get("estrutura")
        for (versoes,) in linhas
        for versao in (versoes or [])
        if isinstance(versao, dict)
    ]
    return deduplicar_estruturas(estruturas)


def sortear_split(
    temas: list[str], seed: int, fracao_teste: float = 0.4
) -> dict[str, str]:
    """Atribui cada tema a "dev" ou "teste". Determinístico (independe da ordem de
    entrada); com 2+ temas, cada lado recebe pelo menos um.
    """
    ordenados = sorted(set(temas))
    if len(ordenados) < 2:
        return {t: "dev" for t in ordenados}
    random.Random(seed).shuffle(ordenados)
    n_teste = min(max(round(fracao_teste * len(ordenados)), 1), len(ordenados) - 1)
    return {t: ("teste" if i < n_teste else "dev") for i, t in enumerate(ordenados)}
