# Triagem por IA no lugar do reranker — plano de implementação

> **Para agentes:** SUB-SKILL OBRIGATÓRIA: use superpowers:subagent-driven-development (recomendado) ou superpowers:executing-plans para implementar este plano tarefa a tarefa. Os passos usam checkbox (`- [ ]`).

**Objetivo:** tirar o reranker e pôr a IA para avaliar (nota 0–3) os ~50 resultados da busca em lotes progressivos e interrompíveis. A nota ordena a lista. A resposta é gerada só com as decisões relacionadas.

**Arquitetura:**

- O `/query` devolve 50 cards na ordem do RRF, sem reranker.
- O front dispara `POST /triagem` em lotes de 10, com 2 em voo, e reordena a lista a cada lote.
- Cada par tese × decisão é guardado em `public.triagem_cache`.
- Ao concluir, ou quando o advogado para, o front congela a ordem e chama `POST /resposta` com as decisões de nota ≥ 2. O servidor lê a posição de cada uma no cache da triagem.

**Stack:** FastAPI + OpenAI SDK (`chat.completions.parse`, structured output) + psycopg; Next.js/React + Jest/RTL.

**Spec:** `docs/superpowers/specs/2026-11-17-triagem-ia-design.md`. Leia-a antes de começar. Este plano decide arquivos, nomes e testes; a spec explica o porquê.

**Comandos:**

- Backend: `uv run pytest <arquivo> -q`, na raiz.
- Front: `pnpm test -- <arquivo>` e `pnpm lint`, em `frontend/`.

## Restrições globais

- À OpenAI vão só os campos da tese (`pedido_principal`, `agente_nocivo`, `violacoes`, `normas`, `tese_central`) e ementas públicas vindas do banco, nunca do cliente.
- Busca: `N_RESULTADOS_TRIAGEM = 50`, `N_RESULTADOS_LIVRE = 20`, `N_CANDIDATOS_COM_FILTRO = 120`.
- Triagem:
  - até 10 ids por lote;
  - ementa cortada em `MAX_EMENTA_TRIAGEM = 1200` caracteres (começo + fim);
  - `TIMEOUT_S = 20`;
  - modelo `OPENAI_TRIAGEM_MODEL`, padrão `gpt-4o-mini`;
  - `temperature` de `OPENAI_GEN_TEMPERATURE`, padrão `"0"`.
- Escala da nota, com estes rótulos na tela:
  - 3 "Mesmo problema e fato"
  - 2 "Mesmo pedido"
  - 1 "Mesmo ramo"
  - 0 "Outro tema"
- Resposta: até 25 ids, `TIMEOUT_S = 40`, `MAX_EMENTA = 2000` (mantém).
- Front: lotes de 10, `EM_VOO = 2`, 1 nova tentativa por lote.
- Limite diário da ação `"triagem"`:
  - por conta: `LIMITE_DIARIO_TRIAGEM_POR_CONTA`, padrão 5 × `LIMITE_DIARIO_POR_CONTA`;
  - total: `LIMITE_DIARIO_TRIAGEM_TOTAL`, padrão 5 × `LIMITE_DIARIO_TOTAL`;
  - conta 1 por lote que chama a OpenAI; acerto total no cache não conta.
- Textos fixos da tela:
  - "Avaliando decisões com a IA… X de N"
  - "Parar e responder"
  - "Avaliar N restantes"
  - "Pouco relacionadas (N)"
  - "Ainda não avaliadas (N)"
  - "É relevante"
  - "Marcada por você"
  - "Desfazer"
  - "Avaliação por IA indisponível agora; a lista está na ordem da busca."
  - "A resposta sai quando a avaliação terminar ou você parar."
  - "Nenhuma decisão avaliada como relacionada à tese."
- O projeto escreve código, comentários e testes em português, com docstrings curtas que dizem o porquê. Siga o estilo dos arquivos vizinhos.

## Foco da revisão

Cinco situações que a spec implica e que podem passar despercebidas. Cada uma tem teste na tarefa dona:

1. **Lote abortado volta depois.** O advogado clica "Parar e responder" e a resposta de um lote em voo chega mesmo assim. Ela não pode reordenar a lista nem mudar a numeração congelada. → Tarefa 9, `parar descarta lote que chega depois`.
2. **Busca com menos de 10 resultados, ou zero.** Um lote só, ou nenhum: o status vai direto para `"concluida"` sem chamar a API e a resposta não é pedida. → Tarefa 9, `sem resultados conclui sem chamar a API`.
3. **Modelo devolve número repetido, fora do lote ou nota fora da escala.** O item é descartado e o resto do lote vale. → Tarefa 3, `test_numero_repetido_ou_fora_e_nota_invalida_sao_descartados`.
4. **Trocar de versão (V1↔V2) com a avaliação em andamento.** Os lotes da versão anterior são abortados e não escrevem na nova. → Tarefa 9, `trocar a chave aborta os lotes da anterior`.
5. **Voto em decisão que depois some do filtro de tribunal/período.** Continua salvo e volta a aparecer ao limpar o filtro. → Tarefa 10, `voto sobrevive a filtro que esconde o card`.

---

### Tarefa 1: Busca sem reranker (e remoção do reranker do projeto)

**Arquivos:**
- Modificar: `query/search/pipeline.py`, `query/api/app.py`, `avaliacao/sistemas.py`, `avaliacao/benchmark.py`, `tests/fakes.py`, `tests/test_pipeline.py`, `tests/test_api.py`, `tests/test_avaliacao_sistemas.py`, `tests/test_avaliacao_benchmark.py`, `pyproject.toml`, `uv.lock`, `docs/deploy/2026-11-01-deploy-vps.md`
- Apagar: `query/search/reranker.py`, `query/search/reranker_onnx.py`, `query/search/reranker_monoptt5.py`, `tests/test_reranker.py`, `tests/test_reranker_onnx.py`, `tests/test_reranker_monoptt5.py`

**Interfaces:**
- Produz: `buscar(estrutura, *, hybrid, retriever, n_resultados: int, provimento=None, data_inicio=None, data_fim=None, documento_ids=None, marcar_canais=False) -> list[ResultCard]`, e as constantes `N_RESULTADOS_TRIAGEM = 50`, `N_RESULTADOS_LIVRE = 20` e `N_CANDIDATOS_COM_FILTRO = 120` em `pipeline.py`. `SISTEMAS = ("S0", "S1", "S2")` em `avaliacao/sistemas.py`; a Tarefa 7 acrescenta o S7. `rodar_sistema(sistema, estrutura, deps) -> list[str]`, sem o parâmetro `rerankers`.

- [ ] **Passo 1: ajustar os testes do pipeline** (`tests/test_pipeline.py`). Substitua os testes de reranker por:

```python
def test_buscar_mantem_ordem_do_rrf_e_corta_em_n_resultados():
    # hybrid fake devolve 60 ids em ordem; n_resultados=50
    cards = buscar(est, hybrid=hybrid, retriever=FakeDocRetriever(docs), n_resultados=50)
    assert [c.id for c in cards] == ids[:50]
    assert hybrid.calls[0]["n_results"] == 50

def test_buscar_com_periodo_usa_pool_120_e_corta_depois_do_filtro():
    cards = buscar(est, hybrid=hybrid, retriever=..., n_resultados=50, data_inicio=date(2025, 1, 1))
    assert hybrid.calls[0]["n_results"] == N_CANDIDATOS_COM_FILTRO == 120
    assert len(cards) <= 50

def test_buscar_devolve_score_rrf_cru():
    # scores do fake: 0.9, 0.5 → os cards trazem exatamente esses valores (sem min-max)
```

Apague `test_buscar_mantem_ordem_do_reranker_e_corta_em_20`, `test_buscar_sem_reranker_mantem_ordem_do_rrf` e o uso de `N_CANDIDATOS_PARA_RERANK`.

- [ ] **Passo 2: rodar e ver falhar.** `uv run pytest tests/test_pipeline.py -q` → FAIL: `buscar()` não aceita `n_resultados`.

- [ ] **Passo 3: implementar em `pipeline.py`.**
  - Tire o import de `Reranker`, o parâmetro `reranker`, o bloco de re-ranking, `normalizar_scores`, `N_RESULTS_FINAL` e `N_CANDIDATOS_PARA_RERANK`.
  - O pool pedido ao `hybrid.search` é `N_CANDIDATOS_COM_FILTRO` quando há filtro de período, senão `n_resultados`. O corte final é `[:n_resultados]`.
  - Atualize a docstring do módulo: o pipeline vira `Query Builder -> Hybrid Search (RRF) -> Doc Retriever -> filtros -> corte -> Result Formatter`, e a ordem da tela vem da triagem (`query/search/triagem.py`).

- [ ] **Passo 4: API.** Em `app.py`:
  - tire `app.state.reranker`, `get_reranker` e o parâmetro de `_buscar_cards`;
  - `_buscar_cards(body, hybrid, retriever, ids, n_resultados: int)`;
  - `/query` passa `N_RESULTADOS_TRIAGEM` e `/query/livre` passa `N_RESULTADOS_LIVRE`.

  Em `tests/test_api.py`:
  - tire `_reranker_passthrough`, `FakeReranker` e `test_query_reranking_promove_candidato_mal_rankeado_pelo_rrf`;
  - troque a asserção da linha ~353 por `fake_hybrid.calls[0]["n_results"] == 50`;
  - acrescente `test_query_livre_devolve_no_maximo_20` (fake com 30 ids → 20 cards).

  Tire `FakeReranker` de `tests/fakes.py`.

- [ ] **Passo 5: benchmark.**
  - Em `avaliacao/sistemas.py`: `SISTEMAS = ("S0", "S1", "S2")`; `PROFUNDIDADE = 20 * CANDIDATOS_POR_CANAL`, com o número explícito e o comentário mantido; `candidatos_hibrido(..., n: int = 50)`.
  - `rodar_sistema(sistema, estrutura, deps)` chama `buscar(..., n_resultados=50)` e devolve os 20 primeiros ids.
  - Tire `_monoptt5` e `construir_rerankers`.
  - Em `avaliacao/benchmark.py`: tire `_nomes_dos_modelos` (`"modelos"` vira `{}`), `_checar_dependencias`, o parâmetro `rerankers` e a construção/liberação por sistema.
  - Ajuste os testes de `tests/test_avaliacao_sistemas.py` e `tests/test_avaliacao_benchmark.py`: apague os de reranker e monoPTT5 e tire o argumento `rerankers` dos fakes de `rodar_sistema`.

- [ ] **Passo 6: dependências e deploy.**
  - Em `pyproject.toml`, tire `flashrank`, o grupo `benchmark` e o índice/fonte `pytorch-cpu`. Rode `uv lock`.
  - Apague os 3 módulos e os 3 testes de reranker.
  - No doc de deploy, tire a linha do reranker na tabela de tamanhos, o `rsync` do `reranker_cache` e a menção ao reranker em "Busca lenta demais".

- [ ] **Passo 7: rodar tudo.** `uv run pytest -q` → PASS. `git grep -n -i rerank -- ':!docs/superpowers' ':!docs/refactor'` → nada em código; só sobra o `README.md`, que a Tarefa 4 reescreve.

- [ ] **Passo 8: commit.** `git commit -m "Busca sem reranker: /query devolve 50 na ordem do RRF; reranker sai do projeto"`

---

### Tarefa 2: Limite diário por ação e `GET /uso`

**Arquivos:**
- Modificar: `query/api/uso_diario.py`, `query/api/app.py`, `.env.example`
- Teste: `tests/test_uso_diario_integration.py`; e um arquivo novo, `tests/test_uso_diario.py`

**Interfaces:**
- Produz:
  - `UsoDiario.limites(acao: str) -> tuple[int, int]` (por conta, total). `consumir(usuario_id, acao)` usa `limites(acao)`.
  - `ACOES_PAGAS = ("enrich", "query", "triagem", "resposta")`.
  - `UsoDiario.do_dia(usuario_id) -> dict[str, int]`: uso de hoje por ação, 0 se não houver linha. Erro do psycopg propaga.
  - `GET /uso`: devolve `UsoResponse { acoes: list[UsoAcao{acao: str, usado: int, limite: int}] }`, na ordem de `ACOES_PAGAS`. Sessão obrigatória. Erro do banco ou `uso` ausente (`None`) → 503.

- [ ] **Passo 1: teste** (`tests/test_uso_diario.py`, sem banco):

```python
def test_triagem_tem_5x_o_limite_e_aceita_override(monkeypatch):
    for v in ("LIMITE_DIARIO_TRIAGEM_POR_CONTA", "LIMITE_DIARIO_TRIAGEM_TOTAL"):
        monkeypatch.delenv(v, raising=False)
    uso = UsoDiario("postgresql://x", por_conta=30, total=300)
    assert uso.limites("query") == (30, 300)
    assert uso.limites("triagem") == (150, 1500)
    monkeypatch.setenv("LIMITE_DIARIO_TRIAGEM_POR_CONTA", "40")
    assert UsoDiario("postgresql://x", por_conta=30, total=300).limites("triagem") == (40, 1500)
```

No teste de integração, se já houver padrão de limite estourado: `test_triagem_estourada_usa_mensagem_sem_numero`. A mensagem por conta, para `"triagem"`, é "Você atingiu o limite de uso da IA de hoje. Ele renova à meia-noite." As demais ações mantêm a mensagem atual.

Rotas, com fake de `UsoDiario` via `get_uso_diario`:

```python
def test_uso_devolve_as_4_acoes_na_ordem_com_usado_e_limite():
    # fake.do_dia → {"query": 3}; limites: 30 e triagem 150
    assert client.get("/uso").json() == {"acoes": [
        {"acao": "enrich", "usado": 0, "limite": 30}, {"acao": "query", "usado": 3, "limite": 30},
        {"acao": "triagem", "usado": 0, "limite": 150}, {"acao": "resposta", "usado": 0, "limite": 30}]}
def test_uso_com_banco_fora_503()
def test_uso_sem_sessao_401()
```

Integração: `test_do_dia_conta_so_hoje_e_so_a_conta` (consumir 2× `query` para A e 1× para B → A vê `{"query": 2}`).

- [ ] **Passo 2: falha.** `uv run pytest tests/test_uso_diario.py -q` → FAIL: `limites` não existe.
- [ ] **Passo 3: implementar** `limites`, `do_dia` e a rota. As variáveis são lidas no `__init__`. Documente as duas em `.env.example`.
- [ ] **Passo 4: passa.** `uv run pytest tests/test_uso_diario.py tests/test_uso_diario_integration.py -q`. O teste de integração é pulado se não houver banco, como já é.
- [ ] **Passo 5: commit.** `git commit -m "Limite diário por ação (triagem 5x) e GET /uso"`

---

### Tarefa 3: Núcleo da triagem (sem HTTP)

**Arquivos:**
- Criar: `query/search/triagem.py`, `tests/test_triagem.py`

**Interfaces:**
- Produz:
  - `NotaTriagem = Literal[0, 1, 2, 3]`
  - `class Avaliacao(BaseModel): nota: NotaTriagem; posicao: PosicaoTese; motivo: str`. `PosicaoTese` é importado de `query/search/resposta.py`.
  - `tese_para_ia(estrutura: EstruturaArgumentativa) -> dict`: só os 5 campos da tese, sem defaults.
  - `chave_da_triagem(estrutura, documento_id: str) -> str`: sha256 de (modelo, temperatura, `_PROMPT`, `tese_para_ia`, documento_id).
  - `avaliar_lote(estrutura, decisoes: dict[str, DocumentoJuridico], client: OpenAI) -> dict[str, Avaliacao]`: as chaves de `decisoes` são ids, na ordem de inserção = `#1..#k`. Levanta `openai.OpenAIError`.
  - Em `resposta.py`, `_posicao(d: Desfecho)` vira `posicao_de(pedido_da_tese: str, fatos_da_premissa: bool) -> PosicaoTese`. Fica em `resposta.py` para a dependência ter uma direção só: `triagem.py` importa de `resposta.py` (`PosicaoTese`, `posicao_de`, `_cabecalho`), nunca o contrário.
- Schema do modelo:
  - `class ItemTriagem(BaseModel): numero: int; motivo: str; nota: int; pedido_da_tese: Literal["deferiu","negou","outro"]; fatos_da_premissa: bool`
  - `class TriagemGerada(BaseModel): itens: list[ItemTriagem]`

- [ ] **Passo 1: testes**, usando `FakeOpenAI` e `documento_fake` de `tests/fakes.py`:

```python
def test_cada_item_vira_avaliacao_pelo_id_e_posicao_segue_a_premissa():
    # itens: #1 nota 3 deferiu; #2 nota 2 negou fatos_da_premissa=False
    r = avaliar_lote(est, {"a": d1, "b": d2}, fake)
    assert r["a"] == Avaliacao(nota=3, posicao="deferiu", motivo="m1")
    assert r["b"].posicao == "fato_diferente"

def test_numero_repetido_ou_fora_e_nota_invalida_sao_descartados():
    # itens: #1 nota 2, #1 nota 0 (repetido), #3 (fora de 2), #2 nota 5
    assert set(avaliar_lote(est, {"a": d1, "b": d2}, fake)) == {"a"} and r["a"].nota == 2

def test_ao_modelo_vao_so_campos_da_tese_e_ementa_cortada_com_cabecalho():
    est = EstruturaArgumentativa(tese_central="calor", tribunais=["TRT12"], expressoes=["calor"])
    avaliar_lote(est, {"a": documento_fake(ementa="A" * 1300 + "FIM", tribunal="TRT12", turma="1ª Turma")}, fake)
    user = fake.chamadas[0]["messages"][1]["content"]
    assert "tribunais" not in user and "expressoes" not in user and "calor" in user
    assert "#1 (" in user and "TRT12" in user and user.count("A") < 1300 and "FIM" in user
    assert fake.chamadas[0]["response_format"] is TriagemGerada and fake.chamadas[0]["timeout"] == 20

def test_recusa_do_modelo_devolve_vazio():  # parsed=None → {}
def test_lote_vazio_nao_chama_a_openai():   # {} → {} e fake.chamadas == []

def test_chave_muda_com_tese_doc_e_modelo_mas_nao_com_filtros(monkeypatch):
    base = chave_da_triagem(EstruturaArgumentativa(tese_central="calor"), "a")
    assert base == chave_da_triagem(EstruturaArgumentativa(tese_central="calor", tribunais=["TRT4"]), "a")
    assert base != chave_da_triagem(EstruturaArgumentativa(tese_central="ruído"), "a")
    assert base != chave_da_triagem(EstruturaArgumentativa(tese_central="calor"), "b")
    monkeypatch.setenv("OPENAI_TRIAGEM_MODEL", "outro")
    assert base != chave_da_triagem(EstruturaArgumentativa(tese_central="calor"), "a")
```

- [ ] **Passo 2: falha.** `uv run pytest tests/test_triagem.py -q` → FAIL: o módulo não existe.
- [ ] **Passo 3: implementar `triagem.py`.**
  - O `_PROMPT` define:
    - a escala 0–3, com as frases da spec;
    - `motivo`: até 12 palavras, antes da nota;
    - as regras de `pedido_da_tese` e `fatos_da_premissa`, movidas do prompt de `resposta.py`, com os mesmos exemplos.
  - `_trecho_triagem(ementa)`: até 1.200 caracteres; acima disso, 800 do começo + `" […] "` + os últimos 400.
  - O cabeçalho reusa `_cabecalho` de `resposta.py`.
  - Primeira ocorrência válida de cada número vence. Nota fora de 0..3 sai.
- [ ] **Passo 4: passa.** `uv run pytest tests/test_triagem.py tests/test_resposta.py -q` → PASS.
- [ ] **Passo 5: commit.** `git commit -m "Triagem: IA dá nota 0-3 e posição para cada ementa do lote"`

---

### Tarefa 4: Cache da triagem e `POST /triagem`

**Arquivos:**
- Criar: `query/search/triagem_cache.py`, `tests/test_triagem_api.py`
- Modificar: `query/api/app.py`, `.env.example` (`OPENAI_TRIAGEM_MODEL=gpt-4o-mini`), `README.md`

**Interfaces:**
- Consome: Tarefa 3 (`avaliar_lote`, `chave_da_triagem`, `Avaliacao`, `tese_para_ia`); Tarefa 2 (ação `"triagem"`).
- Produz:
  - `TriagemCache(database_url)` com `ler_varios(chaves: list[str]) -> dict[str, dict]` e `gravar_varios(itens: dict[str, dict]) -> None`, mais `ensure_schema(database_url)`. A tabela é `public.triagem_cache (chave TEXT PK, avaliacao JSONB NOT NULL, criada_em TIMESTAMPTZ DEFAULT now())` e a gravação usa `ON CONFLICT DO NOTHING`.
  - Dependency `get_triagem_cache(request) -> TriagemCache | None`.
  - Endpoint `POST /triagem`:
    - corpo: `TriagemRequest { estrutura, ids: list[uuid] (min 1, max 10), apenas_cache: bool = False }`;
    - resposta: `TriagemResponse { avaliacoes: list[AvaliacaoItem{id: str, nota, posicao, motivo}] }`.
  - Helper para a Tarefa 5: `avaliacoes_do_cache(cache, estrutura, ids) -> dict[str, Avaliacao]`, em `triagem_cache.py`.

- [ ] **Passo 1: testes**, com o mesmo padrão de fixture `usar` e `_FakeCache` de `tests/test_resposta.py`:

```python
def test_avalia_e_devolve_por_id_e_grava_no_cache(usar)           # 2 ids → 2 avaliações, cache com 2 chaves
def test_so_os_ids_sem_cache_vao_a_openai(usar)                   # 1 de 2 em cache → ementas do prompt só têm o outro (#1)
def test_tudo_em_cache_nao_chama_a_openai_nem_conta_limite(usar)  # fake.chamadas == [] and uso.usos == 0
def test_apenas_cache_nunca_chama_a_openai(usar)                  # 2 ids, 1 em cache → devolve 1, chamadas == []
def test_lote_que_chama_a_openai_conta_um_uso_de_triagem(usar)    # _FakeUso registra acao == "triagem"
def test_limite_estourado_429_sem_chamar_a_openai(usar)
def test_openai_fora_vira_503_com_mensagem(usar)                  # detail == "Avaliação por IA indisponível agora."
def test_cache_fora_do_ar_avalia_mesmo_assim(usar)
def test_mais_de_10_ids_422(usar)
def test_estrutura_sem_tese_422(usar)                             # estrutura só com tribunais
def test_sem_sessao_401()
```

Para registrar a ação, o `_FakeUso` deste arquivo guarda `self.acoes.append(acao)`.

- [ ] **Passo 2: falha.** `uv run pytest tests/test_triagem_api.py -q` → FAIL.
- [ ] **Passo 3: implementar.**
  - No lifespan: `ensure_triagem_cache_schema` e `app.state.triagem_cache`, como o `resposta_cache`.
  - Fluxo do endpoint:
    1. Valida que `tese_para_ia(estrutura)` não está vazio; se estiver, 422.
    2. Lê o cache. Falha do psycopg só gera log.
    3. Se `apenas_cache` ou não falta nada: devolve só o que está no cache.
    4. Senão: `consumir_limite(uso, usuario, "triagem")`, `retriever.fetch(faltam, completo=False)` e `avaliar_lote` em threadpool. `OpenAIError` vira 503.
    5. Grava as novas no cache e devolve cache + novas, na ordem de `ids`.
  - Atualize o docstring do topo de `app.py`, com a lista de endpoints e o pipeline.
- [ ] **Passo 4: README.** Atualize o diagrama do pipeline (o reranker vira "Triagem por IA (POST /triagem, em lotes, no front)"), a seção "Ordem dos resultados", a tabela de tecnologias (sai o FlashRank) e a seção de re-ranking (vira "Triagem por IA", com 5–8 linhas: lotes, cache por par, limite, queda da OpenAI → ordem do RRF).
- [ ] **Passo 5: passa.** `uv run pytest tests/test_triagem_api.py tests/test_triagem.py -q` → PASS.
- [ ] **Passo 6: commit.** `git commit -m "POST /triagem com cache por par tese x decisão"`

---

### Tarefa 5: Resposta só com as relacionadas, posição vinda da triagem

**Arquivos:**
- Modificar: `query/search/resposta.py`, `query/api/app.py` (rota `/resposta`), `tests/test_resposta.py`

**Interfaces:**
- Consome: Tarefa 4, `avaliacoes_do_cache(cache, estrutura, ids) -> dict[str, Avaliacao]`.
- Produz:
  - `gerar_resposta(estrutura, decisoes: dict[int, DocumentoJuridico], posicoes: dict[int, PosicaoTese], client) -> Resposta`.
  - `Resposta` passa a ter só `frases: list[Frase]`; `PosicaoDecisao`, `Desfecho` e `RespostaGerada.desfechos` saem.
  - `RespostaRequest.ids: list[uuid] = Field(min_length=1, max_length=25)`.

- [ ] **Passo 1: ajustar os testes.**
  - `_gerada` sem `desfechos`; `_d` e `_UMA_FRASE` sem desfechos.
  - O fixture `usar` também sobrescreve `get_triagem_cache` com um fake que devolve posições pré-carregadas por id.
  - Testes novos ou alterados:

```python
def test_divergencia_so_cita_decisao_com_a_posicao_da_triagem(usar)  # triagem: #1 deferiu, #2 negou, #3 fato_diferente
def test_id_sem_triagem_vale_outro_e_nao_entra_em_divergencia(usar)
def test_cabecalho_leva_a_posicao(usar)        # "#2 (RORSum, TRT2, 11ª Turma, … · negou)" no prompt
def test_mais_de_25_ids_422(usar)              # substitui test_mais_de_20_ids_422
def test_timeout_40(usar)                      # fake.chamadas[0]["timeout"] == 40
```

  - Apague `test_posicoes_validas_vao_ao_cliente_sem_o_motivo`.
- [ ] **Passo 2: falha.** `uv run pytest tests/test_resposta.py -q` → FAIL.
- [ ] **Passo 3: implementar.**
  - Tire do `_PROMPT` o item `desfechos` e diga que a posição de cada decisão vem no cabeçalho.
  - `_cabecalho(n, doc, posicao)` acrescenta `" · <posicao>"`. Mantenha a assinatura antiga funcionando para a triagem, com `posicao: str | None = None`.
  - As regras de `exigida` usam `posicoes`.
  - A rota lê as posições com `avaliacoes_do_cache`. Se o cache estiver fora ou faltar o id, a posição é `"outro"`.
  - `TIMEOUT_S = 40`.
- [ ] **Passo 4: passa.** `uv run pytest tests/test_resposta.py tests/test_triagem*.py -q` → PASS.
- [ ] **Passo 5: commit.** `git commit -m "Resposta: só relacionadas, até 25, posição lida da triagem"`

---

### Tarefa 6: Voto "É relevante" salvo na versão da conversa

**Arquivos:**
- Modificar: `conversations/store.py`, `query/api/conversa_routes.py`, `tests/test_conversa_routes.py`, `tests/test_conversa_store_integration.py`

**Interfaces:**
- Produz:
  - `ConversaStore.set_relevantes(conversa_id, usuario_id, numero: int, ids: list[str]) -> Conversa`. Usa `jsonb_set(versoes, ARRAY[(numero-1)::text, 'relevantes_usuario'], %s::jsonb)`, com `WHERE id AND usuario_id AND jsonb_array_length(versoes) >= numero`. Se nenhuma linha mudar, levanta `ConversaNaoEncontradaError`.
  - `VersaoResponse.relevantes_usuario: list[str] = []`. Versões antigas não têm o campo.
  - `PATCH /conversas/{id}/versoes/{numero}`: corpo `{ relevantes_usuario: list[uuid] (max 50) }`; devolve `ConversaResponse`.

- [ ] **Passo 1: testes.**
  - Rotas, com fake store como os testes vizinhos:
    - `test_patch_versao_grava_relevantes_e_devolve_conversa`
    - `test_patch_versao_inexistente_404`
    - `test_patch_versao_de_outro_usuario_404`
    - `test_patch_mais_de_50_ids_422`
    - `test_versao_antiga_sem_campo_vem_com_lista_vazia`
  - Integração: `test_set_relevantes_altera_so_a_versao_pedida` (V1 e V2; muda V2; V1 sem o campo, demais campos de V2 intactos).
- [ ] **Passo 2: falha.** `uv run pytest tests/test_conversa_routes.py -q` → FAIL.
- [ ] **Passo 3: implementar** o store, a rota e o modelo.
- [ ] **Passo 4: passa.** `uv run pytest tests/test_conversa_routes.py tests/test_conversa_store_integration.py -q` → PASS (integração pulada sem banco).
- [ ] **Passo 5: commit.** `git commit -m "Conversa: PATCH da versão grava as decisões marcadas como relevantes"`

---

### Tarefa 7: Benchmark S7 e pool de 50

**Arquivos:**
- Modificar: `avaliacao/sistemas.py`, `avaliacao/benchmark.py`, `avaliacao/contexto.py`, `avaliacao/pooling.py`, `docs/avaliacao/README.md`, `tests/test_avaliacao_sistemas.py`, `tests/test_avaliacao_pooling.py`

**Interfaces:**
- Consome: Tarefa 3 (`avaliar_lote`, `chave_da_triagem`); Tarefa 4 (`TriagemCache`).
- Produz:
  - `SISTEMAS = ("S0", "S1", "S2", "S7")`.
  - `ordenar_por_triagem(ids: list[str], avaliacoes: dict[str, Avaliacao]) -> list[str]`: nota decrescente, com desempate pela ordem de entrada; sem avaliação conta como −1.
  - `deps` ganha `openai` (cliente) e `triagem_cache`, montados em `carregar_dependencias`.
  - `montar_pool(..., n_hibrido: int = 50)`.

- [ ] **Passo 1: testes.**

```python
def test_ordenar_por_triagem_nota_desc_desempate_pela_entrada_e_sem_nota_no_fim():
    av = {"b": A(nota=3), "c": A(nota=3), "a": A(nota=1)}
    assert ordenar_por_triagem(["a", "b", "c", "d"], av) == ["b", "c", "a", "d"]

def test_s7_avalia_os_50_em_lotes_de_10_usando_o_cache_e_devolve_top20(monkeypatch)
    # avaliar_lote monkeypatchado conta chamadas: 5 lotes; 2ª execução com cache cheio → 0 chamadas

def test_pool_usa_50_do_hibrido()  # em tests/test_avaliacao_pooling.py
```

- [ ] **Passo 2: falha.** `uv run pytest tests/test_avaliacao_sistemas.py tests/test_avaliacao_pooling.py -q` → FAIL.
- [ ] **Passo 3: implementar.**
  - O S7 chama `buscar(n_resultados=50)`. Os ids já no cache vêm via `ler_varios`; os que faltam vão em lotes de 10 a `avaliar_lote`, sequencialmente (o benchmark não precisa de paralelismo) e gravando no cache. Depois `ordenar_por_triagem(...)[:20]`.
  - Em `benchmark.py`, `"fora_dos_candidatos"` vale para S2 e S7.
  - No README de avaliação: a seção 2 passa a se chamar "Benchmark de sistemas (S0, S1, S2, S7)", com a tabela nova; pool de 50; nota de que os pares 31–50 precisam ser julgados antes da medição; a escolha 40 vs 50 se faz rodando S7 no split dev.
- [ ] **Passo 4: passa.** `uv run pytest tests/test_avaliacao_*.py -q` → PASS.
- [ ] **Passo 5: commit.** `git commit -m "Benchmark: S7 (RRF + triagem por IA) e pool de 50 candidatos"`

---

### Tarefa 8: Front — API, versão e sessão

**Arquivos:**
- Modificar: `frontend/src/lib/api.ts`, `frontend/src/lib/conversations.tsx`, `frontend/src/lib/search-session.tsx`, `frontend/src/components/revisao/entity-review-page.tsx`, `frontend/src/__tests__/lib/api.test.ts`, `frontend/src/__tests__/lib/conversations.test.ts`

**Interfaces:**
- Consome: Tarefas 4, 5 e 6 (contratos HTTP).
- Produz:
  - `type NotaTriagem = 0 | 1 | 2 | 3`
  - `interface Avaliacao { nota: NotaTriagem; posicao: PosicaoTese; motivo: string }`
  - `avaliarLote(estrutura, ids: string[], opcoes: { apenasCache?: boolean }, signal?: AbortSignal): Promise<Record<string, Avaliacao>>`: converte a lista do servidor em mapa por id.
  - `RespostaIA = { frases: FraseResposta[] }`; `gerarResposta` corta em 25.
  - `salvarRelevantes(conversaId: string, numero: number, ids: string[]): Promise<ConversaApi>`
  - `VersaoApi.relevantes_usuario?: string[]`; `ConversationVersion.relevantesUsuario: string[]` (`[]` quando ausente).
  - No contexto de conversas: `setRelevantes(conversaId: string, numero: number, ids: string[]): Promise<void>`. Atualiza a versão local com o retorno da API.
  - Na sessão: `buscaNova: boolean`. `loadVersion(version, opcoes?: { buscaNova?: boolean })` e `relevantesUsuario: string[]`.
  - A Revisão chama `loadVersion(versao, { buscaNova: true })`. A sidebar e o seletor de versão não mudam (padrão `false`).

- [ ] **Passo 1: testes.**
  - Em `api.test.ts`: `avaliarLote manda apenas_cache e devolve mapa por id`; `gerarResposta corta em 25`; `salvarRelevantes faz PATCH na versão`.
  - Em `conversations.test.ts`: `versão sem relevantes_usuario vira lista vazia`.
- [ ] **Passo 2: falha.** `cd frontend && pnpm test -- src/__tests__/lib/api.test.ts src/__tests__/lib/conversations.test.ts` → FAIL.
- [ ] **Passo 3: implementar.**
- [ ] **Passo 4: passa**, mais `pnpm test` inteiro (para pegar quem usava `posicoes`) e `pnpm lint`.
- [ ] **Passo 5: commit.** `git commit -m "Front: cliente de /triagem, voto na versão e flag de busca nova"`

---

### Tarefa 9: Front — hook `useTriagem` (lotes, parar, falhas)

**Arquivos:**
- Criar: `frontend/src/components/resultados/triagem.ts`, `frontend/src/__tests__/components/triagem.test.tsx`

**Interfaces:**
- Consome: Tarefa 8, `avaliarLote`.
- Produz:

```ts
export type StatusTriagem = "avaliando" | "parada" | "concluida" | "indisponivel" | "ociosa";
export function useTriagem(
  estrutura: EstruturaArgumentativa | null,
  resultados: ResultCard[],            // ordem do RRF
  opcoes: { automatica: boolean },
): {
  avaliacoes: Map<string, Avaliacao>;
  status: StatusTriagem;
  avaliadas: number; total: number;
  erro: string | null;                 // mensagem do 429
  parar: () => void;                   // aborta em voo, não dispara mais → "parada"
  continuar: () => void;               // avalia os que faltam → "avaliando"
};
export const TAMANHO_LOTE = 10;
export const EM_VOO = 2;
```

**Regras:**

- A chave é `ids + JSON(estrutura)`. Há um cache em memória por chave, como em `resposta-gerada.tsx`.
- Ao montar ou trocar a chave:
  - `automatica: true`: avalia normalmente.
  - `automatica: false`: um passe com `apenasCache: true` em todos os lotes, sem limite de concorrência; depois o status vira `"concluida"` se não faltar nada, senão `"ociosa"`.
- Falha de lote: uma nova tentativa. Na segunda falha:
  - se for o primeiro lote e o erro for 503 ou de rede, o status vira `"indisponivel"`;
  - senão, os ids ficam sem avaliação.
- `ApiError` 429: para tudo, `erro = message`, status `"parada"`.
- Desmontar ou trocar a chave aborta todos os `AbortController`. Resultado que chega com o sinal abortado é ignorado.

- [ ] **Passo 1: testes**, com `renderHook` e `avaliarLote` mockado com o helper `pendente` do `busca-cancelada.test.tsx`:

```ts
test("dispara 2 lotes por vez e o 3º só quando um termina")
test("cada lote que chega entra em avaliacoes e avança avaliadas")
test("termina em concluida quando todos chegam")
test("parar descarta lote que chega depois")            // resolve o lote abortado: avaliacoes não muda
test("continuar avalia só os que faltam")
test("primeiro lote falha duas vezes → indisponivel e nenhum outro lote")
test("lote do meio falha duas vezes → segue com os outros")
test("429 para tudo e expõe a mensagem")
test("reaberta (automatica false) usa só cache; faltando, fica ociosa")
test("sem resultados conclui sem chamar a API")
test("trocar a chave aborta os lotes da anterior")
```

- [ ] **Passo 2: falha.** `pnpm test -- src/__tests__/components/triagem.test.tsx` → FAIL.
- [ ] **Passo 3: implementar.** Uma fila de lotes num `useRef`. Cada lote termina com `then`/`catch` e chama `proximo()` enquanto houver lote e `emVoo < EM_VOO`. O estado vai num `useReducer`.
- [ ] **Passo 4: passa**, mais `pnpm lint`.
- [ ] **Passo 5: commit.** `git commit -m "Front: useTriagem avalia em lotes de 10, 2 em voo, com parar e continuar"`

---

### Tarefa 10: Front — organizar a lista em seções

**Arquivos:**
- Criar: `frontend/src/lib/triagem-view.ts`, `frontend/src/__tests__/lib/triagem-view.test.ts`

**Interfaces:**
- Produz:

```ts
export const ROTULO_NOTA: Record<NotaTriagem, string>; // 3 "Mesmo problema e fato", 2 "Mesmo pedido", 1 "Mesmo ramo", 0 "Outro tema"
export interface Secoes { relacionadas: ResultCard[]; naoAvaliadas: ResultCard[]; poucoRelacionadas: ResultCard[] }
export function organizar(
  resultados: ResultCard[],              // ordem do RRF
  avaliacoes: Map<string, Avaliacao>,
  relevantesUsuario: string[],           // na ordem do voto
): Secoes;
export function numeracao(s: Secoes): Map<string, number>;  // #1.. na ordem relacionadas, não avaliadas, pouco relacionadas
export function idsParaResposta(s: Secoes, avaliacoes: Map<string, Avaliacao>): string[]; // nota ≥2, máx 25, sem os votados
```

- [ ] **Passo 1: testes.**

```ts
test("relacionadas: nota 3 antes de 2, desempate pela ordem do RRF; depois as votadas na ordem do voto")
test("pouco relacionadas: nota 1 antes de 0; votada sai daqui")
test("sem avaliação vai para não avaliadas, na ordem do RRF")
test("numeracao segue relacionadas → não avaliadas → pouco relacionadas")
test("idsParaResposta corta em 25 e não inclui votadas")
test("voto sobrevive a filtro que esconde o card")  // organizar com resultados filtrados sem o votado e depois com ele: o id continua em relevantesUsuario e reaparece em relacionadas
```

- [ ] **Passo 2: falha.** `pnpm test -- src/__tests__/lib/triagem-view.test.ts` → FAIL.
- [ ] **Passo 3: implementar.**
- [ ] **Passo 4: passa.**
- [ ] **Passo 5: commit.** `git commit -m "Front: lista em seções pela nota da triagem"`

---

### Tarefa 11: Front — tela de resultados

**Arquivos:**
- Modificar: `frontend/src/components/resultados/search-results-page.tsx`, `resposta-gerada.tsx`, `parecer-pesquisa.tsx`, `resultado-card.tsx`, `resumo-decisoes.tsx` (se ele usar a posição), `frontend/src/__tests__/components/parecer-pesquisa.test.tsx`
- Criar: `frontend/src/components/resultados/progresso-triagem.tsx`, `frontend/src/__tests__/components/resultados-triagem.test.tsx`

**Interfaces:**
- Consome:
  - Tarefa 9: `useTriagem`.
  - Tarefa 10: `organizar`, `numeracao`, `idsParaResposta`, `ROTULO_NOTA`.
  - Tarefa 8: `buscaNova`, `relevantesUsuario`, `setRelevantes`.
- Produz:
  - `useRespostaGerada(estrutura, ids: string[] | null)`: `null` = ainda não pedir. O estado ganha `{ status: "aguardando" }` e `{ status: "vazia" }`.
  - `ResultadoCard` ganha as props `numero?: number`, `avaliacao?: Avaliacao`, `marcadaPorVoce?: boolean`, `onRelevante?: () => void` e `onDesfazer?: () => void`. Com `avaliacao`, o selo de rank vira `ROTULO_NOTA[nota]` com `title={motivo}`; sem ela, não há selo.

**Comportamento na página:**

- **Triagem:** `useTriagem(estrutura, porRank, { automatica: buscaNova })`.
- **Ordem congelada:** `ordemCongelada: string[] | null` em `useState`.
  - Quando o status vira `"concluida"` ou `"parada"` e ainda não há ordem congelada, congela `numeracao(organizar(...))` e os ids de `idsParaResposta`.
  - `continuar()` limpa a ordem congelada.
  - Trocar de versão também limpa.
- **Resposta:** os ids vêm de `idsParaResposta` na hora de congelar.
  - Enquanto avalia: "A resposta sai quando a avaliação terminar ou você parar."
  - Lista vazia: "Nenhuma decisão avaliada como relacionada à tese."
  - `"indisponivel"`: o bloco da resposta não aparece e a lista é uma seção só na ordem do RRF, com o aviso da spec.
- **Seções:**
  - "Pouco relacionadas (N)" usa `CollapsibleSection`, fechada por padrão.
  - Os filtros e a ordenação de data existentes valem dentro de cada seção.
- **Números:** com a ordem congelada, vêm dela; senão, de `numeracao` ao vivo.
- **"Decisões que sustentam"** lê a posição de `avaliacoes`.
- **Voto:**
  - "É relevante" chama `setRelevantes(activeId, versionNumero, [...relevantes, id])`, com atualização otimista. Se falhar, desfaz e mostra o erro em linha no card.
  - "Desfazer" remove o id da lista.
  - O voto não toca a ordem congelada.
- **`ProgressoTriagem`:**
  - em `"avaliando"`: "Avaliando decisões com a IA… X de N" e o botão "Parar e responder";
  - em `"ociosa"` ou `"parada"` com itens faltando: "Avaliar N restantes";
  - erro 429 em linha.

- [ ] **Passo 1: testes** (`resultados-triagem.test.tsx`), com `avaliarLote`, `gerarResposta` e `setRelevantes` mockados:

```ts
test("busca nova: mostra progresso e reordena quando o lote chega")
test("parar e responder pede a resposta só com as relacionadas, na numeração congelada")
test("pouco relacionadas ficam recolhidas; É relevante move para relacionadas com 'Marcada por você' e salva na versão")
test("OpenAI fora: aviso, lista na ordem da busca e sem bloco de resposta")
test("versão reaberta com tudo em cache não chama a IA e mostra a resposta")
test("continuar depois de parar descarta a resposta e pede de novo ao concluir")
```

Ajuste `parecer-pesquisa.test.tsx` para o estado sem `posicoes`.

- [ ] **Passo 2: falha.** `pnpm test -- src/__tests__/components/resultados-triagem.test.tsx` → FAIL.
- [ ] **Passo 3: implementar.**
- [ ] **Passo 4: passa**, mais `pnpm test` inteiro e `pnpm lint`.
- [ ] **Passo 5: verificação manual.** Use o skill `run` para subir a API e o front e fazer uma busca real, como a de calor no TRT-12. Confira:
  - a barra de progresso aparece;
  - a lista se reordena;
  - "Parar e responder" funciona;
  - a resposta cita números que batem com os cards;
  - com `OPENAI_API_KEY` inválida, o aviso aparece e a lista vem na ordem da busca.
- [ ] **Passo 6: commit.** `git commit -m "Tela de resultados: triagem progressiva, seções, voto e resposta das relacionadas"`

---

### Tarefa 12: Front — indicador "Uso de hoje" na sidebar

**Arquivos:**
- Criar: `frontend/src/lib/uso-diario.tsx`, `frontend/src/components/uso-diario.tsx`, `frontend/src/__tests__/components/uso-diario.test.tsx`
- Modificar: `frontend/src/lib/api.ts` (`getUso`), o layout `(app)` (`frontend/src/app/(app)/layout.tsx`, envolver com o provider), `frontend/src/components/sidebar.tsx` (bloco acima do perfil), e os pontos que chamam APIs pagas: `home-page.tsx` (`/enrich`), `entity-review-page.tsx` (`/query`), `triagem.ts` (cada lote) e `resposta-gerada.tsx` (`/resposta`)

**Interfaces:**
- Consome: Tarefa 2 (`GET /uso`).
- Produz:
  - `getUso(): Promise<{ acoes: { acao: string; usado: number; limite: number }[] }>`
  - `UsoDiarioProvider` e `useUsoDiario(): { acoes: UsoAcao[] | null; atualizar: () => void }`. `useUsoDiario` fora do provider devolve `{ acoes: null, atualizar: () => {} }`, para os testes existentes não quebrarem.
  - `UsoDiarioIndicador`: nada quando `acoes === null`.

- [ ] **Passo 1: testes.**

```ts
test("mostra 'Uso de hoje' com rótulo e usado/limite de cada ação")   // "Buscas" "3 / 30", "Avaliações da IA" "12 / 150"
test("barra âmbar a partir de 80% e vermelha em 100%")               // data-nivel="alerta" | "esgotado"
test("falha do /uso esconde o bloco")
test("atualizar() busca de novo e re-renderiza")
```

- [ ] **Passo 2: falha.** `pnpm test -- src/__tests__/components/uso-diario.test.tsx` → FAIL.
- [ ] **Passo 3: implementar.**
  - Rótulos: `enrich` "Leitura do caso", `query` "Buscas", `triagem` "Avaliações da IA" (com `title` "Cada lote de até 10 decisões conta 1"), `resposta` "Respostas da IA".
  - O `atualizar()` vai no `finally` de cada chamada paga: no `/enrich`, no `/query`, em cada lote da triagem e no `/resposta`. Nunca roda quando a chamada foi abortada.
- [ ] **Passo 4: passa**, mais `pnpm test` inteiro e `pnpm lint`.
- [ ] **Passo 5: commit.** `git commit -m "Sidebar: indicador do uso diário por ação"`
