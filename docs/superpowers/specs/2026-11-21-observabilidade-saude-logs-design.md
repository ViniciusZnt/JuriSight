# Observabilidade: saúde dos serviços, logs, Qdrant/Caddy e contêineres — design curto

Data: 21/11/2026. Continua `2026-11-21-sonarcloud-observabilidade-design.md` (já em produção:
Prometheus + node-exporter + Grafana, `/metrics` da API, painel "JuriSight").

## Por quê

O painel atual não mostra quando um serviço que não é a API cai (Qdrant, Ollama, Postgres,
site), não tem logs e não diz quem consome recursos. O Vinicius escolheu os itens 1 a 4 da
lista proposta; alertas ficaram de fora.

## Abordagens (escolha do Vinicius: 1 a 4)

1. **Health check de cada serviço** — `blackbox-exporter` (sondas HTTP/TCP feitas pelo
   Prometheus).
2. **Logs centralizados no Grafana** — Loki + Grafana Alloy (o Promtail está descontinuado;
   o Alloy é o sucessor oficial).
3. **Métricas nativas do Qdrant e do Caddy** — só configuração.
4. **CPU/RAM por contêiner** — cAdvisor.

Descartados: alertas (fora de escopo); Dozzle para logs (seria outra interface, fora do
Grafana); postgres_exporter (o health check TCP basta para "está no ar").

## O que muda

- **Health checks** (`deploy/blackbox/blackbox.yml`, job `servicos` no Prometheus):
  - HTTP 2xx: site `web:3000/`, API `api:8000/health`, Qdrant `qdrant:6333/readyz`,
    Ollama `ollama:11434/api/tags`, Dagster `dagster:3000/server_info`;
  - TCP: Postgres `postgres:5432`.
  - Rótulo `servico` legível em cada alvo (site, api, qdrant, ollama, dagster, postgres).
- **Qdrant:** o Prometheus lê `qdrant:6333/metrics` (sem chave: o Qdrant da produção não
  usa API key).
- **Caddy:** métricas ligadas na opção global e servidas num endereço **interno** só para
  métricas (ex.: `:9180` com a diretiva `metrics`), sem publicar porta e **sem expor a API
  de administração do Caddy** à rede.
- **cAdvisor:** CPU, RAM e reinícios por contêiner; intervalo de coleta folgado para pesar
  pouco.
- **Logs:** Alloy descobre os contêineres pelo Docker e envia os logs ao Loki, com o rótulo
  `servico` = nome do serviço do compose; Loki guarda **15 dias** em disco (volume próprio).
  O Grafana ganha a fonte de dados Loki provisionada.
- **Painel "JuriSight"** ganha: "Serviços no ar" (verde/vermelho por serviço), tempo de
  resposta das sondas, Qdrant (requisições e latência), Caddy (requisições por código de
  status), CPU e RAM por contêiner, e um painel de **logs** com filtro por serviço.
- **Deploy:** o passo que reinicia `caddy prometheus` depois do `up -d` passa a reiniciar
  também os serviços cujos arquivos de configuração montados mudaram (blackbox, Loki, Alloy).
- Imagens com versão fixa; nada publicado além do Grafana em `127.0.0.1:3001`.

## Decisões minhas (podem ser revistas)

- **Socket do Docker:** Alloy (para descobrir contêineres e ler logs) e cAdvisor precisam
  ler o Docker do host. O socket montado "somente leitura" ainda dá acesso amplo à API do
  Docker — é o padrão dessas ferramentas, e os dois contêineres não têm porta publicada.
  Aceito como risco declarado; a alternativa (ler arquivos de log do disco) dá mais trabalho
  e perde o nome do serviço.
- Um painel só (o mesmo "JuriSight"), em seções, em vez de vários painéis.
- Sem limites de memória por contêiner (a VPS usa ~24% da RAM).

## Fora

- Alertas; tracing; postgres_exporter.

## Como saber que funcionou

- No Grafana, "Serviços no ar" mostra os 6 serviços em verde; parar um (ex.: Qdrant) deixa-o
  vermelho em até ~1 min.
- O painel de logs mostra linhas da API ao fazer uma busca, filtrando por serviço.
- Painéis de Qdrant, Caddy e contêineres com dados depois de uso.
- Nada novo publicado fora do servidor; testes, lint e build verdes.
