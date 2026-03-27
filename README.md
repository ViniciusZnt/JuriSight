# JurisLens

> Sistema de Análise Contextual de Jurisprudência Trabalhista com IA

**Autor:** Vinicius Gabriel Zanatta\
**Curso:** Engenharia de Software --- Católica SC\
**Linha de Projeto:** IA (GraphRAG + NLP + Busca Híbrida)

------------------------------------------------------------------------

## O que é

JurisLens recebe o documento de um caso trabalhista e a intenção
argumentativa do advogado, e retorna jurisprudências do TST ---
acórdãos, súmulas, OJs e precedentes normativos --- ordenados pela
hierarquia das fontes jurídicas e alinhados à tese.

**Problema resolvido:** Advogados trabalhistas gastam \~5h semanais
pesquisando jurisprudência em ferramentas que retornam resultados sem
alinhamento argumentativo e sem distinguir o peso jurídico de cada tipo
de documento.

------------------------------------------------------------------------

## Pipeline

    Portal TST → [Scraper] → [pdfplumber] → [NER] → [SAC Chunking]
               → [Poly-Vector Embeddings] → [ChromaDB + LightRAG]
               → [Query Enrichment] → [Busca Híbrida + RRF]
               → [Sort Categórico] → [Streamlit]

Custo operacional: **R\$ 0 --- 100% local via Ollama.**

------------------------------------------------------------------------

## Estrutura

    juris-lens/
    ├── scraper/
    │   ├── spiders/
    │   ├── middlewares/
    │   ├── pipelines/
    │   ├── items/
    │   └── settings.py
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
    ├── scripts/
    ├── .env.example
    ├── pyproject.toml
    └── README.md

------------------------------------------------------------------------

# Quick Start (uv)

## 1 --- Instalar uv

Linux / WSL / Mac:

``` bash
curl -Ls https://astral.sh/uv/install.sh | sh
```

Verifique:

``` bash
uv --version
```

------------------------------------------------------------------------

## 2 --- Criar ambiente do projeto

``` bash
uv init
uv venv
```

Ativar:

``` bash
source .venv/bin/activate
```

------------------------------------------------------------------------

## 3 --- Instalar dependências

``` bash
uv add scrapy scrapy-playwright playwright pdfplumber spacy chromadb lightrag-hku rank-bm25 ollama streamlit python-dotenv loguru tqdm
```

------------------------------------------------------------------------

## 4 --- Instalar browsers do Playwright

``` bash
uv run playwright install chromium
```

Instalar dependências do Chromium:

``` bash
uv run playwright install-deps
```

------------------------------------------------------------------------

## 5 --- Baixar modelos locais

``` bash
ollama pull llama3.2:3b
ollama pull nomic-embed-text
```

------------------------------------------------------------------------

## 6 --- Baixar modelo spaCy

``` bash
uv run python -m spacy download pt_core_news_lg
```

------------------------------------------------------------------------

## 7 --- Configurar variáveis de ambiente

``` bash
cp .env.example .env
```

------------------------------------------------------------------------

## 8 --- Executar scraping

``` bash
bash scripts/run_scraper.sh
```

------------------------------------------------------------------------

## 9 --- Rodar interface

``` bash
uv run streamlit run interface/app.py
```

------------------------------------------------------------------------

## Windows

Obrigatório usar **WSL2**.

Scrapy + Playwright não funciona corretamente no PowerShell nativo.

------------------------------------------------------------------------

## Hierarquia Categórica dos Documentos

  -----------------------------------------------------------------------
  Categoria               Tipo                    Descrição
  ----------------------- ----------------------- -----------------------
  1                       Súmula                  Entendimento
                                                  consolidado --- máximo
                                                  peso argumentativo

  2                       Orientação              Interpretação técnica
                          Jurisprudencial (OJ)    oficial

  3                       Precedente Normativo    Regra aplicável por
                                                  categoria profissional

  4                       Acórdão                 Decisão colegiada

  5                       Decisão Monocrática     Tendência recente de um
                                                  ministro
  -----------------------------------------------------------------------

Ordenação categórica baseada na hierarquia das fontes jurídicas
brasileiras.

------------------------------------------------------------------------

## Stack

  Tecnologia                   Função
  ---------------------------- ----------------------
  Scrapy + scrapy-playwright   Coleta do portal TST
  pdfplumber                   Extração de texto
  spaCy                        NER
  Ollama                       LLM local
  nomic-embed-text             Embeddings
  ChromaDB                     Banco vetorial
  LightRAG                     GraphRAG
  rank-bm25                    Busca lexical
  Streamlit                    Interface

------------------------------------------------------------------------

## Conformidade

-   Dados 100% públicos do portal TST
-   Documentos privados processados apenas em memória
-   Conformidade com LGPD
-   Scraping com throttling respeitoso

```{=html}
<!-- -->
```
    DOWNLOAD_DELAY = 2

------------------------------------------------------------------------

## Autor

**Vinicius Gabriel Zanatta**\
Engenharia de Software --- Católica SC

Validação de domínio:\
**Alexia S. Rebello --- Assistente Jurídica (Direito Trabalhista)**
