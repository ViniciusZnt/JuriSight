# Harness de Avaliação JuriSight — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Construir o passo 0 (teste do Jev em português) e a etapa 1 (conjunto-ouro com relevância + stance, tela de rotulação e comando `eval`) descritos no spec.

**Architecture:** Novo pacote `avaliacao/` no padrão de `auth/`/`conversations/` (psycopg puro, sem FastAPI dentro). A lógica do `/query` é extraída para `query/search/pipeline.py::buscar` e reusada pelo eval. Juiz = Jev via `typesafe-sdk`, atrás de um protocolo `Juiz`. Rotas finas em `query/api/avaliacao_routes.py` e página `/avaliacao` no Next.js.

**Tech Stack:** Python 3.13 + uv, FastAPI, psycopg 3, Postgres (schema novo `avaliacao`), `typesafe-sdk` 0.7.5 (import `typesafe_sdk`), OpenAI SDK (geração de teses), Next.js 16 / React, pytest, Jest.

**Spec:** `docs/superpowers/specs/2026-10-17-harness-avaliacao-design.md`

## Global Constraints

- Juiz: Jev, modelo lido de `TYPESAFE_MODEL` (padrão `jev-1.13.0`), chave `TYPESAFE_API_KEY`. Nunca `jev-latest`.
- Gerador de teses: OpenAI, modelo de `OPENAI_GEN_MODEL` (padrão `gpt-4o-mini`), chave `OPENAI_API_KEY` já existente.
- Relevância: inteiro 0–3. Stance: `"fortalece" | "enfraquece" | "neutro"`.
- Relevante = relevância ≥ 2.
- Kappa: Cohen simples para stance, ponderado **quadrático** para relevância; aprovação ≥ 0,6; calculado só sobre a metade `sorteada`.
- Amostra: 75 `sorteada` + 75 `incerta`.
- Pool: top-20 de cada corredor (`bm25`, `vetorial`, `pipeline`).
- Fundamentação no estado do juiz truncada em 3.000 caracteres.
- Concorrência das chamadas ao Jev: 8 threads.
- Rótulo final de um par: humano se existir, senão Jev rodada 1.
- Toda rodada grava a versão do Jev; relatórios do eval em `data/eval/runs/` com data, commit git e versão do Jev.
- Acesso à tela: e-mails em `AVALIACAO_EMAILS` (separados por vírgula).
- Seed fixa para sorteios: `AVALIACAO_SEED` (padrão `42`).
- Testes do pacote rodam sem infraestrutura real (fakes); integração real só em testes `skipif` sem `DATABASE_URL`/`TYPESAFE_API_KEY`.
- Textos de UI e mensagens em português.
- Commits terminam com `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.

## Review Focus

1. **Jev falha no meio de um lote** (429, 5xx, timeout): o que já foi julgado fica salvo e rodar o comando de novo continua de onde parou, sem rejulgar pares que já têm julgamento daquela rodada → teste em Task 9 (`test_construir_retoma_sem_rejulgar`).
2. **Acórdão sem ementa ou sem fundamentação** (`None`/vazio) no pool: o juiz recebe string vazia no campo ausente; se os dois estiverem vazios o par é descartado do pool → testes em Task 4 (`test_estado_com_campos_ausentes`) e Task 6 (`test_pool_descarta_documento_sem_texto`).
3. **Kappa degenerado** (todos os rótulos iguais dos dois lados, ou menos de 2 pares): devolve `None` em vez de dividir por zero, e o relatório mostra "indefinido" → teste em Task 2 (`test_kappa_degenerado_retorna_none`).
4. **Tese sem nenhum par relevante no conjunto-ouro**: Recall@20 é indefinido para ela e é excluída da média (contagem de excluídas no relatório), nDCG idem → teste em Task 2 (`test_recall_sem_relevantes_retorna_none`) e Task 10 (`test_eval_ignora_teses_sem_relevantes`).
5. **Rotulador fora da lista ou fila acabada**: e-mail fora de `AVALIACAO_EMAILS` → 403; sem mais pares → 200 com `{"par": null, "feitos": n, "total": n}` e a tela mostra "Tudo rotulado" → testes em Task 11.

---

### Task 1: Extrair o pipeline do `/query`

**Files:**
- Create: `query/search/pipeline.py`
- Modify: `query/api/app.py` (corpo de `query()`, `_aplicar_filtros`, `_normalizar_scores` e constantes `N_*` saem daqui)
- Test: `tests/test_pipeline.py`; `tests/test_api.py` continua passando sem mudança (ajustar só imports de `_normalizar_scores`/`N_*` se referenciados via `api_app.`)

**Interfaces:**
- Produces: `buscar(estrutura: EstruturaArgumentativa, *, hybrid, retriever, reranker, provimento: Provimento | None = None, data_inicio: date | None = None, data_fim: date | None = None, ordenar_por: str = "relevancia") -> list[ResultCard]` em `query/search/pipeline.py`. Levanta `ValueError` (vinda do query_builder) para estrutura vazia. Constantes `N_RESULTS_FINAL=20`, `N_CANDIDATOS_PARA_RERANK=30`, `N_CANDIDATOS_COM_FILTRO=80`, e funções `aplicar_filtros`, `normalizar_scores` movem para cá (sem underscore). `app.py` reexporta os nomes antigos (`_normalizar_scores = normalizar_scores`, `N_CANDIDATOS_PARA_RERANK`, etc.) para os testes existentes.

- [ ] **Step 1: Write the failing test** em `tests/test_pipeline.py`: `test_buscar_ordena_hierarquia_e_corta_em_20` — usa `_FakeHybrid`, `_FakeDocRetriever`, `_FakeReranker` (copiar de `tests/test_api.py`), 25 docs acórdão + 1 súmula; assert `len(resultado) == 20` e `resultado[0].tipo_documento == TipoDocumento.SUMULA`. E `test_buscar_estrutura_vazia_levanta_value_error`.
- [ ] **Step 2: Run** `uv run pytest tests/test_pipeline.py -v` → FAIL (`ModuleNotFoundError: query.search.pipeline`).
- [ ] **Step 3: Implement** movendo o corpo atual de `query()` para `buscar` (síncrono — o endpoint chama via `run_in_threadpool(buscar, ...)`, convertendo `ValueError` em 422 como hoje).
- [ ] **Step 4: Run** `uv run pytest tests/test_pipeline.py tests/test_api.py -q` → todos PASS.
- [ ] **Step 5: Commit** `git commit -m "Extrai o pipeline do /query para query/search/pipeline.py"`.

### Task 2: Métricas

**Files:**
- Create: `avaliacao/__init__.py` (vazio), `avaliacao/metricas.py`
- Test: `tests/test_avaliacao_metricas.py`

**Interfaces:**
- Produces (em `avaliacao/metricas.py`):
  - `ndcg_at_k(ranking: list[str], ganhos: dict[str, int], k: int = 10) -> float | None` — ganho = relevância; doc fora de `ganhos` = 0; DCG com `(2**g - 1) / log2(i + 2)`; `None` se o ideal for 0.
  - `recall_at_k(ranking: list[str], ganhos: dict[str, int], k: int = 20, limiar: int = 2) -> float | None` — `None` se não há relevantes.
  - `fracao_fortalece(ranking: list[str], ganhos: dict[str, int], stances: dict[str, str], k: int = 10) -> float | None` — entre os relevantes do top-k; `None` se nenhum.
  - `fracao_nao_julgados(ranking: list[str], ganhos: dict[str, int], k: int = 10) -> float`.
  - `kappa_cohen(a: list[str], b: list[str]) -> float | None`.
  - `kappa_ponderado_quadratico(a: list[int], b: list[int], n_niveis: int = 4) -> float | None`.

- [ ] **Step 1: Write failing tests:**
  - `test_ndcg_ranking_ideal_e_1`: `ndcg_at_k(["a","b"], {"a":3,"b":1}) == 1.0`.
  - `test_ndcg_invertido_menor_que_1`: `ndcg_at_k(["b","a"], {"a":3,"b":1}) < 1.0`.
  - `test_recall_conta_so_relevancia_2_ou_mais`: `recall_at_k(["a","x"], {"a":2,"b":3,"c":1}, k=2) == 0.5`.
  - `test_recall_sem_relevantes_retorna_none`: `recall_at_k(["a"], {"a":1}) is None`.
  - `test_fracao_fortalece`: ranking `["a","b","c"]`, ganhos `{"a":3,"b":2,"c":0}`, stances `{"a":"fortalece","b":"enfraquece","c":"fortalece"}` → `0.5`.
  - `test_fracao_nao_julgados`: `fracao_nao_julgados(["a","z","y"], {"a":1}, k=3) == pytest.approx(2/3)`.
  - `test_kappa_concordancia_perfeita_e_1`: `kappa_cohen(["f","e","n"], ["f","e","n"]) == 1.0`.
  - `test_kappa_valor_conhecido`: `kappa_cohen(["s","s","n","n"], ["s","n","n","n"]) == pytest.approx(0.5)`.
  - `test_kappa_ponderado_penaliza_distancia`: `kappa_ponderado_quadratico([0,3,1,2],[1,3,1,2]) > kappa_ponderado_quadratico([0,3,1,2],[3,3,1,2])`.
  - `test_kappa_degenerado_retorna_none`: `kappa_cohen(["n","n"], ["n","n"]) is None`, `kappa_cohen(["n"], ["f"]) is None` (menos de 2), idem para o ponderado.
- [ ] **Step 2: Run** `uv run pytest tests/test_avaliacao_metricas.py -v` → FAIL.
- [ ] **Step 3: Implement** em Python puro (sem numpy/sklearn). Kappa: `(po - pe) / (1 - pe)`, `None` quando `len < 2` ou `pe == 1`. Ponderado quadrático: pesos `w_ij = (i-j)**2 / (n-1)**2`, `1 - Σw·O / Σw·E`, `None` se denominador 0.
- [ ] **Step 4: Run** → PASS.
- [ ] **Step 5: Commit** `"Adiciona métricas do harness (nDCG, Recall, kappa)"`.

### Task 3: Schema e store do conjunto-ouro

**Files:**
- Create: `avaliacao/db.py`, `avaliacao/store.py`
- Modify: `query/api/app.py` (lifespan chama `avaliacao.db.ensure_schema` e cria `app.state.avaliacao_store`)
- Test: `tests/test_avaliacao_store_integration.py` (skipif sem Postgres, padrão de `tests/test_conversa_store_integration.py`)

**Interfaces:**
- Produces:
  - `avaliacao.db.ensure_schema(database_url: str | None = None) -> None` — cria schema `avaliacao` e tabelas `teses`, `pares`, `julgamentos`, `amostra` exatamente como §3.2 do spec (checks em `origem`, `split`, `relevancia BETWEEN 0 AND 3`, `stance IN (...)`, `metade IN ('sorteada','incerta')`; `unique(tese_id, documento_id)` em `pares`; `unique(par_id, juiz, rodada)` em `julgamentos`; `amostra.par_id` PK).
  - Dataclasses em `avaliacao/store.py`: `Tese(id: uuid.UUID, estrutura: dict, origem: str, tema: str, split: str, documento_origem_id: str | None)`, `Par(id: uuid.UUID, tese_id: uuid.UUID, documento_id: str, corredores: list[str])`, `Julgamento(par_id: uuid.UUID, juiz: str, rodada: int, relevancia: int, stance: str, relevancia_probs: dict | None = None, stance_probs: dict | None = None, confianca_rel: float | None = None, confianca_stance: float | None = None)`.
  - `AvaliacaoStore(database_url: str)` com:
    - `criar_tese(estrutura: dict, origem: str, tema: str, split: str, documento_origem_id: str | None = None) -> Tese`
    - `listar_teses(split: str | None = None) -> list[Tese]`
    - `adicionar_pares(tese_id: uuid.UUID, docs: dict[str, list[str]]) -> list[Par]` — `docs` = documento_id → corredores; upsert que **une** corredores em conflito.
    - `pares_da_tese(tese_id: uuid.UUID) -> list[Par]`
    - `pares_sem_julgamento(juiz: str, rodada: int) -> list[Par]`
    - `gravar_julgamento(j: Julgamento) -> None` — upsert por `(par_id, juiz, rodada)`.
    - `julgamentos(juiz_prefixo: str | None = None) -> list[Julgamento]` (`"jev:"` ou `"humano:"`)
    - `rotulos_finais(tese_id: uuid.UUID) -> tuple[dict[str, int], dict[str, str]]` — documento_id → relevância e → stance; humano prevalece sobre Jev rodada 1.
    - `definir_amostra(par_ids: dict[uuid.UUID, str]) -> None`; `amostra() -> dict[uuid.UUID, str]`
    - `proximo_da_fila(juiz: str) -> tuple[Par, Tese] | None` — próximo par da `amostra` sem julgamento desse juiz humano, ordenado por `metade` (sorteada primeiro) e id; `progresso(juiz: str) -> tuple[int, int]`.

- [ ] **Step 1: Write failing integration tests:** `test_round_trip_tese_par_julgamento`, `test_adicionar_pares_une_corredores` (mesmo doc vindo de `bm25` depois `pipeline` → `corredores == ["bm25","pipeline"]`), `test_rotulo_humano_prevalece`, `test_fila_segue_ordem_e_progresso`, `test_pares_sem_julgamento_ignora_rodada_feita`. Cada teste cria dados com UUIDs próprios e apaga as teses ao final (`ON DELETE CASCADE`).
- [ ] **Step 2: Run** `set -a; source .env; set +a; uv run pytest tests/test_avaliacao_store_integration.py -v` → FAIL.
- [ ] **Step 3: Implement** `db.py` (DDL idempotente) e `store.py` (uma conexão por chamada, `psycopg.types.json.Json` para JSONB, casts explícitos `%s::tipo` em `jsonb_build_object` se usado — ver o bug documentado em `tests/test_conversa_store_integration.py`).
- [ ] **Step 4: Run** → PASS; `uv run pytest tests/ -q --ignore=tests/test_api_stress.py` sem regressões.
- [ ] **Step 5: Commit** `"Adiciona schema e store do conjunto-ouro (avaliacao)"`.

### Task 4: Juiz Jev e temas

**Files:**
- Modify: `pyproject.toml`/`uv.lock` (`uv add typesafe-sdk`), `.env.example` (adicionar `AVALIACAO_EMAILS=`, `AVALIACAO_SEED=42`, `OPENAI_GEN_MODEL=gpt-4o-mini` com comentário)
- Create: `avaliacao/juiz.py`, `avaliacao/temas.py`
- Test: `tests/test_avaliacao_juiz.py`

**Interfaces:**
- Consumes: `Julgamento` (Task 3).
- Produces:
  - `avaliacao/juiz.py`: `class Juiz(Protocol): nome: str; def julgar(self, tese: dict, documento: DocumentoJuridico, rodada: int, par_id: uuid.UUID) -> Julgamento`.
  - `montar_estado(tese: dict, documento: DocumentoJuridico) -> dict` → `{"tese": tese, "acordao": {"ementa": str, "fundamentacao_inicio": str}}` (`None` → `""`, fundamentação `[:3000]`).
  - `PERGUNTAS: dict[str, Score | Choice]` com chaves `"relevancia"` (Score, `criteria` = os 4 níveis do spec §3.3, na ordem 0→3) e `"stance"` (Choice, `criteria` = `{"fortalece": ..., "enfraquece": ..., "neutro": ...}` com as descrições do spec). Texto copiado do spec.
  - `class JuizJev: __init__(self, client: TypeSafeClient | None = None, model: str | None = None)`; `nome = f"jev:{model}"`; `julgar(...)` chama `client.system_one(state=montar_estado(...), questions=PERGUNTAS, model=self.model)` e converte: `relevancia = int(argmax(answers["relevancia"].probabilities))`, `relevancia_probs = probabilities`, `confianca_rel = answers["relevancia"].confidence`; stance de `answers["stance"].choice`/`.probabilities`/`.confidence`.
  - `julgar_lote(juiz: Juiz, itens: list[tuple[uuid.UUID, dict, DocumentoJuridico]], rodada: int, ao_julgar: Callable[[Julgamento], None], max_workers: int = 8) -> int` — chama `ao_julgar` a cada sucesso; exceções do SDK de um item são registradas (log) e o item é pulado; devolve quantos deram certo.
  - `avaliacao/temas.py`: `TEMAS: list[str]` = `["insalubridade", "periculosidade", "horas extras", "intervalo intrajornada", "dano moral", "assédio moral", "acidente de trabalho / doença ocupacional", "vínculo empregatício", "rescisão indireta", "equiparação salarial", "estabilidade", "verbas rescisórias", "outro"]`; `atribuir_tema(estrutura: dict, client: TypeSafeClient | None = None, model: str | None = None) -> str` (Choice com critérios = os temas).

- [ ] **Step 1: Write failing tests** com um `_FakeClient` cujo `system_one` grava os argumentos e devolve um objeto com `.answers` contendo fakes `score/probabilities/confidence` e `choice/probabilities/confidence`:
  - `test_julgar_converte_resposta`: probs relevância `{"0":.1,"1":.1,"2":.7,"3":.1}`, stance `"enfraquece"` → `Julgamento(relevancia=2, stance="enfraquece", juiz="jev:jev-1.13.0", ...)`.
  - `test_estado_com_campos_ausentes`: documento com `ementa=None`, fundamentação de 5.000 chars → `estado["acordao"]["ementa"] == ""` e `len(fundamentacao_inicio) == 3000`.
  - `test_modelo_fixado_por_env` (monkeypatch `TYPESAFE_MODEL="jev-x"`) → chamada com `model="jev-x"`.
  - `test_julgar_lote_pula_falha_e_segue`: fake levanta `TypeSafeRateLimitError` num item → retorna `n-1`, `ao_julgar` chamado `n-1` vezes.
  - `test_atribuir_tema_retorna_item_da_lista`.
  - `test_jev_real_responde_em_portugues` marcado `skipif(not TYPESAFE_API_KEY)`: uma chamada real com o exemplo de EPI do spec; asserta só tipos e faixas (`0 <= relevancia <= 3`, stance no conjunto).
- [ ] **Step 2: Run** `uv run pytest tests/test_avaliacao_juiz.py -v` → FAIL.
- [ ] **Step 3: Implement** (após `uv add typesafe-sdk`); `TypeSafeClient()` lê `TYPESAFE_API_KEY` sozinho; `model` padrão `os.getenv("TYPESAFE_MODEL", "jev-1.13.0")`.
- [ ] **Step 4: Run** com `.env` carregado → todos PASS (incluindo o real).
- [ ] **Step 5: Commit** `"Adiciona juiz Jev (relevância + stance) e atribuição de tema"`.

### Task 5: Teses (sintéticas, reais, split)

**Files:**
- Create: `avaliacao/geracao.py`
- Test: `tests/test_avaliacao_geracao.py`

**Interfaces:**
- Consumes: `Juiz`, `JuizJev` (Task 4), `atribuir_tema` (Task 4), `AvaliacaoStore` (Task 3).
- Produces:
  - `sortear_acordaos(database_url: str, n: int, seed: int) -> list[DocumentoJuridico]` — `tipo_documento='ACORDAO' AND possui_ementa`, metade com `provimento='APROVADO'`/`PARCIAL`, metade `NEGADO` (`ORDER BY md5(id::text || seed)`).
  - `gerar_tese(documento: DocumentoJuridico, lado: Literal["favoravel","contrario"], client: OpenAI | None = None) -> EstruturaArgumentativa` — `chat.completions` com `response_format` JSON schema de `EstruturaArgumentativa`, `temperature=0.7`, modelo `OPENAI_GEN_MODEL`; prompt pede a tese de um advogado para quem o acórdão é favorável (`favoravel`) ou contrário (`contrario`).
  - `passa_filtro(juiz: Juiz, tese: dict, documento: DocumentoJuridico) -> bool` — `P(relevância ≥ 2) = probs["2"] + probs["3"] >= 0.5`.
  - `teses_reais(database_url: str) -> list[dict]` — estrutura de cada versão em `public.conversas.versoes`, dedup por `json.dumps(sort_keys=True)`.
  - `sortear_split(temas: list[str], seed: int, fracao_teste: float = 0.4) -> dict[str, str]` — tema → `"dev"|"teste"`; determinístico; pelo menos 1 tema em cada lado se houver ≥2 temas.

- [ ] **Step 1: Write failing tests:** `test_gerar_tese_valida_schema` (fake OpenAI devolvendo JSON → `EstruturaArgumentativa`; prompt contém o lado), `test_filtro_usa_prob_relevancia_2_ou_mais` (probs `{"0":.3,"1":.3,"2":.2,"3":.2}` → False; `{"2":.3,"3":.3}` → True), `test_split_deterministico_e_cobre_os_dois_lados`, `test_teses_reais_deduplica` (com fake de cursor ou integração skipif).
- [ ] **Step 2: Run** → FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** → PASS.
- [ ] **Step 5: Commit** `"Adiciona geração de teses sintéticas, teses reais e split por tema"`.

### Task 6: Pooling

**Files:**
- Create: `avaliacao/pooling.py`
- Test: `tests/test_avaliacao_pooling.py`

**Interfaces:**
- Consumes: `buscar` (Task 1); `HybridSearch` internals (`hybrid.bm25.search(texto, n)`, `hybrid.embedder.embed_text(texto)`, `hybrid.store.query(vetor, n_results=..., collection=...)`, `COLLECTION_COMPLETO/EMENTA`, `reciprocal_rank_fusion`, `_doc_id_do_chunk`, `_dedup_ordenado` de `query/search/hybrid_search.py`); `query_builder.build_bm25_query/build_frase_tese`.
- Produces: `montar_pool(estrutura: EstruturaArgumentativa, *, hybrid, retriever, reranker, k: int = 20) -> dict[str, list[str]]` — documento_id → corredores (`"bm25"`, `"vetorial"`, `"pipeline"`), cada corredor contribuindo seu top-k de **documentos**; documentos cujo `ementa` e `fundamentacao` estão ambos vazios (via `retriever.fetch`) são removidos.

- [ ] **Step 1: Write failing tests** com fakes (`_FakeBM25` devolvendo chunk_ids `"d1:0","d1:1","d2:0"`, `_FakeStore`, `_FakeEmbedder`, `_FakeRetriever`): `test_pool_une_corredores_e_colapsa_chunks` (`d1` aparece uma vez, com `["bm25","vetorial"]` quando vem dos dois), `test_cada_corredor_limitado_a_k`, `test_pool_descarta_documento_sem_texto`.
- [ ] **Step 2: Run** → FAIL.
- [ ] **Step 3: Implement** (vetorial = RRF das duas coleções Qdrant, como em `HybridSearch.search`, sem BM25; pipeline = ids do `buscar`).
- [ ] **Step 4: Run** → PASS.
- [ ] **Step 5: Commit** `"Adiciona pooling de 3 corredores"`.

### Task 7: Amostra mista

**Files:**
- Create: `avaliacao/amostra.py`
- Test: `tests/test_avaliacao_amostra.py`

**Interfaces:**
- Consumes: `Par`, `Julgamento`, `Tese` (Task 3).
- Produces: `escolher_amostra(itens: list[ItemAmostra], *, n_sorteada: int = 75, n_incerta: int = 75, seed: int, obrigatorios: set[uuid.UUID] = frozenset()) -> dict[uuid.UUID, str]` onde `ItemAmostra = NamedTuple(par_id: uuid.UUID, tema: str, origem: str, relevancia: int, stance: str, confianca: float)` (`confianca = min(confianca_rel, confianca_stance)`).
  - Sorteada: `obrigatorios` (pares do passo 0) entram primeiro; o resto é preenchido por estrato `(tema, relevancia, stance, origem)` em round-robin com ordem embaralhada pela seed, até `n_sorteada`.
  - Incerta: menores `confianca` entre os não sorteados, até `n_incerta`.

- [ ] **Step 1: Write failing tests:** `test_tamanhos_e_disjuncao`, `test_obrigatorios_entram_na_sorteada`, `test_estratos_raros_representados` (estrato com 1 item aparece na sorteada), `test_incerta_pega_menor_confianca`, `test_deterministico_pela_seed`, `test_menos_itens_que_o_pedido` (devolve todos, sem erro).
- [ ] **Step 2: Run** → FAIL. **Step 3: Implement.** **Step 4: Run** → PASS.
- [ ] **Step 5: Commit** `"Adiciona amostra mista da especialista"`.

### Task 8: Passo 0 (CLI)

**Files:**
- Create: `avaliacao/contexto.py`, `avaliacao/passo_zero.py`
- Test: `tests/test_avaliacao_passo_zero.py`

**Interfaces:**
- Consumes: Tasks 1, 3–6.
- Produces:
  - `avaliacao/contexto.py`: `carregar_dependencias() -> SimpleNamespace(hybrid, retriever, reranker, store: AvaliacaoStore, database_url)` — monta o mesmo que o lifespan de `app.py` (carrega `.env` via `python-dotenv`).
  - `python -m avaliacao.passo_zero preparar [--teses 5] [--por-tese 4]`: gera teses sintéticas (Task 5, metade favorável/contrário), grava no store com `split` pela regra da Task 5; por tese escolhe 4 docs = top-2 do `buscar` + 1 doc da posição 15–20 + 1 doc de outra tese (tema diferente); julga com Jev **rodadas 1 e 2**; escreve `data/eval/passo_zero.csv` com colunas `par_id,tese,ementa,link,relevancia_alexia,stance_alexia` (sem notas do Jev).
  - `python -m avaliacao.passo_zero comparar [--csv data/eval/passo_zero.csv] [--rotulador email]`: grava os rótulos preenchidos como `humano:<email>`, imprime kappa ponderado (relevância), kappa (stance), concordância rodada 1 × 2, matriz de confusão de stance; funções puras `resumo_comparacao(humanos: list[Julgamento], jev1: list[Julgamento], jev2: list[Julgamento]) -> dict`.
  - Antes de qualquer chamada paga, imprime `pares × ~1.300 tokens` e pede confirmação (flag `--sim` pula).

- [ ] **Step 1: Write failing tests:** `test_resumo_comparacao_valores` (listas pequenas montadas à mão → kappas e matriz esperados), `test_ler_csv_ignora_linhas_nao_preenchidas`, `test_csv_nao_vaza_nota_do_jev` (cabeçalho exato).
- [ ] **Step 2: Run** → FAIL. **Step 3: Implement.** **Step 4: Run** → PASS.
- [ ] **Step 5: Smoke real:** `uv run python -m avaliacao.passo_zero preparar --teses 1 --por-tese 2 --sim` → CSV com 2 linhas e 4 julgamentos Jev no banco.
- [ ] **Step 6: Commit** `"Adiciona CLI do passo 0 (teste do Jev em português)"`.

### Task 9: Construção do conjunto-ouro (CLI)

**Files:**
- Create: `avaliacao/construir.py`
- Test: `tests/test_avaliacao_construir.py`

**Interfaces:**
- Consumes: Tasks 3–7, `carregar_dependencias` (Task 8).
- Produces: `python -m avaliacao.construir [--teses 100] [--rodadas 2] [--sim]` em etapas idempotentes, cada uma pulando o que já existe:
  1. teses: completa até `--teses` com reais (Task 5) + sintéticas filtradas; tema por `atribuir_tema`; split por `sortear_split`.
  2. pool: `montar_pool` para teses sem pares.
  3. julgamento: `pares_sem_julgamento("jev:<versão>", r)` para `r in 1..rodadas`, via `julgar_lote` gravando a cada sucesso.
  4. amostra: `escolher_amostra` (obrigatórios = pares já com julgamento humano) → `definir_amostra`, só se ainda não houver amostra.
  - Função testável `etapa_julgamento(store, juiz, carregar_doc: Callable[[str], DocumentoJuridico], rodadas: int) -> int`.
  - Antes das etapas 1 e 3 imprime a estimativa (`chamadas × ~1.300 tokens` no Jev, `teses × ~1.500 tokens` na OpenAI) e pede confirmação; `--sim` pula. `passa_filtro` (Task 5) chama `juiz.julgar(..., rodada=0, par_id=uuid4())` e não grava o resultado.

- [ ] **Step 1: Write failing test** `test_construir_retoma_sem_rejulgar`: store fake com 3 pares, juiz fake que falha no 2º par na primeira execução; após duas execuções de `etapa_julgamento`, cada par tem exatamente 1 julgamento por rodada e o juiz foi chamado 4 vezes no total para `rodadas=1` (3 + 1 retry).
- [ ] **Step 2: Run** → FAIL. **Step 3: Implement.** **Step 4: Run** → PASS.
- [ ] **Step 5: Commit** `"Adiciona construção idempotente do conjunto-ouro"`.

### Task 10: Comando eval

**Files:**
- Create: `avaliacao/eval.py`
- Test: `tests/test_avaliacao_eval.py`

**Interfaces:**
- Consumes: `buscar` (Task 1), métricas (Task 2), `AvaliacaoStore.rotulos_finais/listar_teses/julgamentos` (Task 3), `carregar_dependencias` (Task 8).
- Produces:
  - `avaliar(teses: list[Tese], buscar_ids: Callable[[dict], list[str]], rotulos: Callable[[uuid.UUID], tuple[dict[str,int], dict[str,str]]]) -> dict` — por tese calcula as 4 métricas; agrega médias por `split` e por `origem` ignorando `None`, com `excluidas` (contagem) por métrica.
  - `concordancia_reteste(julgamentos: list[Julgamento]) -> dict` — kappa ponderado e kappa stance entre rodada 1 e 2 do mesmo juiz.
  - `kappas_calibracao(store) -> dict` — kappas humano × Jev rodada 1 só na metade `sorteada`; limite de confiança pelos `incerta` (menor limite com acurácia ≥ 0,8 acima dele, `None` se nenhum).
  - CLI `python -m avaliacao.eval --split {dev,teste} [--saida data/eval/runs/]`: imprime tabela legível e grava `data/eval/runs/<AAAA-MM-DD_HHMMSS>_<split>.json` com `commit` (`git rev-parse --short HEAD`), `modelo_jev`, métricas, reteste e calibração.

- [ ] **Step 1: Write failing tests:** `test_eval_agrega_por_split_e_origem` (2 teses com rótulos conhecidos → médias esperadas), `test_eval_ignora_teses_sem_relevantes` (`excluidas["recall_20"] == 1`), `test_reteste_concordancia_perfeita`, `test_kappa_calibracao_usa_so_sorteada`, `test_limite_confianca`.
- [ ] **Step 2: Run** → FAIL. **Step 3: Implement.** **Step 4: Run** → PASS.
- [ ] **Step 5: Commit** `"Adiciona comando eval do harness"`.

### Task 11: Rotas de rotulação

**Files:**
- Create: `query/api/avaliacao_routes.py`
- Modify: `query/api/app.py` (`include_router`), `.env` não (só `.env.example` já feito na Task 4)
- Test: `tests/test_avaliacao_routes.py`

**Interfaces:**
- Consumes: `get_current_user` (`query/api/auth_routes.py`), `AvaliacaoStore` (Task 3), `DocRetriever`.
- Produces:
  - `get_avaliacao_store(request) -> AvaliacaoStore` (de `app.state`); `exigir_rotulador(usuario = Depends(get_current_user)) -> Usuario` — 403 `"Acesso restrito à avaliação."` se `usuario.email.lower()` não está em `AVALIACAO_EMAILS`.
  - `GET /avaliacao/fila` → `{"par": {"id", "tese": EstruturaArgumentativa, "documento": {"id","ementa","fundamentacao_inicio","link_original","numero_processo","tribunal"}} | null, "feitos": int, "total": int}`; juiz humano = `f"humano:{email}"`; nunca inclui julgamentos do Jev.
  - `POST /avaliacao/pares/{par_id}/rotulo` body `{"relevancia": 0..3, "stance": "fortalece"|"enfraquece"|"neutro"}` → 204; 422 fora da faixa; 404 par fora da amostra.

- [ ] **Step 1: Write failing tests** (padrão `dependency_overrides` de `tests/test_conversa_routes.py`, store fake): `test_fila_retorna_par_sem_nota_do_jev`, `test_fila_vazia_retorna_par_null`, `test_email_fora_da_lista_403`, `test_rotulo_grava_julgamento_humano`, `test_rotulo_invalido_422`, `test_par_fora_da_amostra_404`.
- [ ] **Step 2: Run** → FAIL. **Step 3: Implement.** **Step 4: Run** → PASS + suíte completa.
- [ ] **Step 5: Commit** `"Adiciona rotas de rotulação da avaliação"`.

### Task 12: Tela `/avaliacao`

**Files:**
- Create: `frontend/src/app/(app)/avaliacao/page.tsx`, `frontend/src/components/avaliacao/rotulacao-page.tsx`
- Modify: `frontend/src/lib/api.ts` (`ParAvaliacao`, `FilaAvaliacao`, `obterFilaAvaliacao(): Promise<FilaAvaliacao>`, `enviarRotulo(parId: string, relevancia: number, stance: "fortalece"|"enfraquece"|"neutro"): Promise<void>`)
- Test: `frontend/src/__tests__/components/rotulacao-page.test.tsx`

**Interfaces:**
- Consumes: rotas da Task 11.
- Produces: página com tese no topo (pedido principal, tese central, normas), um acórdão por vez (número do processo, tribunal, ementa, trecho da fundamentação, link "Ver inteiro teor"), botões "0 Nada a ver", "1 Tema vizinho", "2 Mesmo pedido", "3 Mesmo caso" e "Fortalece / Enfraquece / Neutro", atalhos `1–4` (relevância 0–3) e `F/E/N`; envia quando os dois estão escolhidos e carrega o próximo; progresso "X de Y"; estados: carregando, erro com "Tentar de novo", 403 → "Acesso restrito à avaliação.", fila vazia → "Tudo rotulado. Obrigado!". Mesmo visual das outras páginas (tokens/classes de `search-results-page.tsx`).

- [ ] **Step 1: Write failing tests** (Jest + RTL, mock de `@/lib/api`): `envia_rotulo_com_atalhos` (teclas `3` e `F` → `enviarRotulo(id, 2, "fortalece")`), `mostra_tudo_rotulado_quando_fila_vazia`, `mostra_acesso_restrito_em_403`, `nao_envia_com_so_um_eixo_escolhido`.
- [ ] **Step 2: Run** `cd frontend && npx jest rotulacao-page` → FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** jest → PASS; `npx tsc --noEmit` limpo.
- [ ] **Step 5: Verificar no navegador** com backend + frontend no ar e um e-mail em `AVALIACAO_EMAILS`: rotular 2 pares e conferir no banco.
- [ ] **Step 6: Commit** `"Adiciona tela de rotulação /avaliacao"`.

### Task 13: Documentação

**Files:**
- Modify: `README.md` (seção "Avaliação da busca": o que é, passo 0, `construir`, `/avaliacao`, `eval`, variáveis novas; linha na tabela de testes; `avaliacao/` na árvore de pastas)

- [ ] **Step 1:** Escrever a seção com os comandos exatos das Tasks 8–10 e as variáveis `TYPESAFE_API_KEY`, `TYPESAFE_MODEL`, `OPENAI_GEN_MODEL`, `AVALIACAO_EMAILS`, `AVALIACAO_SEED`.
- [ ] **Step 2: Run** `uv run pytest tests/ -q --ignore=tests/test_api_stress.py` e `cd frontend && npx jest --silent && npx tsc --noEmit` → tudo PASS.
- [ ] **Step 3: Commit** `"Documenta o harness de avaliação no README"`.
