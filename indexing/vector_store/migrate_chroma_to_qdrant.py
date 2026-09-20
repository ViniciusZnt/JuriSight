"""
Migração ChromaDB -> Qdrant (README §Escalabilidade).

Script ÚNICO USO: copia os vetores já embedados do Chroma persistente para o
Qdrant, SEM chamar a OpenAI de novo (os embeddings já existem — recomputá-los
custaria dinheiro e tempo à toa). É só leitura no Chroma; a base antiga nunca é
tocada/apagada por este script, então pode ser reexecutado ou abortado a
qualquer momento sem risco de perder dados.

Idempotente e resumível:
  - o id de cada ponto no Qdrant é determinístico (chunk_point_id() para
    chunks_completo; o próprio documento_id, já UUID, para chunks_ementa) —
    reexecutar uma faixa já migrada faz upsert, nunca duplica;
  - um checkpoint em disco grava o offset já migrado de cada coleção após cada
    lote confirmado, então uma migração interrompida (Ctrl+C, queda de energia,
    OOM) continua de onde parou em vez de reler tudo do zero — importante aqui
    porque só ABRIR o Chroma já é lento nesta máquina (I/O em HD físico).

Mantido no repositório como registro de como a migração foi feita (2026-09-13) e
para o caso raro de precisar reimportar de um backup antigo do Chroma. `chromadb`
não é mais dependência do projeto — para rodar este script de novo, instale-o
à parte: `uv pip install chromadb`.

Uso:
    uv run python indexing/vector_store/migrate_chroma_to_qdrant.py
    uv run python indexing/vector_store/migrate_chroma_to_qdrant.py --collection chunks_ementa   # só a menor, pra validar primeiro
    uv run python indexing/vector_store/migrate_chroma_to_qdrant.py --batch-size 200
    uv run python indexing/vector_store/migrate_chroma_to_qdrant.py --verify   # só compara as contagens, não migra nada
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import time
from pathlib import Path

import chromadb
from qdrant_client import QdrantClient, models

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv
load_dotenv(ROOT / ".env")

from indexing.vector_store.qdrant_store import (  # noqa: E402
    COLLECTION_COMPLETO,
    COLLECTION_EMENTA,
    EMBED_DIM,
    QdrantStore,
    chunk_point_id,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)
for _noisy in ("httpx", "httpcore", "urllib3"):
    logging.getLogger(_noisy).setLevel(logging.WARNING)

CHROMA_PERSIST_DIR = os.getenv("CHROMA_PERSIST_DIR", "~/.local/share/jurisight/chroma")
QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost:6333")
CHECKPOINT_PATH = Path(os.getenv("MIGRATION_CHECKPOINT_PATH", "./data/index/qdrant_migration_checkpoint.json"))

# Timeout generoso: nesta máquina (HD físico), operações do Qdrant sob I/O pesado
# podem levar bem mais que o timeout default do client.
_CLIENT_TIMEOUT_S = 120


def _load_checkpoint() -> dict:
    if CHECKPOINT_PATH.exists():
        return json.loads(CHECKPOINT_PATH.read_text())
    return {}


def _save_checkpoint(state: dict) -> None:
    CHECKPOINT_PATH.parent.mkdir(parents=True, exist_ok=True)
    CHECKPOINT_PATH.write_text(json.dumps(state, indent=2))


def _point_for_completo(chroma_id: str, embedding: list[float], metadata: dict) -> models.PointStruct:
    payload = dict(metadata)
    payload["chunk_id"] = chroma_id  # não vem no metadata do Chroma — é o próprio id do ponto lá
    return models.PointStruct(id=chunk_point_id(chroma_id), vector=embedding, payload=payload)


def _point_for_ementa(chroma_id: str, embedding: list[float], metadata: dict) -> models.PointStruct:
    payload = dict(metadata)
    payload["chunk_id"] = chroma_id
    return models.PointStruct(id=chroma_id, vector=embedding, payload=payload)  # já é o documento_id (UUID)


def migrate_collection(
    chroma_client: chromadb.ClientAPI,
    qdrant_client: QdrantClient,
    name: str,
    point_builder,
    batch_size: int,
) -> None:
    """Copia uma coleção inteira do Chroma para o Qdrant, em lotes, com checkpoint.

    Input:  chroma_client, qdrant_client; name — nome da coleção (igual nos dois
            bancos); point_builder — monta o PointStruct certo pro tipo de coleção
            (COMPLETO usa uuid5 do chunk_id, EMENTA usa o documento_id direto);
            batch_size — quantos pontos ler/escrever por vez.
    Returns: None. Efeito colateral: grava progresso em CHECKPOINT_PATH.
    """
    checkpoint = _load_checkpoint()
    offset = checkpoint.get(name, 0)

    logger.info("Abrindo coleção Chroma '%s' (pode levar minutos nesta máquina)...", name)
    t0 = time.monotonic()
    col = chroma_client.get_collection(name)
    total = col.count()
    logger.info("Coleção '%s' aberta em %.0fs — %d pontos no Chroma.", name, time.monotonic() - t0, total)

    if offset:
        logger.info("Retomando '%s' do checkpoint: offset=%d/%d.", name, offset, total)

    while offset < total:
        t_batch = time.monotonic()
        got = col.get(limit=batch_size, offset=offset, include=["embeddings", "metadatas"])
        ids = got["ids"]
        if not ids:
            break  # coleção mudou de tamanho por baixo do tapete — para com segurança

        points = [
            point_builder(cid, emb.tolist() if hasattr(emb, "tolist") else list(emb), meta or {})
            for cid, emb, meta in zip(ids, got["embeddings"], got["metadatas"])
        ]
        qdrant_client.upsert(collection_name=name, points=points)

        offset += len(ids)
        checkpoint[name] = offset
        _save_checkpoint(checkpoint)

        elapsed = time.monotonic() - t_batch
        logger.info(
            "[%s] %d/%d migrados (+%d neste lote, %.1fs, %.0f pontos/s).",
            name, offset, total, len(ids), elapsed, len(ids) / elapsed if elapsed > 0 else 0,
        )

    logger.info("Coleção '%s' migrada por completo: %d pontos.", name, offset)


def verify(chroma_client: chromadb.ClientAPI, qdrant_client: QdrantClient) -> None:
    """Compara as contagens Chroma vs Qdrant nas duas coleções, sem migrar nada."""
    for name in (COLLECTION_COMPLETO, COLLECTION_EMENTA):
        chroma_count = chroma_client.get_collection(name).count()
        qdrant_count = qdrant_client.count(name, exact=True).count if qdrant_client.collection_exists(name) else 0
        status = "OK" if chroma_count == qdrant_count else "DIVERGENTE"
        logger.info("[%s] Chroma=%d Qdrant=%d -> %s", name, chroma_count, qdrant_count, status)


def main() -> None:
    p = argparse.ArgumentParser(description="Migra os vetores já embedados do Chroma para o Qdrant.")
    p.add_argument("--collection", choices=[COLLECTION_COMPLETO, COLLECTION_EMENTA], default=None,
                   help="Migra só esta coleção (default: as duas — primeiro a ementa, menor, depois a completo).")
    p.add_argument("--batch-size", type=int, default=500, help="Pontos por lote de leitura/escrita (default 500).")
    p.add_argument("--verify", action="store_true", help="Só compara as contagens Chroma vs Qdrant; não migra nada.")
    args = p.parse_args()

    chroma_client = chromadb.PersistentClient(path=os.path.expanduser(CHROMA_PERSIST_DIR))
    qdrant_client = QdrantClient(url=QDRANT_URL, timeout=_CLIENT_TIMEOUT_S)

    if args.verify:
        verify(chroma_client, qdrant_client)
        return

    QdrantStore(qdrant_client)  # garante as coleções (vetores/HNSW em disco) antes de escrever

    # Ementa primeiro: 69k pontos (bem mais rápida) valida o caminho antes de encarar
    # os ~400k da completo.
    collections = [args.collection] if args.collection else [COLLECTION_EMENTA, COLLECTION_COMPLETO]
    builders = {COLLECTION_COMPLETO: _point_for_completo, COLLECTION_EMENTA: _point_for_ementa}

    for name in collections:
        migrate_collection(chroma_client, qdrant_client, name, builders[name], args.batch_size)

    logger.info("Migração concluída. Rode com --verify para conferir as contagens.")


if __name__ == "__main__":
    main()
