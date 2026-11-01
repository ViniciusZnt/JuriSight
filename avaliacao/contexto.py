"""Dependências reais do harness fora do FastAPI (CLIs do pacote `avaliacao`).

Monta o mesmo que o lifespan de query/api/app.py, menos o QueryEnricher:
os CLIs já têm a estrutura argumentativa pronta, então não precisam do Ollama.
"""
from __future__ import annotations

import os
from pathlib import Path
from types import SimpleNamespace

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent


def _database_url() -> str:
    load_dotenv(ROOT / ".env")
    url = os.getenv("DATABASE_URL")
    if not url:
        raise RuntimeError("DATABASE_URL não definida (veja o .env)")
    return url


def carregar_store():
    """Só o AvaliacaoStore (leve: não carrega BM25, embedder nem reranker)."""
    from avaliacao.db import ensure_schema
    from avaliacao.store import AvaliacaoStore

    url = _database_url()
    ensure_schema(url)
    return AvaliacaoStore(url)


def carregar_dependencias() -> SimpleNamespace:
    """Devolve SimpleNamespace(hybrid, retriever, reranker, store, database_url).

    Lento (BM25, embedder e reranker) — chame uma vez por processo.
    """
    url = _database_url()

    from qdrant_client import QdrantClient

    from indexing.lexical.bm25_builder import BM25Builder
    from indexing.vector_store.qdrant_store import QdrantStore
    from processing.embeddings.poly_vector import PolyVectorEmbedder
    from query.search.doc_retriever import DocRetriever
    from query.search.hybrid_search import HybridSearch
    from query.search.reranker import Reranker

    client = QdrantClient(url=os.getenv("QDRANT_URL", "http://localhost:6333"), timeout=210)
    hybrid = HybridSearch(PolyVectorEmbedder(), QdrantStore(client), BM25Builder.load())
    return SimpleNamespace(
        hybrid=hybrid,
        retriever=DocRetriever(url),
        reranker=Reranker(),
        store=carregar_store(),
        database_url=url,
    )
