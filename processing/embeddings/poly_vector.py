"""
Poly-Vector Embedder (componente C4 — Pipeline de Ingestão / RFC §5.3 etapa 4, Decisão 8).

Gera DOIS embeddings por chunk com `nomic-embed-text-v2` via Ollama (local, RNF03):
  - `embedding_completo`: do `chunk.texto` (janela + prefixo SAC) — contexto rico;
  - `embedding_ementa`:   do `chunk.sac_summary` (ementa/tese) — precisão jurídica.

Ambos são vetores de 768 dimensões. Na busca, os dois vetores são consultados
independentemente e os rankings fundidos via RRF (ver query/search/hybrid_search.py).
O embedding duplo melhora a recuperação de súmulas e OJs (texto curto, denso).
"""
from __future__ import annotations

import os

import ollama

from processing.chunking.sac_chunker import Chunk

EMBED_MODEL = os.getenv("OLLAMA_EMBED_MODEL", "nomic-embed-text")
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
EMBED_DIM = 768

Vector = list[float]


class PolyVectorEmbedder:
    """Cliente de embeddings sobre o Ollama local."""

    def __init__(self, model: str = EMBED_MODEL, base_url: str = OLLAMA_BASE_URL) -> None:
        self.model = model
        self._client = ollama.Client(host=base_url)

    def embed_text(self, text: str) -> Vector:
        """Embedda um único texto. Retorna vetor de EMBED_DIM dimensões.

        TODO:
          - chamar self._client.embeddings(model=self.model, prompt=text);
          - normalizar (L2) se a estratégia de similaridade exigir;
          - validar que len(vetor) == EMBED_DIM.
        """
        raise NotImplementedError

    def embed_batch(self, texts: list[str]) -> list[Vector]:
        """Embedda vários textos. Considerar paralelismo/limite de carga local.

        TODO: implementar (loop sobre embed_text ou API de batch do Ollama).
        """
        raise NotImplementedError

    def embed_chunk(self, chunk: Chunk) -> tuple[Vector, Vector]:
        """Retorna (embedding_completo, embedding_ementa) de um chunk.

          embedding_completo ← chunk.texto
          embedding_ementa   ← chunk.sac_summary

        TODO: implementar usando embed_text/embed_batch.
        """
        raise NotImplementedError
