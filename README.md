# JurisLens

> Sistema de Análise Contextual de Jurisprudência Trabalhista com IA

**Autor:** Vinicius Gabriel Zanatta  
**Curso:** Engenharia de Software — Católica SC  
**Linha de Projeto:** IA (GraphRAG + NLP + Busca Híbrida)

---

## O que é

JurisLens recebe o documento de um caso trabalhista e a intenção argumentativa do advogado, e retorna jurisprudências do TST — acórdãos, súmulas, OJs e precedentes normativos — ordenados pela hierarquia das fontes jurídicas e alinhados à tese.

**Problema resolvido:** Advogados trabalhistas gastam ~5h semanais pesquisando jurisprudência em ferramentas que retornam resultados sem alinhamento argumentativo e sem distinguir o peso jurídico de cada tipo de documento.

---

## Pipeline

```
Portal TST → [Scraper] → [pdfplumber] → [NER] → [SAC Chunking]
           → [Poly-Vector Embeddings] → [ChromaDB + LightRAG]
           → [Query Enrichment] → [Busca Híbrida + RRF]
           → [Sort Categórico] → [Streamlit]
```

Custo operacional: **R$ 0** — 100% local via Ollama.

---

## Estrutura

```
juris-lens/
├── scraper/            # Scrapy + Playwright — coleta do portal TST
│   ├── spiders/        # tst_acordaos, tst_sumulas, tst_ojs, tst_delta
│   ├── middlewares/    # Rate limiter
│   ├── pipelines/      # Armazenamento
│   ├── items/          # DocumentItem
│   └── settings.py     # Configuração Scrapy + Playwright
│
├── processing/         # Processamento de texto
│   ├── chunking/       # SAC Chunking (Llama 3.2 3B via Ollama)
│   ├── ner/            # NER jurídico (spaCy + LeNER-Br)
│   └── embeddings/     # Poly-Vector (nomic-embed-text-v2)
│
├── indexing/           # Indexação
│   ├── vector_store/   # ChromaDB
│   └── graph/          # LightRAG (GraphRAG)
│
├── query/              # Busca e enriquecimento
│   ├── enrichment/     # PDF extractor + Query builder
│   └── search/         # Busca híbrida + Sort categórico
│
├── interface/          # Streamlit
│   ├── app.py
│   └── components/     # upload, results, filters
│
├── data/               # Dados locais (não versionados)
│   ├── raw/            # PDFs brutos
│   ├── processed/      # JSONs processados
│   └── index/          # ChromaDB persistido
│
├── docs/               # RFC, Arquitetura, Justificativa Técnica
├── tests/              # Testes por módulo
├── scripts/            # run_scraper.sh, run_delta.sh
├── .env.example
└── requirements.txt
```

---

## Quick Start

```bash
# 1. Instalar dependências
pip install -r requirements.txt
playwright install chromium

# 2. Baixar modelos locais
ollama pull llama3.2:3b
ollama pull nomic-embed-text

# 3. Copiar e configurar .env
cp .env.example .env

# 4. Executar scraping
bash scripts/run_scraper.sh

# 5. Iniciar interface
streamlit run interface/app.py
```

> **Windows:** obrigatório usar WSL2 — Scrapy-Playwright não funciona no PowerShell nativo.

---

## Hierarquia Categórica dos Documentos

| Categoria | Tipo | Descrição |
|---|---|---|
| 1 | Súmula | Entendimento consolidado — máximo peso argumentativo |
| 2 | Orientação Jurisprudencial (OJ) | Interpretação técnica oficial |
| 3 | Precedente Normativo | Regra aplicável por categoria profissional |
| 4 | Acórdão | Decisão colegiada |
| 5 | Decisão Monocrática | Tendência recente de um ministro |

> Ordenação **categórica** baseada na hierarquia das fontes jurídicas brasileiras — doutrina consolidada no direito processual do trabalho.

---

## Stack

| Tecnologia | Função |
|---|---|
| Scrapy + scrapy-playwright | Coleta do portal TST com JS rendering |
| pdfplumber | Extração de texto por seção |
| spaCy + LeNER-Br | NER jurídico offline |
| Ollama + Llama 3.2 3B | SAC Chunking + Query Enrichment (local) |
| nomic-embed-text-v2 | Poly-Vector Embeddings (local) |
| ChromaDB | Banco de vetores persistente |
| LightRAG | GraphRAG leve (dual-level: vector + 1-hop graph) |
| rank-bm25 | Busca lexical |
| Streamlit | Interface |

---

## Conformidade

- Dados 100% públicos do portal TST
- Documentos privados processados em memória — nunca armazenados
- Conformidade com LGPD (Lei 13.709/2018)
- Scraping com throttling respeitoso (DOWNLOAD_DELAY = 2s)

---

## Autor

**Vinicius Gabriel Zanatta** — Engenharia de Software, Católica SC  
Validação do domínio: **Alexia S. Rebello** — Assistente Jurídica, Direito Trabalhista
