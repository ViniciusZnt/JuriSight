# JuriSight

> Sistema de Análise Contextual de Jurisprudência Trabalhista com IA

**Autor:** Vinicius Gabriel Zanatta\
**Curso:** Engenharia de Software — Católica SC\
**Linha de Projeto:** IA (GraphRAG + NLP + Busca Híbrida)

---

## O que é

JuriSight recebe o documento de um caso trabalhista e a intenção
argumentativa do advogado, e retorna acórdãos dos TRTs ordenados por
relevância e alinhados à tese.

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
    → [Next.js]
```

**Ordem dos resultados:** a ordem final é a do reranker (cross-encoder), ou seja,
por relevância para a tese. A tela de resultados também ordena por data, no próprio
navegador. **Não há ordenação por hierarquia das fontes** (súmula antes de acórdão):
o acervo tem só acórdãos (69.349, todos com `hierarquia_categoria = 4`), então essa
ordenação não teria o que separar. O `categorical_sort.py` e o parâmetro `ordenar_por`
foram removidos por isso no commit
[`d2a6abe`](https://github.com/ViniciusZnt/JuriSight/commit/d2a6abe42fb54e134754d7aad6c1b2312c55ad38).
Se súmulas e OJs entrarem no acervo, a hierarquia volta a fazer sentido.

Custo: o LLM e o enriquecimento de query rodam **100% locais** (Ollama). Só os
**embeddings** usam a OpenAI (`text-embedding-3-small`) — **~US$ 8 uma única vez**
para indexar todo o corpus; por consulta, o custo é desprezível.

---

## Estrutura

```
jurisight/
├── scraper/        ← coleta no portal do TST, estado da coleta e classificação de provimento (regex e Jev)
├── processing/     ← SAC Chunking e embeddings (Poly-Vector)
├── indexing/       ← vector_store (Qdrant), lexical (BM25) e a CLI de indexação
├── query/          ← enrichment (PDF, LLM, Query Builder), search (RRF, reranker), filtros e api (FastAPI)
├── auth/           ← autenticação (senha, JWT, schema; decisões em auth/DESIGN.md)
├── conversations/  ← histórico de busca persistido (public.conversas, ver §Conformidade)
├── avaliacao/      ← harness de avaliação da busca (ver §Avaliação da busca)
├── pipeline/       ← jobs do Dagster (coleta, indexação, filtros, Jev)
├── utils/          ← reclassificação de provimento
├── deploy/         ← Caddyfile e scripts de backup da VPS
├── frontend/       ← interface Next.js (App Router)
├── tests/          ← testes do backend
├── docs/           ← RFCs, diagramas, backup, deploy e avaliação
├── data/           ← índices locais (data/index) e saídas da avaliação (data/eval)
├── main.py         ← sobe a API
├── run.sh          ← sobe infra, backend e frontend de uma vez
├── Dockerfile, docker-compose.yml, docker-compose.prod.yml
└── .env.example, pyproject.toml
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

| Variável            | Descrição                        |
|---------------------|----------------------------------|
| `DATABASE_URL`      | Conexão com o PostgreSQL (padrão do `.env.example`: `postgresql://postgres:postgres@localhost:5432/jurisight`) |
| `OPENAI_API_KEY`    | Chave da OpenAI (embeddings) — **obrigatória**, exige crédito pré-pago |
| `JWT_SECRET_KEY`    | Segredo dos tokens de sessão — **obrigatória**, sem valor padrão (gere com `openssl rand -hex 32`) |

As demais (`QDRANT_URL`, `BM25_INDEX_PATH`, `OLLAMA_*`, `API_*`, `CORS_ORIGINS`, `COOKIE_SECURE`, SMTP,
Typesafe, avaliação) têm padrão para dev local e estão comentadas no `.env.example`.

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

O frontend tem testes unitários e de componente (Jest + React Testing Library) e end-to-end (Cypress),
ambos em `frontend/`:

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

Os testes de backend estão na seção seguinte; os dois rodam no CI (ver [CI](#ci)).

---

## Testes (backend)

```bash
uv run pytest
```

Os testes ficam em `tests/`, um módulo por área.

> Todos rodam sem infraestrutura real: Postgres, Qdrant, Ollama e OpenAI entram como fakes
> injetados, e os testes que usam o banco de verdade só rodam com `DATABASE_URL`. O smoke
> test de ponta a ponta, com a infra no ar, é o passo 8 do Quick Start.

---

## CI

O GitHub Actions ([`.github/workflows/ci.yml`](.github/workflows/ci.yml)) roda em todo
pull request e em todo push na `main`:

| Job | O que faz |
|-----|-----------|
| `backend` | Instala com `uv sync --frozen` e roda `uv run pytest`, sem `tests/test_api_stress.py`, que faz requisições ao portal da Justiça do Trabalho |
| `frontend` | `pnpm install --frozen-lockfile`, `pnpm test` (Jest) e `pnpm build` |
| `deploy` | Só em push na `main`, com os dois jobs verdes: atualiza a VPS por SSH (ver `docs/deploy/2026-11-01-deploy-vps.md`) |

Nenhum teste precisa de chave: OpenAI, Ollama, Qdrant e Postgres entram como fakes, e os
testes que usam o banco de verdade são pulados sem `DATABASE_URL`. O workflow não tem chave
de API; só o deploy usa os secrets `VPS_HOST`, `VPS_USER` e `VPS_SSH_KEY`.

---

## Avaliação da busca

Para saber se uma mudança na busca melhorou ou piorou o resultado, o projeto tem um
**conjunto-ouro** de pares (tese × acórdão), julgados por pessoas com relevância 0–3 e
stance, e um `benchmark` que compara sete sistemas de busca (S0–S6, do BM25 sozinho ao
pipeline de produção com FlashRank) por nDCG@10 e outras métricas, com testes
estatísticos. O manual completo (construir o conjunto-ouro, exportar e importar as
planilhas de julgamento, adjudicação, rodar e ler o relatório) está em
[`docs/avaliacao/README.md`](docs/avaliacao/README.md).

```bash
uv run python -m avaliacao.construir                    # monta o conjunto-ouro
uv run python -m avaliacao.benchmark rodar              # roda S0–S6
```

---

## Provimento com o Jev

A coluna `documentos.provimento` vem de uma regex sobre o dispositivo, que diz se o
recurso foi aceito, mas não quem ganhou: "recurso negado" é vitória do trabalhador
quando quem recorreu foi a empresa. Esta etapa pergunta ao Jev, para cada acórdão, o
**resultado** do recurso, o **recorrente** e **quem é favorecido**, guarda as respostas
com probabilidades na tabela `provimento_jev` e, depois de uma conferência manual, pode
passar a usar o resultado do Jev em `documentos.provimento`. A regex continua gravada
ao lado (`provimento_regex`). Racional e decisões: [`docs/superpowers/specs/2026-10-20-provimento-jev-design.md`](docs/superpowers/specs/2026-10-20-provimento-jev-design.md).

Usa `TYPESAFE_API_KEY` e `TYPESAFE_MODEL` (versão fixa, padrão `jev-1.13.0`; um modelo
terminado em `-latest` é recusado) e precisa do Postgres no ar. Os comandos, na ordem de uso:

```bash
# 1. Classifica os acórdãos pendentes (mostra a estimativa e pede confirmação)
uv run python -m scraper.provimento_jev_cli classificar [--limite N] [--lote 500] [--max-workers 8] [--sim]

# 2. Mostra o que mudaria; só escreve em documentos.provimento com --confirmar
uv run python -m scraper.provimento_jev_cli aplicar [--confianca-min 0.8] [--confirmar]

# 3. Leva documentos.provimento ao Qdrant e ao BM25 (a busca filtra por ele)
uv run python -m scraper.provimento_jev_cli sincronizar [--lote 1000] [--so-bm25 | --so-qdrant]
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
- **Validação:** foi feita por duas conferências cegas, documentadas em
  `docs/superpowers/specs/2026-10-20-provimento-jev-conferencia.md` e
  `docs/superpowers/specs/2026-10-22-provimento-jev-conferencia-2.md`.

---

## Filtro restrito

Além do texto livre, a busca aceita filtros que restringem o resultado. Entre tipos de filtro vale **"E"**;
só tribunal e fase também já tornam a busca restrita:

- **Tribunal:** um ou mais (ex.: "TRT-4", gravado como `TRT4`); entre os escolhidos vale **"OU"**.
- **Fase do processo:** uma só, deduzida da classe processual: **Conhecimento** (ROT, RORSum, RO, RemNecRO,
  RemNecTrab, AIRO), **Execução** (AP, AIAP) ou **Outras** (todo o resto, inclusive classe vazia).
- **Normas e dispositivos:** um campo só, com autocompletar. O que se escolhe da lista vira filtro
  (dispositivos como `art_791_clt`, `b_ii_art_10_adct`, e também NR, Tema e Súmula Vinculante). O texto
  digitado e confirmado com Enter, sem ser escolhido da lista, vira norma "só busca livre": orienta a busca
  mas **não filtra**.
- **Expressões obrigatórias:** campo separado; cada expressão (ex.: "dano moral coletivo", singular ou
  plural, sem depender de acento ou quebra de linha) é filtro.

Com algum filtro, o `/query` devolve só decisões que cumprem **todos** eles (faixa "restrita"); a busca
livre, sem esses filtros, vem sob demanda em `/query/livre` (faixa "livre"). `/filtros/*` dá o autocompletar
e as contagens. `/filtros/*` e `/query/livre` exigem login; só o `/query` conta no limite diário.

**NR, Tema e Súmula Vinculante** são extraídos do texto (ementa e fundamentação) pelo preparo, com os
códigos `nr_<n>` ("NR-15"), `tema_<n>` ("Tema 1046") e `sv_<n>` ("Súmula Vinculante 4"); Súmula Vinculante
só quando o texto diz "vinculante" ou "SV" colado ao número. Listas ("Temas 1046 e 725", "NRs 15 e 16")
só são lidas depois da palavra no plural. O número do Tema não está ligado a um tribunal (ex.: "Tema 2"
no acervo é o IRDR do TST), como a especificação aceitou.

Os dispositivos e o índice de texto saem de tabelas que precisam ser preparadas antes do primeiro uso (rode de novo quando entrarem decisões novas):

```bash
# local
uv run python -m query.filtros.preparar

# produção
docker compose -f docker-compose.prod.yml exec api uv run --no-sync python -m query.filtros.preparar
```

- **Depois do deploy, rode o preparo na VPS**, fora do horário de uso: sem ele NR, Tema e Súmula
  Vinculante não aparecem no autocompletar. O preparo refaz os dispositivos com `TRUNCATE`, e o
  autocompletar, as contagens e a busca com filtro esperam até ele terminar. Confira o `df -h` antes
  (o índice de texto e as tabelas de dispositivos ocupam centenas de MB).
- **Desempenho:** a busca restrita usa o mesmo pool de 30 candidatos da busca normal, então fica
  praticamente no mesmo tempo; a contagem roda uma consulta por expressão, em paralelo.
- **Texto indexado:** só letras sem acento e números; hífen e pontuação viram espaço e o ponto entre
  dígitos sai, então "auxílio-doença" casa "auxilio doença" e "Lei 13.467" casa "Lei 13467". Se essa
  forma mudar (`_VERSAO_TEXTO` em `query/filtros/preparar.py`), o próximo preparo refaz o índice de
  texto do zero sozinho.
- **Códigos do acervo:** o acervo grava o art. 59-B da CLT como `b_art_59_clt`, então ele aparece como
  "CLT art. 59, b", e escolher "CLT art. 59" também traz quem cita só o 59-B.
- **Decisões novas:** só entram no filtro depois de rodar o preparo de novo (os dispositivos são
  refeitos do zero; o índice de texto só acrescenta as decisões que ainda não estão nele).
  Sem o preparo, o filtro responde 503.
- **Testes:** `tests/test_filtros_store_integration.py` só lê o banco já preparado; o teste que roda o
  preparo (reescreve as tabelas) só roda com `JURISIGHT_TESTAR_PREPARO=1`.

---

## Pipeline de dados (Dagster)

Em produção a coleta, a indexação e o preparo dos filtros rodam pelo Dagster, no serviço `dagster` do
`docker-compose.prod.yml` (a cópia local→VPS do deploy é só histórica). A UI não é pública: fica em
`127.0.0.1:3000` da VPS e se abre por túnel SSH.

```bash
ssh -L 3001:localhost:3000 deploy@IP   # depois abra http://localhost:3001
```

| Job | O que faz |
|-----|-----------|
| `full` | `acervo` (coleta) → `indices` (Qdrant + BM25, sem reset) → `filtros` (preparo do filtro restrito) |
| `coleta` | só `acervo` |
| `indexacao` | só `indices` |
| `so_filtros` | só `filtros` |
| `jev` | classificar → aplicar → sincronizar o provimento com o Jev |

- **Datas da coleta:** na config do `acervo` (`data_inicio`, `data_fim`, em `AAAA-MM-DD`; `colecao`, padrão
  `acordaos`). Em branco, a coleta continua do banco.
- **Jev:** `limite` é o máximo de acórdãos classificados por run (padrão 500; `0` = sem limite). O `jev` só grava em `documentos.provimento` acima de `confianca_min`
  (0,8) e sincroniza Qdrant e BM25.
- **Depois do `full`:** `docker compose -f docker-compose.prod.yml restart api` (recarrega o BM25).
- **Fila:** um run por vez (`pipeline/dagster.yaml`); runs disparados durante outro ficam na fila.

---

## Guia de uso

A página `/guia` (botão **Como usar** no topo da tela inicial) explica, para quem nunca usou,
o caminho de uma busca, o que cada campo da Revisão de Contexto faz e os limites do acervo.
As três buscas têm cor própria em todo o app (guia, Revisão, painel "Como esta busca foi
feita" e cartões), definida num lugar só, `frontend/src/lib/cores-busca.ts`:

| Busca | Cor | Usa |
|---|---|---|
| Filtro restrito | marinho `#1A3A5C` | normas da lista, expressões obrigatórias, tribunal, fase |
| Busca semântica | violeta `#6D4FC2` | Tese central (também ordena o resultado) |
| Busca por termos | verde-água `#0E8A80` | Pedido, Fatos, Condutas, normas "só busca livre" |

Os números do guia (69.349 acórdãos, 96% de 2025, 25 tribunais) são fixos no texto; se o
acervo crescer, atualize `TOTAL_ACERVO` e as frases do guia.

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
não mudaram de lógica, só de import. A migração Chroma→Qdrant foi feita por
`indexing/vector_store/migrate_chroma_to_qdrant.py` (removido; último estado em 1fb6d8a).

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

A autenticação (`auth/`, `query/api/auth_routes.py`) cobre cadastro, login, logout, sessão via
cookie httpOnly, redefinição de senha por e-mail (`/auth/esqueci-senha` e `/auth/redefinir-senha`,
com SMTP configurado pelo `.env`), senha com Argon2id, JWT e proteção contra timing attack e CSRF.
Decisões em [`auth/DESIGN.md`](auth/DESIGN.md). Deliberadamente **não** implementado:

- **Verificação de e-mail** — hoje qualquer e-mail digitado é aceito sem confirmação.
- **2FA** (segundo fator de autenticação).
- **Rate limiting / lockout** de tentativas de login (força bruta hoje não tem
  nenhum limite além do custo do próprio Argon2id).
- **Papéis e permissões** (`is_superuser`) e **refresh token**.

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
