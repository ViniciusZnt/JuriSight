# Provimento com o Jev — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Classificar cada acórdão com o Jev (resultado do recurso, quem recorreu, a quem favorece), guardar ao lado da regex, comparar, deixar o usuário conferir e, sob comando explícito, adotar o resultado em `documentos.provimento`.

**Architecture:** Um módulo puro de classificação (`scraper/provimento_jev.py`) com as perguntas do Jev e regras de mapeamento; um store psycopg (`scraper/provimento_jev_db.py`) com a tabela `public.provimento_jev`; um CLI com quatro subcomandos (`scraper/provimento_jev_cli.py`, rodado com `uv run python -m scraper.provimento_jev_cli`: classificar, comparar, conferir, aplicar). Nada no fluxo de coleta nem na busca muda.

**Tech Stack:** Python 3.13, `typesafe-sdk` (Choice), psycopg 3, pytest; `uv run`.

**Spec:** `docs/superpowers/specs/2026-10-20-provimento-jev-design.md`

**Branch:** `feat/provimento-jev`, criada a partir de `feat/harness-avaliacao` (que já tem o `typesafe-sdk`, o padrão de juiz e o `.env` com `TYPESAFE_MODEL`).

## Global Constraints

- Modelo: `os.getenv("TYPESAFE_MODEL", "jev-1.13.0")`; nunca `jev-latest`.
- Rótulos exatos: resultado ∈ `provido, parcialmente_provido, nao_provido, nao_conhecido, sem_recurso`; recorrente ∈ `reclamante, reclamada, ambos, outro, indefinido`; favorece ∈ `reclamante, reclamada, ambos_em_parte, indefinido`.
- Texto das perguntas e critérios: copiar literalmente da seção "Perguntas" do spec.
- Estado do Jev: `{"acordao": {"ementa": (ementa or "")[:1500], "dispositivo": acordao[-4000:]}}`; acórdão vazio ou só espaços nunca vai ao Jev.
- Mapa para o enum: `provido→APROVADO`, `parcialmente_provido→PARCIAL`, `nao_provido→NEGADO`, `nao_conhecido→NEGADO`, `sem_recurso→NAO_APLICAVEL`.
- `documentos.provimento` só é escrito por `aplicar --confirmar`; padrão de `--confianca-min` = 0.8.
- "Já classificado" = linha em `provimento_jev` com o mesmo `modelo` e `perguntas_sha`.
- Custo: estimativa `n × 1.600 tokens` impressa e confirmação `s/N` antes de chamar o Jev; `--sim` pula.
- Identificadores e docstrings em português; psycopg puro; fakes injetados nos testes; nunca imprimir nem editar o `.env`.
- Testes de integração com Postgres: `pytest.mark.skipif` sem `DATABASE_URL`, como em `tests/test_avaliacao_store_integration.py`; cada teste cria a sua própria linha em `documentos` (`id_documento` = `"TESTE-PJ-" + uuid`) e a apaga no fim.
- Suíte completa antes de cada commit: `set -a; source .env; set +a; uv run pytest tests/ -q --ignore=tests/test_api_stress.py`.

## Review Focus

1. Backfill interrompido (Ctrl-C ou queda) e rodado de novo → retoma sem reclassificar o que já foi gravado com o mesmo modelo e perguntas (Task 3, `test_classificar_retoma_sem_repetir`).
2. Trocar `TYPESAFE_MODEL` ou o texto das perguntas → os documentos voltam a ficar pendentes (Task 2, `test_pendentes_volta_com_outro_sha`).
3. Erro do Jev num acórdão → os outros seguem, a falha é contada e o comando sai com código 1 (Task 3, `test_falha_nao_para_o_lote`).
4. `aplicar` sem `--confirmar` → não escreve nada no banco (Task 5, `test_aplicar_sem_confirmar_nao_escreve`).
5. Rodar `comparar` de novo depois de o usuário preencher o CSV → recusa sobrescrever (Task 4, `test_csv_conferido_nao_e_sobrescrito`).

---

### Task 1: Classificador do provimento

**Files:**
- Create: `scraper/provimento_jev.py`
- Modify: `avaliacao/juiz.py` (`perguntas_sha` passa a delegar para `sha_perguntas`)
- Test: `tests/test_provimento_jev.py`

**Interfaces:**
- Consumes: `typesafe_sdk.Choice`, `TypeSafeClient`; `scraper.schema.Provimento`.
- Produces:
  - `RESULTADOS`, `RECORRENTES`, `FAVORECE: tuple[str, ...]`; `PERGUNTAS_PROVIMENTO: dict[str, Choice]` (chaves `resultado`, `recorrente`, `favorece`); `TAMANHO_DISPOSITIVO = 4000`, `TAMANHO_EMENTA = 1500`, `TOKENS_POR_ACORDAO = 1600`.
  - `sha_perguntas(perguntas: dict) -> str` e `perguntas_sha() -> str` (= `sha_perguntas(PERGUNTAS_PROVIMENTO)`).
  - `montar_estado(acordao: str, ementa: str | None) -> dict`.
  - `@dataclass(frozen=True) ClassificacaoProvimento(resultado: str, recorrente: str, favorece: str, probs: dict[str, dict[str, float]], confianca_resultado: float, confianca_recorrente: float, confianca_favorece: float)`.
  - `class ClassificadorJev(client: TypeSafeClient | None = None, model: str | None = None)` com `.model` e `.classificar(acordao: str | None, ementa: str | None) -> ClassificacaoProvimento`; levanta `ValueError` para acórdão vazio, sem chamar o Jev.
  - `para_provimento(resultado: str) -> Provimento`.
  - `favorece_por_regra(resultado: str, recorrente: str) -> str | None`.

- [ ] **Step 1: Write the failing tests** (fake client no padrão de `tests/test_avaliacao_juiz.py::_FakeClient`, respondendo `SimpleNamespace(choice=..., probabilities=..., confidence=...)` para as três chaves):
  - `test_classificar_converte_resposta` — devolve `ClassificacaoProvimento` com os `choice`, `probs == {"resultado": {...}, "recorrente": {...}, "favorece": {...}}` e as três confianças; a chamada usa `model="jev-1.13.0"` e `questions is PERGUNTAS_PROVIMENTO`.
  - `test_estado_trunca` — `acordao = "x" * 5000 + "FIM"` e `ementa = "e" * 2000` → `estado["acordao"]["dispositivo"]` tem 4000 caracteres e termina em `"FIM"`; `estado["acordao"]["ementa"]` tem 1500; `ementa=None` → `""`.
  - `test_acordao_vazio_nao_chama_jev` — `None`, `""` e `"   "` levantam `ValueError` e `client.chamadas == []`.
  - `test_para_provimento` — os cinco pares do mapa das Global Constraints.
  - `test_favorece_por_regra` — a tabela do spec (6 casos) e `None` para `("provido", "ambos")`, `("nao_provido", "indefinido")`, `("sem_recurso", "reclamante")`.
  - `test_perguntas_tem_os_rotulos` — `set(PERGUNTAS_PROVIMENTO["resultado"].criteria) == set(RESULTADOS)` e idem para recorrente e favorece.
  - `test_sha_juiz_inalterado` — `avaliacao.juiz.perguntas_sha() == sha_perguntas(avaliacao.juiz.PERGUNTAS)` e `perguntas_sha()` tem 64 caracteres hex.
- [ ] **Step 2: Run** `uv run pytest tests/test_provimento_jev.py -v` → FAIL (módulo inexistente).
- [ ] **Step 3: Implement** `scraper/provimento_jev.py` e troque o corpo de `avaliacao.juiz.perguntas_sha` por `return sha_perguntas(PERGUNTAS)` (mesma serialização de hoje: `model_dump(mode="json")`, `json.dumps(sort_keys=True, ensure_ascii=False)`, sha256). O valor de `perguntas_sha()` do juiz não pode mudar.
- [ ] **Step 4: Run** o arquivo e a suíte completa → PASS.
- [ ] **Step 5: Commit** `"Adiciona classificador de provimento com o Jev"`.

### Task 2: Tabela e store

**Files:**
- Create: `scraper/provimento_jev_db.py`
- Test: `tests/test_provimento_jev_db_integration.py`

**Interfaces:**
- Consumes: `ClassificacaoProvimento` (Task 1).
- Produces:
  - `ensure_schema(database_url: str) -> None` — cria `public.provimento_jev` (colunas do spec: `documento_id UUID PRIMARY KEY REFERENCES documentos(id) ON DELETE CASCADE`, `resultado`, `recorrente`, `favorece` TEXT NOT NULL, `probs JSONB NOT NULL`, `confianca_resultado`, `confianca_recorrente`, `confianca_favorece` REAL, `provimento_regex TEXT`, `modelo TEXT NOT NULL`, `perguntas_sha TEXT NOT NULL`, `criado_em TIMESTAMPTZ NOT NULL DEFAULT NOW()`).
  - `@dataclass(frozen=True) ItemPendente(documento_id: str, acordao: str, ementa: str | None, provimento_regex: str)`.
  - `@dataclass(frozen=True) LinhaClassificada(documento_id: str, resultado: str, recorrente: str, favorece: str, confianca_resultado: float, provimento_regex: str, provimento_atual: str)`.
  - `class ProvimentoJevStore(database_url: str)`:
    - `pendentes(modelo: str, perguntas_sha: str, limite: int | None = None) -> list[ItemPendente]` — acórdãos (`tipo_documento = 'ACORDAO'`) com texto não vazio e sem linha do mesmo modelo e sha; ordem por `id`.
    - `contar_sem_texto() -> int` — acórdãos com `acordao` nulo ou só espaços.
    - `gravar(documento_id: str, c: ClassificacaoProvimento, provimento_regex: str, modelo: str, perguntas_sha: str) -> None` — upsert por `documento_id`, atualizando `criado_em`.
    - `linhas(modelo: str, perguntas_sha: str) -> list[LinhaClassificada]` — junta com `documentos.provimento` (atual).
    - `trechos(documento_ids: list[str], tamanho: int = 1500) -> dict[str, tuple[str | None, str]]` — `link_original` e os últimos `tamanho` caracteres do `acordao`.
    - `aplicar(mudancas: list[tuple[str, str]]) -> int` — `UPDATE documentos SET provimento` por `(documento_id, novo)`, numa transação; devolve quantas linhas mudaram.

- [ ] **Step 1: Write failing integration tests:** `test_gravar_e_ler` (grava, `linhas` devolve os valores e o `provimento_regex`), `test_pendentes_ignora_feito` (depois de gravar com `("jev-1.13.0", "sha1")`, o documento não aparece em `pendentes("jev-1.13.0", "sha1")`), `test_pendentes_volta_com_outro_sha` (aparece em `pendentes("jev-1.13.0", "sha2")` e em `pendentes("outro-modelo", "sha1")`), `test_pendentes_ignora_acordao_vazio` (documento com `acordao = "   "` não aparece e conta em `contar_sem_texto`), `test_aplicar_muda_provimento` (`aplicar([(id, "PARCIAL")]) == 1` e a coluna muda), `test_cascade` (apagar o documento apaga a linha). Use `pendentes(..., limite=None)` filtrando pelos ids criados no teste, para não depender do resto do banco.
- [ ] **Step 2: Run** com `.env` carregado → FAIL.
- [ ] **Step 3: Implement** no padrão de `avaliacao/db.py` + `avaliacao/store.py`.
- [ ] **Step 4: Run** o arquivo e a suíte completa → PASS.
- [ ] **Step 5: Commit** `"Adiciona tabela provimento_jev e store"`.

### Task 3: Subcomando `classificar`

**Files:**
- Create: `scraper/provimento_jev_cli.py`
- Test: `tests/test_provimento_jev_cli.py`

**Interfaces:**
- Consumes: Tasks 1 e 2; `avaliacao.passo_zero.confirmar`.
- Produces:
  - `classificar_pendentes(store, classificador, itens: list[ItemPendente], perguntas_sha: str, max_workers: int = 8) -> tuple[int, int]` — `(ok, falhas)`. Usa `ThreadPoolExecutor.map` (Ctrl-C cancela os pendentes), captura `TypeSafeError` por item, grava cada sucesso na thread principal com `store.gravar(..., modelo=classificador.model, ...)`.
  - `main(argv: list[str] | None = None) -> int` com subcomandos; aqui só `classificar [--limite N] [--max-workers 8] [--sim]`. Carrega o `.env` com `dotenv` (como `avaliacao/contexto.py`), roda `ensure_schema`, imprime modelo, `perguntas_sha`, pendentes, sem texto e a estimativa `pendentes × 1.600 tokens`, pede `confirmar` (pula com `--sim`) e devolve 1 se houver falhas.

- [ ] **Step 1: Write failing tests** com store e classificador falsos em memória:
  - `test_classificar_retoma_sem_repetir` — 3 itens, classificador que falha (`TypeSafeError`) no 2º só na primeira vez; depois da 1ª chamada `(ok, falhas) == (2, 1)`; o store falso devolve como pendentes só o que não gravou; na 2ª `(1, 0)`; cada documento gravado uma vez; classificador chamado 4 vezes.
  - `test_falha_nao_para_o_lote` — falha no 1º de 3 → os outros 2 gravados.
  - `test_cancelado_nao_chama_jev` — `main(["classificar"])` com `confirmar` respondendo não → classificador nunca chamado, retorno 1.
- [ ] **Step 2: Run** → FAIL. **Step 3: Implement.** **Step 4: Run** → PASS + suíte.
- [ ] **Step 5: Smoke real (pago, pequeno):** `set -a; source .env; set +a; uv run python -m scraper.provimento_jev_cli classificar --limite 20 --sim` → 20 linhas em `provimento_jev`; rodar o mesmo comando de novo classifica outros 20 (os primeiros já não aparecem como pendentes), total 40. Registre a distribuição de resultado/recorrente/favorece no report.
- [ ] **Step 6: Commit** `"Adiciona backfill retomável do provimento com o Jev"`.

### Task 4: Subcomandos `comparar` e `conferir`

**Files:**
- Modify: `scraper/provimento_jev_cli.py`
- Test: `tests/test_provimento_jev_cli.py`

**Interfaces:**
- Consumes: `LinhaClassificada`, `ProvimentoJevStore.linhas/trechos`, `para_provimento`, `favorece_por_regra`.
- Produces:
  - `resumo(linhas: list[LinhaClassificada]) -> dict` com `n`, `matriz` (`provimento_regex → para_provimento(resultado).value → contagem`), `concordancia` (fração em que os dois coincidem), `distribuicao` (`{"resultado": Counter, "recorrente": Counter, "favorece": Counter}` como dicts), `coerencia_favorece` (`{"n": casos em que a regra opina, "concordam": fração}`).
  - `divergencias(linhas, n: int, seed: int) -> list[LinhaClassificada]` — ordena por `documento_id` e sorteia até `n` entre as que divergem da regex.
  - `escrever_csv_divergencias(caminho: Path, linhas, trechos: dict) -> None` — colunas `documento_id,link,trecho_dispositivo,regex,jev_resultado,jev_recorrente,jev_favorece,confianca,quem_acertou` (`quem_acertou` vazio), UTF-8 com BOM como o CSV do passo 0.
  - `csv_conferido(caminho: Path) -> bool` — existe e tem algum `quem_acertou` preenchido.
  - `resumo_conferencia(caminho: Path) -> dict` — contagem de `jev`, `regex`, `ambos`, `nenhum`; vazios ignorados; outros valores avisados em stderr e pulados.
  - CLI: `comparar [--amostra 100] [--csv data/eval/provimento_divergencias.csv]` (imprime o `resumo`, recusa com código 1 se `csv_conferido`, escreve o CSV) e `conferir [--csv ...]` (imprime o `resumo_conferencia`). Seed de `AVALIACAO_SEED` (padrão 42).

- [ ] **Step 1: Write failing tests:** `test_resumo_matriz_e_concordancia` (3 linhas montadas à mão → matriz e concordância esperadas), `test_coerencia_favorece` (uma linha coerente com a regra, uma incoerente, uma em que a regra não opina → `{"n": 2, "concordam": 0.5}`), `test_divergencias_deterministicas` (mesma seed → mesma amostra; só divergentes), `test_csv_conferido_nao_e_sobrescrito` (CSV com `quem_acertou=jev` numa linha → `comparar` devolve 1 e o arquivo não muda), `test_resumo_conferencia` (valores válidos contados, vazio ignorado, `"talvez"` avisado).
- [ ] **Step 2: Run** → FAIL. **Step 3: Implement.** **Step 4: Run** → PASS + suíte.
- [ ] **Step 5: Commit** `"Adiciona comparação e conferência do provimento do Jev"`.

### Task 5: Subcomando `aplicar` e documentação

**Files:**
- Modify: `scraper/provimento_jev_cli.py`, `README.md`
- Test: `tests/test_provimento_jev_cli.py`

**Interfaces:**
- Consumes: `ProvimentoJevStore.linhas/aplicar`, `para_provimento`.
- Produces:
  - `mudancas(linhas: list[LinhaClassificada], confianca_min: float) -> list[tuple[str, str, str]]` — `(documento_id, atual, novo)` só onde `confianca_resultado >= confianca_min` e `novo != atual`.
  - CLI `aplicar [--confianca-min 0.8] [--confirmar]` — imprime as transições agrupadas (`atual → novo: n`) e quantos ficaram abaixo do limite; só chama `store.aplicar` com `--confirmar`; ao final lembra que a regex pode ser restaurada com `uv run python utils/reclassify.py`.

- [ ] **Step 1: Write failing tests:** `test_mudancas_respeita_confianca` (0,79 fica de fora, 0,8 entra), `test_mudancas_ignora_iguais`, `test_aplicar_sem_confirmar_nao_escreve` (store falso: `aplicar` nunca chamado; retorno 0), `test_aplicar_com_confirmar_escreve` (chamado uma vez com as mudanças).
- [ ] **Step 2: Run** → FAIL. **Step 3: Implement.** **Step 4: Run** → PASS + suíte.
- [ ] **Step 5: README:** seção "Provimento com o Jev", perto de onde o README fala do provimento: por que (o "negado" não diz quem ganhou), os quatro subcomandos na ordem de uso (`classificar` → `comparar` → preencher `quem_acertou` → `conferir` → `aplicar --confirmar`), o custo estimado (~110 M tokens para o acervo), que a regex continua recuperável e que `favorece`/`recorrente` ainda não são usados pela busca.
- [ ] **Step 6: Commit** `"Adiciona aplicação do provimento do Jev e documenta"`.
