# Provimento do Jev e filtro antes da busca — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ajustar as perguntas do provimento (Parte A) e fazer os três canais da busca (BM25, Qdrant completo, Qdrant ementa) buscarem só entre acórdãos do provimento escolhido (Parte B).

**Architecture:** O provimento de `documentos.provimento` é levado, por um subcomando `sincronizar`, ao payload das duas coleções do Qdrant (com índice `keyword`) e a um arquivo `provimentos.json` paralelo aos `chunk_ids.json` do BM25. A busca passa o provimento como filtro do Qdrant e como `weight_mask` do `bm25s`. Sem filtro, nada muda.

**Tech Stack:** Python 3.13, `bm25s` 0.3.11 (`retrieve(weight_mask=...)`), `qdrant-client` (`set_payload`, `create_payload_index`, modo `:memory:` nos testes), psycopg 3, pytest.

**Spec:** `docs/superpowers/specs/2026-10-21-provimento-jev-filtro-design.md` (e, para as perguntas e a tabela, `docs/superpowers/specs/2026-10-20-provimento-jev-design.md`).

**Branch:** `feat/provimento-filtro`, criada de `refactor/limpeza-projeto`.

## Global Constraints

- Máquina com 11 GB de RAM e sem GPU; nada pode carregar o corpus inteiro na RAM (o BM25 é `mmap=True`).
- Jev: `TYPESAFE_MODEL` (padrão `jev-1.13.0`), nunca `-latest`.
- Escala: 69.349 acórdãos, 397.924 chunks em `chunks_completo`, 69.341 pontos em `chunks_ementa`.
- Valores de provimento: os do enum `scraper.schema.Provimento` (`APROVADO`, `PARCIAL`, `NEGADO`, `NAO_APLICAVEL`), sempre como `str` (`.value`) no payload e no arquivo.
- Sem filtro de provimento, os três canais recebem exatamente as mesmas chamadas de hoje (mesmo `where`, mesmo `n`, sem máscara).
- `aplicar_filtros` continua checando provimento no Postgres depois da busca (rede de segurança).
- Nunca reindexar embeddings nem chamar a OpenAI para atualizar provimento.
- Nunca escrever em `documentos.provimento` (só `aplicar --confirmar`, que é do Vinicius).
- Identificadores e docstrings em português; psycopg puro; fakes injetados nos testes; nunca imprimir nem editar o `.env`; integração com Postgres com `skipif` sem `DATABASE_URL`.
- Suíte antes de cada commit: `set -a; source .env; set +a; uv run pytest tests/ -q --ignore=tests/test_api_stress.py`.

## Review Focus

1. Índice BM25 sem `provimentos.json` (índice antigo, `sincronizar` nunca rodou) e busca com filtro → a busca não quebra: roda sem máscara, registra um aviso, e `aplicar_filtros` segura o resultado (Task 2, `test_search_sem_arquivo_ignora_filtro`).
2. Provimento raro: menos chunks daquele provimento que `n` → o BM25 não devolve chunks de score 0 de outro provimento (Task 2, `test_search_com_filtro_descarta_score_zero`).
3. `provimentos.json` com tamanho diferente de `chunk_ids.json` (índice reconstruído e `sincronizar` velho) → erro claro ao carregar, não máscara desalinhada (Task 2, `test_load_rejeita_provimentos_desalinhados`).
4. Rodar `sincronizar` duas vezes → mesmo estado, sem erro na criação dos índices (Task 3, `test_garantir_indices_idempotente`; Task 5, `test_sincronizar_idempotente`).
5. Busca sem filtro depois de toda a Parte B → mesmas chamadas aos três canais de antes (Task 4, `test_sem_filtro_chamadas_identicas`).

---

### Task 1: Ajustar as perguntas do provimento

**Files:**
- Modify: `scraper/provimento_jev.py` (`PERGUNTAS_PROVIMENTO["resultado"]`)
- Modify: `docs/superpowers/specs/2026-10-20-provimento-jev-design.md` (seção "Perguntas", mesmo texto)
- Test: `tests/test_provimento_jev.py`

**Interfaces:**
- Produces: `perguntas_sha()` com valor novo (os 90 documentos já classificados voltam a ficar pendentes, de propósito).

Texto novo (copiar literalmente; só a pergunta `resultado` muda; `recorrente` e `favorece` ficam iguais):

- instruções de `resultado`: "Qual foi o resultado do recurso julgado neste acórdão (`acordao`)? Se houver mais de um recurso, escolha parcialmente_provido só quando pelo menos um deles foi provido, no todo ou em parte; se nenhum foi provido e pelo menos um foi conhecido, escolha nao_provido. Embargos de declaração acolhidos apenas para prestar esclarecimentos, sem efeito modificativo, contam como nao_provido."
- `parcialmente_provido`: "O recurso foi provido em parte, ou há mais de um recurso e pelo menos um deles foi provido, no todo ou em parte."
- `nao_provido`: "O recurso foi conhecido, mas o provimento foi negado. Também quando há mais de um recurso e nenhum foi provido, ou quando embargos de declaração foram acolhidos só para esclarecer, sem efeito modificativo."
- `provido`, `nao_conhecido` e `sem_recurso`: sem mudança.

- [ ] **Step 1: Write failing tests:** `test_resultado_cobre_embargos_sem_efeito` (instruções e critério de `nao_provido` contêm "sem efeito modificativo"), `test_parcial_exige_algum_provido` (critério de `parcialmente_provido` contém "pelo menos um deles foi provido" e não contém "resultados diferentes"), `test_sha_mudou` (`perguntas_sha() != "73991da3abf8971271ab633ba8931ddd3b5e1b1f965df37fc47df5a9d5ab05cc"`).
- [ ] **Step 2: Run** `uv run pytest tests/test_provimento_jev.py -v` → FAIL.
- [ ] **Step 3: Implement** o texto acima nos dois arquivos.
- [ ] **Step 4: Run** o arquivo e a suíte → PASS.
- [ ] **Step 5: Commit** `"Ajusta as perguntas do provimento: embargos sem efeito e nenhum recurso provido"`.

### Task 2: Provimento por chunk no BM25

**Files:**
- Modify: `indexing/lexical/bm25_builder.py`
- Test: `tests/test_bm25.py`

**Interfaces:**
- Produces:
  - `PROVIMENTOS_FILENAME = "provimentos.json"` (lista de `str`, mesma ordem de `chunk_ids.json`).
  - `gravar_provimentos(index_path: Path, provimentos: list[str]) -> None` — grava atomicamente (`.tmp` + `os.replace`).
  - `BM25Builder.add` passa a guardar `chunk.provimento` em paralelo; `build_and_save` também grava `provimentos.json`.
  - `BM25Builder.load` carrega `provimentos.json` se existir; se o tamanho diferir de `chunk_ids`, levanta `ValueError` com mensagem que manda rodar `sincronizar`.
  - `LoadedBM25(retriever, chunk_ids, provimentos: list[str] | None = None)` monta, uma vez, uma máscara `np.float32` por valor distinto (1.0 onde o chunk tem aquele provimento, 0.0 no resto).
  - `LoadedBM25.search(query: str, n: int = 20, provimento: str | None = None) -> list[tuple[str, float]]` — com `provimento`, passa `weight_mask` ao `retrieve` e descarta resultados com score `<= 0`; provimento sem nenhum chunk devolve `[]`; sem `provimentos` carregados, ignora o filtro e registra `logger.warning` uma vez.

- [ ] **Step 1: Write failing tests** (índice real pequeno em `tmp_path`, como os testes existentes): `test_build_grava_provimentos` (arquivo existe, mesma ordem dos chunk_ids), `test_search_com_filtro_so_traz_o_provimento` (3 chunks com o termo, 1 APROVADO → só ele volta), `test_search_com_filtro_descarta_score_zero` (`n=10`, 1 chunk do provimento → 1 resultado), `test_search_sem_filtro_inalterada` (mesmos resultados que antes com `provimento=None`), `test_search_sem_arquivo_ignora_filtro` (apagar `provimentos.json`, recarregar; com filtro devolve os mesmos resultados que sem filtro), `test_load_rejeita_provimentos_desalinhados`, `test_gravar_provimentos_atomico` (não sobra `.tmp`).
- [ ] **Step 2: Run** → FAIL. **Step 3: Implement.** **Step 4: Run** → PASS + suíte.
- [ ] **Step 5: Commit** `"BM25 com provimento por chunk e máscara de busca"`.

### Task 3: Provimento no payload do Qdrant

**Files:**
- Modify: `indexing/vector_store/qdrant_store.py`
- Test: `tests/test_qdrant_provimento.py` (com `QdrantClient(":memory:")`, coleções pequenas de vetor 4D criadas no teste)

**Interfaces:**
- Produces:
  - `QdrantStore.garantir_indices_payload() -> None` — cria índice `keyword` em `provimento` e em `documento_id` nas duas coleções; idempotente (não falha se já existe).
  - `QdrantStore.atualizar_provimento(provimento: str, documento_ids: list[str], lote: int = 1000) -> int` — `set_payload({"provimento": provimento})` por filtro `MatchAny` em `documento_id`, em lotes, nas duas coleções; devolve quantos `documento_ids` foram enviados.
  - O construtor de `QdrantStore` não muda. Para os testes, as coleções do `:memory:` podem ser criadas com outra dimensão antes de construir o store (o `_garantir_colecao` não mexe em coleção existente).

- [ ] **Step 1: Write failing tests:** `test_atualizar_provimento_nas_duas_colecoes` (2 docs, 3 chunks; atualizar 1 doc → os chunks dele e o ponto da ementa mudam, o outro doc não), `test_atualizar_em_lotes` (`lote=1` com 3 ids → todos atualizados), `test_garantir_indices_idempotente` (chamar 2 vezes sem erro; `payload_schema` das duas coleções tem `provimento` e `documento_id`), `test_query_filtra_por_provimento` (depois de atualizar, `query(..., where={"provimento": "APROVADO"})` só devolve o doc atualizado).
- [ ] **Step 2: Run** → FAIL. **Step 3: Implement.** **Step 4: Run** → PASS + suíte.
- [ ] **Step 5: Commit** `"Índices de payload e atualização de provimento no Qdrant"`.

### Task 4: Busca filtrada nos canais

**Files:**
- Modify: `query/search/hybrid_search.py`, `query/search/pipeline.py`
- Modify (fakes que quebrarem com a nova assinatura): `tests/test_pipeline.py`, `tests/test_api.py`, `tests/test_hybrid_search.py`
- Test: `tests/test_hybrid_search.py`, `tests/test_pipeline.py`

**Interfaces:**
- Consumes: `LoadedBM25.search(query, n, provimento=None)` (Task 2); `QdrantStore.query(..., where=...)` (já existe).
- Produces:
  - `HybridSearch.search(query, n_results=20, where=None, *, bm25_query=None, provimento: str | None = None)` — com `provimento`, junta `{"provimento": provimento}` ao `where` das duas consultas do Qdrant e passa `provimento=` ao BM25. Sem `provimento`, chama `self.bm25.search(texto, n=n)` exatamente como hoje (sem o kwarg).
  - `buscar(..., filtrar_nos_canais: bool = True)` em `pipeline.py`:
    - com `provimento` e `filtrar_nos_canais`, chama `hybrid.search(..., provimento=provimento.value)`;
    - `n_candidatos`: `N_CANDIDATOS_COM_FILTRO` (80) se houver `data_inicio`/`data_fim`, ou se houver provimento com `filtrar_nos_canais=False`; `N_CANDIDATOS_PARA_RERANK` (30) se só houver provimento filtrado nos canais, ou nenhum filtro;
    - `aplicar_filtros` roda sempre que houver qualquer filtro, como hoje.
  - `filtrar_nos_canais=False` reproduz o comportamento antigo (usado pela medição da Task 6).

- [ ] **Step 1: Write failing tests:** `test_search_com_provimento_filtra_os_tres_canais` (fakes registram `where` do Qdrant com `provimento` e o kwarg do BM25), `test_search_junta_where_existente`, `test_sem_filtro_chamadas_identicas` (sem provimento: BM25 chamado sem kwarg `provimento`, Qdrant com `where=None`), `test_buscar_so_provimento_usa_pool_30`, `test_buscar_com_periodo_usa_pool_80`, `test_buscar_sem_filtrar_nos_canais_comportamento_antigo` (80 candidatos, nenhum `provimento` passado ao hybrid, `aplicar_filtros` descarta os de outro provimento).
- [ ] **Step 2: Run** → FAIL. **Step 3: Implement.** **Step 4: Run** → PASS + suíte.
- [ ] **Step 5: Commit** `"Filtra por provimento dentro dos três canais da busca"`.

### Task 5: Subcomando `sincronizar`

**Files:**
- Modify: `scraper/provimento_jev_db.py` (`ProvimentoJevStore.provimentos_documentos`), `scraper/provimento_jev_cli.py`
- Test: `tests/test_provimento_jev_cli.py`, `tests/test_provimento_jev_db_integration.py`

**Interfaces:**
- Consumes: `QdrantStore.garantir_indices_payload/atualizar_provimento` (Task 3); `gravar_provimentos`, `PROVIMENTOS_FILENAME`, `BM25_INDEX_PATH` (Task 2).
- Produces:
  - `ProvimentoJevStore.provimentos_documentos() -> dict[str, str]` — `documento_id → provimento` de todos os `documentos` (só essas duas colunas; `NULL` vira `NAO_APLICAVEL`).
  - `provimentos_dos_chunks(chunk_ids: list[str], por_documento: dict[str, str]) -> tuple[list[str], int]` — provimento de cada chunk pelo `documento_id` (parte antes do último `:`); chunk de documento ausente recebe `NAO_APLICAVEL` e entra na contagem devolvida.
  - CLI `sincronizar [--lote 1000] [--so-bm25] [--so-qdrant]`: lê o dicionário, agrupa por provimento, chama `garantir_indices_payload` e `atualizar_provimento` por grupo; lê `chunk_ids.json` de `BM25_INDEX_PATH`, monta e grava `provimentos.json`; imprime contagens por provimento, chunks sem documento e o lembrete de reiniciar o backend para o BM25 recarregar. Não usa o Jev (não cria cliente). `main` ganha a injeção opcional `qdrant=None` (como já faz com `store`).

- [ ] **Step 1: Write failing tests:** `test_provimentos_dos_chunks` (inclui chunk órfão), `test_sincronizar_atualiza_qdrant_e_bm25` (Qdrant `:memory:` + `tmp_path` com `chunk_ids.json`; `BM25_INDEX_PATH` via monkeypatch ou argumento), `test_sincronizar_idempotente` (rodar 2 vezes, mesmo estado), `test_sincronizar_nao_cria_cliente_jev`, e na integração `test_provimentos_documentos` (doc criado pelo teste aparece com o provimento certo).
- [ ] **Step 2: Run** → FAIL. **Step 3: Implement.** **Step 4: Run** → PASS + suíte.
- [ ] **Step 5: Execução real:** `uv run python -m scraper.provimento_jev_cli sincronizar` contra o Qdrant e o índice locais; registrar no report as contagens, o tempo e o `payload_schema` das duas coleções depois.
- [ ] **Step 6: Commit** `"Adiciona o sincronizar do provimento com o Qdrant e o BM25"`.

### Task 6: Medição com e sem filtro e documentação

**Files:**
- Create: `avaliacao/medir_filtro.py` (rodado com `uv run python -m avaliacao.medir_filtro`)
- Modify: `README.md`
- Test: `tests/test_medir_filtro.py`

**Interfaces:**
- Consumes: `buscar(..., filtrar_nos_canais=...)` (Task 4); `carregar_dependencias()` e `AvaliacaoStore.listar_teses()` (harness).
- Produces:
  - `medir(teses: list[dict], buscar_cards: Callable[[dict, str, bool], tuple[list, float]]) -> list[dict]` — para cada tese, para `APROVADO`, `PARCIAL`, `NEGADO`, e para `filtrar_nos_canais` em `(False, True)`, registra `{"tese", "provimento", "modo": "antes"|"depois", "n_resultados", "latencia_s", "fracao_provimento_certo"}`.
  - `resumir(linhas) -> dict` — por provimento e modo: média de resultados, fração de buscas com 10 ou mais resultados, latência média, fração mínima de provimento certo.
  - CLI: imprime a tabela e grava `data/eval/runs/<AAAA-MM-DD_HHMMSS>_filtro.json`. Teses: as do `AvaliacaoStore`; se não houver nenhuma, avisa e sai com 1.

- [ ] **Step 1: Write failing tests** com `buscar_cards` falso: `test_medir_cobre_provimentos_e_modos` (2 teses → 12 linhas), `test_resumir` (valores montados à mão).
- [ ] **Step 2: Run** → FAIL. **Step 3: Implement.** **Step 4: Run** → PASS + suíte.
- [ ] **Step 5: Execução real** (depois do `sincronizar` real): rodar e colar a tabela no report.
- [ ] **Step 6: README:** na seção "Provimento com o Jev", o `sincronizar` (quando rodar: depois de cada `aplicar` ou reindexação; reiniciar o backend depois), o filtro agora dentro dos canais e o comando de medição.
- [ ] **Step 7: Commit** `"Mede o filtro de provimento antes da busca e documenta"`.

---

## Parte A — checklist operacional (não são tarefas de implementação)

Depois da Task 1:

1. Nova conferência: 50 acórdãos novos com o mesmo método de 20/10 (leitores cegos com o mesmo trecho do Jev), mais um conjunto extra só com os dois casos da Task 1. Registrar em `docs/superpowers/specs/2026-10-22-provimento-jev-conferencia-2.md`. Seguir só com provimento ≥ 90% e nenhum erro nos dois casos.
2. Lote cronometrado: `classificar --limite 500 --sim`.
3. `classificar --sim` no acervo inteiro.
4. `comparar` (gera o CSV para o Vinicius). `conferir` e `aplicar --confirmar` são do Vinicius.
5. Depois do `aplicar`: `sincronizar` e reiniciar o backend.
