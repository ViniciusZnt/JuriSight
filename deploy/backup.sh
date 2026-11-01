#!/usr/bin/env bash
# Backup diário do Postgres de produção; guarda 7 dias.
# crontab do usuário deploy:  0 3 * * * /opt/jurisight/deploy/backup.sh >> /opt/backups/backup.log 2>&1
set -euo pipefail
cd "$(dirname "$0")/.."
DESTINO=/opt/backups
mkdir -p "$DESTINO"
arquivo="$DESTINO/jurisight-$(date +%F).dump"
docker compose -f docker-compose.prod.yml exec -T postgres pg_dump -U postgres -Fc jurisight > "$arquivo"
find "$DESTINO" -name 'jurisight-*.dump' -mtime +7 -delete
echo "$(date '+%F %T') backup ok: $arquivo ($(du -h "$arquivo" | cut -f1))"
