"""
Ponto de entrada da Indexação.

Orquestra a metade inferior do C4 "Pipeline de Ingestão": lê os DocumentoJuridico
do PostgreSQL → SAC Chunker → Poly-Vector Embedder → ChromaDB + BM25 Builder.
Roda DEPOIS do scraper/run.py (que já populou o PostgreSQL).

Uso:
    uv run python indexing/run.py
    uv run python indexing/run.py --reset        # reindexa do zero (limpa Chroma/BM25)
    uv run python indexing/run.py --limit 50     # indexa só 50 documentos (teste)
    uv run python indexing/run.py --workers 12   # nº de embeddings concorrentes (default 12)
"""
from __future__ import annotations

import argparse
import logging
import os
import sys
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
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
# Silencia o ruído das libs HTTP (uma linha por chamada à OpenAI).
for _noisy in ("httpx", "httpcore", "urllib3"):
    logging.getLogger(_noisy).setLevel(logging.WARNING)

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://postgres:postgres@localhost:5432/jurisight",
)


def _embed_doc(chunks, embedder) -> tuple[list, list]:
    """Embeda os chunks de UM documento — a parte cara (chamadas à OpenAI).

    Roda em thread worker; NÃO toca no Chroma/BM25 (a escrita fica na thread
    principal). embedding_completo: um por chunk (batch numa chamada). embedding do
    resumo: o sac_summary é o mesmo em todos os chunks do doc, então embeda UMA vez e
    replica (súmula com sac vazio reusa o vetor do texto — zero chamada extra).

    Input:  chunks (todos de um mesmo documento); embedder.
    Returns: (emb_completo, emb_ementa) — vetores alinhados aos chunks.
    """
    emb_completo = embedder.embed_batch([c.texto for c in chunks])
    sac_summary = chunks[0].sac_summary
    resumo_vec = embedder.embed_text(sac_summary) if sac_summary else emb_completo[0]
    emb_ementa = [resumo_vec] * len(chunks)
    return emb_completo, emb_ementa


def main() -> None:
    parser = argparse.ArgumentParser(description="Indexa documentos do PostgreSQL no ChromaDB + BM25.")
    parser.add_argument("--reset", action="store_true", help="Limpa Chroma antes de indexar (força reindexação total).")
    parser.add_argument("--limit", type=int, default=None, help="Indexa no máximo N documentos (teste).")
    parser.add_argument("--workers", type=int, default=12,
                        help="Nº de embeddings concorrentes (default 12). O teto real é o limite de tokens/min da OpenAI.")
    parser.add_argument("--flush-docs", type=int, default=100,
                        help="Grava no Chroma a cada N docs (default 100). Em disco lento (HD) reduz fsyncs; em SSD pode baixar.")
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

    # Pool limitado: o embedding (I/O na OpenAI) roda em `workers` threads; a escrita
    # no Chroma fica só nesta thread (serializada, sem race). Mantemos no máx.
    # `workers * 3` futures em voo para não bufferizar os 69k docs na memória.
    workers = max(1, args.workers)
    # Fila em voo folgada (workers * 5): mantém os workers alimentados enquanto a thread
    # principal está ocupada num _flush() (escrita em lote), evitando que fiquem ociosos.
    max_inflight = workers * 5
    futures: dict = {}   # future -> (documento_id, chunks)

    # Buffer de escrita: no WSL2 sobre HD, cada add_chunks faz fsync (seek do disco) e
    # custa ~1,5s/doc. Acumulando ~flush_docs documentos por gravação, o write cai para
    # ~47ms/doc (33x). Custo: um crash perde no máx. `flush_docs` docs (o delta refaz).
    buf: dict = {"chunks": [], "ec": [], "ee": [], "docs": 0}

    def _flush() -> None:
        """Grava o buffer acumulado no Chroma numa única chamada (poucos fsyncs)."""
        if not buf["chunks"]:
            return
        chroma.add_chunks(buf["chunks"], buf["ec"], buf["ee"])
        buf["chunks"].clear(); buf["ec"].clear(); buf["ee"].clear()
        buf["docs"] = 0

    def _colher(fut) -> None:
        """Colhe um embedding pronto e o acumula no buffer de escrita (thread principal)."""
        nonlocal total_novos, total_falhas
        documento_id, chunks = futures.pop(fut)
        try:
            emb_completo, emb_ementa = fut.result()
        except Exception:
            # Uma falha de embedding não deve abortar uma indexação de 69k.
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
            try:
                chunks = chunker.chunk_document(doc, documento_id)
            except Exception:
                total_falhas += 1
                logger.exception("Falha ao chunkar documento %s — pulando.", documento_id)
                continue
            if not chunks:
                continue
            bm25.add(chunks)                      # sempre: BM25 precisa do corpus completo
            total_docs += 1
            total_chunks += len(chunks)

            if documento_id in ja_indexados:
                continue                          # delta: já no Chroma, pula o embedding

            futures[executor.submit(_embed_doc, chunks, embedder)] = (documento_id, chunks)
            # Buffer cheio: drena os que já terminaram antes de submeter mais.
            if len(futures) >= max_inflight:
                done, _ = wait(futures, return_when=FIRST_COMPLETED)
                for fut in done:
                    _colher(fut)

        # Drena o restante em voo e grava o que sobrou no buffer.
        for fut in list(futures):
            _colher(fut)
        _flush()

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
