# SonarCloud + observabilidade (Prometheus e Grafana) — design curto

Data: 21/11/2026.

## Por quê

O "núcleo comum de engenharia" do Portfólio exige, para todas as linhas de projeto,
**análise estática de código e segurança** (ex.: SonarQube, SonarCloud) e **monitoramento ou
observabilidade da solução em execução**. O objetivo é cumprir os dois com o mínimo de
infraestrutura e ter evidência para mostrar na banca. Nada de alertas, plantão ou
sofisticação além disso.

## Abordagens

- **Análise estática:** **SonarCloud** (escolhido pelo Vinicius) — roda no GitHub Actions,
  sem servidor, gratuito (repositório público). Descartado: SonarQube na VPS (2–4 GB de RAM,
  Elasticsearch, ajuste de kernel, manutenção).
- **Observabilidade:** **Prometheus + Grafana** (escolhido pelo Vinicius) — métricas da API
  por rota e da máquina, painel pronto. Descartado: Uptime Kuma (só "está no ar?").
- Custo em dinheiro: zero (SonarCloud gratuito para repo público; Prometheus/Grafana são
  software livre na VPS já paga; ~400 MB de RAM).

## O que muda

### Análise estática (SonarCloud)

- `sonar-project.properties` na raiz: código Python (`query`, `scraper`, `indexing`,
  `processing`, `auth`, `conversations`, `pipeline`, `utils`, `avaliacao`, `main.py`) e
  TypeScript (`frontend/src`); testes em `tests/` e `frontend/src/__tests__/`; fora da
  análise: `data/`, `docs/`, `node_modules`, `.next`, arquivos gerados e de lock.
- **Cobertura** entra no relatório: backend com `pytest --cov` (dependência de dev
  `pytest-cov`) gerando `coverage.xml`; frontend com `jest --coverage` gerando
  `lcov.info`. Não há meta de cobertura (o próprio Portfólio não exige).
- CI: o job do Sonar roda depois dos testes, em push na `main` e em PR, usando a action
  oficial da SonarSource com o secret `SONAR_TOKEN`. A análise **não bloqueia** o deploy
  (quality gate informativo).
- README ganha os selos (quality gate, bugs, vulnerabilidades) e uma linha sobre o Sonar.
- **Passo do Vinicius (uma vez):** entrar em sonarcloud.io com o GitHub, importar o
  repositório, desligar a "Automatic Analysis" (a análise é pelo CI), copiar o token para o
  secret `SONAR_TOKEN` e informar a organização e a chave do projeto (vão no
  `sonar-project.properties`).

### Observabilidade (Prometheus + Grafana)

- **API:** `prometheus-fastapi-instrumentator` expõe `/metrics` (pedidos, erros e latência
  por rota e status). A rota não exige login, mas **não é pública**: o Caddy responde 404 a
  `/api/metrics`; só o Prometheus, pela rede interna do Docker, lê `api:8000/metrics`.
- **Serviços novos em `docker-compose.prod.yml`** (imagens com versão fixa):
  - `prometheus`: coleta a API e o `node-exporter` a cada 15 s, guarda 15 dias, sem porta
    publicada;
  - `node-exporter`: CPU, RAM, disco e rede da VPS;
  - `grafana`: publicado só em `127.0.0.1:3001` (o 3000 é do Dagster), acesso por túnel
    SSH como o Dagster; senha do admin pela variável `GRAFANA_ADMIN_PASSWORD` no `.env` da
    VPS (o Vinicius define; o `.env.production.example` ganha a linha).
- **Provisionamento em arquivo** (`deploy/grafana/`): a fonte de dados Prometheus e **um
  painel** "JuriSight" já carregados ao subir, com: pedidos por minuto e erros (4xx/5xx) por
  rota; latência p50/p95 das rotas de IA (`/enrich`, `/query`, `/triagem`, `/resposta`);
  CPU, RAM e disco da VPS.
- README: seção curta "Observabilidade" (túnel, o que o painel mostra).

## Decisões minhas (podem ser revistas)

- `/metrics` bloqueado no Caddy em vez de exigir login (o Prometheus não faz login; o
  bloqueio na borda é o mais simples).
- Sem cAdvisor, exporter de Postgres, Loki ou alertas: o requisito pede observabilidade da
  solução, e API + máquina cobrem isso com o menor número de peças.
- Grafana na porta 3001 e só por túnel (nada de subdomínio público com login).
- Só produção: o `docker-compose.yml` de desenvolvimento não ganha os serviços (dá para
  ligar depois se quiser ver local).
- Sonar não bloqueia merge nem deploy.

## Fora

- Wiki do GitHub (também é obrigatória no núcleo comum; tratar à parte, se ainda não existir).
- Alertas (e-mail/Telegram), logs centralizados, tracing.

## Como saber que funcionou

- PR mostra a análise do SonarCloud; README mostra o selo do quality gate.
- Na VPS, `ssh -L 3001:localhost:3001 deploy@IP` abre o Grafana com o painel "JuriSight"
  preenchido depois de algumas buscas.
- `https://<domínio>/api/metrics` responde 404 de fora.
- Testes, lint e build continuam verdes; a imagem da api constrói.
