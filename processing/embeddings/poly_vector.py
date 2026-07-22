"""
Poly-Vector Embedder.

Gera DOIS embeddings por chunk com `text-embedding-3-small` (OpenAI):
  - `embedding_completo`: do `chunk.texto` (janela + prefixo SAC);
  - `embedding_ementa`:   do `chunk.sac_summary` (ementa/tese) — precisão jurídica.

Vetores de 1536 dimensões, já L2-normalizados pela API (cosseno ≈ produto interno).
Na busca, os dois vetores são consultados independentemente e fundidos via RRF.

Requer OPENAI_API_KEY no ambiente (carregado do .env pelos pontos de entrada).
A MESMA função embeda documentos e queries — o custo por query é desprezível
(~centenas de tokens); o gasto real é a indexação única do corpus.
"""
from __future__ import annotations
import os

from openai import OpenAI

from processing.chunking.sac_chunker import Chunk

EMBED_MODEL = os.getenv("OPENAI_EMBED_MODEL", "text-embedding-3-small")
EMBED_DIM = 1536

Vector = list[float]


class PolyVectorEmbedder:
    """Cliente de embeddings sobre a API da OpenAI."""

    def __init__(self, model: str = EMBED_MODEL, client: OpenAI | None = None) -> None:
        """Monta o cliente OpenAI.

        Input:  model — modelo de embedding; client — cliente OpenAI (injeta nos testes).
        Returns: None.
        """
        self.model = model
        # max_retries alto: sob concorrência, bursts encostam no limite de 1M TPM (Tier 1)
        # e a API responde 429; o SDK respeita o retry-after e espera a janela reabrir.
        self._client = client or OpenAI(max_retries=8)  # lê OPENAI_API_KEY do ambiente

    def embed_text(self, text: str) -> Vector:
        """Embedda um único texto.

        Input:  text — texto não vazio.
        Returns: vetor de EMBED_DIM dimensões.
        """
        if not text or not text.strip():
            raise ValueError("embed_text recebeu texto vazio.")
        return self.embed_batch([text])[0]

    def embed_batch(self, texts: list[str]) -> list[Vector]:
        """Embedda vários textos numa única chamada (batch nativo da API).

        Input:  texts — lista de textos não vazios.
        Returns: lista de vetores na mesma ordem dos textos; valida a dimensão.
        """
        if not texts:
            return []
        resp = self._client.embeddings.create(model=self.model, input=texts)
        # A API pode devolver fora de ordem; reordena por .index para alinhar com texts.
        data = sorted(resp.data, key=lambda d: d.index)
        vetores = [d.embedding for d in data]
        for v in vetores:
            if len(v) != EMBED_DIM:
                raise RuntimeError(
                    f"Dimensão inesperada do embedding: {len(v)} (esperado {EMBED_DIM})."
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
