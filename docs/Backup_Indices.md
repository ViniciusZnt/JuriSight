# Backup dos dados: Postgres, Qdrant e BM25

O que precisa de cópia, em ordem de custo para refazer:

| Item | Onde fica | Método |
|------|-----------|--------|
| Postgres (`documentos`, `scraper_state`, `auth.*`, `conversas`, ...) | container `jurisight_postgres` | `pg_dump -Fc` (lógico, todos os schemas) |
| Qdrant (`chunks_completo` e `chunks_ementa`) | volume `qdrant_data` | snapshot pela API, com o serviço no ar |
| BM25 (lexical) | diretório `data/index/bm25s_index` (`BM25_INDEX_PATH`) | `tar` + `zstd` |

O Postgres tem dados que não dá para re-coletar do zero (contas, conversas, correções
de provimento). Qdrant e BM25 se refazem com `indexing/run.py`, mas leva horas. Na VPS,
o dump do Postgres é diário (`deploy/backup.sh`, 7 dias; ver
`docs/deploy/2026-11-01-deploy-vps.md`).

## Backup

```bash
# Postgres: dump lógico em formato custom (comprimido, restaura seletivamente)
docker exec jurisight_postgres pg_dump -U postgres -Fc -Z 6 -f /tmp/jurisight.dump jurisight
docker cp jurisight_postgres:/tmp/jurisight.dump dumps/postgres-jurisight-$(date +%F).dump
docker exec jurisight_postgres rm -f /tmp/jurisight.dump

# Qdrant: snapshot ao vivo (sem downtime), baixa e apaga para liberar espaço no volume
curl -X POST "http://localhost:6333/snapshots?wait=true"
curl -o dumps/qdrant-full-$(date +%F).snapshot "http://localhost:6333/snapshots/<nome-do-snapshot>"
curl -X DELETE "http://localhost:6333/snapshots/<nome-do-snapshot>"

# BM25: o índice é um diretório
tar -C data/index -cf - bm25s_index | zstd -T0 -19 -o dumps/bm25s-$(date +%F).tar.zst
```

Vetores float não comprimem bem: o snapshot do Qdrant fica perto do tamanho original
(~3 GB em 2026-09). Em pendrive FAT32 (sem arquivo acima de 4 GB), quebre o que passar
disso com `split -b 3900M -d`. Monte o pendrive como seu usuário, sem sudo:
`sudo mount -t drvfs E: /mnt/e -o uid=$(id -u),gid=$(id -g)`.

## Validação (antes de apagar o original)

```bash
pg_restore --list postgres-jurisight-*.dump      # lista as tabelas com dados
zstd -t bm25s-*.tar.zst                          # confere os checksums embutidos
sha256sum -c SHA256SUMS.txt                      # depois de copiar, se gerou os checksums
```

## Restauração

```bash
# Postgres (banco novo/vazio: recria schemas e tabelas a partir do dump)
docker exec -i jurisight_postgres pg_restore -U postgres -d jurisight --clean --if-exists \
    < postgres-jurisight-<data>.dump

# Qdrant (container no ar)
docker cp qdrant-full-<data>.snapshot jurisight_qdrant:/qdrant/snapshots/restaurar.snapshot
curl -X PUT "http://localhost:6333/snapshots/restaurar.snapshot/recover" \
    -H "Content-Type: application/json" -d '{"location": "file:///qdrant/snapshots/restaurar.snapshot"}'

# BM25
zstd -dc bm25s-<data>.tar.zst | tar -C data/index -xf -
```
