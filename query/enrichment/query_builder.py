"""
Query Builder (RFC Tabela 6).

Constrói, DETERMINISTICAMENTE (sem LLM), as duas strings de busca a partir da
EstruturaArgumentativa já revisada pelo usuário:
  - build_bm25_query: termos exatos para a busca lexical (BM25) — "NR-15",
    "CLT art. 192", nomes de agentes nocivos e violações;
  - build_frase_tese: uma frase natural para a busca vetorial (embedding).

Componente separado do Query Enrichment (query_enrichment.py): aquele entende o
caso via LLM, este só formata o que já foi entendido.
"""
from __future__ import annotations

from query.enrichment.schema import EstruturaArgumentativa


def build_bm25_query(estrutura: EstruturaArgumentativa) -> str:
    """Monta a string lexical para o BM25 a partir dos termos exatos do caso.

    Exclui tese_central (frase natural, não agrega termo exato) e setor/cargo
    (baixo valor discriminativo para achar jurisprudência alinhada).

    Input:  estrutura — EstruturaArgumentativa revisada pelo usuário.
    Returns: string com pedido_principal + agente_nocivo + violacoes + normas.
    """
    termos = [
        estrutura.pedido_principal,
        *estrutura.agente_nocivo,
        *estrutura.violacoes,
        *estrutura.normas,
    ]
    return " ".join(t for t in termos if t and t.strip())


def build_frase_tese(estrutura: EstruturaArgumentativa) -> str:
    """Monta a frase-tese para a busca vetorial (embedding).

    Usa tese_central quando disponível (já é uma frase natural, ideal para
    embedding); cai para pedido_principal + violacoes quando o LLM não extraiu
    uma tese_central.

    Input:  estrutura — EstruturaArgumentativa revisada pelo usuário.
    Returns: frase-tese não vazia.
    Raises: ValueError se não houver texto algum (protege embed_text, que já
            rejeita string vazia).
    """
    if estrutura.tese_central and estrutura.tese_central.strip():
        return estrutura.tese_central.strip()

    fallback = " ".join(
        t for t in [estrutura.pedido_principal, *estrutura.violacoes] if t and t.strip()
    )
    if not fallback:
        raise ValueError(
            "EstruturaArgumentativa vazia: não há tese_central nem "
            "pedido_principal/violacoes para montar a frase-tese."
        )
    return fallback
