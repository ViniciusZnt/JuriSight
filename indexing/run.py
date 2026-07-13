"""
Ponto de entrada da Indexação (RFC §5.3 etapa 5 — M3).

Orquestra a metade inferior do C4 "Pipeline de Ingestão": lê os DocumentoJuridico
do PostgreSQL → SAC Chunker → Poly-Vector Embedder → ChromaDB + BM25 Builder.
Roda DEPOIS do scraper/run.py (que já populou o PostgreSQL).

Uso:
    uv run python indexing/run.py
    uv run python indexing/run.py --reset       # reindexa do zero (limpa Chroma/BM25)
    uv run python indexing/run.py --limit 50    # indexa só 50 documentos (teste)
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


def _embed_e_grava(chunks, embedder, chroma) -> None:
    """Embeda os chunks e grava no ChromaDB — a parte cara (chamadas ao Ollama).

    embedding_completo: um por chunk (batch numa chamada). embedding do resumo: o
    sac_summary é o mesmo em todos os chunks do doc, então embeda UMA vez e replica
    (súmula com sac vazio reusa o vetor do texto — zero chamada extra).

    Input:  chunks (todos de um mesmo documento); embedder; chroma.
    Returns: None.
    """
    emb_completo = embedder.embed_batch([c.texto for c in chunks])
    sac_summary = chunks[0].sac_summary
    resumo_vec = embedder.embed_text(sac_summary) if sac_summary else emb_completo[0]
    emb_ementa = [resumo_vec] * len(chunks)
    chroma.add_chunks(chunks, emb_completo, emb_ementa)


def main() -> None:
    parser = argparse.ArgumentParser(description="Indexa documentos do PostgreSQL no ChromaDB + BM25.")
    parser.add_argument("--reset", action="store_true", help="Limpa Chroma antes de indexar (força reindexação total).")
    parser.add_argument("--limit", type=int, default=None, help="Indexa no máximo N documentos (teste).")
    args = parser.parse_args()

    source = DocumentSource(DATABASE_URL)
    chunker = SACChunker()
    embedder = PolyVectorEmbedder()
    chroma = ChromaStore()
    bm25 = BM25Builder()

    if args.reset:
        logger.info("Reset: limpando coleções do ChromaDB.")
        chroma.reset()

    # Delta: documentos já no Chroma pulam o embedding (o caro). O BM25 NÃO é
    # incremental, então todo chunk ainda é re-tokenizado (barato) para reconstruir
    # o corpus — só o embedding + upsert dos já-indexados é que são evitados.
    ja_indexados = chroma.documento_ids_indexados()
    if ja_indexados:
        logger.info("Delta: %d documentos já indexados — só os novos serão embedados.", len(ja_indexados))

    total_docs = total_chunks = total_novos = total_falhas = 0

    for i, (documento_id, doc) in enumerate(source.iter_documents()):
        if args.limit is not None and i >= args.limit:
            break
        try:
            chunks = chunker.chunk_document(doc, documento_id)
            if not chunks:
                continue
            bm25.add(chunks)                      # sempre: BM25 precisa do corpus completo
            total_docs += 1
            total_chunks += len(chunks)

            if documento_id in ja_indexados:
                continue                          # delta: já no Chroma, pula o embedding
            _embed_e_grava(chunks, embedder, chroma)
            total_novos += 1
            if total_novos % 100 == 0:
                logger.info("  ... %d novos documentos embedados", total_novos)
        except Exception:
            # Um documento problemático não deve abortar uma indexação de 54k.
            total_falhas += 1
            logger.exception("Falha ao indexar documento %s — pulando.", documento_id)

    # BM25 é reconstruído do corpus inteiro (não incremental); só salva se há chunks.
    if total_chunks:
        bm25.build_and_save()
        logger.info("Índice BM25 salvo em %s", bm25.index_path)
    else:
        logger.warning("Nenhum chunk indexado — BM25 não foi construído.")

    logger.info(
        "Indexação concluída: %d documentos (%d novos embedados), %d chunks, %d falhas.",
        total_docs, total_novos, total_chunks, total_falhas,
    )


if __name__ == "__main__":
    main()
