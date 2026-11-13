"""Ambiente comum dos testes, aplicado antes de importar o app."""
import os
from pathlib import Path

from dotenv import load_dotenv

# O cookie de sessão é Secure por padrão (issue #17); o cliente de teste fala HTTP, como o dev
# local, então desliga explicitamente — o mesmo que o .env.example faz.
os.environ.setdefault("COOKIE_SECURE", "false")

import psycopg
import pytest

load_dotenv(Path(__file__).resolve().parent.parent / ".env")
DATABASE_URL = os.getenv("DATABASE_URL")


def _postgres_disponivel() -> bool:
    if not DATABASE_URL:
        return False
    try:
        psycopg.connect(DATABASE_URL, connect_timeout=2).close()
        return True
    except psycopg.OperationalError:
        return False


# Os testes de integração usam `pytestmark = requer_postgres`.
requer_postgres = pytest.mark.skipif(
    not _postgres_disponivel(),
    reason="Requer DATABASE_URL apontando para um Postgres real e acessível.",
)
