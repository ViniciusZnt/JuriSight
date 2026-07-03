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
    → [Poly-Vector Embeddings]
    → [ChromaDB]                ← busca semântica
    → [BM25 Index]              ← busca lexical
    → [FastAPI + RRF]           ← fusão dos rankings
    → [Sort Categórico]         ← hierarquia jurídica
    → [Streamlit]
```

Custo operacional: **R$ 0 — 100% local via Ollama.**

---

## Estrutura

```
jurisight/
├── scraper/
│   ├── run.py              ← ponto de entrada da coleta
│   ├── api.py              ← cliente HTTP (requests.Session)
│   ├── core.py             ← loop de coleta com delay adaptativo
│   ├── db.py               ← PostgresStore + CheckpointStore
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
├── interface/
│   ├── app.py
│   └── components/
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
| uv         | qualquer      | Gerenciador de pacotes  |
| Docker     | 24+           | Para o PostgreSQL       |
| Ollama     | qualquer      | Modelos LLM locais      |
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

### 3 — Baixar modelos Ollama

```bash
ollama pull llama3.2:3b
ollama pull nomic-embed-text
```

O servidor Ollama precisa estar no ar em `http://localhost:11434`. Na maioria
das instalações ele já sobe sozinho como serviço em segundo plano — confira com:

```bash
ollama list            # lista os modelos baixados (só responde se o servidor está no ar)
curl -s http://localhost:11434/api/tags   # deve retornar JSON com os modelos
```

Se `ollama serve` reclamar de `address already in use`, **não é erro** — significa
que o servidor já está rodando. Não precisa iniciá-lo de novo.

### 4 — Configurar variáveis de ambiente

```bash
cp .env.example .env
```

| Variável         | Padrão                                              | Descrição                   |
|------------------|-----------------------------------------------------|-----------------------------|
| `DATABASE_URL`   | `postgresql://postgres:postgres@localhost:5432/jurisight` | Conexão com o PostgreSQL |
| `OLLAMA_BASE_URL`| `http://localhost:11434`                            | URL do servidor Ollama      |

### 5 — Subir a infraestrutura (Docker)

```bash
docker compose up -d
docker compose ps   # aguarda "healthy"
```

A tabela `documentos` é criada automaticamente na primeira execução do scraper.

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

# Interrompido? Só rodar de novo — checkpoint retoma de onde parou
uv run python scraper/run.py
```

**Coleções disponíveis:** `acordaos` · `sumulas` · `ojs` · `precedentes`

O progresso é salvo em `scraper/checkpoint.json` a cada página coletada.

### 7 — Indexar documentos (SAC Chunking + Poly-Vector + BM25)

Lê os documentos do PostgreSQL, gera os chunks e embeddings e popula o ChromaDB
e o índice BM25. Roda **depois** da coleta. Requer o Ollama no ar (passo 3).

```bash
uv run python indexing/run.py

# Reindexar do zero (limpa Chroma e BM25 antes)
uv run python indexing/run.py --reset
```

### 8 — Rodar interface

```bash
uv run streamlit run interface/app.py
```

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
| nomic-embed-text   | Embeddings (768d)                           |
| rank-bm25          | Busca lexical — índice BM25                 |
| FastAPI            | Backend — fusão RRF dos rankings            |
| Streamlit          | Interface do usuário                        |

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
