# Observabilidade: saúde, logs, Qdrant/Caddy e contêineres — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Acrescentar ao Prometheus/Grafana da produção: health check de cada serviço, logs de todos os contêineres, métricas do Qdrant e do Caddy e CPU/RAM por contêiner, tudo no painel "JuriSight".

**Architecture:** Novos serviços no `docker-compose.prod.yml` (blackbox-exporter, cAdvisor, Loki, Alloy) com configuração em `deploy/`; novos jobs no `deploy/prometheus/prometheus.yml`; Caddy serve métricas num endereço interno; Grafana provisiona a fonte Loki e o painel ganha seções.

**Tech Stack:** Prometheus, blackbox-exporter, cAdvisor, Loki, Grafana Alloy, Caddy, Grafana.

**Spec:** `docs/superpowers/specs/2026-11-21-observabilidade-saude-logs-design.md`

## Global Constraints

- Nunca imprimir nem editar o `.env`; **nunca** `docker compose config` sem `--quiet`.
- Nenhuma porta nova publicada; só o Grafana continua em `127.0.0.1:3001`. A API de administração do Caddy (porta 2019) **não** pode ficar acessível pela rede.
- Imagens com tag exata conferida com `docker pull`; nada de `latest`.
- Rótulo `servico` com os nomes: `site`, `api`, `qdrant`, `ollama`, `dagster`, `postgres` (health checks) e o nome do serviço do compose (logs e contêineres).
- Sondas: HTTP 2xx em `web:3000/`, `api:8000/health`, `qdrant:6333/readyz`, `ollama:11434/api/tags`, `dagster:3000/server_info`; TCP em `postgres:5432`.
- Loki: retenção de **15 dias**, volume próprio. Socket do Docker montado só onde precisa (Alloy, cAdvisor), somente leitura.
- O passo do deploy no CI reinicia, depois do `up -d`, todos os serviços com arquivo de configuração montado: `caddy prometheus blackbox loki alloy` (manter o comentário do porquê; não quebrar a continuação de linha do `ssh` — conferir com shellcheck).
- pt-BR; mínimo de peças; trailer de commit `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.
- Verificação backend `set -a && . ./.env && set +a && uv run pytest -q` (o código Python não muda nesta tarefa; rodar para confirmar).

## Review Focus

1. Um serviço fora do ar (ex.: Qdrant parado) → "Serviços no ar" fica vermelho para ele, os outros seguem verdes. (fumaça da Task 1: parar um alvo e ver `probe_success` = 0)
2. A API de administração do Caddy alcançável pela rede interna (alguém do compose poderia reconfigurar o Caddy) → só o endereço de métricas fica ouvindo; `admin` continua em `localhost`. (Task 1: `curl caddy:2019` de outro contêiner falha)
3. Logs com segredos (ex.: a API logando `DATABASE_URL` ou tokens) → só o que os serviços já logam; nada novo é logado. (Task 2: amostra dos logs da API na fumaça)
4. Loki enchendo o disco → retenção de 15 dias ligada de fato (compactor com retenção habilitada). (Task 2: config validada)
5. Deploy quebrando por reinício de serviço inexistente ou continuação de linha → shellcheck do passo e nomes iguais aos do compose. (Task 1)

---

### Task 1: Health checks, Qdrant, Caddy e cAdvisor no Prometheus

**Files:**
- Create: `deploy/blackbox/blackbox.yml` (módulos `http_2xx` e `tcp_connect`)
- Modify: `deploy/prometheus/prometheus.yml` (jobs `servicos` via blackbox com relabel e rótulo `servico`; `qdrant` em `qdrant:6333/metrics`; `caddy` no endereço interno de métricas; `cadvisor` em `cadvisor:8080`)
- Modify: `deploy/Caddyfile` (métricas ligadas na opção global; site interno só de métricas, ex. `:9180`)
- Modify: `docker-compose.prod.yml` (serviços `blackbox` e `cadvisor`, imagens fixas, sem portas)
- Modify: `.github/workflows/ci.yml` (lista do `restart`)

**Interfaces (Produces):** séries `probe_success{servico=...}`, `probe_duration_seconds{servico=...}`; métricas do Qdrant (`rest_responses_*`/`grpc_responses_*`, conferir nomes reais), do Caddy (`caddy_http_requests_total` etc., conferir nomes reais) e do cAdvisor (`container_cpu_usage_seconds_total`, `container_memory_working_set_bytes`, com rótulo do nome do serviço — conferir qual rótulo do cAdvisor traz o nome do serviço do compose).

- [ ] **Step 1: Escrever** configs e serviços.
- [ ] **Step 2: Validar** — `promtool check config`; `blackbox_exporter --config.check` (pela imagem); `caddy validate` com `DOMINIO=exemplo.com`; `docker compose -f docker-compose.prod.yml config --quiet` (com `GRAFANA_ADMIN_PASSWORD` de teste no ambiente); shellcheck do `run:` do deploy.
- [ ] **Step 3: Fumaça local** (compose temporário no scratchpad, sem tocar no `.env` real): Prometheus + blackbox + cAdvisor + um Qdrant e um Caddy de teste + um alvo HTTP simples no lugar dos que não sobem localmente; conferir `probe_success` = 1 para alvos vivos e = 0 para um alvo parado; métricas do Qdrant, do Caddy e do cAdvisor presentes; `curl http://caddy:2019/config/` de outro contêiner **falha**. Anotar no relatório os nomes reais das métricas e rótulos (a Task 3 usa). Derrubar tudo.
- [ ] **Step 4: Commit** — `"Health check dos serviços, métricas do Qdrant, do Caddy e dos contêineres"`.

### Task 2: Logs no Grafana (Loki + Alloy)

**Files:**
- Create: `deploy/loki/loki.yml` (single binary, armazenamento em sistema de arquivos, retenção 15 dias com compactor)
- Create: `deploy/alloy/config.alloy` (descoberta pelo Docker, rótulo `servico` = `com.docker.compose.service`, envio ao Loki)
- Create: `deploy/grafana/provisioning/datasources/loki.yml` (uid `loki`)
- Modify: `docker-compose.prod.yml` (serviços `loki` e `alloy`, volume `loki_data`, imagens fixas, sem portas)

**Interfaces (Produces):** fonte de dados Grafana uid `loki`; streams com rótulo `servico`.

- [ ] **Step 1: Escrever** configs e serviços.
- [ ] **Step 2: Validar** — `loki -config.file=... -verify-config` (pela imagem); `alloy fmt` / validação pela imagem; `compose config --quiet`.
- [ ] **Step 3: Fumaça local**: Loki + Alloy + um contêiner que escreve logs com rótulo de serviço de compose; consultar o Loki (`/loki/api/v1/query_range` com `{servico="..."}`) e ver linhas; Grafana de teste com a fonte `loki` provisionada e saudável. Derrubar tudo.
- [ ] **Step 4: Commit** — `"Logs de todos os contêineres no Grafana (Loki + Alloy, 15 dias)"`.

### Task 3: Painel e README

**Files:**
- Modify: `deploy/grafana/dashboards/jurisight.json` (seções novas, consultas com os nomes reais anotados nas Tasks 1–2)
- Modify: `README.md` (seção Observabilidade: o que cada seção mostra; a decisão do socket do Docker em uma linha)

Seções novas (títulos em pt-BR): "Serviços no ar" (stat verde/vermelho por `servico`), "Tempo de resposta dos serviços", "Qdrant: requisições e latência", "Caddy: requisições por código de status", "CPU e RAM por contêiner", "Logs" (painel de logs da fonte `loki` com variável `servico`).

- [ ] **Step 1: Escrever** o painel.
- [ ] **Step 2: Fumaça**: Grafana de teste com o painel provisionado (200 em `/api/dashboards/uid/jurisight`) e cada consulta nova avaliada contra o Prometheus/Loki da fumaça (ou, se os serviços não sobem localmente, contra os nomes anotados), sem erro de sintaxe.
- [ ] **Step 3: Commit** — `"Painel JuriSight: serviços no ar, Qdrant, Caddy, contêineres e logs"`.
