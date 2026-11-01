#!/usr/bin/env bash
# Traz para esta máquina os dumps diários do Postgres de produção (/opt/backups na VPS).
# Uso (no WSL, com a chave SSH carregada no agente):  ./deploy/puxar-backups.sh
# Destino: ~/JuriSight-backups/diarios/ (só acrescenta; nada é apagado aqui).
set -euo pipefail
VPS="${VPS:-deploy@16.5.6.82}"
DESTINO="${DESTINO:-$HOME/JuriSight-backups/diarios}"
mkdir -p "$DESTINO"
rsync -a --info=stats1 --include='jurisight-*.dump' --exclude='*' "$VPS:/opt/backups/" "$DESTINO/"
ls -lh "$DESTINO" | tail -n +2
