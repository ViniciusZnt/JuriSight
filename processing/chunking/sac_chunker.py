"""
SAC Chunker (componente C4 — Pipeline de Ingestão / RFC §5.3 etapa 3, Decisão 3).

Summary-Augmented Chunking: usa a **ementa** do documento como resumo global (SAC
summary) e a injeta como prefixo de cada chunk do `acordao`. Isso ancora cada
fragmento à decisão específica de onde veio, eliminando confusão entre acórdãos
estruturalmente similares (mesmo tema, mesmo vocabulário).

NÃO usa LLM (baixo custo computacional — RFC §5.3 etapa 3). O chunking é puramente
textual: divide o `acordao` em janelas de 600–800 tokens e prefixa a ementa.

Entrada:  DocumentoJuridico (lido do PostgreSQL — source of truth).
Saída:    list[Chunk] pronta para o Poly-Vector Embedder e os indexadores.
"""
from __future__ import annotations

import uuid

from pydantic import BaseModel, Field

from scraper.schema import DocumentoJuridico

# Alvo de tamanho do chunk (RFC §5.2 / §5.3 — 600–800 tokens).
TARGET_TOKENS = 700
MIN_TOKENS = 600
MAX_TOKENS = 800
# Sobreposição entre chunks consecutivos para não cortar contexto no limite.
OVERLAP_TOKENS = 80


class Chunk(BaseModel):
    """Fragmento de um documento jurídico (RFC §5.2 — entidade `Chunk`).

    Os campos de metadado (tipo_documento, provimento, data_julgamento,
    numero_processo, hierarquia_categoria) são duplicados aqui para serem
    gravados no ChromaDB e permitir filtragem sem consultar o PostgreSQL.
    Os embeddings são preenchidos depois, pelo Poly-Vector Embedder.
    """

    chunk_id:     str = Field(default_factory=lambda: str(uuid.uuid4()))
    documento_id: str            # FK → documentos.id (UUID no PostgreSQL)
    texto:        str            # chunk do acordao COM o prefixo SAC (ementa)
    sac_summary:  str            # ementa usada como contexto global
    posicao:      int            # posição ordinal do chunk no documento

    # Metadados de filtragem (duplicados no ChromaDB)
    tipo_documento:       str
    provimento:           str
    data_julgamento:      str | None = None   # ISO 8601, p/ filtro por período
    numero_processo:      str = ""
    hierarquia_categoria: int = 0


def _count_tokens(text: str) -> int:
    """Conta tokens do texto.

    TODO: decidir a estratégia de contagem. Opções:
      - aproximação por whitespace (`len(text.split())`) — simples, sem dep;
      - tiktoken/transformers tokenizer — mais fiel ao limite real do modelo.
    O RFC fala em "600–800 tokens"; alinhar com o tokenizer do nomic-embed-text.
    """
    raise NotImplementedError


def _split_into_windows(texto: str) -> list[str]:
    """Divide um texto longo em janelas de ~TARGET_TOKENS com OVERLAP_TOKENS.

    TODO:
      - quebrar preferencialmente em fronteiras de sentença/parágrafo;
      - respeitar MIN/MAX_TOKENS;
      - aplicar sobreposição entre janelas consecutivas.
    """
    raise NotImplementedError


class SACChunker:
    """Divide o `acordao` em chunks e prefixa a ementa (SAC summary)."""

    def __init__(
        self,
        target_tokens: int = TARGET_TOKENS,
        overlap_tokens: int = OVERLAP_TOKENS,
    ) -> None:
        self.target_tokens = target_tokens
        self.overlap_tokens = overlap_tokens

    def chunk_document(self, doc: DocumentoJuridico, documento_id: str) -> list[Chunk]:
        """Gera os chunks de um documento.

        `documento_id` é o UUID `id` da linha no PostgreSQL (FK usada no ChromaDB,
        RFC §5.2) — NÃO confundir com `doc.id_documento` (chave natural do portal).

        Regras:
          - sac_summary = doc.ementa (se vazia, definir fallback — ver TODO);
          - corpo a fragmentar = doc.acordao; para docs curtos (súmula/OJ) sem
            acordao, usar a própria ementa como chunk único;
          - cada chunk.texto = f"{sac_summary}\n\n{janela}" (prefixo SAC);
          - copiar metadados de filtragem de `doc` (tipo, provimento, datas...).

        TODO: implementar.
        """
        raise NotImplementedError
