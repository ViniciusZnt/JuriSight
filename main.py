"""
Ponto de entrada da API (RFC Tabela 13: FastAPI + Uvicorn).

Uso:
    uv run python main.py
"""
import os
import sys
from pathlib import Path

# main.py está na raiz do projeto (1 nível acima, não 2 como em indexing/run.py).
ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv

load_dotenv(ROOT / ".env")

import uvicorn

API_HOST = os.getenv("API_HOST", "0.0.0.0")
API_PORT = int(os.getenv("API_PORT", "8000"))
API_RELOAD = os.getenv("API_RELOAD", "true").lower() == "true"


def main() -> None:
    uvicorn.run("query.api.app:app", host=API_HOST, port=API_PORT, reload=API_RELOAD)


if __name__ == "__main__":
    main()
