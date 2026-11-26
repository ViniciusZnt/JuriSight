#!/usr/bin/env bash
# Atualiza a produção. O job deploy do ci.yml roda este script no runner self-hosted da VPS;
# também dá para rodar à mão, como o usuário deploy.
set -euo pipefail

cd /opt/jurisight
git pull --ff-only
docker compose -f docker-compose.prod.yml up -d --build
# O git pull troca os arquivos montados (Caddyfile, prometheus.yml, blackbox.yml,
# loki.yml, config.alloy) por novos inodes e o Compose não recria o contêiner só
# por isso; o Grafana só lê o provisionamento ao iniciar.
docker compose -f docker-compose.prod.yml restart caddy prometheus blackbox loki alloy grafana
docker image prune -f
