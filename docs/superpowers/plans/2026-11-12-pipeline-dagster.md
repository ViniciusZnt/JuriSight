# Pipeline Dagster + limpeza de código morto — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Orquestrar o pipeline de dados (coleta → indexação → filtros; Jev à parte) como assets/jobs do Dagster rodando na VPS, e remover o código morto confirmado.

**Architecture:** As etapas existentes viram funções chamáveis (os CLIs atuais ficam como wrappers finos e continuam funcionando). Um pacote novo `pipeline/` define os assets que chamam essas funções e convertem os números retornados em metadados do Dagster. Um segundo estágio do Dockerfile (base da api + Chromium do Playwright) vira o serviço `dagster` do compose de produção, com UI só em `127.0.0.1` (túnel SSH).

**Tech Stack:** Dagster (`dagster` + `dagster-webserver`, processo único `dagster dev`), SQLite no `DAGSTER_HOME`, Docker multi-stage.

**Spec:** `docs/superpowers/specs/2026-11-12-pipeline-dagster-design.md`

## Global Constraints

- Nunca imprimir ou editar segredos do `.env`. Testes de integração: `set -a && . ./.env && set +a && uv run pytest …`.
- Os CLIs atuais (`scraper/run.py`, `indexing/run.py`, `python -m query.filtros.preparar`, `python -m scraper.provimento_jev_cli …`) continuam com os mesmos argumentos e o mesmo comportamento, inclusive `sys.exit(2)` na coleta interrompida e os prompts s/N do Jev.
- Nenhum asset expõe `--reset` (nem do scraper, nem da indexação).
- O estágio `api` do Dockerfile produz imagem idêntica à atual (só ganha o nome do estágio).
- Job `full` = `acervo` → `indices` → `filtros`, **sem Jev**.
- `jev_classificacoes`: `limite` padrão **500**; `0` = sem limite.
- Porta do Dagster publicada só em `127.0.0.1:3000` na VPS; nada no Caddy.
- Fila de 1 run por vez (`QueuedRunCoordinator`, `max_concurrent_runs: 1`).
- Código e comentários em pt-BR, no estilo do repo; mínimo de código (sem partições, sensores, schedules, retry).

## Review Focus

1. Data inválida no run config (`"2024-13-01"`) → erro de validação legível antes de coletar, não traceback no meio do run. (teste na Task 3)
2. Coleta interrompida pelo portal (`completed=False`) → o run falha com o progresso nos metadados e o `full` não indexa pela metade. (teste na Task 3)
3. `limite=0` no Jev → classifica todo o backlog (vira `None`), e `limite` ausente → 500. (teste na Task 3)
4. `preparar` num banco sem documentos → dict com zeros, sem exceção. (teste na Task 1)
5. Dois runs disparados juntos entram em fila — não testável em unidade; conferido no deploy (checklist da Task 4).

---

### Task 1: Etapas como funções chamáveis (scraper, indexação, filtros)

**Files:**
- Modify: `scraper/run.py` (extrai `coletar`; `main()` vira wrapper)
- Modify: `indexing/run.py` (extrai `indexar`; `main()` vira wrapper)
- Modify: `query/filtros/preparar.py` (função passa a retornar dict)
- Test: `tests/test_pipeline_etapas.py` (novo), `tests/test_filtros_preparar.py` (existente — ajustar se asserta retorno)

**Interfaces (Produces):**
- `scraper.run.coletar(from_date: date | None, to_date: date | None, colecao: str = "acordaos", database_url: str | None = None) -> dict` — chaves: `completed: bool`, `documents_saved: int`, `requests_made: int`, `inicio: str`, `fim: str` (ISO), e `halt_reason`/`halt_message` quando `completed=False`. Sem `sys.exit`, sem `--reset`. Se `start > end` (nada a coletar): `completed=True`, `documents_saved=0`.
- `indexing.run.indexar(reset: bool = False, limit: int | None = None, workers: int = 6, flush_docs: int = 100, no_bm25: bool = False) -> dict` — chaves: `docs`, `chunks`, `novos`, `falhas`, `bm25_salvo: bool`, `tempo_s: float`.
- `query.filtros.preparar.preparar(database_url: str) -> dict` — chaves: `dispositivos: int`, `pares: int`, `por_familia: dict[str, int]` (pares por família para `nr`, `tema`, `sv`), `tempo_s: float`.

- [ ] **Step 1: Testes que falham** em `tests/test_pipeline_etapas.py`:

```python
def test_coletar_devolve_resultado(monkeypatch):
    # monkeypatch PostgresWriter, WebScraper e Orchestrator (run -> dict fake
    # {"completed": True, "documents_saved": 7, "requests_made": 3})
    r = coletar(date(2025, 1, 1), date(2025, 1, 2))
    assert r["completed"] is True and r["documents_saved"] == 7
    assert r["inicio"] == "2025-01-01" and r["fim"] == "2025-01-02"

def test_coletar_interrompida_nao_levanta(monkeypatch):
    # Orchestrator.run -> {"completed": False, ..., "halt_reason": "blocked", "halt_message": "x"}
    r = coletar(date(2025, 1, 1), date(2025, 1, 2))
    assert r["completed"] is False and r["halt_reason"] == "blocked"

def test_main_do_scraper_sai_com_2_quando_interrompida(monkeypatch, capsys):
    # monkeypatch coletar -> completed False; main() deve chamar sys.exit(2)

def test_indexar_devolve_contagens(monkeypatch):
    # monkeypatch QdrantClient/DocumentSource/SACChunker/PolyVectorEmbedder/QdrantStore/BM25Builder
    # fonte com 0 documentos -> {"docs": 0, ..., "bm25_salvo": False}
    r = indexar()
    assert set(r) >= {"docs", "chunks", "novos", "falhas", "bm25_salvo", "tempo_s"}
```

E em `tests/test_filtros_preparar.py` (ou novo teste no mesmo arquivo), com o banco de teste vazio: `preparar(url)` devolve `{"dispositivos": 0, "pares": 0, ...}` sem exceção (Review Focus 4).

- [ ] **Step 2: Rodar e ver falhar** — `uv run pytest tests/test_pipeline_etapas.py -q` → falha com import/atributo inexistente.
- [ ] **Step 3: Implementar.** Mover o corpo do `main()` de `scraper/run.py` para `coletar(...)` (resolve datas via `resolve_dates`, monta writer/scraper/orchestrator, fecha o writer em `finally`); `main()` continua com argparse, `--reset` (chama `writer.reset()` antes), os prints atuais e `sys.exit(2)`. Idem em `indexing/run.py`: o corpo vira `indexar(...)`, `main()` só faz `_parse_args()` e repassa. Em `preparar`, acumular os números que hoje são `print` e retornar o dict (o `__main__` imprime como hoje).
- [ ] **Step 4: Suíte inteira verde** — `set -a && . ./.env && set +a && uv run pytest -q --deselect tests/test_api_stress.py` → tudo passa (hoje: 640 passed, 1 skipped).
- [ ] **Step 5: Commit** — `git commit -m "Etapas do pipeline viram funções chamáveis"`.

### Task 2: Funções chamáveis do Jev

**Files:**
- Modify: `scraper/provimento_jev_cli.py`
- Test: `tests/test_provimento_jev_cli.py` (existente — os `_cmd_*` seguem testados; somar testes das funções novas)

**Interfaces (Produces):**
- `classificar(store, classificador, limite: int | None, lote: int = 500, max_workers: int = 8) -> dict` — chaves: `ok`, `falhas`, `tentados`, `pendentes`, `estimativa_tokens`, `modelo`. Sem `input()`: a função nunca pergunta (a confirmação é de quem chama). `classificador=None` → cria `ClassificadorJev()`.
- `aplicar(store, confianca_min: float, confirmar: bool) -> dict` — chaves: `transicoes: dict[str, int]` ("ATUAL → NOVO" → n), `abaixo_limite: int`, `aplicadas: int` (0 quando `confirmar=False`).
- `sincronizar(store, qdrant, lote: int = 1000, so_bm25: bool = False, so_qdrant: bool = False) -> dict` — chaves: `docs`, `tempo_s`.

- [ ] **Step 1: Testes que falham** (fakes de store/classificador já usados nos testes atuais): `classificar` com store fake de 3 pendentes e `limite=2` → `tentados == 2` e `estimativa_tokens == 2 * TOKENS_POR_ACORDAO`; `aplicar(confirmar=False)` não chama o método de escrita do store; `sincronizar` devolve `docs`.
- [ ] **Step 2: Rodar e ver falhar.**
- [ ] **Step 3: Implementar** movendo a lógica dos `_cmd_*` para as funções; os `_cmd_*` mantêm prints, prompt s/N (`--sim`) e códigos de retorno chamando as funções.
- [ ] **Step 4: Suíte verde** (mesmo comando da Task 1).
- [ ] **Step 5: Commit** — `"Jev: classificar/aplicar/sincronizar chamáveis sem prompt"`.

### Task 3: Assets e jobs do Dagster

**Files:**
- Modify: `pyproject.toml` (dependências novas: `dagster` e `dagster-webserver`, piso na minor estável corrente; `uv lock`)
- Create: `pipeline/__init__.py`, `pipeline/definitions.py`
- Test: `tests/test_pipeline_definitions.py`

**Interfaces:**
- Consumes: as funções das Tasks 1–2, importadas **dentro** dos assets (import tardio: a UI carrega sem puxar playwright/embedder).
- Produces: `pipeline/definitions.py` com `defs = Definitions(...)` contendo os assets `acervo`, `indices`, `filtros`, `jev_classificacoes`, `jev_provimento`, `jev_sincronizado` e os jobs `full`, `coleta`, `indexacao`, `so_filtros`, `jev`.

Decisões fixadas:
- Config do `acervo` (pydantic `Config` do Dagster): `data_inicio: str | None = None`, `data_fim: str | None = None`, `colecao: str = "acordaos"`; strings viram `date` com `date.fromisoformat` num `field_validator` (erro de config legível — Review Focus 1).
- `acervo` chama `coletar(...)`; se `completed=False`, levanta `dagster.Failure(description=halt_message, metadata={progresso})` (Review Focus 2). Senão, `MaterializeResult(metadata={"documentos_salvos": …, "requisicoes": …, "inicio": …, "fim": …})`.
- `indices`: deps `[acervo]`, chama `indexar()` (sem reset) e devolve as contagens + `"lembrete": "docker compose -f docker-compose.prod.yml restart api (recarrega o BM25)"` nos metadados.
- `filtros`: deps `[indices]`, chama `preparar(os.environ["DATABASE_URL"])`, metadados do dict.
- Config do `jev_classificacoes`: `limite: int = 500`, `lote: int = 500`, `max_workers: int = 8`; `limite == 0` → passa `None` (Review Focus 3). `jev_provimento`: `confianca_min: float = 0.8`, chama `aplicar(confirmar=True)`. `jev_sincronizado` chama `sincronizar`.
- Jobs via `define_asset_job` com seleção por nome; `full` seleciona `acervo, indices, filtros`; `jev` seleciona a cadeia Jev.

- [ ] **Step 1: Testes que falham** em `tests/test_pipeline_definitions.py`, usando `dagster.materialize([...])` com as funções de etapa monkeypatchadas no módulo `pipeline.definitions` (os imports tardios: monkeypatchar o módulo de origem, ex.: `scraper.run.coletar`):

```python
def test_defs_tem_assets_e_jobs():
    # nomes exatos dos 6 assets e 5 jobs

def test_acervo_vira_metadados(monkeypatch):
    # coletar -> completed True, 7 docs; materialize([acervo], run_config com datas)
    # resultado success e metadado documentos_salvos == 7

def test_acervo_falha_com_coleta_interrompida(monkeypatch):
    # coletar -> completed False; materialize(..., raise_on_error=False) -> not success

def test_data_invalida_e_erro_de_config():
    # run_config data_inicio="2024-13-01" -> DagsterInvalidConfigError (ou Failure de validação)

def test_jev_limite_zero_vira_none(monkeypatch):
    # espiona classificar; config limite=0 -> chamado com limite=None; sem config -> 500
```

- [ ] **Step 2: Rodar e ver falhar.**
- [ ] **Step 3: Adicionar as dependências** (`uv add dagster dagster-webserver`), **implementar `pipeline/definitions.py`** com os assets/jobs acima.
- [ ] **Step 4: Testes novos e suíte verde**; conferir também `uv run python -c "from pipeline.definitions import defs; print(sorted(j.name for j in defs.jobs))"` → os 5 nomes.
- [ ] **Step 5: Commit** — `"Pipeline de dados como assets e jobs do Dagster"`.

### Task 4: Docker, compose, dagster.yaml e README

**Files:**
- Modify: `Dockerfile` (estágio atual ganha `AS api`; novo estágio `FROM api AS dagster`)
- Modify: `docker-compose.prod.yml` (api aponta `target: api`; serviço e volume novos)
- Create: `pipeline/dagster.yaml`
- Modify: `README.md`

**Interfaces:**
- Consumes: `pipeline/definitions.py` (Task 3).

Decisões fixadas:
- Estágio `dagster`: `RUN uv run --no-sync playwright install --with-deps chromium`; `ENV DAGSTER_HOME=/app/dagster_home`; CMD copia `pipeline/dagster.yaml` para `$DAGSTER_HOME/dagster.yaml` (sobrescrevendo — config é do repo) e roda `uv run --no-sync dagster dev -f pipeline/definitions.py -h 0.0.0.0 -p 3000`.
- `pipeline/dagster.yaml`: `run_coordinator: QueuedRunCoordinator` com `max_concurrent_runs: 1` e `telemetry: enabled: false`.
- Serviço `dagster` no compose de produção: `build: {context: ., target: dagster}`, `restart: unless-stopped`, `env_file: .env`, volumes `./data:/app/data` (o mesmo bind da api) e `dagster_home:/app/dagster_home` (volume novo), `ports: ["127.0.0.1:3000:3000"]`, `depends_on` igual ao da api.
- README: seção nova "Pipeline de dados (Dagster)" dentro do bloco de produção — túnel (`ssh -L 3001:localhost:3000 deploy@IP`, abrir `http://localhost:3001`), os 5 jobs e o que cada um faz, config de datas da coleta, Jev (limite 500, 0 = tudo; custo), restart da api depois do `full`, fila de 1 run. A seção da cópia local→VPS do deploy vira nota histórica de uma linha apontando o novo caminho.

- [ ] **Step 1: Implementar** Dockerfile, compose, `pipeline/dagster.yaml`.
- [ ] **Step 2: Verificar a imagem da api não mudou** — `docker build --target api -t jurisight-api-check . && docker run --rm jurisight-api-check uv run --no-sync python -c "import query.api.app; print('ok')"` → `ok`.
- [ ] **Step 3: Verificar o estágio dagster** — `docker build --target dagster -t jurisight-dagster-check .` termina; `docker run --rm jurisight-dagster-check uv run --no-sync python -c "import playwright, dagster; from pipeline.definitions import defs; print('ok')"` → `ok`.
- [ ] **Step 4: README** com a seção acima; `uv run pytest -q --deselect tests/test_api_stress.py` segue verde.
- [ ] **Step 5: Commit** — `"Serviço dagster no compose de produção (túnel SSH, fila de 1 run)"`.

Checklist de deploy (fora dos subagentes, comigo + Vinicius depois do merge): `up -d --build` na VPS; túnel abre a UI; rodar `coleta` com um período curto e ver os metadados; disparar dois runs e ver a fila; `restart api` depois de um `full`.

### Task 5: Código morto

**Files:**
- Delete: `indexing/vector_store/migrate_chroma_to_qdrant.py`
- Modify: `README.md` (§Escalabilidade: a menção ao script vira meia-linha histórica — "a migração Chroma→Qdrant foi feita por um script removido em <hash deste commit>")
- Modify: `.gitignore` (se faltar cobertura para os itens abaixo)
- Local (sem git): apagar `evaluation/` (só `__pycache__`), `jurisight.egg-info/`, `indexing.log`, `Legal AI Research Platform.zip`, `data/index/bm25.pkl`

- [ ] **Step 1: Confirmar que está morto** — `grep -rn "migrate_chroma" --include=*.py . | grep -v __pycache__` → só o próprio arquivo; nenhuma outra referência fora do README.
- [ ] **Step 2: Remover** o script, ajustar o README, apagar os arquivos locais, conferir `.gitignore` (`*.egg-info`, `*.log`, `__pycache__/` etc. — acrescentar só o que faltar).
- [ ] **Step 3: Suíte verde** — mesmo comando de sempre; e `uv run python -c "import indexing.run"` ok.
- [ ] **Step 4: Commit** — `"Remove a migração Chroma→Qdrant concluída e lixo local"`.
