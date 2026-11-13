# Avaliação da busca

Para saber se uma mudança na busca melhorou ou piorou o resultado, o projeto tem uma
régua: um **conjunto-ouro** de pares (tese × acórdão) com **relevância 0–3** e **stance**
(fortalece / enfraquece / neutro), julgados por pessoas. O `benchmark` roda a busca (e o
pipeline de produção, S3) para cada tese e reporta as métricas. Só mede, não muda a busca.

Precisa do Postgres no ar e do índice Qdrant/BM25 construído (Quick Start do README,
passos 5 e 7). Variáveis do `.env` (ver `.env.example`): `OPENAI_GEN_MODEL` (escreve as
teses sintéticas e atribui o tema), `AVALIACAO_SEED` (sorteios; padrão 42) e
`AVALIACAO_ADJUDICADOR` (e-mail de quem decide os pares em que os avaliadores discordam).

## 1. `construir`: o conjunto-ouro

```bash
uv run python -m avaliacao.construir [--teses 100] [--sim]
```

Duas etapas **idempotentes** (dá para interromper e retomar):

1. **teses**: completa até `--teses` (reais das conversas e sintéticas; conversas de contas
   `@example.com`, dos testes E2E, ficam de fora). A OpenAI escreve as sintéticas e atribui o
   tema, que decide o split dev/teste. Mostra a estimativa e pede confirmação (`--sim` pula);
2. **pool**: para cada tese, une os 30 candidatos do híbrido, o top-10 do BM25 e o top-10 do denso.

## 2. Benchmark de rerankers (S0–S6)

Compara sete sistemas sobre as mesmas teses, com rótulos de duas pessoas:

1. **Teses dos advogados:** `uv run python -m avaliacao.teses_advogados importar ARQUIVO...`, com
   `docs/avaliacao/1-producao-de-teses.xlsx` preenchida (origem `advogado`; idempotente).
2. **`construir`** (seção 1): completa com teses sintéticas e monta o pool.
3. **Exportar os lotes:** `uv run python -m avaliacao.planilha_julgamento exportar [--teses id,... | --todas] [--pasta data/eval/lotes] [--seed 42]`
   gera um `.xlsx` por tese, embaralhado e sem pista do sistema de origem. Envie cada lote a **duas pessoas**.
4. **Importar:** `... planilha_julgamento importar ARQUIVO...` grava `humano:<email>`, rodada 1
   (linhas inválidas são avisadas e ignoradas; reimportar não duplica). Os pares pendentes vão
   ao adjudicador num lote exportado de novo; `... importar --adjudicacao ARQUIVO` grava a
   **rodada 2** e falha sem gravar se o e-mail do arquivo não for o do adjudicador.
5. **Rodar:** `uv run python -m avaliacao.benchmark rodar [--sistemas S0,...,S6] [--split dev|teste|todos] [--saida DIR]`
   grava `data/eval/runs/<data>_runs.json`.
6. **Relatório:** `uv run python -m avaliacao.benchmark relatorio data/eval/runs/<data>_runs.json`.

**Escala (0–3):** 0 outro problema jurídico; 1 mesmo ramo, mas outro pedido ou fato central;
2 mesmo pedido, com fato decisivo diferente ou só em parte; 3 mesmo problema e mesmo fato
decisivo ("eu citaria na peça"). O **stance** só vale para nota 2 ou 3; com 0 ou 1 grava-se `neutro`.

**Rótulo final** de um par com vários humanos: se o adjudicador julgou na rodada 2, vale o
dele. Senão, notas iguais valem a nota; diferença de 1 fica com a **menor**; diferença de 2 ou
mais (ou stance diferente com as duas notas >= 2) fica **pendente** e sai das métricas. Com um
só humano, vale o dele. O relatório lista cada pendente; **zere-os antes da medição final**. A
concordância (kappa, alfa, AC2) usa só a rodada 1.

**Sistemas.** Todos devolvem o top-20. S3 a S6 reordenam os mesmos 30 candidatos do S2, com a
mesma entrada (tese contra a ementa cortada em 1.200 caracteres). O embedding da OpenAI é
calculado uma vez por texto e reaproveitado, então a latência medida exclui o embedding repetido. Cada tese/sistema S2 a S6 grava `fora_dos_candidatos` (deve vir vazio) e falhas isoladas ficam em `teses_com_erro`, sem abortar a run.

| Sistema | O que é |
|---------|---------|
| S0 | BM25 sozinho |
| S1 | Denso sozinho (2 coleções, RRF) |
| S2 | Híbrido RRF, sem reranker |
| S3 | S2 + FlashRank (o de produção) |
| S4 | S2 + `gte-multilingual-reranker-base` |
| S5 | S2 + `bge-reranker-v2-m3` |
| S6 | S2 + `unicamp-dl/monoptt5-base` |

O S6 precisa do PyTorch (CPU), no grupo opcional `benchmark`: `uv sync --group benchmark` e
`uv run --group benchmark python -m avaliacao.benchmark rodar`. Sem o grupo, `rodar` com S6
falha logo no início.

**Métricas.** A principal é o **nDCG@10** (ganho 2^nota − 1). As demais: MRR@10, P@5, P@10,
Recall@10, Recall@20 e MAP@10 (relevante = nota >= 2) e **Judged@10** (fração do top-10 com
rótulo). Tese sem nenhum relevante fica fora das médias que dependem disso. O **teto** é o
nDCG@10 da melhor ordem possível dos 30 candidatos; os **perdidos** são os relevantes que BM25
ou denso trouxeram no top-10 e o híbrido deixou fora dos 30.

**Limitação:** o Recall@20 de S0 e S1 é enviesado para baixo, porque as posições 11 a 20 deles
só têm rótulo se caírem nos 30 do híbrido. Compare-os por Judged@10 e nDCG@10.

**Estatística.** Diferenças pareadas por tese (S3×S2, S4×S3, S5×S3, S6×S3, S0×S2, S1×S2): teste t
pareado com correção de **Holm**, Wilcoxon com Benjamini-Hochberg como checagem e IC95% por
bootstrap (10.000 reamostragens, seed fixa). Como a correção depende de quantos contrastes
entram (`m_holm` no JSON), **só cite p ajustado de uma run com todos os sistemas**.
