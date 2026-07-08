"""
Poly-Vector Embedder.

Gera DOIS embeddings por chunk com `nomic-embed-text` via Ollama (local):
  - `embedding_completo`: do `chunk.texto` (janela + prefixo SAC) — contexto rico;
  - `embedding_ementa`:   do `chunk.sac_summary` (ementa/tese) — precisão jurídica.

Ambos são vetores de 768 dimensões. Na busca, os dois vetores são consultados
independentemente e os rankings fundidos via RRF (ver query/search/hybrid_search.py).
O embedding duplo melhora a recuperação de súmulas e OJs (texto curto, denso).

Não normalizamos os vetores aqui: o ChromaDB indexa com `hnsw:space=cosine`, que
já é invariante à magnitude — normalizar de novo seria redundante.
"""
from __future__ import annotations

import os

import ollama

from processing.chunking.sac_chunker import Chunk

EMBED_MODEL = os.getenv("OLLAMA_EMBED_MODEL")
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL")
EMBED_DIM = 768

Vector = list[float]


class PolyVectorEmbedder:
    """Cliente de embeddings sobre o Ollama local."""

    def __init__(self, model: str = EMBED_MODEL, base_url: str = OLLAMA_BASE_URL) -> None:
        self.model = model
        self._client = ollama.Client(host=base_url)

    def embed_text(self, text: str) -> Vector:
        """Embedda um único texto. Retorna vetor de EMBED_DIM dimensões."""
        if not text or not text.strip():
            raise ValueError("embed_text recebeu texto vazio.")
        return self.embed_batch([text])[0]

    def embed_batch(self, texts: list[str]) -> list[Vector]:
        """Embedda vários textos numa única chamada ."""
        if not texts:
            return []
        resp = self._client.embed(model=self.model, input=texts)
        vetores = resp["embeddings"]
        if len(vetores) != len(texts):
            raise RuntimeError(
                f"Ollama devolveu {len(vetores)} vetores para {len(texts)} textos."
            )
        for v in vetores:
            if len(v) != EMBED_DIM:
                raise RuntimeError(
                    f"Dimensão inesperada do embedding: {len(v)} (esperado {EMBED_DIM}). "
                )
        return vetores

    def embed_chunk(self, chunk: Chunk) -> tuple[Vector, Vector]:
        """Retorna (embedding_completo, embedding_ementa) de um chunk.

        - embedding_completo ← chunk.texto (janela + prefixo SAC);
        - embedding_ementa   ← chunk.sac_summary; quando vazio (súmulas/OJs, que
          não têm prefixo próprio), cai para chunk.texto para não embedar string
          vazia — nesse caso os dois vetores coincidem, o que é esperado.

        Os dois textos vão numa única chamada de batch (um round-trip só).
        """
        fonte_ementa = chunk.sac_summary or chunk.texto
        completo, ementa = self.embed_batch([chunk.texto, fonte_ementa])
        return completo, ementa
