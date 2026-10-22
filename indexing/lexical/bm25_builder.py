"""
BM25 Builder

Constrói o índice lexical a partir do campo `texto_bruto` (SEM o prefixo SAC) de
cada chunk e o persiste em disco. Garante precisão em termos jurídicos exatos —
"NR-15", "CLT art. 193", "LTCAT", "benzeno" — que embeddings aproximam mas não
casam literalmente. O Backend carrega esse índice para a busca lexical, fundida
com a vetorial via RRF.

Via `bm25s` (matriz esparsa CSC do scipy), não `rank_bm25` (que guardava um dict
Python por DOCUMENTO — para ~400k chunks isso media ~6-7GB de RAM no processo do
backend, a causa raiz de buscas levando 80-125s medida nesta infra: a máquina
tem só 11GB de RAM total, e esse footprint sozinho já empurrava o sistema pra
swap, competindo por I/O de disco com o próprio Qdrant). `bm25s` permite carregar
o índice via `mmap=True`: os arrays da matriz ficam em disco, paginados sob
demanda pelo SO — igual ao que o Qdrant já faz com os vetores — então o processo
do backend passa a usar só dezenas de MB pro BM25 em vez de gigabytes.

Mantém um array paralelo ao corpus:
  - chunk_ids (bm25s indexa por posição inteira; nosso `search()` traduz de
    volta pro chunk_id usando esse array, passado como `corpus=` ao `retrieve()`).
"""
from __future__ import annotations

import json
import os
import re
import unicodedata
from pathlib import Path

import bm25s
from stop_words import get_stop_words

from processing.chunking.sac_chunker import Chunk

BM25_INDEX_PATH = Path(os.getenv("BM25_INDEX_PATH", "./data/index/bm25s_index"))
_CHUNK_IDS_FILENAME = "chunk_ids.json"


def _strip_accents(text: str) -> str:
    """Minúsculas e sem acento (base comum do tokenizer e das stopwords).

    Input:  text.
    Returns: texto em minúsculas, sem diacríticos.
    """
    text = text.lower()
    text = unicodedata.normalize("NFKD", text)
    return "".join(ch for ch in text if not unicodedata.combining(ch))


# Stopwords em português (lib stop-words), normalizadas para casar com os tokens.
# Removidas do índice porque o IDF já as neutralizaria — tirá-las só o encolhe.
# "nao" é mantido de propósito: a negação pode ser relevante como termo de busca.
STOPWORDS: frozenset[str] = frozenset(
    _strip_accents(w) for w in get_stop_words("portuguese")
) - {"nao"}


def _tokenize(text: str) -> list[str]:
    """Tokeniza texto para o BM25 (mesma função no índice e na query).

    Minúsculas, sem acento, tokens alfanuméricos e sem stopwords: "CLT art. 193"
    → ["clt", "art", "193"]; "NR-15 e a norma" → ["nr", "15", "norma"]. Precisa
    ser idêntica dos dois lados (índice e busca), senão o recall cai.

    Sem stemming nem lematização, de propósito: o BM25 serve para termos exatos e
    o canal denso cobre as variações de forma (decisão "BM25 sem tratamento de
    NLP" em docs/superpowers/specs/2026-10-21-inventario-e-plano-design.md).

    Input:  text — texto a tokenizar.
    Returns: lista de tokens normalizados, sem stopwords.
    """
    tokens = re.findall(r"[a-z0-9]+", _strip_accents(text))
    return [t for t in tokens if t not in STOPWORDS]


class BM25Builder:
    """Constrói e persiste o índice lexical dos chunks."""

    def __init__(self, index_path: Path = BM25_INDEX_PATH) -> None:
        """Inicializa os arrays paralelos do corpus.

        Input:  index_path — diretório onde o índice será persistido.
        Returns: None.
        """
        self.index_path = index_path
        self._corpus_tokens: list[list[str]] = []
        self._chunk_ids: list[str] = []

    def add(self, chunks: list[Chunk]) -> None:
        """Acumula chunks no corpus (tokeniza texto_bruto e guarda chunk_id).

        Input:  chunks — lote de chunks a indexar.
        Returns: None (estende _corpus_tokens e _chunk_ids em paralelo).
        """
        for c in chunks:
            self._corpus_tokens.append(_tokenize(c.texto_bruto))
            self._chunk_ids.append(c.chunk_id)

    def build_and_save(self) -> None:
        """Constrói o índice bm25s sobre o corpus e persiste em self.index_path.

        Input:  nenhum (usa o corpus acumulado por add()).
        Returns: None. Grava os arrays da matriz CSC + vocabulário (bm25s.save)
        e, à parte, chunk_ids.json (o mapeamento posição → chunk_id que o bm25s
        não sabe persistir sozinho).
        """
        # TODO (delta): reconstrói do corpus inteiro, não é incremental — igual
        #   à limitação já documentada quando isto usava rank_bm25.
        if not self._corpus_tokens:
            raise ValueError("Corpus vazio: chame add() antes de build_and_save().")
        retriever = bm25s.BM25()
        retriever.index(self._corpus_tokens)
        self.index_path.mkdir(parents=True, exist_ok=True)
        retriever.save(str(self.index_path))
        with open(self.index_path / _CHUNK_IDS_FILENAME, "w") as f:
            json.dump(self._chunk_ids, f)

    @staticmethod
    def load(index_path: Path = BM25_INDEX_PATH) -> "LoadedBM25":
        """Carrega o índice persistido para uso na busca (lado do Backend).

        `mmap=True`: os arrays da matriz ficam em disco (mmap), paginados sob
        demanda — não carrega o corpus inteiro pra RAM na subida (era o ponto
        inteiro desta troca, ver docstring do módulo).

        Input:  index_path — diretório do índice.
        Returns: um LoadedBM25 pronto para consulta.
        """
        retriever = bm25s.BM25.load(str(index_path), mmap=True, load_corpus=False, show_progress=False)
        with open(index_path / _CHUNK_IDS_FILENAME) as f:
            chunk_ids = json.load(f)
        return LoadedBM25(retriever, chunk_ids)


class LoadedBM25:
    """Índice BM25 carregado (mmap), pronto para consulta (usado na busca).

    Vive aqui por proximidade com o builder, mas é consumido por
    query/search/hybrid_search.py.
    """

    def __init__(self, retriever: bm25s.BM25, chunk_ids: list[str]) -> None:
        """Guarda o índice e o mapeamento posição → chunk_id.

        Input:  retriever — bm25s.BM25 carregado; chunk_ids — ids na ordem do corpus
                (mesma ordem usada na indexação — bm25s indexa por posição inteira).
        Returns: None.
        """
        self._retriever = retriever
        self._chunk_ids = chunk_ids

    def search(self, query: str, n: int = 20) -> list[tuple[str, float]]:
        """Busca lexical: pontua a query contra o corpus e devolve os top-n.

        Input:  query — texto da busca; n — quantos resultados.
        Returns: lista [(chunk_id, score)] ordenada por score desc.
        """
        tokens = _tokenize(query)
        if not tokens or not self._chunk_ids:
            return []
        n = min(n, len(self._chunk_ids))
        # corpus=self._chunk_ids: o bm25s devolve o chunk_id diretamente (em vez
        # do índice numérico interno), então não precisamos traduzir na mão.
        resultado = self._retriever.retrieve(
            [tokens], corpus=self._chunk_ids, k=n, show_progress=False
        )
        docs, scores = resultado.documents[0], resultado.scores[0]
        return [(docs[i], float(scores[i])) for i in range(len(docs))]
