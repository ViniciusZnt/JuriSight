"""
Backfill de reclassificação de provimento (utilitário de manutenção, uso pontual).

Por que existe
--------------
O `provimento` é um campo DERIVADO: `scraper.provimento.classify` o calcula a
partir do texto do dispositivo (coluna `acordao`), que fica persistido no
PostgreSQL. Como a fonte da classificação já está no banco, mudar a lógica de
classificação NÃO exige re-coletar nada da API — basta reprocessar o texto local.

Este script foi criado quando PARCIAL deixou de colapsar em APROVADO e virou uma
categoria própria no enum `Provimento`: os documentos já coletados guardavam
`provimento = APROVADO` para decisões que eram, juridicamente, parcialmente
providas. O backfill relê `acordao`, reclassifica e corrige a coluna in-place.

Serve para qualquer mudança futura em `classify`: sempre que a regra evoluir,
rode isto para alinhar os dados históricos à lógica atual. Como `classify` é
determinística sobre `acordao`, o resultado equivale a ter coletado tudo de novo
com a lógica vigente — e é idempotente (rodar de novo não muda mais nada).

Uso:
    uv run python utils/reclassify.py --dry-run   # só mostra o que mudaria
    uv run python utils/reclassify.py             # aplica as mudanças
"""
import argparse
import logging
import os
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv
load_dotenv(ROOT / ".env")

import psycopg

from scraper.provimento import classify
from scraper.schema import TipoDocumento

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

_SELECT = "SELECT id, acordao, tipo_documento, provimento FROM documentos"
_UPDATE = "UPDATE documentos SET provimento = %s WHERE id = %s"


def main() -> None:
    parser = argparse.ArgumentParser(description="Reclassifica o provimento dos documentos já coletados.")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Não grava; apenas reporta quantos registros mudariam e como.",
    )
    args = parser.parse_args()

    conn = psycopg.connect(DATABASE_URL)
    try:
        transitions: Counter[tuple[str, str]] = Counter()
        pending: list[tuple[str, str]] = []  # (novo_provimento, id)

        with conn.cursor() as cur:
            cur.execute(_SELECT)
            rows = cur.fetchall()

        for doc_id, acordao, tipo_raw, provimento_atual in rows:
            try:
                tipo = TipoDocumento(tipo_raw)
            except ValueError:
                logger.warning("tipo_documento desconhecido %r (id=%s) — ignorando.", tipo_raw, doc_id)
                continue

            novo = classify(acordao or "", tipo).value
            if novo != provimento_atual:
                transitions[(provimento_atual, novo)] += 1
                pending.append((novo, doc_id))

        total = len(rows)
        logger.info("Documentos avaliados: %d | mudariam: %d", total, len(pending))
        for (antigo, novo), n in sorted(transitions.items(), key=lambda x: -x[1]):
            logger.info("  %-14s → %-14s : %d", antigo, novo, n)

        if not pending:
            logger.info("Nada a fazer — classificação já está consistente.")
            return

        if args.dry_run:
            logger.info("--dry-run: nenhuma alteração gravada.")
            return

        with conn.cursor() as cur:
            cur.executemany(_UPDATE, pending)
        conn.commit()
        logger.info("Backfill concluído: %d registros atualizados.", len(pending))
    finally:
        conn.close()


if __name__ == "__main__":
    main()
