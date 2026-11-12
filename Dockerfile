# Backend do JuriSight (FastAPI). Os índices e modelos (data/) entram como volume, não na imagem.
FROM python:3.13-slim AS api

COPY --from=ghcr.io/astral-sh/uv:0.8.4 /uv /usr/local/bin/uv
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy PYTHONUNBUFFERED=1
WORKDIR /app

# Dependências primeiro (camada em cache enquanto o uv.lock não muda); sem dev nem benchmark.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY . .
RUN uv sync --frozen --no-dev

EXPOSE 8000
CMD ["uv", "run", "--no-sync", "uvicorn", "query.api.app:app", "--host", "0.0.0.0", "--port", "8000"]

# Pipeline de dados (Dagster): mesma base da api + Chromium do Playwright para o scraper.
FROM api AS dagster
RUN uv run --no-sync playwright install --with-deps chromium
ENV DAGSTER_HOME=/app/dagster_home
EXPOSE 3000
CMD ["sh", "-c", "mkdir -p $DAGSTER_HOME && cp pipeline/dagster.yaml $DAGSTER_HOME/dagster.yaml && exec uv run --no-sync dagster dev -f pipeline/definitions.py -h 0.0.0.0 -p 3000"]
