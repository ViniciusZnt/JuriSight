"""
Ponto de entrada para coleta de acórdãos TST.

Uso:
    uv run python scraper/run.py
    uv run python scraper/run.py --from 2024-01-01
    uv run python scraper/run.py --from 2024-01-01 --to 2024-06-30
    uv run python scraper/run.py --checkpoint caminho/checkpoint.json
"""
import argparse
import logging
import os
import sys
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv
load_dotenv(ROOT / ".env")

from scraper.api import ApiClient
from scraper.core import Scraper
from scraper.db import CheckpointStore, PostgresStore

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://postgres:postgres@localhost:5432/jurisight",
)
CHECKPOINT_PATH = ROOT / "scraper" / "checkpoint.json"

COLLECTION_START = date(2023, 1, 1)


def resolve_dates(from_date: date | None, to_date: date | None, store: PostgresStore) -> tuple[date, date]:
    end = to_date or date.today() - timedelta(days=1)

    if from_date:
        print(f"Data de início forçada: {from_date}")
        return from_date, end

    last_raw = store.get_last_collected_date()
    if last_raw:
        last = date.fromisoformat(last_raw)
        print(f"Último dia coletado: {last} — re-coletando a partir desse dia.")
        return last, end

    print(f"Banco vazio — iniciando do começo: {COLLECTION_START}")
    return COLLECTION_START, end


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
        "--checkpoint",
        dest="checkpoint",
        type=Path,
        default=CHECKPOINT_PATH,
        help=f"Caminho do arquivo de checkpoint. Padrão: {CHECKPOINT_PATH}",
    )
    args = parser.parse_args()

    store = PostgresStore(DATABASE_URL)
    try:
        store.connect()
    except Exception as e:
        print(f"Erro ao conectar no PostgreSQL: {e}", file=sys.stderr)
        sys.exit(1)

    try:
        start, end = resolve_dates(args.from_date, args.to_date, store)
    except Exception as e:
        print(f"Erro ao resolver datas: {e}", file=sys.stderr)
        store.close()
        sys.exit(1)

    if start > end:
        print(f"Nenhuma coleta necessária: início ({start}) >= fim ({end}).")
        store.close()
        return

    print(f"\nColetando de {start} até {end}.")

    checkpoint = CheckpointStore(args.checkpoint)
    api = ApiClient()
    scraper = Scraper(
        api_client=api,
        store=store,
        checkpoint_store=checkpoint,
        colecao=args.colecao,
    )

    try:
        result = scraper.run(start.isoformat(), end.isoformat())
    finally:
        store.close()

    print("\n--- Resultado ---")
    print(f"  Concluído:        {result['completed']}")
    print(f"  Documentos salvos: {result['documents_saved']}")
    print(f"  Requisições feitas: {result['requests_made']}")
    print(f"  Último delay:      {result['current_delay_seconds']}s")

    if not result["completed"]:
        print(f"\n  Motivo da parada: {result.get('halt_reason', '?')}")
        print(f"  Mensagem:         {result.get('halt_message', '')}")
        print(f"\nRetome com: uv run python scraper/run.py")
        sys.exit(2)


if __name__ == "__main__":
    main()
