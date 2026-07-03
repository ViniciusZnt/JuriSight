"""
BM25 Builder (componente C4 — Pipeline de Ingestão / RFC §5.3 etapa 5, Decisão 2).

Constrói o índice lexical (rank_bm25) a partir do campo `texto` de cada chunk e o
persiste em disco (JSON/pickle). Garante precisão em termos jurídicos exatos —
"NR-15", "CLT art. 193", "LTCAT", "benzeno" — que embeddings podem aproximar mas
não casar literalmente. O Backend carrega esse índice em memória para a busca
lexical, depois fundida com a vetorial via RRF (ver query/search/hybrid_search.py).

Mantém DOIS arrays paralelos ao corpus:
  - tokens por documento (entrada do BM25Okapi);
  - chunk_ids correspondentes (para mapear rank → chunk).
"""
from __future__ import annotations

import os
import pickle
from pathlib import Path

from rank_bm25 import BM25Okapi

from processing.chunking.sac_chunker import Chunk

BM25_INDEX_PATH = Path(os.getenv("BM25_INDEX_PATH", "./data/index/bm25.pkl"))


def _tokenize(text: str) -> list[str]:
    """Tokeniza para BM25.

    TODO: decidir normalização — minúsculas, remoção de acento, preservação de
    tokens jurídicos ("nr-15", "art.", números). Deve ser a MESMA tokenização
    aplicada na query em tempo de busca, senão o recall cai.
    """
    raise NotImplementedError


class BM25Builder:
    """Constrói e persiste o índice lexical dos chunks."""

    def __init__(self, index_path: Path = BM25_INDEX_PATH) -> None:
        self.index_path = index_path
        self._corpus_tokens: list[list[str]] = []
        self._chunk_ids: list[str] = []

    def add(self, chunks: list[Chunk]) -> None:
        """Acumula chunks no corpus (tokeniza chunk.texto e guarda chunk_id).

        TODO: estender _corpus_tokens e _chunk_ids em paralelo.
        """
        raise NotImplementedError

    def build_and_save(self) -> None:
        """Constrói o BM25Okapi sobre o corpus e serializa para self.index_path.

        Persistir juntos: o objeto BM25, o corpus tokenizado e os chunk_ids.
        TODO: criar diretório pai, montar BM25Okapi(self._corpus_tokens), pickle.dump.
        """
        raise NotImplementedError

    @staticmethod
    def load(index_path: Path = BM25_INDEX_PATH) -> "LoadedBM25":
        """Carrega o índice persistido para uso na busca (lado do Backend).

        TODO: pickle.load e devolver um LoadedBM25.
        """
        raise NotImplementedError


class LoadedBM25:
    """Índice BM25 carregado em memória, pronto para consulta (usado na busca).

    Vive aqui por proximidade com o builder, mas é consumido por
    query/search/hybrid_search.py.
    """

    def __init__(self, bm25: BM25Okapi, chunk_ids: list[str]) -> None:
        self._bm25 = bm25
        self._chunk_ids = chunk_ids

    def search(self, query: str, n: int = 20) -> list[tuple[str, float]]:
        """Retorna [(chunk_id, score)] dos top-n para a query.

        TODO: tokenizar a query com _tokenize, get_scores, argsort desc, top-n.
        """
        raise NotImplementedError
