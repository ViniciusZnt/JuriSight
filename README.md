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
    → [ChromaDB]                ← busca semântica
    → [BM25 Index]              ← busca lexical
    → [FastAPI + RRF]           ← fusão dos rankings
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
├── scraper/
│   ├── run.py              ← ponto de entrada da coleta
│   ├── api.py              ← cliente HTTP (requests.Session)
│   ├── core.py             ← loop de coleta com delay adaptativo
│   ├── db_writer.py        ← PostgresStore + estado da coleta (scraper_state)
│   ├── html_parser.py      ← extração de seções do HTML dos acórdãos
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
│   ├── enrichment/
│   └── search/
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
| `CHROMA_PERSIST_DIR`| `~/.local/share/jurisight/chroma`                   | Índice ChromaDB — **no FS Linux, não em `/mnt/d`** (ver passo 7) |
| `BM25_INDEX_PATH`   | `./data/index/bm25.pkl`                             | Índice lexical BM25 (pickle)     |

> A chave da OpenAI vai só no `.env` (gitignored) — **nunca** commitada. Sem crédito
> pré-pago na conta, a API responde `429 insufficient_quota`.

### 5 — Subir a infraestrutura (Docker)

```bash
docker compose up -d          # sobe Postgres (+ Ollama, se optar pela opção B do passo 3)
docker compose ps             # aguarda "healthy"
```

Para subir só o Postgres (usando o Ollama nativo): `docker compose up -d postgres`.

A tabela `documentos` é criada automaticamente na primeira execução do scraper.

> **ChromaDB não é um serviço.** Ele roda embedded (biblioteca Python) e persiste
> em disco no diretório `CHROMA_PERSIST_DIR`, criado automaticamente na primeira
> indexação — não há container nem porta para ele.

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
ChromaDB e o índice BM25. Roda **depois** da coleta. Requer a `OPENAI_API_KEY`
(passo 4). A carga completa leva ~4-5h e é resumível — o delta pula o que já está
no Chroma.

```bash
# Teste rápido (100 docs)
uv run python indexing/run.py --reset --limit 100

# Carga completa em background
nohup uv run python indexing/run.py --reset > indexing.log 2>&1 &

# Retomar após queda ou falhas (sem --reset, o delta continua)
uv run python indexing/run.py
```

> No WSL2, mantenha o `CHROMA_PERSIST_DIR` no FS Linux (`~/…`), não em `/mnt/d`:
> gravar no HD/drive Windows deixa o Chroma ~30x mais lento (fsync).

### 8 — Rodar interface

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
| ChromaDB           | Banco vetorial — busca semântica            |
| Ollama / Llama 3.2 3B | Query enrichment local                 |
| OpenAI text-embedding-3-small | Embeddings (1536d)              |
| rank-bm25          | Busca lexical — índice BM25                 |
| FastAPI            | Backend — fusão RRF dos rankings            |
| Next.js / React    | Interface do usuário                        |
| Jest + React Testing Library | Testes unitários e de componente (frontend) |
| Cypress            | Testes end-to-end (frontend)                |

---

## Escalabilidade

O ChromaDB é RAM-bound: o HNSW carrega o índice inteiro em memória, então o tamanho
da coleção é limitado pela RAM. Passou da RAM, entra em swap e trava
([docs](https://docs.trychroma.com/guides/deploy/performance)).

Escala atual: ~69k acórdãos (~400k chunks, ~3 GB de vetores) em 11 GB de RAM.

Migração planejada para **Qdrant** (índice em disco com mmap) quando o acervo
crescer além da RAM. Troca localizada: só o `ChromaStore` muda — o Postgres é a
fonte de verdade e a busca fica atrás do `HybridSearch`.
https://qdrant.tech/documentation/migrate-to-qdrant/from-chroma/

---

## Conformidade

- Dados 100% públicos do portal TST
- Documentos privados processados apenas em memória
- Conformidade com LGPD
- Delay adaptativo entre requisições (mínimo 2s, aumenta automaticamente em caso de erro)

---

## Autor

**Vinicius Gabriel Zanatta**\
Engenharia de Software — Católica SC

Validação de domínio:\
**Alexia S. Rebello — Assistente Jurídica (Direito Trabalhista)**
