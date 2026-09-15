# Backup dos índices (Chroma + BM25)

> **Histórico.** Válido para a época do ChromaDB (embedded, até 2026-09-13). O
> vetorial migrou para Qdrant (ver README §Escalabilidade) — o Qdrant persiste no
> volume Docker `qdrant_data`; para backup, pare o container e copie o volume
> (`docker run --rm -v jurisight_qdrant_data:/data -v $(pwd):/backup alpine tar
> czf /backup/qdrant-backup.tar.gz -C / data`) ou use o endpoint de snapshot da
> própria API do Qdrant (`POST /collections/{nome}/snapshots`) com o serviço no
> ar. O procedimento do BM25 abaixo continua válido (não mudou).

Como salvar e restaurar os dois índices da indexação. Feito em 2026-07-23.

---

## Backup 2026-09-14 — Postgres + Qdrant + BM25 (atual)

Com a migração pro Qdrant e a autenticação real (`auth.usuarios`, com contas de
verdade), o backup passou a cobrir **três** coisas, não duas — Postgres agora
guarda dado que não dá pra simplesmente re-coletar do zero.

| Item | Método | Tamanho original | Comprimido | Arquivo |
|------|--------|-------------------|------------|---------|
| Postgres (`documentos` + `scraper_state` + `auth.usuarios`) | `pg_dump -Fc -Z 6` (lógico, todos os schemas) | ~1016 MB | 403 MB | `postgres-jurisight-2026-09-14.dump` |
| Qdrant (`chunks_completo` + `chunks_ementa`) | Snapshot da própria API (`POST /snapshots`, ao vivo, sem parar o serviço) | ~3.7 GB | 3.0 GB (formato do Qdrant já não comprime muito mais — vetores float não compactam bem) | `qdrant-full-2026-09-14.snapshot` |
| BM25 | `zstd -T0 -19` (igual ao procedimento de 2026-07-23) | 1.1 GB | 165 MB | `bm25-2026-09-14.pkl.zst` |

Total: ~3.5 GB. **Nenhum arquivo passa de 4 GB** — cabe em FAT32 sem precisar
quebrar em partes (diferente do backup de Chroma de 2026-07-23, que precisava).

Comandos usados:

```bash
# Postgres — dump lógico, formato custom (comprimido, restaura seletivamente)
docker exec jurisight_postgres pg_dump -U postgres -Fc -Z 6 \
    -f /tmp/jurisight-2026-09-14.dump jurisight
docker cp jurisight_postgres:/tmp/jurisight-2026-09-14.dump \
    dumps/backup_2026-09-14/postgres-jurisight-2026-09-14.dump
docker exec jurisight_postgres rm -f /tmp/jurisight-2026-09-14.dump

# Qdrant — snapshot ao vivo via API (sem downtime), depois baixa e limpa
curl -X POST "http://localhost:6333/snapshots?wait=true"
curl -o dumps/backup_2026-09-14/qdrant-full-2026-09-14.snapshot \
    "http://localhost:6333/snapshots/<nome-do-snapshot>"
curl -X DELETE "http://localhost:6333/snapshots/<nome-do-snapshot>"  # libera espaço no volume

# BM25
zstd -T0 -19 data/index/bm25.pkl -o dumps/backup_2026-09-14/bm25-2026-09-14.pkl.zst
```

Validado: `pg_restore --list` confirma as 3 tabelas com dados (`auth.usuarios`,
`public.documentos`, `public.scraper_state`); o checksum do snapshot do Qdrant
bate com o que a própria API calculou; `zstd -t` confirma o BM25 íntegro.
Checksums de todos os três em `dumps/backup_2026-09-14/SHA256SUMS.txt` — depois
de copiar pro pendrive, `sha256sum -c SHA256SUMS.txt` confirma que a cópia não
corrompeu nada.

### Restauração

```bash
# Postgres (banco novo/vazio — cria os schemas/tabelas a partir do dump)
docker exec -i jurisight_postgres pg_restore -U postgres -d jurisight --clean --if-exists \
    < postgres-jurisight-2026-09-14.dump

# Qdrant (com o container no ar; renomeie o arquivo pra bater com o padrão que a API espera)
docker cp qdrant-full-2026-09-14.snapshot jurisight_qdrant:/qdrant/snapshots/restaurar.snapshot
curl -X PUT "http://localhost:6333/snapshots/restaurar.snapshot/recover" \
    -H "Content-Type: application/json" -d '{"location": "file:///qdrant/snapshots/restaurar.snapshot"}'

# BM25
zstd -d bm25-2026-09-14.pkl.zst -o data/index/bm25.pkl
```

## O que é feito backup

| Índice | Caminho real | Tamanho |
|--------|--------------|---------|
| Chroma (vetorial) | `~/.local/share/jurisight/chroma/` | ~14G (sqlite + segmentos HNSW) |
| BM25 (lexical) | `data/index/bm25.pkl` | ~552M |


## Backup

O Chroma precisa do diretório inteiro (sqlite + segmentos), não só o `.sqlite3`. Comprime com zstd.

```bash
# Chroma → tar + zstd (~14G vira ~6.5G)
tar -C ~/.local/share/jurisight -cf - chroma | zstd -T0 -9 -o /tmp/chroma-2026-07-23.tar.zst

# BM25 → zstd direto
zstd -T0 -19 data/index/bm25.pkl -o /tmp/bm25-2026-07-23.pkl.zst
```

### Pendrive FAT32: split obrigatório

FAT32 não aceita arquivo > 4G. O `.tar.zst` do Chroma (6.5G) tem que ser quebrado:

```bash
split -b 3900M -d --verbose /tmp/chroma-2026-07-23.tar.zst /mnt/e/.../chroma-2026-07-23.tar.zst.part
```

Gera `.part00`, `.part01`. O BM25 (85M comprimido) cabe inteiro.

> Monte o pendrive como seu usuário para não precisar de sudo:
> `sudo mount -t drvfs E: /mnt/e -o uid=$(id -u),gid=$(id -g)`

## Validação (antes de apagar o original)

`zstd -t` descomprime em memória e confere os checksums embutidos — se passar, não corrompeu.

```bash
# BM25
zstd -t bm25-2026-07-23.pkl.zst

# Chroma (junta as partes e testa o stream inteiro)
cat chroma-2026-07-23.tar.zst.part* | zstd -t
```

Só apague a cópia de origem depois que os dois testes passarem.

## Restauração

```bash
# Chroma
cat chroma-2026-07-23.tar.zst.part* > chroma.tar.zst
zstd -dc chroma.tar.zst | tar -C ~/.local/share/jurisight -xf -

# BM25
zstd -d bm25-2026-07-23.pkl.zst -o data/index/bm25.pkl
```
