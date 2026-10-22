"""
CLI do provimento com o Jev. Subcomandos: `classificar` (backfill retomável),
`aplicar` (escreve o Jev em `documentos.provimento`, só com --confirmar) e
`sincronizar` (leva `documentos.provimento` ao Qdrant e ao provimentos.json do BM25).
Ver docs/superpowers/specs/2026-10-20-provimento-jev-design.md.

Uso: uv run python -m scraper.provimento_jev_cli classificar [--limite N] [--sim]
     uv run python -m scraper.provimento_jev_cli aplicar [--confianca-min 0.8] [--confirmar]
     uv run python -m scraper.provimento_jev_cli sincronizar [--lote 1000] [--so-bm25] [--so-qdrant]
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from typesafe_sdk import TypeSafeError

from scraper.provimento_jev import (
    MODELO_PADRAO,
    TOKENS_POR_ACORDAO,
    ClassificadorJev,
    validar_modelo,
    para_provimento,
    perguntas_sha,
)

ROOT = Path(__file__).resolve().parent.parent
logger = logging.getLogger(__name__)


def confirmar(pergunta: str) -> bool:
    """Pergunta s/N; sem terminal interativo (EOF) conta como não."""
    try:
        return input(pergunta).strip().lower() == "s"
    except EOFError:
        return False


def classificar_pendentes(
    store, classificador, itens: list, perguntas_sha: str, max_workers: int = 8
) -> tuple[int, int]:
    """Classifica `itens` em paralelo e grava cada sucesso (na thread principal).
    Devolve `(ok, falhas)`; falha de um item não derruba o lote."""

    def _um(item):
        try:
            return item, classificador.classificar(item.acordao, item.ementa), None
        except (TypeSafeError, ValueError) as e:
            return item, None, e

    ok = falhas = 0
    pool = ThreadPoolExecutor(max_workers=max_workers)
    try:
        futuros = [pool.submit(_um, item) for item in itens]
        # as_completed grava cada resultado pago assim que chega, sem esperar item lento.
        for futuro in as_completed(futuros):
            item, c, erro = futuro.result()
            if erro is not None:
                falhas += 1
                logger.warning("Falha em %s: %s", item.documento_id, erro)
                continue
            store.gravar(
                item.documento_id, c, item.provimento_regex,
                modelo=classificador.model, perguntas_sha=perguntas_sha,
            )
            ok += 1
    except BaseException:
        # Não espera chamadas pagas ainda enfileiradas (inclui Ctrl-C).
        pool.shutdown(wait=False, cancel_futures=True)
        raise
    pool.shutdown()
    return ok, falhas


def _construir_store():
    from dotenv import load_dotenv

    from scraper.provimento_jev_db import ProvimentoJevStore, ensure_schema

    load_dotenv(ROOT / ".env")
    url = os.getenv("DATABASE_URL")
    if not url:
        raise RuntimeError("DATABASE_URL não definida (veja o .env)")
    ensure_schema(url)
    return ProvimentoJevStore(url)


def _positivo(valor: str) -> int:
    n = int(valor)
    if n <= 0:
        raise argparse.ArgumentTypeError("deve ser > 0")
    return n


def _cmd_classificar(args, store, classificador) -> int:
    # O cliente real só é criado depois da confirmação.
    modelo = classificador.model if classificador else os.getenv("TYPESAFE_MODEL", MODELO_PADRAO)
    sha = perguntas_sha()
    n = store.contar_pendentes(modelo, sha)
    if args.limite is not None:
        n = min(n, args.limite)
    print(f"Modelo: {modelo}")
    print(f"perguntas_sha: {sha}")
    print(f"Pendentes: {n}")
    print(f"Sem texto (ignorados): {store.contar_sem_texto()}")
    print(f"Estimativa: {n * TOKENS_POR_ACORDAO:,} tokens ({n} × {TOKENS_POR_ACORDAO})")
    if not args.sim and not confirmar("Chamar o Jev (custo)? [s/N] "):
        print("Cancelado.")
        return 1
    classificador = classificador or ClassificadorJev()

    ok = falhas = tentados = 0
    cursor = None
    while args.limite is None or tentados < args.limite:
        restante = args.lote if args.limite is None else min(args.lote, args.limite - tentados)
        itens = store.pendentes(modelo, sha, limite=restante, apos_id=cursor)
        if not itens:
            break
        o, f = classificar_pendentes(store, classificador, itens, sha, args.max_workers)
        ok, falhas, tentados = ok + o, falhas + f, tentados + len(itens)
        cursor = itens[-1].documento_id  # item que sempre falha não volta
        print(f"  {tentados} tentados (ok={ok}, falhas={falhas})")
    print(f"ok={ok} falhas={falhas}")
    return 1 if falhas else 0


def mudancas(linhas: list, confianca_min: float) -> list[tuple[str, str, str]]:
    """`(documento_id, atual, novo)` onde a confiança atinge o mínimo e o valor muda."""
    r = []
    for l in linhas:
        novo = para_provimento(l.resultado).value
        if l.confianca_resultado >= confianca_min and novo != l.provimento_atual:
            r.append((l.documento_id, l.provimento_atual, novo))
    return r


def _cmd_aplicar(args, store) -> int:
    modelo = os.getenv("TYPESAFE_MODEL", MODELO_PADRAO)
    linhas = store.linhas(modelo, perguntas_sha())
    if not linhas:
        print(f"Nenhuma classificação para {modelo}; rode `classificar` primeiro.")
        return 1
    muda = mudancas(linhas, args.confianca_min)
    abaixo = [l for l in linhas if l.confianca_resultado < args.confianca_min]
    abaixo_muda = sum(para_provimento(l.resultado).value != l.provimento_atual for l in abaixo)
    for (atual, novo), n in sorted(Counter((a, n) for _, a, n in muda).items()):
        print(f"{atual or '(vazio)'} → {novo}: {n}")
    print(f"Mudanças: {len(muda)} de {len(linhas)} linhas")
    limite = args.confianca_min
    print(f"Linhas abaixo do limite e mudariam: {abaixo_muda} (confiança < {limite})")
    print(f"Linhas abaixo do limite sem mudança: {len(abaixo) - abaixo_muda} (confiança < {limite})")
    if not args.confirmar:
        print("Nada foi escrito; use --confirmar para aplicar.")
        return 0
    mudou = store.aplicar([(d, novo) for d, _, novo in muda])
    print(f"Linhas alteradas em documentos.provimento: {mudou}")
    print("Para restaurar a regex: uv run python utils/reclassify.py")
    return 0


def _fracao(valor: str) -> float:
    x = float(valor)
    if not 0.0 <= x <= 1.0:
        raise argparse.ArgumentTypeError("deve estar entre 0 e 1")
    return x


def provimentos_dos_chunks(
    chunk_ids: list[str], por_documento: dict[str, str]
) -> tuple[list[str], int]:
    """Provimento de cada chunk pelo documento (parte antes do último `:`).
    Chunk de documento ausente vira NAO_APLICAVEL; devolve também quantos foram."""
    nao_aplicavel = "NAO_APLICAVEL"
    resultado, orfaos = [], 0
    for chunk_id in chunk_ids:
        prov = por_documento.get(chunk_id.rpartition(":")[0])
        if prov is None:
            prov, orfaos = nao_aplicavel, orfaos + 1
        resultado.append(prov)
    return resultado, orfaos


def _construir_qdrant():
    from qdrant_client import QdrantClient

    from indexing.vector_store.qdrant_store import QdrantStore

    # Timeout de 5 s (padrão) estoura em set_payload de lotes grandes nesta máquina.
    url = os.getenv("QDRANT_URL", "http://localhost:6333")
    return QdrantStore(QdrantClient(url=url, timeout=210))


def _cmd_sincronizar(args, store, qdrant) -> int:
    inicio = time.monotonic()
    por_documento = store.provimentos_documentos()
    print(f"Documentos no Postgres: {len(por_documento)}")
    grupos: dict[str, list[str]] = {}
    for doc_id, prov in por_documento.items():
        grupos.setdefault(prov, []).append(doc_id)

    if not args.so_bm25:
        qdrant = qdrant or _construir_qdrant()
        qdrant.garantir_indices_payload()
        for prov, ids in sorted(grupos.items()):
            enviados = qdrant.atualizar_provimento(prov, sorted(ids), lote=args.lote)
            print(f"Qdrant {prov}: {enviados} documentos")

    if not args.so_qdrant:
        from indexing.lexical import bm25_builder

        indice = args.indice_bm25 or bm25_builder.BM25_INDEX_PATH
        with open(Path(indice) / "chunk_ids.json") as f:
            chunk_ids = json.load(f)
        provimentos, orfaos = provimentos_dos_chunks(chunk_ids, por_documento)
        bm25_builder.gravar_provimentos(Path(indice), provimentos)
        for prov, n in sorted(Counter(provimentos).items()):
            print(f"BM25 {prov}: {n} chunks")
        print(f"Chunks órfãos (documento ausente, NAO_APLICAVEL): {orfaos}")
        print(f"Gravado {Path(indice) / bm25_builder.PROVIMENTOS_FILENAME}")
    print(f"Tempo total: {time.monotonic() - inicio:.1f}s")
    print("Reinicie o backend para o BM25 recarregar o provimentos.json.")
    return 0


def main(
    argv: list[str] | None = None, *, store=None, classificador=None, qdrant=None
) -> int:
    parser = argparse.ArgumentParser(prog="provimento_jev_cli")
    sub = parser.add_subparsers(dest="comando", required=True)
    p = sub.add_parser("classificar", help="backfill retomável com o Jev")
    p.add_argument("--limite", type=_positivo, default=None, help="teto de documentos tentados")
    p.add_argument("--lote", type=_positivo, default=500)
    p.add_argument("--max-workers", type=_positivo, default=8)
    p.add_argument("--sim", action="store_true", help="pula a confirmação")
    p = sub.add_parser("aplicar", help="escreve o provimento do Jev em documentos (só com --confirmar)")
    p.add_argument("--confianca-min", type=_fracao, default=0.8)
    p.add_argument("--confirmar", action="store_true", help="grava de fato")
    p = sub.add_parser("sincronizar", help="leva documentos.provimento ao Qdrant e ao BM25")
    p.add_argument("--lote", type=_positivo, default=1000, help="documento_ids por chamada ao Qdrant")
    p.add_argument("--so-bm25", action="store_true")
    p.add_argument("--so-qdrant", action="store_true")
    p.add_argument("--indice-bm25", type=Path, default=None, help="padrão: BM25_INDEX_PATH")
    args = parser.parse_args(argv)
    if args.comando == "sincronizar" and args.so_bm25 and args.so_qdrant:
        parser.error("--so-bm25 e --so-qdrant são excludentes")

    if args.comando == "sincronizar":
        return _cmd_sincronizar(args, store or _construir_store(), qdrant)
    try:
        validar_modelo(os.getenv("TYPESAFE_MODEL", MODELO_PADRAO))
    except ValueError as e:
        print(e, file=sys.stderr)
        return 2
    store = store or _construir_store()
    if args.comando == "aplicar":
        return _cmd_aplicar(args, store)

    if args.comando == "classificar":
        return _cmd_classificar(args, store, classificador)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
