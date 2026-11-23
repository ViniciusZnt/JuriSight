# Backend do JuriSight (FastAPI). Os índices e modelos (data/) entram como volume, não na imagem.
FROM python:3.13-slim AS api

COPY --from=ghcr.io/astral-sh/uv:0.8.4 /uv /usr/local/bin/uv
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy PYTHONUNBUFFERED=1
WORKDIR /app

# Dependências primeiro (camada em cache enquanto o uv.lock não muda); sem dev nem benchmark.
# --no-build: só wheels prontos, sem rodar scripts de build de dependência. O projeto não é instalado:
# uvicorn/dagster rodam em /app e importam os pacotes (query, auth, pipeline…) dali.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-build --no-install-project

COPY . .

EXPOSE 8000
CMD ["uv", "run", "--no-sync", "uvicorn", "query.api.app:app", "--host", "0.0.0.0", "--port", "8000"]

# Pipeline de dados (Dagster): mesma base da api + Chromium do Playwright para o scraper.
# Roda como o usuário `dagster` (não root). O uid deve ser o mesmo do dono de ./data na VPS
# (o usuário do rsync), para os dois conseguirem gravar lá: DAGSTER_UID no .env, padrão 1000.
# O serviço dagster-permissoes do compose de produção acerta o dono de ./data e do dagster_home.
FROM api AS dagster
ARG DAGSTER_UID=1000
# Chromium fora do /root, para o usuário dagster conseguir abrir.
ENV PLAYWRIGHT_BROWSERS_PATH=/opt/ms-playwright DAGSTER_HOME=/app/dagster_home
RUN uv run --no-sync playwright install --with-deps chromium \
 && useradd --uid "$DAGSTER_UID" --create-home --shell /usr/sbin/nologin dagster \
 && mkdir -p "$DAGSTER_HOME" /app/data \
 && chown dagster:dagster "$DAGSTER_HOME" /app/data
USER dagster
EXPOSE 3000
CMD ["sh", "-c", "mkdir -p $DAGSTER_HOME && cp pipeline/dagster.yaml $DAGSTER_HOME/dagster.yaml && exec uv run --no-sync dagster dev -f pipeline/definitions.py -h 0.0.0.0 -p 3000"]
