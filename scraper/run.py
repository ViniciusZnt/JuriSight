"""
Ponto de entrada para coleta de acórdãos TST.

Uso:
    uv run python scraper/run.py
    uv run python scraper/run.py --from 2024-01-01
    uv run python scraper/run.py --from 2024-01-01 --to 2024-06-30
"""
import argparse
import logging
import os
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv
load_dotenv(ROOT / ".env")

from scraper.web_scraper import WebScraper
from scraper.orchestrator import Orchestrator
from scraper.db_writer import PostgresWriter
from scraper.delta import DbStateStore, resolve_collection_window

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
# Silencia o ruído de bibliotecas de terceiros.
for noisy in ("urllib3", "asyncio", "playwright"):
    logging.getLogger(noisy).setLevel(logging.WARNING)

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://postgres:postgres@localhost:5432/jurisight",
)


def resolve_dates(from_date: date | None, to_date: date | None, writer: PostgresWriter) -> tuple[date, date]:
    return resolve_collection_window(from_date, to_date, writer.get_last_collected_date())


def main() -> None:
    parser = argparse.ArgumentParser(description="Coleta acórdãos TST e persiste no PostgreSQL.")
    parser.add_argument(
        "--from",
        dest="from_date",
        type=date.fromisoformat,
        default=None,
        help="Data de início (YYYY-MM-DD). Padrão: detecta pelo banco.",
    )
    parser.add_argument(
        "--to",
        dest="to_date",
        type=date.fromisoformat,
        default=None,
        help="Data final (YYYY-MM-DD). Padrão: ontem.",
    )
    parser.add_argument(
        "--colecao",
        dest="colecao",
        default="acordaos",
        choices=["acordaos", "sumulas", "precedentes", "ojs"],
        help="Coleção a coletar. Padrão: acordaos.",
    )
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Dropa a tabela e zera o estado antes de coletar (re-scrape do zero).",
    )
    args = parser.parse_args()

    writer = PostgresWriter(DATABASE_URL)
    try:
        writer.connect()
    except Exception as e:
        print(f"Erro ao conectar no PostgreSQL: {e}", file=sys.stderr)
        sys.exit(1)

    if args.reset:
        writer.reset()
        print("Reset: tabela documentos recriada e estado zerado.")

    try:
        start, end = resolve_dates(args.from_date, args.to_date, writer)
    except Exception as e:
        print(f"Erro ao resolver datas: {e}", file=sys.stderr)
        writer.close()
        sys.exit(1)

    if start > end:
        print(f"Nenhuma coleta necessária: início ({start}) >= fim ({end}).")
        writer.close()
        return

    gaps = writer.find_all_gaps(start.isoformat(), end.isoformat())
    if gaps:
        print("\nDias sem coleta no histórico (use --from/--to para preencher):")
        print(gaps)

    print(f"\nColetando de {start} até {end}.")

    state_store = DbStateStore(writer, args.colecao)
    api = WebScraper()
    orchestrator = Orchestrator(
        api_client=api,
        writer=writer,
        checkpoint_store=state_store,
        colecao=args.colecao,
    )

    try:
        result = orchestrator.run(start.isoformat(), end.isoformat())
    finally:
        writer.close()

    print("\n--- Resultado ---")
    print(f"  Concluído:        {result['completed']}")
    print(f"  Documentos salvos: {result['documents_saved']}")
    print(f"  Requisições feitas: {result['requests_made']}")

    if not result["completed"]:
        print(f"\n  Motivo da parada: {result.get('halt_reason', '?')}")
        print(f"  Mensagem:         {result.get('halt_message', '')}")
        print(f"\nRetome com: uv run python scraper/run.py")
        sys.exit(2)


if __name__ == "__main__":
    main()
