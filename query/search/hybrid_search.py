"""
Hybrid Search.

Funde busca vetorial (ChromaDB) e lexical (BM25) via Reciprocal Rank Fusion (RRF),
no nível de documento_id, e devolve os documentos mais relevantes para a query.

Três canais de recuperação:
  - Chroma COMPLETO (por chunk)  → casa a passagem semanticamente;
  - Chroma EMENTA   (por doc)    → casa a tese semanticamente;
  - BM25            (por chunk)  → casa termos exatos (NR-15, art. 193).
Os hits de chunk são projetados para documento_id antes da fusão (a coleção da
ementa já é por documento).
"""
from __future__ import annotations

from dataclasses import dataclass

from indexing.lexical.bm25_builder import LoadedBM25
from indexing.vector_store.chroma_store import (
    COLLECTION_COMPLETO,
    COLLECTION_EMENTA,
    ChromaStore,
)
from processing.embeddings.poly_vector import PolyVectorEmbedder

# Constante de amortecimento do RRF (60 é o padrão da literatura).
RRF_K = 60
# Quantos candidatos pedir por canal (chunks colapsam em docs, então buscamos mais).
CANDIDATOS_POR_CANAL = 5


def _doc_id_do_chunk(chunk_id: str) -> str:
    """Extrai o documento_id de um chunk_id no formato 'documento_id:posicao'.

    Input:  chunk_id — ex.: '8d755fc9-...-...:3'.
    Returns: o documento_id (a parte antes do último ':').
    """
    return chunk_id.rsplit(":", 1)[0]


def _dedup_ordenado(doc_ids: list[str]) -> list[str]:
    """Remove duplicatas preservando a ordem (mantém a 1ª/melhor ocorrência).

    Input:  doc_ids — lista de documento_id, melhor primeiro.
    Returns: mesma lista sem repetições.
    """
    vistos: set[str] = set()
    ordem: list[str] = []
    for d in doc_ids:
        if d not in vistos:
            vistos.add(d)
            ordem.append(d)
    return ordem


def reciprocal_rank_fusion(
    rankings: list[list[str]],
    k: int = RRF_K
) -> list[tuple[str, float]]:
    """Funde várias listas ranqueadas de documento_id via RRF.

    RRF: para cada documento, score = Σ 1/(k + rank) somado sobre cada ranking em
    que ele aparece (rank começa em 1). Combina rankings de canais diferentes sem
    depender da escala de score de cada um — só das posições.

    Input:  rankings — lista de rankings; cada ranking é uma lista de documento_id
            ordenada (melhor primeiro); k — constante de amortecimento.
    Returns: lista [(documento_id, score_rrf)] ordenada por score desc.
    """
    scores: dict[str, float] = {}
    for ranking in rankings:
        for posicao, doc_id in enumerate(ranking):
            scores[doc_id] = scores.get(doc_id, 0.0) + 1.0 / (k + posicao + 1)
    return sorted(scores.items(), key=lambda item: item[1], reverse=True)


@dataclass
class HybridSearch:
    """Orquestra os três canais de recuperação + RRF, no nível de documento."""

    embedder: PolyVectorEmbedder
    chroma: ChromaStore
    bm25: LoadedBM25

    def search(
        self,
        query: str,
        n_results: int = 20,
        where: dict | None = None,
    ) -> list[tuple[str, float]]:
        """Busca híbrida: vetorial (2 coleções) + lexical, fundidos por RRF.

        Input:  query — texto da busca; n_results — top-N documentos; where — filtro
                de metadados do Chroma (provimento/período — UC03/UC04), opcional.
        Returns: lista [(documento_id, score_rrf)] top-N, melhor primeiro.

        Nota: o `where` filtra as buscas do Chroma; o BM25 não filtra por metadados.
        Se um filtro rígido for necessário, aplique-o depois (no Doc Retriever, sobre
        o DocumentoJuridico recuperado).
        """
        n_cand = n_results * CANDIDATOS_POR_CANAL

        qv = self.embedder.embed_text(query)
        hits_completo = self.chroma.query(qv, n_results=n_cand, where=where, collection=COLLECTION_COMPLETO)
        hits_ementa = self.chroma.query(qv, n_results=n_cand, where=where, collection=COLLECTION_EMENTA)
        hits_bm25 = self.bm25.search(query, n=n_cand)

        # Projeta cada canal para uma lista ranqueada de documento_id, sem duplicar.
        r_completo = _dedup_ordenado([h["documento_id"] for h in hits_completo])
        r_ementa = _dedup_ordenado([h["documento_id"] for h in hits_ementa])
        r_bm25 = _dedup_ordenado([_doc_id_do_chunk(cid) for cid, _ in hits_bm25])

        fundidos = reciprocal_rank_fusion([r_completo, r_ementa, r_bm25])
        return fundidos[:n_results]
