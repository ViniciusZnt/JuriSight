"""
Ponto de entrada da Indexação.

Orquestra a metade inferior do C4 "Pipeline de Ingestão": lê os DocumentoJuridico
do PostgreSQL → SAC Chunker → Poly-Vector Embedder → ChromaDB + BM25 Builder.
Roda DEPOIS do scraper/run.py.

Uso:
    uv run python indexing/run.py
    uv run python indexing/run.py --reset        # reindexa do zero (limpa Chroma/BM25)
    uv run python indexing/run.py --limit 50     # indexa só 50 documentos (teste)
    uv run python indexing/run.py --workers 6    # nº de embeddings concorrentes (default 6)
"""
from __future__ import annotations

import argparse
import logging
import os
import sys
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from pathlib import Path
import chromadb

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
# Silencia o ruído das libs HTTP e os retries da OpenAI (os erros reais seguem logados).
for _noisy in ("httpx", "httpcore", "urllib3", "openai"):
    logging.getLogger(_noisy).setLevel(logging.WARNING)

DATABASE_URL = os.getenv("DATABASE_URL")
CHROMA_PERSIST_DIR = os.getenv("CHROMA_PERSIST_DIR")


def _embed_doc(chunks, embedder) -> tuple[list, list]:
    """Embeda os chunks de UM documento (a parte cara: chamadas à OpenAI).

    Roda em thread worker, sem tocar no Chroma/BM25. O sac_summary é igual em todos os
    chunks do doc: embeda uma vez e replica (sac vazio reusa o vetor do próprio texto).

    Input:  chunks (de um mesmo documento); embedder.
    Returns: (emb_completo, emb_ementa) — vetores alinhados aos chunks.
    """
    emb_completo = embedder.embed_batch([c.texto for c in chunks])
    sac_summary = chunks[0].sac_summary
    resumo_vec = embedder.embed_text(sac_summary) if sac_summary else emb_completo[0]
    return emb_completo, [resumo_vec] * len(chunks)


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Indexa documentos do PostgreSQL no ChromaDB + BM25.")
    p.add_argument("--reset", action="store_true", help="Limpa Chroma antes de indexar (reindexação total).")
    p.add_argument("--limit", type=int, default=None, help="Indexa no máximo N documentos (teste).")
    p.add_argument("--workers", type=int, default=6,
                   help="Embeddings concorrentes (default 6). Teto real = TPM da OpenAI; acima disso só gera 429.")
    p.add_argument("--flush-docs", type=int, default=100,
                   help="Grava no Chroma a cada N docs (default 100). Reduz fsyncs em disco lento.")
    p.add_argument("--no-bm25", action="store_true",
                   help="Não constrói o BM25 (economiza ~5-7GB de RAM). Construa-o à parte depois.")
    return p.parse_args()


def main() -> None:
    args = _parse_args()

    client = chromadb.PersistentClient(path=os.path.expanduser(CHROMA_PERSIST_DIR))
    source = DocumentSource(DATABASE_URL)
    chunker = SACChunker()
    embedder = PolyVectorEmbedder()
    chroma = ChromaStore(client)
    bm25 = BM25Builder()

    if args.reset:
        logger.info("Reset: limpando coleções do ChromaDB.")
        chroma.reset()

    # Delta: docs já no Chroma pulam o embedding (a parte cara). Com --no-bm25 são pulados
    # antes de chunkar; sem, ainda são re-tokenizados para reconstruir o corpus do BM25.
    ja_indexados = chroma.documento_ids_indexados()
    if ja_indexados:
        logger.info("Delta: %d documentos já indexados — só os novos serão embedados.", len(ja_indexados))

    total_docs = total_chunks = total_novos = total_falhas = 0

    # Embedding (I/O na OpenAI) roda em `workers` threads; a escrita no Chroma fica só nesta
    # thread. Buffer acumula flush_docs docs por gravação para cortar fsyncs em disco lento.
    workers = max(1, args.workers)
    max_inflight = workers * 5
    futures: dict = {}   # future -> (documento_id, chunks)
    buf: dict = {"chunks": [], "ec": [], "ee": [], "docs": 0}

    def _flush() -> None:
        if not buf["chunks"]:
            return
        chroma.add_chunks(buf["chunks"], buf["ec"], buf["ee"])
        buf["chunks"].clear(); buf["ec"].clear(); buf["ee"].clear()
        buf["docs"] = 0

    def _colher(fut) -> None:
        nonlocal total_novos, total_falhas
        documento_id, chunks = futures.pop(fut)
        try:
            emb_completo, emb_ementa = fut.result()
        except Exception:
            total_falhas += 1
            logger.exception("Falha ao embedar documento %s — pulando.", documento_id)
            return
        buf["chunks"].extend(chunks)
        buf["ec"].extend(emb_completo)
        buf["ee"].extend(emb_ementa)
        buf["docs"] += 1
        total_novos += 1
        if total_novos % 25 == 0:
            logger.info("  ... %d novos documentos embedados", total_novos)
        if buf["docs"] >= args.flush_docs:
            _flush()

    with ThreadPoolExecutor(max_workers=workers) as executor:
        for i, (documento_id, doc) in enumerate(source.iter_documents()):
            if args.limit is not None and i >= args.limit:
                break

            ja_feito = documento_id in ja_indexados
            if ja_feito and args.no_bm25:         # já indexado e sem BM25: nada a fazer
                continue

            try:
                chunks = chunker.chunk_document(doc, documento_id)
            except Exception:
                total_falhas += 1
                logger.exception("Falha ao chunkar documento %s — pulando.", documento_id)
                continue
            if not chunks:
                continue

            if not args.no_bm25:
                bm25.add(chunks)
            total_docs += 1
            total_chunks += len(chunks)

            if ja_feito:
                continue                          # delta: já no Chroma, pula o embedding

            futures[executor.submit(_embed_doc, chunks, embedder)] = (documento_id, chunks)
            if len(futures) >= max_inflight:      # fila cheia: drena os prontos antes de submeter
                done, _ = wait(futures, return_when=FIRST_COMPLETED)
                for fut in done:
                    _colher(fut)

        for fut in list(futures):                 # drena o restante em voo
            _colher(fut)
        _flush()

    if args.no_bm25:
        logger.info("BM25 pulado (--no-bm25). Construa-o à parte depois.")
    elif total_chunks:
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
