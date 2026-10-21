"""
CLI do provimento com o Jev. Subcomandos: `classificar` (backfill retomável).
Ver docs/superpowers/specs/2026-10-20-provimento-jev-design.md.

Uso: uv run python -m scraper.provimento_jev_cli classificar [--limite N] [--sim]
"""
from __future__ import annotations

import argparse
import logging
import os
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from typesafe_sdk import TypeSafeError

from avaliacao.passo_zero import confirmar
from scraper.provimento_jev import TOKENS_POR_ACORDAO, perguntas_sha

ROOT = Path(__file__).resolve().parent.parent
logger = logging.getLogger(__name__)


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
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        for item, c, erro in pool.map(_um, itens):
            if erro is not None:
                falhas += 1
                logger.warning("Falha em %s: %s", item.documento_id, erro)
                continue
            store.gravar(
                item.documento_id, c, item.provimento_regex,
                modelo=classificador.model, perguntas_sha=perguntas_sha,
            )
            ok += 1
    return ok, falhas


def _construir_reais():
    from dotenv import load_dotenv

    from scraper.provimento_jev import ClassificadorJev
    from scraper.provimento_jev_db import ProvimentoJevStore, ensure_schema

    load_dotenv(ROOT / ".env")
    url = os.getenv("DATABASE_URL")
    if not url:
        raise RuntimeError("DATABASE_URL não definida (veja o .env)")
    ensure_schema(url)
    return ProvimentoJevStore(url), ClassificadorJev()


def _cmd_classificar(args, store, classificador) -> int:
    modelo = classificador.model
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


def main(argv: list[str] | None = None, *, store=None, classificador=None) -> int:
    parser = argparse.ArgumentParser(prog="provimento_jev_cli")
    sub = parser.add_subparsers(dest="comando", required=True)
    p = sub.add_parser("classificar", help="backfill retomável com o Jev")
    p.add_argument("--limite", type=int, default=None, help="teto de documentos tentados")
    p.add_argument("--lote", type=int, default=500)
    p.add_argument("--max-workers", type=int, default=8)
    p.add_argument("--sim", action="store_true", help="pula a confirmação")
    args = parser.parse_args(argv)

    if store is None or classificador is None:
        store_real, clf_real = _construir_reais()
        store = store or store_real
        classificador = classificador or clf_real

    if args.comando == "classificar":
        return _cmd_classificar(args, store, classificador)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
