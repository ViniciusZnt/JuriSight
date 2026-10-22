# Benchmark de rerankers (etapa 2) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deixar pronto tudo o que o benchmark de rerankers precisa antes e depois do julgamento humano: pool novo, planilha de julgamento (exportar/importar) com duas pessoas por par, importação das teses dos advogados, os sistemas S0–S6 (incluindo 3 rerankers novos) e o relatório multissistema com estatística.

**Architecture:** Tudo novo mora em `avaliacao/` (pacote do harness) e em adaptadores `query/search/reranker_*.py` com a mesma interface `rerank_scores(query, passagens) -> list[float]` do FlashRank. `buscar()` ganha só `reranker=None` (sem rerank). Os rerankers novos não entram em produção neste plano.

**Tech Stack:** Python 3.13, psycopg 3, onnxruntime + tokenizers + huggingface_hub (já instalados), openpyxl e scipy (novas dependências), PyTorch CPU + transformers só num grupo opcional `benchmark`.

**Spec:** `docs/superpowers/specs/2026-10-21-inventario-e-plano-design.md`, seções "Parte 2 — Metodologia do benchmark" e "Parte 2 — Sistemas comparados".

**Branch:** `feat/benchmark-etapa2`, no worktree `/home/vini/JuriSight-benchmark` (o diretório `/home/vini/JuriSight` é de outra sessão: não fazer checkout nem editar lá). O `.env` fica em `/home/vini/JuriSight/.env`: carregar com `set -a; source /home/vini/JuriSight/.env; set +a`.

## Global Constraints

- Pool por tese = os **30 candidatos do híbrido** (corredor `hibrido`) + **top-10 do BM25** (`bm25`) + **top-10 do denso** (`vetorial`). Pares antigos (corredores `pipeline`, `passo_zero`) continuam no banco e não são apagados.
- Escala de relevância 0–3: 0 outro problema jurídico; 1 mesmo ramo/tema, outro pedido ou fato central; 2 mesmo pedido, fato decisivo diferente ou só em parte; 3 mesmo problema e mesmo fato decisivo, "eu citaria na peça". Stance (`fortalece`, `enfraquece`, `neutro`) só é pedido quando a nota é 2 ou 3; com nota 0 ou 1 grava-se `neutro`.
- Juiz humano = `f"humano:{email.strip().lower()}"`, `rodada=1`.
- Rótulo final de um par com vários humanos: se o adjudicador (`AVALIACAO_ADJUDICADOR`, e-mail) julgou, vale o dele; senão, notas iguais → a nota; diferença de 1 → a menor; diferença ≥ 2 → pendente; stance diferente com as duas notas ≥ 2 → pendente. Com um único humano, vale o dele.
- Sistemas: S0 BM25 sozinho; S1 denso sozinho (2 coleções, RRF); S2 híbrido RRF sem reranker; S3 S2 + FlashRank; S4 S2 + `gte-multilingual-reranker-base`; S5 S2 + `bge-reranker-v2-m3`; S6 S2 + `unicamp-dl/monoptt5-base`. S3–S6 reordenam os mesmos 30 candidatos e recebem a mesma entrada: frase-tese contra a ementa cortada em 1.200 caracteres. Cada sistema devolve o top-20.
- Métricas: nDCG@10 (ganho 2^nota − 1, como já está em `metricas.ndcg_at_k`) principal; MRR@10, P@5, P@10, MAP@10, Recall@10 e Recall@20 com relevância ≥ 2; Judged@10.
- Estatística: diferenças pareadas por tese; teste t pareado com Holm sobre os contrastes registrados (S3×S2; S4×S3, S5×S3, S6×S3; S0×S2, S1×S2) e Wilcoxon com Benjamini-Hochberg como checagem; IC95% por bootstrap (10.000 reamostragens, seed fixa).
- Concordância entre avaliadores: kappa ponderado quadrático (já existe), alfa de Krippendorff ordinal e AC2 de Gwet (pesos quadráticos).
- Nada aqui chama o Jev. Nada escreve em `documentos`. O reranker de produção (`query/search/reranker.py`) não muda.
- Identificadores e docstrings em português; psycopg puro; fakes injetados nos testes; testes de integração com `skipif` sem `DATABASE_URL`; nunca imprimir nem editar o `.env`.
- Suíte antes de cada commit: `set -a; source /home/vini/JuriSight/.env; set +a; uv run pytest tests/ -q --ignore=tests/test_api_stress.py`.

## Review Focus

1. Planilha devolvida com linhas fora de ordem, linhas apagadas ou nota fora de 0–3 → importar só as linhas válidas, avisando as outras, sem gravar lixo (Task 5, `test_importar_ignora_linhas_invalidas`).
2. A mesma planilha importada duas vezes → mesmo resultado, sem duplicar (upsert por par/juiz/rodada) (Task 5, `test_importar_idempotente`).
3. Tese cujo top-10 de um sistema tem acórdão não julgado → Judged@10 < 1 aparece no relatório, e as métricas tratam o não julgado como nota 0 (Task 9, `test_judged_e_nao_julgado_vale_zero`).
4. Tese sem nenhum relevante (todas as notas < 2) → MRR/P/MAP/Recall dessa tese ficam None e a tese sai das médias dessas métricas, com contagem de excluídas (Task 8, `test_tese_sem_relevante_excluida`).
5. Par com avaliadores em desacordo e sem adjudicador → fica pendente e fora das métricas, e o relatório lista os pendentes (Task 6, `test_pendente_fica_fora`).

---

### Task 1: `buscar(reranker=None)` e os sistemas S0–S3

**Files:**
- Modify: `query/search/pipeline.py` (parâmetro `reranker: Reranker | None`)
- Create: `avaliacao/sistemas.py`
- Modify: `avaliacao/pooling.py` (mover os corredores BM25 e vetorial para `avaliacao/sistemas.py` e reaproveitar de lá)
- Test: `tests/test_pipeline.py`, `tests/test_avaliacao_sistemas.py`

**Interfaces:**
- Produces:
  - `buscar(..., reranker: Reranker | None, ...)`: com `None`, não reordena; o corte em 20 e a normalização dos scores (agora os do RRF) continuam.
  - `avaliacao.sistemas`: `SISTEMAS: tuple[str, ...] = ("S0", "S1", "S2", "S3", "S4", "S5", "S6")`; `top_bm25(hybrid, estrutura, k) -> list[str]`; `top_denso(hybrid, estrutura, k) -> list[str]`; `candidatos_hibrido(estrutura, *, hybrid, retriever, n=30) -> list[str]` (ids na ordem do RRF, só os que o retriever encontra); `rodar_sistema(sistema: str, estrutura, deps, rerankers: dict[str, object]) -> list[str]` (top-20 de ids). S0 = `top_bm25(k=20)`, S1 = `top_denso(k=20)`, S2 = `buscar(reranker=None)`, S3–S6 = `buscar(reranker=rerankers[sistema])`. `KeyError` com mensagem clara se o reranker do sistema não foi passado.

- [ ] **Step 1: Failing tests:** `test_buscar_sem_reranker_mantem_ordem_do_rrf` (fakes de `tests/test_pipeline.py`: com `reranker=None` a ordem é a do híbrido e o fake reranker nunca é chamado); `test_rodar_sistema_s2_s3` (S3 usa o reranker passado; S2 não usa nenhum); `test_rodar_sistema_sem_reranker_falha` (`rodar_sistema("S4", ..., rerankers={})` → `KeyError`).
- [ ] **Step 2–4:** RED → implementar → GREEN + suíte (o `montar_pool` atual continua passando nos testes existentes depois da mudança de módulo).
- [ ] **Step 5: Commit** `"Adiciona os sistemas S0–S3 do benchmark e busca sem reranker"`.

### Task 2: Pool novo (30 do híbrido + top-10 BM25 + top-10 denso)

**Files:**
- Modify: `avaliacao/pooling.py`, `avaliacao/construir.py` (`precisa_de_pool`)
- Test: `tests/test_avaliacao_pooling.py`, `tests/test_avaliacao_construir.py`

**Interfaces:**
- Consumes: `candidatos_hibrido`, `top_bm25`, `top_denso` (Task 1).
- Produces: `CORREDORES = ("hibrido", "bm25", "vetorial")`; `montar_pool(estrutura, *, hybrid, retriever, n_hibrido=30, k=10) -> dict[str, list[str]]` (não recebe mais reranker); `precisa_de_pool(pares) -> bool` = nenhum par com o corredor `hibrido`.

- [ ] **Step 1: Failing tests:** `test_pool_une_os_tres_corredores` (corredores na ordem hibrido, bm25, vetorial; tamanhos 30/10/10 nos fakes); `test_tese_com_pool_antigo_precisa_de_pool_novo` (pares só com `bm25`/`vetorial`/`pipeline` → True; com `hibrido` → False). Ajuste os testes antigos que esperavam o corredor `pipeline`.
- [ ] **Step 2–4:** RED → implementar → GREEN + suíte.
- [ ] **Step 5: Commit** `"Muda o pool para os 30 candidatos do híbrido mais top-10 do BM25 e do denso"`.

### Task 3: Rerankers ONNX (gte e bge) — S4 e S5

**Files:**
- Create: `query/search/reranker_onnx.py`
- Modify: `avaliacao/sistemas.py` (fábrica `construir_rerankers(nomes) -> dict[str, object]`)
- Test: `tests/test_reranker_onnx.py`

**Interfaces:**
- Produces: `class CrossEncoderOnnx(repo_id: str, arquivo_onnx: str, max_tokens: int = 512, sessao=None, tokenizer=None)` com `rerank_scores(query, passagens) -> list[float]` (mesma ordem; lista vazia → []); passagem cortada em 1.200 caracteres (a mesma constante do FlashRank, importada de `query/search/reranker.py`); modelos: `GTE = ("onnx-community/gte-multilingual-reranker-base", "onnx/model_int8.onnx")`, `BGE = ("onnx-community/bge-reranker-v2-m3-ONNX", "onnx/model_int8.onnx")`. Baixa com `huggingface_hub.hf_hub_download` para `data/index/reranker_cache`; tokenizer de `tokenizer.json` do mesmo repo; truncamento do par em `max_tokens` priorizando a passagem; passa só as entradas que a sessão declara (`sessao.get_inputs()`); score = logit da saída (sem sigmoide). Para não explodir a latência pelo padding, pontuar uma passagem por chamada, em threads (como o FlashRank).
- `construir_rerankers(["S3", "S4", "S5"])` devolve `{"S3": Reranker(), "S4": CrossEncoderOnnx(*GTE), "S5": CrossEncoderOnnx(*BGE)}` e carrega cada modelo só se pedido.

- [ ] **Step 1: Failing tests** com sessão e tokenizer falsos: `test_scores_na_ordem_de_entrada`, `test_passagem_cortada_em_1200`, `test_so_entradas_declaradas_pela_sessao` (sessão que declara só `input_ids` e `attention_mask` não recebe `token_type_ids`), `test_lista_vazia`.
- [ ] **Step 2–4:** RED → implementar → GREEN + suíte.
- [ ] **Step 5: Smoke real** (baixa ~0,9 GB, autorizado): pontuar uma tese curta contra 3 ementas com S4 e S5 e registrar no report os scores e o tempo; uma ementa relevante tem de sair acima de uma claramente fora do tema.
- [ ] **Step 6: Commit** `"Adiciona os rerankers ONNX gte e bge (S4 e S5)"`.

### Task 4: monoPTT5 (S6), em dependência opcional

**Files:**
- Modify: `pyproject.toml` (`[dependency-groups] benchmark = ["torch", "transformers", "sentencepiece"]`, torch pelo índice CPU `https://download.pytorch.org/whl/cpu`)
- Create: `query/search/reranker_monoptt5.py`
- Modify: `avaliacao/sistemas.py` (S6 na fábrica, com import preguiçoso e mensagem clara se o grupo `benchmark` não estiver instalado)
- Test: `tests/test_reranker_monoptt5.py`

**Interfaces:**
- Produces: `class MonoPTT5(modelo="unicamp-dl/monoptt5-base", max_tokens=512, model=None, tokenizer=None)` com `rerank_scores`. Prompt e tokens de relevância conforme o model card do `unicamp-dl/monoptt5-base` (leia o card; não invente o formato); score = probabilidade (ou log-prob) do token "relevante" no primeiro passo de decodificação. Mesmo corte de 1.200 caracteres na passagem.

- [ ] **Step 1: Failing tests** com modelo e tokenizer falsos: ordem preservada, corte da passagem, prompt montado no formato do card.
- [ ] **Step 2–4:** RED → implementar → GREEN + suíte (o teste não pode exigir torch instalado: faça `pytest.importorskip` só no smoke).
- [ ] **Step 5: Smoke real:** `uv sync --group benchmark` e o mesmo teste de 3 ementas da Task 3. Se a instalação do torch CPU falhar nesta máquina, relate BLOCKED com o erro, sem tentar outras gambiarras.
- [ ] **Step 6: Commit** `"Adiciona o reranker monoPTT5 (S6) em dependência opcional"`.

### Task 5: Planilha de julgamento — exportar e importar

**Files:**
- Modify: `pyproject.toml` (`openpyxl`)
- Create: `avaliacao/planilha_julgamento.py`
- Test: `tests/test_avaliacao_planilha_julgamento.py`

**Interfaces:**
- Consumes: `AvaliacaoStore` (`listar_teses`, `pares_da_tese`, `gravar_julgamento`), `DocRetriever.fetch`.
- Produces:
  - `exportar_lote(tese, pares, documentos: dict, caminho: Path, seed: int) -> int` — um `.xlsx` por tese com as abas **Instruções**, **Rubrica** (a escala 0–3 das Global Constraints, um parágrafo por nota), **Avaliador** (nome, e-mail, atuação) e **Avaliação**. Na Avaliação: no topo, a tese (pedido principal, tese central, normas, e o texto original do advogado se existir em `estrutura["_texto_original"]`); depois uma linha por par, em ordem sorteada com `random.Random(f"{seed}:{tese.id}")`: código do par (coluna oculta com o `par_id`), número, processo, link, ementa (ou o dispositivo — últimos 1.500 caracteres do acórdão — quando não há ementa), início da fundamentação (3.000 caracteres), **Nota** (lista 0–3), **Stance** (lista fortalece/enfraquece/neutro), comentário. Nenhuma pista de qual sistema trouxe o acórdão. Células de resposta em amarelo, cabeçalho fixo. Devolve o número de linhas.
  - `ler_lote(caminho) -> tuple[str, list[tuple[uuid.UUID, int, str]]]` — (e-mail normalizado, linhas válidas `(par_id, nota, stance)`); stance vazia com nota ≥ 2 invalida a linha; nota 0/1 grava `neutro`; linhas inválidas avisadas em stderr; e-mail ausente → `ValueError`.
  - CLI `python -m avaliacao.planilha_julgamento exportar [--teses id,...|--todas] [--pasta data/eval/lotes]` e `importar ARQUIVO...` (grava `Julgamento(par_id, f"humano:{email}", 1, nota, stance)`; par que não pertence à tese do lote é rejeitado).

- [ ] **Step 1: Failing tests:** `test_exportar_tem_as_quatro_abas_e_linhas_sorteadas` (mesma seed → mesma ordem; nenhuma coluna com corredor/sistema), `test_round_trip` (exporta, preenche via openpyxl, importa → julgamentos esperados), `test_importar_ignora_linhas_invalidas`, `test_importar_idempotente`, `test_email_ausente_falha`.
- [ ] **Step 2–4:** RED → implementar → GREEN + suíte.
- [ ] **Step 5: Commit** `"Adiciona a planilha de julgamento (exportar e importar)"`.

### Task 6: Rótulo final com duas pessoas e concordância

**Files:**
- Create: `avaliacao/consenso.py`
- Modify: `avaliacao/store.py` (`rotulos_finais` passa a usar o consenso), `avaliacao/metricas.py` (alfa de Krippendorff ordinal e AC2 de Gwet)
- Test: `tests/test_avaliacao_consenso.py`, `tests/test_avaliacao_metricas.py`, `tests/test_avaliacao_store_integration.py`

**Interfaces:**
- Produces:
  - `rotulo_final(julgamentos: list[tuple[str, int, str]], adjudicador: str | None) -> tuple[int, str] | None` — regra das Global Constraints; `None` = pendente.
  - `AvaliacaoStore.rotulos_finais(tese_id, adjudicador=None)` — mesma assinatura de retorno de hoje; pares pendentes ficam de fora. `AvaliacaoStore.pendentes(adjudicador=None) -> list[tuple[uuid.UUID, uuid.UUID]]` (tese_id, par_id).
  - `metricas.alfa_krippendorff_ordinal(pares: list[tuple[int, int]]) -> float | None`; `metricas.ac2_gwet(pares: list[tuple[int, int]], n_niveis=4) -> float | None` (pesos quadráticos).
  - O adjudicador vem de `os.getenv("AVALIACAO_ADJUDICADOR")` nos CLIs; acrescentar a variável ao `.env.example`.

- [ ] **Step 1: Failing tests:** casos da regra (iguais; diferença 1 → menor; diferença 2 → None; stance diferente com notas ≥ 2 → None; adjudicador prevalece; um só humano), `test_pendente_fica_fora` (integração), valores conhecidos de alfa e AC2 (concordância perfeita = 1; um exemplo calculado à mão).
- [ ] **Step 2–4:** RED → implementar → GREEN + suíte.
- [ ] **Step 5: Commit** `"Adiciona o rótulo final com duas pessoas e as medidas de concordância"`.

### Task 7: Teses dos advogados (importar) e sintéticas no estilo deles

**Files:**
- Modify: `avaliacao/db.py` (`origem` aceita `'advogado'`, via troca idempotente do CHECK), `avaliacao/geracao.py` (`gerar_tese(..., exemplos: list[str] | None = None)`), `avaliacao/construir.py` (passa como exemplos os textos originais das teses de advogado)
- Create: `avaliacao/teses_advogados.py`
- Test: `tests/test_avaliacao_teses_advogados.py`, `tests/test_avaliacao_geracao.py`

**Interfaces:**
- Consumes: a planilha `docs/avaliacao/1-producao-de-teses.xlsx` preenchida (aba **Teses**: dados do avaliador nas linhas 3–6, coluna B; tabela a partir da linha 10, colunas Nº, Tema, Processo, Ementa, Tese, A favor de quem, Observações) e `docs/avaliacao/1-acordaos-selecionados.json` (Nº → `id_documento`).
- Produces:
  - `ler_planilha_teses(caminho) -> list[dict]` com `n`, `tema`, `texto`, `lado`, `email`.
  - `importar(store, enricher, caminho, database_url, seed) -> int` — para cada tese preenchida: `estrutura = enricher.extract_estrutura(texto, intencao=lado)` (o mesmo caminho do `/enrich`), mais `_texto_original`, `_avaliador` e `_lado` na estrutura; `origem="advogado"`; `documento_origem_id` = UUID do acórdão de referência; tema = coluna Tema (ou `atribuir_tema` se vazia); split = `sortear_split(TEMAS, seed)[tema]`. Idempotente: não recria tese com o mesmo (`documento_origem_id`, `_avaliador`, `_texto_original`).
  - `gerar_tese` com `exemplos`: inclui até 5 textos de advogado no prompt como exemplos de estilo ("escreva como estes advogados escrevem; não copie o conteúdo").
  - CLI `python -m avaliacao.teses_advogados importar ARQUIVO...`.

- [ ] **Step 1: Failing tests:** leitura da planilha (gera uma planilha de teste com openpyxl no formato acima), importação com enricher falso e store falso (origem, documento de referência, tema, split, idempotência), prompt com e sem exemplos.
- [ ] **Step 2–4:** RED → implementar → GREEN + suíte.
- [ ] **Step 5: Commit** `"Importa as teses dos advogados e usa o estilo delas nas sintéticas"`.

### Task 8: Métricas do benchmark

**Files:**
- Modify: `avaliacao/metricas.py`
- Test: `tests/test_avaliacao_metricas.py`

**Interfaces:**
- Produces (todas com `ganhos: dict[str, int]`, relevante = ganho ≥ `LIMIAR_RELEVANTE`, documento ausente vale 0; `None` quando não há relevante): `mrr_at_k(ranking, ganhos, k=10)`, `precisao_at_k(ranking, ganhos, k)`, `map_at_k(ranking, ganhos, k=10)` (AP normalizado por `min(k, nº de relevantes)`), `judged_at_k(ranking, ganhos, k=10) -> float` (fração do top-k presente em `ganhos`), `ndcg_teto(candidatos, ganhos, k=10)` (nDCG@10 da melhor ordem possível dos candidatos). `recall_at_k` já existe.

- [ ] **Step 1: Failing tests** com valores calculados à mão para cada função, incluindo `test_tese_sem_relevante_excluida` (todas None) e `test_judged_e_nao_julgado_vale_zero`.
- [ ] **Step 2–4:** RED → implementar → GREEN + suíte.
- [ ] **Step 5: Commit** `"Adiciona MRR, P@k, MAP, Judged e teto às métricas"`.

### Task 9: Benchmark — rodar sistemas e relatório com estatística

**Files:**
- Modify: `pyproject.toml` (`scipy`)
- Create: `avaliacao/benchmark.py`
- Test: `tests/test_avaliacao_benchmark.py`

**Interfaces:**
- Consumes: Tasks 1, 3, 4, 6, 8.
- Produces:
  - `rodar(teses, deps, sistemas, rerankers) -> dict` — por tese e sistema: ids do top-20 e latência em segundos; por tese também os 30 candidatos do híbrido e o top-10 do BM25 e do denso (para teto e perdidos). Grava `data/eval/runs/<AAAA-MM-DD_HHMMSS>_runs.json` com commit, sistemas e modelos.
  - `avaliar_runs(runs: dict, rotulos: Callable[[uuid.UUID], tuple[dict, dict]]) -> dict` — métricas por tese e sistema; médias com contagem de excluídas; latência mediana e p95 por sistema; teto (nDCG@10 ideal dos 30 candidatos); perdidos (relevantes ≥ 2 do top-10 do BM25 ou do denso fora dos 30); contrastes registrados com diferença média, IC95% bootstrap, p do t pareado com Holm e p do Wilcoxon com BH; concordância entre avaliadores (kappa, alfa, AC2) e o número de pares pendentes.
  - CLI `python -m avaliacao.benchmark rodar [--sistemas S0,...,S6] [--split dev|teste|todos]` e `relatorio RUNS.json` (grava o JSON do relatório e imprime uma tabela legível com nDCG@10, MRR@10, P@5, P@10, Recall@10, MAP@10, Judged@10 e latência por sistema).

- [ ] **Step 1: Failing tests** com runs e rótulos montados à mão: médias por sistema, excluídas, contrastes (com uma diferença sintética clara o p < 0,05; com diferenças nulas o p não é significativo), teto, perdidos, Judged@10.
- [ ] **Step 2–4:** RED → implementar → GREEN + suíte.
- [ ] **Step 5: Smoke real:** `rodar --sistemas S0,S1,S2,S3 --split todos` nas teses que existirem no banco (sem julgamento humano, as métricas saem None; o objetivo é validar runs e latência) e `relatorio` sobre o arquivo gerado. Registre os tempos por sistema no report.
- [ ] **Step 6: Commit** `"Adiciona o benchmark multissistema com relatório estatístico"`.

### Task 10: README

**Files:**
- Modify: `README.md` (seção "Avaliação da busca": pool novo, planilha de julgamento, rótulo final, teses de advogado, sistemas S0–S6, `benchmark rodar|relatorio`, `AVALIACAO_ADJUDICADOR`, grupo `benchmark`)

- [ ] **Step 1:** Escrever a seção com os comandos reais (conferir com `--help`).
- [ ] **Step 2:** Suíte completa.
- [ ] **Step 3: Commit** `"Documenta a etapa 2 do benchmark no README"`.
