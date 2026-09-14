# Backup dos índices (Chroma + BM25)

> **Histórico.** Válido para a época do ChromaDB (embedded, até 2026-09-13). O
> vetorial migrou para Qdrant (ver README §Escalabilidade) — o Qdrant persiste no
> volume Docker `qdrant_data`; para backup, pare o container e copie o volume
> (`docker run --rm -v jurisight_qdrant_data:/data -v $(pwd):/backup alpine tar
> czf /backup/qdrant-backup.tar.gz -C / data`) ou use o endpoint de snapshot da
> própria API do Qdrant (`POST /collections/{nome}/snapshots`) com o serviço no
> ar. O procedimento do BM25 abaixo continua válido (não mudou).

Como salvar e restaurar os dois índices da indexação. Feito em 2026-07-23.

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
