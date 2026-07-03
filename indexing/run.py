"""
Ponto de entrada da Indexação (RFC §5.3 etapa 5 — M3).

Orquestra a metade inferior do C4 "Pipeline de Ingestão": lê os DocumentoJuridico
do PostgreSQL → SAC Chunker → Poly-Vector Embedder → ChromaDB + BM25 Builder.
Roda DEPOIS do scraper/run.py (que já populou o PostgreSQL).

Uso:
    uv run python indexing/run.py
    uv run python indexing/run.py --reset      # reindexa do zero (limpa Chroma/BM25)
"""
from __future__ import annotations

import argparse
import logging
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv
load_dotenv(ROOT / ".env")

from indexing.doc_source import DocumentSource
from indexing.lexical.bm25_builder import BM25Builder
from indexing.vector_store.chroma_store import ChromaStore
from processing.chunking.sac_chunker import SACChunker
from processing.embeddings.poly_vector import PolyVectorEmbedder

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://postgres:postgres@localhost:5432/jurisight",
)


def main() -> None:
    parser = argparse.ArgumentParser(description="Indexa documentos do PostgreSQL no ChromaDB + BM25.")
    parser.add_argument("--reset", action="store_true", help="Limpa Chroma e BM25 antes de indexar.")
    args = parser.parse_args()

    source = DocumentSource(DATABASE_URL)
    chunker = SACChunker()
    embedder = PolyVectorEmbedder()
    chroma = ChromaStore()
    bm25 = BM25Builder()

    if args.reset:
        chroma.reset()

    total_docs = total_chunks = 0

    # Pipeline por documento:
    #   1. ler (uuid, doc) do PostgreSQL
    #   2. chunks = chunker.chunk_document(doc, documento_id=uuid)
    #   3. para o lote de chunks: emb_completo, emb_ementa = embedder...
    #   4. chroma.add_chunks(chunks, emb_completo, emb_ementa)
    #   5. bm25.add(chunks)
    # Ao final: bm25.build_and_save()
    #
    # TODO: implementar o loop. Considerar processar em lotes para amortizar
    #       a chamada de embeddings e o upsert no Chroma.
    for documento_id, doc in source.iter_documents():
        raise NotImplementedError  # remover ao implementar o corpo acima

    bm25.build_and_save()

    logger.info("Indexação concluída: %d documentos, %d chunks.", total_docs, total_chunks)


if __name__ == "__main__":
    main()
