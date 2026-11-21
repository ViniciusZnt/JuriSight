# SonarCloud + observabilidade — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Cumprir os itens "análise estática de código e segurança" e "monitoramento/observabilidade" do Portfólio: SonarCloud no CI e Prometheus + Grafana na VPS, com um painel pronto.

**Architecture:** A API expõe `/metrics` (prometheus-fastapi-instrumentator), bloqueado no Caddy; Prometheus, node-exporter e Grafana entram no compose de produção, com configuração e painel em arquivo (`deploy/`). O SonarCloud roda como job do GitHub Actions depois dos testes, lendo a cobertura de backend e frontend.

**Tech Stack:** FastAPI, prometheus-fastapi-instrumentator, pytest-cov, Jest, Prometheus, node-exporter, Grafana, Caddy, GitHub Actions, SonarSource scan action.

**Spec:** `docs/superpowers/specs/2026-11-21-sonarcloud-observabilidade-design.md`

## Global Constraints

- Nunca imprimir nem editar o `.env` (nem com `docker compose config` sem `--quiet`, que imprime os valores).
- `/metrics` não pode ser público: o Caddy responde 404 a `/api/metrics`; o OpenAPI não muda (`/metrics` fora do schema).
- Grafana só em `127.0.0.1:3001` (o 3000 é do Dagster); Prometheus e node-exporter sem porta publicada.
- Senha do Grafana obrigatória: `GRAFANA_ADMIN_PASSWORD` com `${GRAFANA_ADMIN_PASSWORD:?defina GRAFANA_ADMIN_PASSWORD no .env}`; nunca o padrão `admin`.
- Imagens com versão fixa (tag exata, conferida com `docker pull`), nada de `latest`.
- Prometheus: coleta a cada 15 s, retenção 15 dias, volume próprio.
- O job do Sonar **não bloqueia** o deploy (o `deploy` continua `needs: [backend, frontend]`).
- Chaves do SonarCloud: organização e projeto ainda não informados → usar exatamente `SONAR_ORG_PENDENTE` e `SONAR_PROJECT_PENDENTE` como marcadores, para trocar depois.
- pt-BR; mínimo de peças; trailer de commit `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.
- Verificação: backend `set -a && . ./.env && set +a && uv run pytest -q`; frontend `cd frontend && npx jest && npx tsc --noEmit && npx eslint src && npx next build` (eslint: só os 5 problemas pré-existentes).

## Review Focus

1. `/api/metrics` acessível de fora pelo Caddy → deve dar 404. (Task 1: `caddy validate` + leitura da regra; teste de rota no app garante que só `/metrics` foi criado)
2. Rótulos de alta cardinalidade (`/document/<uuid>` cru, um rótulo por documento) → o rótulo deve ser o template da rota. (teste na Task 1)
3. Subir o compose sem `GRAFANA_ADMIN_PASSWORD` → falha com mensagem clara, não sobe com senha padrão. (Task 2: `docker compose config --quiet` com e sem a variável)
4. Push sem `SONAR_TOKEN` (PR de fork, secret ainda não cadastrado) → o job do Sonar é pulado/avisa, CI e deploy seguem. (Task 3)
5. `/metrics` no OpenAPI ou contando a si mesmo/`/health` → fora do schema e excluídos das métricas. (teste na Task 1)

---

### Task 1: API expõe `/metrics` e o Caddy bloqueia por fora

**Files:**
- Modify: `pyproject.toml` / `uv.lock` (`uv add prometheus-fastapi-instrumentator`)
- Modify: `query/api/app.py` (instrumentar logo após criar `app`)
- Modify: `deploy/Caddyfile` (dentro de `handle_path /api/*`: `/metrics` → `respond 404`)
- Test: `tests/test_metrics.py` (novo)

**Interfaces (Produces):** `GET /metrics` na API (texto Prometheus), rótulo `handler` = template da rota; métricas `http_requests_total` e `http_request_duration_seconds` (nomes do instrumentator).

- [ ] **Step 1: Testes que falham** em `tests/test_metrics.py` (usar o `TestClient` e os overrides de dependência que `tests/test_api.py` já usa para a API subir sem banco):
  - `test_metrics_expoe_texto_prometheus`: `GET /metrics` → 200 e o corpo contém `http_requests_total`.
  - `test_metrics_rotulo_e_template_da_rota`: depois de `GET /document/<uuid qualquer>` (status qualquer), o corpo de `/metrics` contém `handler="/document/{doc_id}"` (o template real da rota — conferir o nome do parâmetro em `app.py`) e **não** contém o uuid usado.
  - `test_metrics_fora_do_openapi`: `"/metrics" not in client.get("/openapi.json").json()["paths"]`.
  - `test_metrics_nao_conta_metrics_nem_health`: depois de chamar `/health` e `/metrics`, o corpo não tem `handler="/metrics"` nem `handler="/health"`.
- [ ] **Step 2: Rodar e ver falhar** — `uv run pytest -q tests/test_metrics.py`.
- [ ] **Step 3: Implementar**: `Instrumentator(excluded_handlers=["/metrics", "/health"], should_group_status_codes=True).instrument(app).expose(app, include_in_schema=False)`; Caddy: matcher de caminho `/metrics` dentro do `handle_path /api/*` respondendo 404 antes do `reverse_proxy`.
- [ ] **Step 4: Verde** — suíte backend completa; `docker run --rm -e DOMINIO=exemplo.com -v "$PWD/deploy/Caddyfile:/etc/caddy/Caddyfile:ro" caddy:2.10 caddy validate --config /etc/caddy/Caddyfile` → `Valid configuration`; `docker build --target api .` ok.
- [ ] **Step 5: Commit** — `"API expõe /metrics para o Prometheus; Caddy bloqueia /api/metrics por fora"`.

### Task 2: Prometheus, node-exporter e Grafana com painel pronto

**Files:**
- Modify: `docker-compose.prod.yml` (serviços `prometheus`, `node-exporter`, `grafana`; volumes `prometheus_data`, `grafana_data`)
- Create: `deploy/prometheus/prometheus.yml`
- Create: `deploy/grafana/provisioning/datasources/prometheus.yml`, `deploy/grafana/provisioning/dashboards/jurisight.yml`, `deploy/grafana/dashboards/jurisight.json`
- Modify: `.env.production.example` (linha `GRAFANA_ADMIN_PASSWORD=` com comentário)
- Modify: `README.md` (seção curta "Observabilidade")

**Interfaces:** Consumes `api:8000/metrics` (Task 1).

Fixado:
- `prometheus.yml`: `scrape_interval: 15s`; jobs `api` (`api:8000`, `metrics_path: /metrics`) e `node` (`node-exporter:9100`). Serviço com `--storage.tsdb.retention.time=15d`.
- `node-exporter`: montagens padrão somente leitura de `/proc`, `/sys` e `/` (`--path.rootfs=/host`), `pid: host`.
- `grafana`: `ports: ["127.0.0.1:3001:3000"]`; `GF_SECURITY_ADMIN_PASSWORD=${GRAFANA_ADMIN_PASSWORD:?defina GRAFANA_ADMIN_PASSWORD no .env}`; `GF_USERS_ALLOW_SIGN_UP=false`; `GF_ANALYTICS_REPORTING_ENABLED=false`; provisioning montado somente leitura.
- Painel `jurisight.json` (uid `jurisight`, título "JuriSight"): pedidos/min por rota; erros 4xx/5xx por rota; latência p50 e p95 de `/enrich`, `/query`, `/triagem`, `/resposta` (`histogram_quantile` sobre `http_request_duration_seconds_bucket`); CPU, RAM e disco da VPS (node-exporter). Consultas PromQL escritas à mão, legíveis.

- [ ] **Step 1: Escrever** os arquivos e os serviços.
- [ ] **Step 2: Validar config** — `docker run --rm -v "$PWD/deploy/prometheus:/p:ro" --entrypoint promtool prom/prometheus:<tag> check config /p/prometheus.yml` → `SUCCESS`; `docker compose -f docker-compose.prod.yml config --quiet` com `GRAFANA_ADMIN_PASSWORD` definida → exit 0; sem ela (`env -u GRAFANA_ADMIN_PASSWORD` e sem a linha no env) → falha citando `GRAFANA_ADMIN_PASSWORD`. **Nunca rodar `config` sem `--quiet`.**
- [ ] **Step 3: Fumaça local** — subir só `prometheus`, `node-exporter` e `grafana` (projeto compose temporário ou `docker run` equivalentes com a mesma config e uma senha de teste), conferir: Prometheus com o alvo `node` "up"; `curl -u admin:<senha de teste> http://127.0.0.1:3001/api/dashboards/uid/jurisight` → 200; datasource provisionado. Derrubar e remover os volumes de teste.
- [ ] **Step 4: README** — seção "Observabilidade": túnel `ssh -L 3001:localhost:3001 deploy@IP` → `http://localhost:3001`, usuário `admin` + `GRAFANA_ADMIN_PASSWORD`; o que o painel mostra; `/api/metrics` não é público.
- [ ] **Step 5: Commit** — `"Prometheus, node-exporter e Grafana com o painel JuriSight (só por túnel)"`.

### Task 3: SonarCloud no CI com cobertura

**Files:**
- Create: `sonar-project.properties`
- Modify: `pyproject.toml` / `uv.lock` (grupo dev: `pytest-cov`)
- Modify: `frontend/jest.config.mjs` (`coverageReporters: ["lcov", "text-summary"]`, sem meta)
- Modify: `.github/workflows/ci.yml`
- Modify: `README.md` (selos + 1 linha), `.gitignore` (`coverage.xml`, `frontend/coverage/`, `.scannerwork/`)

Fixado:
- `sonar-project.properties`: `sonar.organization=SONAR_ORG_PENDENTE`, `sonar.projectKey=SONAR_PROJECT_PENDENTE`; `sonar.sources` = `query,scraper,indexing,processing,auth,conversations,pipeline,utils,avaliacao,main.py,frontend/src`; `sonar.tests` = `tests,frontend/src/__tests__`; `sonar.exclusions` cobre `frontend/src/__tests__/**`, `**/node_modules/**`, `data/**`, `docs/**`; `sonar.python.version=3.13`; `sonar.python.coverage.reportPaths=coverage.xml`; `sonar.javascript.lcov.reportPaths=frontend/coverage/lcov.info`.
- CI: job `backend` roda `uv run pytest -q --cov --cov-report=xml` e publica `coverage.xml` como artefato; job `frontend` roda `pnpm test -- --coverage` e publica `frontend/coverage/lcov.info`; job novo `sonar` (`needs: [backend, frontend]`, `fetch-depth: 0`) baixa os dois, **corrige os caminhos do lcov para relativos à raiz** (`SF:src/` → `SF:frontend/src/`, conferir o formato real do arquivo) e roda `SonarSource/sonarqube-scan-action` com tag fixa, `SONAR_TOKEN` do secret. Sem o secret, o job escreve um aviso e termina com sucesso (passo inicial que checa `env.SONAR_TOKEN`). `deploy` não muda (`needs: [backend, frontend]`).
- README: selos de quality gate, bugs e vulnerabilidades do SonarCloud usando os marcadores (trocados quando as chaves chegarem).

- [ ] **Step 1: Escrever** os arquivos.
- [ ] **Step 2: Validar** — `uv run pytest -q --cov --cov-report=xml` gera `coverage.xml` com os caminhos dos pacotes; `cd frontend && npx jest --coverage` gera `coverage/lcov.info`; aplicar o ajuste de caminho localmente e conferir que as linhas `SF:` apontam para arquivos que existem a partir da raiz; YAML do CI parseia; `actionlint` se disponível (`docker run --rm -v "$PWD:/repo" -w /repo rhysd/actionlint:latest` é aceitável só para checar, não fica no repo).
- [ ] **Step 3: Suítes verdes** (comandos das Global Constraints).
- [ ] **Step 4: Commit** — `"SonarCloud no CI com cobertura do backend e do frontend (chaves pendentes)"`.
