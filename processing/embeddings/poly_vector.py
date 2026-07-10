"""
Poly-Vector Embedder.

Gera DOIS embeddings por chunk com `nomic-embed-text` via Ollama (local):
  - `embedding_completo`: do `chunk.texto` (janela + prefixo SAC);
  - `embedding_ementa`:   do `chunk.sac_summary` (ementa/tese) — precisão jurídica.

Ambos são vetores de 768 dimensões. Na busca, os dois vetores são consultados
independentemente e os rankings fundidos via RRF.
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
        """Monta o cliente Ollama.

        Input:  model — modelo de embedding; base_url — URL do servidor Ollama.
        Returns: None.
        """
        self.model = model
        self._client = ollama.Client(host=base_url)

    def embed_text(self, text: str) -> Vector:
        """Embedda um único texto.

        Input:  text — texto não vazio.
        Returns: vetor de EMBED_DIM dimensões.
        """
        if not text or not text.strip():
            raise ValueError("embed_text recebeu texto vazio.")
        return self.embed_batch([text])[0]

    def embed_batch(self, texts: list[str]) -> list[Vector]:
        """Embedda vários textos numa única chamada (batch nativo do Ollama).

        Input:  texts — lista de textos.
        Returns: lista de vetores (mesma ordem); valida contagem e dimensão.
        """
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
        """Gera os dois embeddings Poly-Vector de um chunk.

        Input:  chunk — Chunk a embedar.
        Returns: (embedding_completo ← chunk.texto, embedding_ementa ← chunk.sac_summary).
        """
        # sac_summary vazio (súmulas/OJs) → usa o texto para não embedar string vazia.
        fonte_ementa = chunk.sac_summary or chunk.texto
        completo, ementa = self.embed_batch([chunk.texto, fonte_ementa])
        return completo, ementa
