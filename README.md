# JuriSight

> Sistema de Análise Contextual de Jurisprudência Trabalhista com IA

**Autor:** Vinicius Gabriel Zanatta\
**Curso:** Engenharia de Software — Católica SC\
**Linha de Projeto:** IA (GraphRAG + NLP + Busca Híbrida)

---

## O que é

JuriSight recebe o documento de um caso trabalhista e a intenção
argumentativa do advogado, e retorna jurisprudências do TST —
acórdãos, súmulas, OJs e precedentes normativos — ordenados pela
hierarquia das fontes jurídicas e alinhados à tese.

**Problema resolvido:** Advogados trabalhistas gastam ~5h semanais
pesquisando jurisprudência em ferramentas que retornam resultados sem
alinhamento argumentativo e sem distinguir o peso jurídico de cada tipo
de documento.

---

## Pipeline

```
Portal TST (Falcão)
    → [scraper/run.py]          ← coleta via requests + delay adaptativo
    → [PostgreSQL]              ← source of truth
    → [SAC Chunking]
    → [Poly-Vector Embeddings]  ← OpenAI text-embedding-3-small (1536d)
    → [Qdrant]                  ← busca semântica (vetores em disco, HNSW em RAM)
    → [BM25 Index]              ← busca lexical (bm25s, mmap)
    → [FastAPI + RRF]           ← fusão dos rankings (pool de 30 candidatos)
    → [Cross-Encoder Rerank]    ← reordena por relevância real (FlashRank, ONNX)
    → [Sort Categórico]         ← hierarquia jurídica
    → [Next.js]
```

Custo: o LLM e o enriquecimento de query rodam **100% locais** (Ollama). Só os
**embeddings** usam a OpenAI (`text-embedding-3-small`) — **~US$ 8 uma única vez**
para indexar todo o corpus; por consulta, o custo é desprezível.

---

## Estrutura

```
jurisight/
├── auth/                    ← autenticação real (hash de senha, JWT, acesso a auth.usuarios)
├── conversations/           ← histórico de busca persistido (public.conversas, ver §Conformidade)
├── avaliacao/               ← harness de avaliação da busca (conjunto-ouro, juiz Jev, métricas; ver §Avaliação da busca)
│
├── scraper/
│   ├── run.py              ← ponto de entrada da coleta
│   ├── api.py              ← cliente HTTP (requests.Session)
│   ├── core.py             ← loop de coleta com delay adaptativo
│   ├── db_writer.py        ← PostgresStore + estado da coleta (scraper_state)
│   ├── html_parser.py      ← extração de seções do HTML dos acórdãos
│   ├── provimento_jev*.py  ← provimento com o Jev: classificador, store e CLI (ver §Provimento com o Jev)
│   ├── items/
│   ├── pipelines/
│   └── settings.py         ← configurações Scrapy (uso futuro)
│
├── processing/
│   ├── chunking/
│   ├── ner/
│   └── embeddings/
│
├── indexing/
│   ├── vector_store/
│   └── graph/
│
├── query/
│   ├── enrichment/          ← PDF Extractor, Query Enrichment (LLM), Query Builder
│   ├── search/              ← Hybrid Search (RRF), Doc Retriever, Categorical Sort, Result Formatter
│   └── api/                 ← FastAPI: /enrich, /query, /document/{id}, /health, /auth/*, /conversas
│
├── frontend/                ← interface Next.js (App Router)
│   ├── src/
│   │   ├── app/              ← rotas (home, resultados, decisão, revisão, salvos, login)
│   │   ├── components/
│   │   └── lib/
│   └── package.json
│
├── data/
│   ├── raw/
│   ├── processed/
│   └── index/
│
├── docs/
├── tests/
├── .env.example
├── pyproject.toml
└── README.md
```

---

## Pré-requisitos

| Ferramenta | Versão mínima | Observação              |
|------------|---------------|-------------------------|
| Python     | 3.13          | Gerenciado pelo uv      |
| uv         | qualquer      | Gerenciador de pacotes Python |
| Node.js    | 20+           | Para o frontend Next.js |
| pnpm       | qualquer      | Gerenciador de pacotes do frontend |
| Docker     | 24+           | Para o PostgreSQL       |
| Ollama     | qualquer      | LLM local (enriquecimento de query) |
| Chave OpenAI | —           | Embeddings (`text-embedding-3-small`) — exige crédito pré-pago |
| WSL2       | —             | Obrigatório no Windows  |

---

## Quick Start

### 1 — Instalar uv

```bash
curl -Ls https://astral.sh/uv/install.sh | sh
uv --version
```

### 2 — Instalar dependências

```bash
uv sync
```

### 3 — Ollama (LLM local para enriquecimento de query)

O Ollama roda só o LLM de enriquecimento de query (`llama3.2:3b`). **Os embeddings
não usam Ollama** — são gerados pela OpenAI (passo 4). Há duas formas de rodar —
escolha **uma** (ambas usam a porta 11434):

**Opção A — nativo (instala na máquina, sobe sozinho como serviço):**

```bash
ollama pull llama3.2:3b
```

**Opção B — via Docker (junto do Postgres, no passo 5):** o modelo é baixado
dentro do container e persiste no volume `ollama_models`:

```bash
docker compose up -d ollama
docker compose exec ollama ollama pull llama3.2:3b
```

De qualquer forma, o servidor deve responder em `http://localhost:11434`:

```bash
ollama list            # lista os modelos (só responde se o servidor está no ar)
curl -s http://localhost:11434/api/tags   # deve retornar JSON com os modelos
```

Observações:
- Se `ollama serve` reclamar de `address already in use`, **não é erro** — o
  servidor já está rodando; não precisa iniciá-lo de novo.
- Não rode as duas opções ao mesmo tempo: a porta 11434 só comporta uma. Para
  usar o Docker com o Ollama nativo instalado, pare o nativo antes
  (`sudo systemctl stop ollama`).

### 4 — Configurar variáveis de ambiente

```bash
cp .env.example .env
```

| Variável            | Padrão                                              | Descrição                        |
|---------------------|-----------------------------------------------------|----------------------------------|
| `DATABASE_URL`      | `postgresql://postgres:postgres@localhost:5432/jurisight` | Conexão com o PostgreSQL   |
| `OPENAI_API_KEY`    | —                                                   | Chave da OpenAI (embeddings) — **obrigatória**, exige crédito pré-pago |
| `OPENAI_EMBED_MODEL`| `text-embedding-3-small`                            | Modelo de embeddings (1536d)     |
| `QDRANT_URL`        | `http://localhost:6333`                             | Endpoint do Qdrant (banco vetorial, sobe via `docker compose`) |
| `BM25_INDEX_PATH`   | `./data/index/bm25s_index`                          | Índice lexical BM25 (diretório — matriz esparsa `bm25s`, carregada via mmap) |
| `OLLAMA_HOST`       | `http://localhost:11434`                            | Endpoint do Ollama (Query Enrichment) |
| `OLLAMA_MODEL`      | `llama3.2:3b`                                       | Modelo usado no enriquecimento de query e na sumarização de PDFs longos |
| `API_HOST` / `API_PORT` | `0.0.0.0` / `8000`                              | Endereço do backend FastAPI      |
| `API_RELOAD`        | `true`                                              | Reload automático do Uvicorn em dev |
| `CORS_ORIGINS`      | `http://localhost:3000`                             | Origens permitidas (a interface web em dev) |

> A chave da OpenAI vai só no `.env` (gitignored) — **nunca** commitada. Sem crédito
> pré-pago na conta, a API responde `429 insufficient_quota`.

> **Atalho:** com `.env` preenchido (`OPENAI_API_KEY` e `JWT_SECRET_KEY`, gere a
> segunda com `openssl rand -hex 32`) e a coleta/indexação já feitas (passos 6-7,
> só na primeira vez), `./run.sh` faz os passos 5, 8 e 9 de uma vez — sobe
> infra + backend + frontend com um comando só, espera cada um responder antes
> de seguir, e Ctrl+C encerra backend+frontend (a infra continua no ar).

### 5 — Subir a infraestrutura (Docker)

```bash
docker compose up -d          # sobe Postgres + Qdrant (+ Ollama, se optar pela opção B do passo 3)
docker compose ps             # aguarda "healthy"
```

Para subir só o Postgres (usando o Ollama nativo): `docker compose up -d postgres qdrant`.

A tabela `documentos` é criada automaticamente na primeira execução do scraper.

> **Qdrant é um serviço** (imagem `qdrant/qdrant`, portas 6333/REST e 6334/gRPC),
> ao contrário do antigo ChromaDB embedded. Os vetores ficam em disco (mmap,
> quantizados em int8 em RAM pra busca inicial) dentro do volume `qdrant_data`;
> o grafo HNSW fica em RAM (ver §Escalabilidade).

Para parar sem apagar dados:

```bash
docker compose stop
```

Para parar e apagar tudo:

```bash
docker compose down -v
```

### 6 — Executar coleta

O scraper detecta automaticamente o último dia já coletado no banco e
continua de onde parou. Se o banco estiver vazio, começa de `2023-01-01`.

```bash
# Coleta acórdãos (continua do banco automaticamente)
uv run python scraper/run.py

# Forçar período específico
uv run python scraper/run.py --from 2024-01-01 --to 2024-06-30

# Coletar outra coleção
uv run python scraper/run.py --colecao sumulas
uv run python scraper/run.py --colecao ojs
uv run python scraper/run.py --colecao precedentes

# Interrompido? Só rodar de novo — o estado no banco retoma de onde parou
uv run python scraper/run.py
```

**Coleções disponíveis:** `acordaos` · `sumulas` · `ojs` · `precedentes`

O progresso é salvo no PostgreSQL (tabela `scraper_state`, por coleção) a cada página coletada.

### 7 — Indexar documentos (SAC Chunking + Poly-Vector + BM25)

Lê os documentos do PostgreSQL, gera os chunks e embeddings (OpenAI) e popula o
Qdrant e o índice BM25. Roda **depois** da coleta. Requer a `OPENAI_API_KEY`
(passo 4). A carga completa leva ~4-5h e é resumível — o delta pula o que já está
no Qdrant.

```bash
# Teste rápido (100 docs)
uv run python indexing/run.py --reset --limit 100

# Carga completa em background
nohup uv run python indexing/run.py --reset > indexing.log 2>&1 &

# Retomar após queda ou falhas (sem --reset, o delta continua)
uv run python indexing/run.py
```

### 8 — Rodar a API

Requer Postgres no ar (passo 5), Ollama respondendo (passo 3) e o índice
Qdrant/BM25 já construído (passo 7) — sem eles, os endpoints sobem mas
`/query`/`/enrich` falham ao tentar acessá-los.

```bash
uv run python main.py
```

Sobe em [http://localhost:8000](http://localhost:8000). Endpoints:
`POST /enrich` (PDF e/ou intenção argumentativa → `EstruturaArgumentativa`),
`POST /query` (busca híbrida → lista de resultados), `GET /document/{id}`
(detalhe completo), `GET /health`.

### 9 — Rodar interface

```bash
cd frontend
pnpm install
pnpm dev
```

Abre em [http://localhost:3000](http://localhost:3000).

---

## Testes (frontend)

O frontend tem dois níveis de teste, ambos em `frontend/`:

| Tipo                  | Ferramenta                          | O que cobre                                                        |
|------------------------|--------------------------------------|---------------------------------------------------------------------|
| Unitário / componente | Jest + React Testing Library         | Lógica pura (`initialsOf`, `groupByRecency`, `findDecision`, `OUTCOME_CONFIG`) e componentes (`OutcomeBadge`, `Chip`, `StepIndicator`, `ActionButton`), além do contexto `useSaved` (salvar, remover, persistir) |
| End-to-end             | Cypress                              | Login/cadastro e proteção de rotas, fluxo de consulta (com e sem PDF → revisão → resultados), filtros/ordenação/exportar resultados, e os fluxos alternativos do RFC (FA02, FA03, FA04, FA05) |

```bash
cd frontend

# Unitário/componente
pnpm test              # roda uma vez
pnpm test:watch        # modo watch

# End-to-end (precisa do dev server rodando em localhost:3000)
pnpm cypress:open      # interface interativa
pnpm cypress:run       # headless
pnpm test:e2e          # sobe o dev server sozinho, roda o Cypress headless e derruba o server no final
```

> Ainda não há testes de backend/integração — o pipeline de IA e a API ainda não existem
> (ver [Pipeline](#pipeline)). O frontend inteiro roda sobre dados mockados até lá.

---

## Testes (backend)

```bash
uv run pytest
```

| Módulo | O que cobre |
|--------|-------------|
| `scraper`/`processing`/`indexing` | Parsing HTML, chunking SAC, embeddings (OpenAI mockado), BM25 |
| `query/enrichment` | PDF Extractor (pdfplumber mockado), Query Enrichment (Ollama mockado, RN05), Query Builder |
| `query/search` | Hybrid Search/RRF (Qdrant/BM25 mockados), Categorical Sort, Result Formatter |
| `query/api` | `/enrich`, `/query`, `/document/{id}`, `/health`, `/auth/*`, `/conversas*` via `TestClient`, com `dependency_overrides` no lugar de Postgres/Qdrant/Ollama reais |
| `auth` / `conversations` | Hashing de senha, JWT, `UsuarioStore`/`ConversaStore` (isolamento entre usuários incluso) |
| `avaliacao` / `/avaliacao/*` | Métricas (nDCG, Recall, kappa), juiz Jev com cliente fake, pooling, amostra estratificada, `construir`/`eval`/passo 0, rotas de rotulação via `TestClient`; o store contra Postgres real só roda com `DATABASE_URL` |
| `scraper/provimento_jev*` | Perguntas e mapa para o enum, classificador com cliente fake, backfill retomável, `comparar`/`conferir`/`aplicar` com store falso; o store contra Postgres real só roda com `DATABASE_URL` |

> Todos os testes rodam sem infraestrutura real (Postgres/Qdrant/Ollama/OpenAI) —
> clientes externos são substituídos por fakes injetados. Um smoke test manual de
> ponta a ponta (com a infra de verdade no ar) é o passo 8 do Quick Start.

---

## Avaliação da busca

Para saber se uma mudança na busca melhorou ou piorou o resultado, o projeto tem
uma régua: um **conjunto-ouro** de pares (tese × acórdão) com **relevância 0–3** e
**stance** (fortalece / enfraquece / neutro). A especialista (Alexia) rotula uma
amostra pequena; o **Jev** (TypeSafe System One) rotula o resto, depois de
calibrado contra ela. O comando `eval` roda a busca para cada tese e reporta
**nDCG@10**, **Recall@20**, a fração de "fortalece" entre os relevantes do top-10 e
a fração de resultados **não julgados** no top-10. Esta etapa só mede, não muda a
busca. Racional e decisões: [`docs/superpowers/specs/2026-10-17-harness-avaliacao-design.md`](docs/superpowers/specs/2026-10-17-harness-avaliacao-design.md).

Variáveis novas no `.env` (ver `.env.example`):

| Variável            | Padrão          | Descrição |
|---------------------|-----------------|-----------|
| `TYPESAFE_API_KEY`  | —               | Chave da TypeSafe (juiz Jev) — **obrigatória** |
| `TYPESAFE_MODEL`    | `jev-1.13.0`    | Versão do Jev. Fixada de propósito: o alias `jev-latest` muda sozinho e invalidaria a comparação entre execuções. Trocar o modelo exige **julgar tudo de novo**: `rotulos_finais` aceita o Jev rodada 1 de qualquer modelo, então rótulos de modelos diferentes se misturariam |
| `OPENAI_GEN_MODEL`  | `gpt-4o-mini`   | Modelo da OpenAI que escreve as teses sintéticas |
| `AVALIACAO_EMAILS`  | —               | E-mails (separados por vírgula) que podem usar a tela de rotulação |
| `AVALIACAO_SEED`    | `42`            | Seed dos sorteios (amostra e split dev/teste) |

Precisa do Postgres no ar e do índice Qdrant/BM25 construído (Quick Start, passos 5 e 7).

### 1 — Passo 0: o Jev funciona em português?

Antes de construir o conjunto inteiro, testa-se o Jev numa amostra mínima
(5 teses × 4 acórdãos, julgados duas vezes):

```bash
uv run python -m avaliacao.passo_zero preparar            # gera data/eval/passo_zero.csv
# a Alexia preenche as colunas relevancia_alexia (0-3) e stance_alexia no CSV
uv run python -m avaliacao.passo_zero comparar            # grava os rótulos e mostra os kappas
```

Flags: `preparar [--teses 5] [--por-tese 4] [--csv ...] [--sim]` e
`comparar [--csv ...] [--rotulador email]`.

- O CSV não traz a nota do Jev, para não enviesar a Alexia. As colunas são
  `par_id,tese,ementa,fundamentacao_inicio,link,relevancia_alexia,stance_alexia`: a
  `tese` traz pedido, tese central e normas (`Pedido: … | Tese: … | Normas: a; b`) e
  `fundamentacao_inicio` traz os mesmos 3.000 caracteres de fundamentação que o Jev
  recebe, para a Alexia julgar a mesma evidência.
- O `preparar` pula acórdãos que já originaram alguma tese no banco e sorteia a mais
  para ainda gerar `--teses` teses novas.
- O `preparar` **recusa sobrescrever** um CSV que já tenha rótulos preenchidos.
- `--rotulador` usa por padrão o **primeiro e-mail de `AVALIACAO_EMAILS`**. Esse deve
  ser o mesmo e-mail da conta usada na tela `/avaliacao`: o juiz humano é gravado
  como `humano:<email>` (sem espaços nas pontas e em minúsculas; o `comparar` normaliza
  o e-mail assim), e e-mails diferentes viram rotuladores diferentes.
- Decisão a partir do relatório: seguir, usar o Jev só para relevância, ou trocar o juiz.

### 2 — `construir`: o conjunto-ouro

```bash
uv run python -m avaliacao.construir [--teses 100] [--rodadas 2] [--sim]
```

Quatro etapas **idempotentes** (cada uma pula o que já existe, então dá para
interromper e retomar de onde parou):

1. **teses** — completa até `--teses` (reais das conversas + sintéticas filtradas;
   conversas de contas `@example.com`, usadas nos testes E2E, ficam de fora);
2. **pool** — une o top-20 de BM25, vetorial e pipeline completo para cada tese;
3. **julgamento** — o Jev julga os pares ainda sem julgamento, nas rodadas `1..--rodadas`;
4. **amostra** — escolhe os pares que a Alexia vai rotular (75 sorteados + 75 de menor confiança).

As etapas pagas (teses sintéticas na OpenAI e julgamento no Jev) mostram a
estimativa e **pedem confirmação**; `--sim` pula. Ordem de grandeza: ~1.300 tokens
do Jev por chamada e ~40 pares por tese x rodadas (100 teses x 40 pares x 2
rodadas = ~8.000 chamadas, ~10 milhões de tokens). A amostra só é montada quando
**todos os pares têm a rodada 1 julgada**; se alguma chamada falhou, rode de novo.

### 3 — Tela `/avaliacao`: a Alexia rotula

Abra `http://localhost:3000/avaliacao` (não há link na sidebar; o acesso é pela URL
direta). Exige login **e** e-mail em `AVALIACAO_EMAILS`. A tela mostra a tese no
topo e um acórdão por vez, **sem a nota do Jev**, com progresso.

| Tecla | Ação |
|-------|------|
| `1` `2` `3` `4` | Relevância 0, 1, 2, 3 |
| `F` `E` `N`     | Stance: fortalece, enfraquece, neutro |

Escolha a relevância e o stance; quando os dois estão escolhidos, o rótulo é salvo e o
próximo acórdão aparece, então dá para parar e voltar depois. Se o envio falhar, a
seleção fica na tela e dá para tentar de novo.

### 4 — `eval`: medir a busca

```bash
uv run python -m avaliacao.eval --split dev [--saida data/eval/runs/]
uv run python -m avaliacao.eval --split teste     # só para a medição final
```

Não chama a API do Jev, mas roda a busca real para cada tese: precisa de Qdrant, do
índice BM25 e do embedding da OpenAI (além do Postgres). Se a busca de uma tese falhar,
ela é avisada em stderr, fica fora das médias (conta como excluída) e seu id vai para
`teses_com_erro` no JSON. Grava um JSON em `data/eval/runs/` com as
métricas, o **commit** git, o **modelo do Jev**, o `perguntas_sha` (hash das
perguntas feitas ao Jev) e a **calibração**: kappa de relevância (ponderado) e de
stance contra a Alexia — **aprovado** se os dois forem **>= 0,6** — e o limite de
confiança a partir do qual o Jev acerta >= 80%. Use `dev` para iterar; o split
`teste` deve ser usado **só na medição final**, senão deixa de ser uma medida
independente.

---

## Provimento com o Jev

A coluna `documentos.provimento` vem de uma regex sobre o dispositivo, que diz se o
recurso foi aceito, mas não quem ganhou: "recurso negado" é vitória do trabalhador
quando quem recorreu foi a empresa. Esta etapa pergunta ao Jev, para cada acórdão, o
**resultado** do recurso, o **recorrente** e **quem é favorecido**, guarda as respostas
com probabilidades na tabela `provimento_jev` e, depois de uma conferência manual, pode
passar a usar o resultado do Jev em `documentos.provimento`. A regex continua gravada
ao lado (`provimento_regex`). Racional e decisões: [`docs/superpowers/specs/2026-10-20-provimento-jev-design.md`](docs/superpowers/specs/2026-10-20-provimento-jev-design.md).

Usa `TYPESAFE_API_KEY` e `TYPESAFE_MODEL` (padrão `jev-1.13.0`), como a avaliação, e
precisa do Postgres no ar. Os comandos, na ordem de uso:

```bash
# 1. Classifica os acórdãos pendentes (mostra a estimativa e pede confirmação)
uv run python -m scraper.provimento_jev_cli classificar [--limite N] [--lote 500] [--max-workers 8] [--sim]

# 2. Compara regex x Jev e escreve o CSV de divergências (data/eval/provimento_divergencias.csv)
uv run python -m scraper.provimento_jev_cli comparar [--amostra 100] [--csv CAMINHO]

# 3. Preencha a coluna quem_acertou do CSV: jev, regex, ambos ou nenhum

# 4. Resume a conferência
uv run python -m scraper.provimento_jev_cli conferir [--csv CAMINHO]

# 5. Mostra o que mudaria; só escreve em documentos.provimento com --confirmar
uv run python -m scraper.provimento_jev_cli aplicar [--confianca-min 0.8] [--confirmar]
```

- **Custo:** ~1.600 tokens por acórdão, cerca de **110 M tokens** para o acervo inteiro
  (~69 mil). O `classificar` imprime a estimativa e pergunta `s/N` antes de chamar o
  Jev; `--sim` pula a pergunta.
- **Retomável:** o `classificar` pode ser interrompido (Ctrl-C) e rodado de novo. Só
  classifica o que ainda não tem linha com o mesmo modelo e as mesmas perguntas.
- **`aplicar`:** sem `--confirmar` apenas imprime as transições (`ATUAL → NOVO: n`) e
  quantas linhas ficaram abaixo do limite de confiança (`--confianca-min`, de 0 a 1), separando as que mudariam das que não mudam.
  Com `--confirmar`, grava só onde a confiança atinge o limite e o valor muda.
- **Voltar à regex:** `uv run python utils/reclassify.py` recalcula a coluna a partir do texto.
- **Ainda não usados:** `favorece` e `recorrente` ficam guardados, mas a busca ainda
  não os usa; só o resultado entra em `documentos.provimento`.
- **Excel em português:** o `conferir` aceita o CSV com `,` ou `;` como separador. Se o
  arquivo não tiver a coluna `quem_acertou`, o `conferir` avisa e sai com código 2.
- **Conferência protegida:** o `comparar` recusa sobrescrever um CSV que já tenha
  `quem_acertou` preenchido (ou que não tenha a coluna), para não apagar a conferência manual.
- **Modelo fixo:** `TYPESAFE_MODEL` terminado em `-latest` é recusado; use uma versão
  fixa (ex.: `jev-1.13.0`).

---

## Hierarquia Categórica dos Documentos

| Categoria | Tipo                        | Descrição                                          |
|-----------|-----------------------------|----------------------------------------------------|
| 1         | Súmula                      | Entendimento consolidado — máximo peso argumentativo |
| 2         | Orientação Jurisprudencial (OJ) | Interpretação técnica oficial                  |
| 3         | Precedente Normativo        | Regra aplicável por categoria profissional         |
| 4         | Acórdão                     | Decisão colegiada                                  |
| 5         | Decisão Monocrática         | Tendência recente de um ministro                   |

---

## Stack

| Tecnologia         | Função                                      |
|--------------------|---------------------------------------------|
| requests           | Coleta do portal TST (Falcão)               |
| PostgreSQL         | Source of truth — documentos completos      |
| Qdrant             | Banco vetorial — busca semântica (vetores/HNSW em disco) |
| Ollama / Llama 3.2 3B | Query enrichment local + sumarização de PDFs longos |
| OpenAI text-embedding-3-small | Embeddings (1536d)              |
| bm25s              | Busca lexical — índice BM25 (matriz esparsa, mmap) |
| FlashRank          | Re-ranking pós-RRF — cross-encoder ONNX (sem PyTorch), multilíngue |
| pdfplumber         | Extração de texto do PDF do usuário         |
| FastAPI / Uvicorn  | Backend — API REST, fusão RRF dos rankings  |
| Next.js / React    | Interface do usuário                        |
| Jest + React Testing Library | Testes unitários e de componente (frontend) |
| Cypress            | Testes end-to-end (frontend)                |

---

## Escalabilidade

**Migração ChromaDB → Qdrant concluída em 2026-09-13.** O ChromaDB era RAM-bound:
o HNSW carregava o índice inteiro em memória, e com ~69k acórdãos (~470k pontos
somando as duas coleções Poly-Vector) isso já travava numa máquina com RAM
limitada ([docs](https://docs.trychroma.com/guides/deploy/performance)).

O Qdrant (`indexing/vector_store/qdrant_store.py`) guarda os vetores brutos em
disco (mmap, `VectorParams.on_disk=True` — a parte grande, ~2.4GB pra 400k
pontos de 1536 dims). Troca localizada, como planejado: só o `ChromaStore`
virou `QdrantStore` — `HybridSearch`, `query/api/app.py` e `indexing/run.py`
não mudaram de lógica, só de import. Dados migrados com
`indexing/vector_store/migrate_chroma_to_qdrant.py` (lê o Chroma antigo, sem
apagá-lo, e faz upsert idempotente no Qdrant).

**Ajuste de 2026-09-28 — grafo HNSW em RAM + quantização.** A primeira versão
também colocava o grafo HNSW em disco (`HnswConfigDiff.on_disk=True`), na
teoria pra economizar RAM. Na prática, cada busca nova percorre o grafo fazendo
I/O a disco a cada salto — medido nesta infra, 80-125s por busca. O grafo em si
(só os links entre vizinhos) custa dezenas de MB pra 400k pontos — bem menos
que os vetores — então voltou pra RAM (`on_disk=False`, o default do Qdrant).
Também foi ligada quantização escalar int8 nas duas coleções: uma versão
comprimida (~4x menor) de cada vetor fica em RAM pra busca inicial no grafo, e
só os poucos candidatos finais são re-pontuados com o vetor original em disco
— reduz ainda mais o I/O por busca. Resultado combinado (com a mudança do BM25
abaixo): a mesma busca caiu de 80-330s para 3-5s.

BM25 migrou de `rank_bm25` para `bm25s` (2026-09-28). O `rank_bm25` guardava um
dict Python por documento — pra ~400k chunks isso media ~6-7GB desserializado
em RAM no processo do backend, que numa máquina de 11GB empurrava o sistema
inteiro pra swap (confirmado via `pswpin`/`pswpout` subindo durante as buscas
lentas — o Qdrant ficava competindo com o swap pela banda de disco, daí os
80-125s do parágrafo acima serem ainda piores na prática). `bm25s` guarda o
índice como matriz esparsa CSC e carrega via `mmap=True`
(`indexing/lexical/bm25_builder.py`) — fica em disco, paginado sob demanda,
igual ao Qdrant já fazia com os vetores. RAM do processo do backend: de ~7.4GB
para ~300MB.

**Re-ranking pós-RRF (2026-10-04).** RRF funde bem o RANK de cada canal
(Qdrant completo, Qdrant ementa, BM25), mas não lê o conteúdo — só a posição
relativa. `query/search/reranker.py` adiciona um cross-encoder (FlashRank,
`ms-marco-MultiBERT-L-12`, ONNX — sem PyTorch/Transformers de propósito, pra
não pesar a RAM que o BM25 acabou de liberar) que pontua tese+ementa juntas e
reordena o pool do RRF antes do corte final. Dois problemas de performance
reais até ficar aceitável: (1) mandar todas as passagens num só
`RerankRequest` tinha custo super-linear (~49s pra 50) — uma chamada por
passagem, paralelizada em 8 threads, caiu pra ~5s; (2) uma única ementa-outlier
(a base tem casos >60 mil caracteres) travava o lote inteiro — corrigido
truncando a 1200 chars antes de reranquear. `N_CANDIDATOS_PARA_RERANK = 30`
(não os 50 "de livro-texto"): a busca híbrida pede 5x esse número por canal,
então o pool também pesa na busca, não só no re-ranking — 30 é o equilíbrio
que manteve o re-ranking em si consistente (~2s) sem inflar demais a busca.

---

## Autenticação — pendências futuras

A autenticação real (`auth/`, `query/api/auth_routes.py`) cobre hoje o essencial e
funcional: cadastro, login, logout, sessão via cookie httpOnly, senha com Argon2id,
JWT, proteção contra timing attack e contra CSRF via `<form>`. Deliberadamente
**não** implementado (escopo cortado a pedido — não é trabalho pela metade, é
trabalho que ainda não começou):

- **Verificação de e-mail** — hoje qualquer e-mail digitado é aceito sem confirmação.
- **Recuperação de senha** ("esqueci minha senha") — a tela `/esqueci-senha` existe
  no frontend mas não fala com nenhum backend real.
- **2FA** (segundo fator de autenticação).
- **Rate limiting / lockout** de tentativas de login (força bruta hoje não tem
  nenhum limite além do custo do próprio Argon2id).

Ver `auth/SCHEMA.md` para o que já foi propositalmente deixado de fora do schema
(is_superuser/roles, tabela de sessões/refresh tokens) — mesma lista, mesma razão.

---

## Conformidade

- Dados 100% públicos do portal TST
- Documentos privados (PDF enviado pelo usuário) processados apenas em
  memória — nunca tocam disco nem banco. O que É persistido (Postgres,
  `public.conversas`, ver `conversations/db.py`) é só a EstruturaArgumentativa
  já revisada e os resultados do `/query` — dado derivado/estruturado, não o
  documento em si — pra manter o histórico de busca disponível entre sessões.
  Cada busca bem-sucedida numa conversa (a original + cada "Refinar consulta")
  vira uma versão própria no array `versoes` (V1, V2, ... — dropdown navegável
  na página de Resultados), nenhuma sobrescreve as anteriores.
- Conformidade com LGPD
- Delay adaptativo entre requisições (mínimo 2s, aumenta automaticamente em caso de erro)

---

## Autor

**Vinicius Gabriel Zanatta**\
Engenharia de Software — Católica SC

Validação de domínio:\
**Alexia S. Rebello — Assistente Jurídica (Direito Trabalhista)**
