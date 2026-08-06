"""
BM25 Builder

Constrói o índice lexical a partir do campo `texto_bruto`(SEM o prefixo SAC) de cada chunk e o
persiste em disco (pickle). Garante precisão em termos jurídicos exatos — "NR-15", "CLT art. 193",
"LTCAT", "benzeno" — que embeddings aproximam mas não casam literalmente. O Backendcarrega esse índice
em memória para a busca lexical, fundida com a vetorial via RRF.

Mantém DOIS arrays paralelos ao corpus:
  - tokens por documento (entrada do BM25Okapi);
  - chunk_ids correspondentes (para mapear rank → chunk).
"""
from __future__ import annotations

import os
import pickle
import re
import unicodedata
from pathlib import Path

from rank_bm25 import BM25Okapi
from stop_words import get_stop_words

from processing.chunking.sac_chunker import Chunk

BM25_INDEX_PATH = Path(os.getenv("BM25_INDEX_PATH", "./data/index/bm25.pkl"))


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

    Input:  text — texto a tokenizar.
    Returns: lista de tokens normalizados, sem stopwords.
    """
    tokens = re.findall(r"[a-z0-9]+", _strip_accents(text))
    return [t for t in tokens if t not in STOPWORDS]


def _validar_indice(path: Path, esperado: int) -> None:
    """Reabre um índice recém-escrito e confere que carrega íntegro.

    Input:  path — arquivo a validar; esperado — nº de chunk_ids esperado.
    Returns: None. Levanta RuntimeError se o pickle não carrega ou vem incompleto.
    """
    try:
        with open(path, "rb") as f:
            data = pickle.load(f)
    except Exception as e:
        raise RuntimeError(
            f"Índice BM25 em {path} corrompido/truncado (não carregou): {e}"
        ) from e
    n = len(data.get("chunk_ids", []))
    if n != esperado:
        raise RuntimeError(
            f"Índice BM25 em {path} incompleto: {n} chunk_ids, esperava {esperado}."
        )


class BM25Builder:
    """Constrói e persiste o índice lexical dos chunks."""

    def __init__(self, index_path: Path = BM25_INDEX_PATH) -> None:
        """Inicializa os arrays paralelos do corpus.

        Input:  index_path — caminho do índice serializado.
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
        """Constrói o BM25Okapi sobre o corpus e serializa para self.index_path.

        Input:  nenhum (usa o corpus acumulado por add()).
        Returns: None. Grava (de forma atômica e validada) um pickle {bm25, chunk_ids}.
        """
        # TODO (delta): o BM25Okapi não é incremental — reconstrói do corpus inteiro.
        #   Para indexação delta sem re-chunkar tudo, persistir também o corpus
        #   tokenizado e, no delta, carregar + adicionar/remover só o que mudou.
        if not self._corpus_tokens:
            raise ValueError("Corpus vazio: chame add() antes de build_and_save().")
        esperado = len(self._chunk_ids)
        bm25 = BM25Okapi(self._corpus_tokens)
        # O BM25Okapi já derivou doc_freqs/idf/doc_len e NÃO guarda o corpus cru.
        # Liberamos os ~vários GB de tokens ANTES do dump (o momento de pico de RAM),
        # não depois — foi aqui que estourava a memória na base de ~400k chunks.
        self._corpus_tokens = []
        self.index_path.parent.mkdir(parents=True, exist_ok=True)

        # Escrita atômica: grava num .tmp, valida que recarrega e só então troca pelo
        # arquivo final (os.replace é atômico no mesmo filesystem). Um crash/OOM no
        # meio do dump deixa o índice anterior intacto, em vez de sobrescrevê-lo com
        # um pickle truncado (que só falha na hora de carregar, lá na frente).
        tmp = self.index_path.with_name(self.index_path.name + ".tmp")
        try:
            with open(tmp, "wb") as f:
                pickle.dump({"bm25": bm25, "chunk_ids": self._chunk_ids}, f)
                f.flush()
                os.fsync(f.fileno())      # garante que os bytes chegaram ao disco
            del bm25                       # libera antes do reload de validação
            _validar_indice(tmp, esperado)
            os.replace(tmp, self.index_path)
        except BaseException:
            tmp.unlink(missing_ok=True)    # não deixa .tmp truncado pra trás
            raise

    @staticmethod
    def load(index_path: Path = BM25_INDEX_PATH) -> "LoadedBM25":
        """Carrega o índice persistido para uso na busca (lado do Backend).

        Input:  index_path — caminho do índice.
        Returns: um LoadedBM25 pronto para consulta.
        """
        with open(index_path, "rb") as f:
            data = pickle.load(f)
        return LoadedBM25(data["bm25"], data["chunk_ids"])


class LoadedBM25:
    """Índice BM25 carregado em memória, pronto para consulta (usado na busca).

    Vive aqui por proximidade com o builder, mas é consumido por
    query/search/hybrid_search.py.
    """

    def __init__(self, bm25: BM25Okapi, chunk_ids: list[str]) -> None:
        """Guarda o índice e o mapeamento posição → chunk_id.

        Input:  bm25 — BM25Okapi treinado; chunk_ids — ids na ordem do corpus.
        Returns: None.
        """
        self._bm25 = bm25
        self._chunk_ids = chunk_ids

    def search(self, query: str, n: int = 20) -> list[tuple[str, float]]:
        """Busca lexical: pontua a query contra o corpus e devolve os top-n.

        Input:  query — texto da busca; n — quantos resultados.
        Returns: lista [(chunk_id, score)] ordenada por score desc.
        """
        tokens = _tokenize(query)
        if not tokens or not self._chunk_ids:
            return []
        scores = self._bm25.get_scores(tokens)
        ranked = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:n]
        return [(self._chunk_ids[i], float(scores[i])) for i in ranked]
