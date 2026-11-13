# Redução de linhas — plano

> **Para quem executa:** use superpowers:subagent-driven-development, um lote por vez, um commit por lote. Passos em checkbox.

**Objetivo:** deixar a codebase menor e mais fácil de explicar na review, sem mudar comportamento. Quando houver mudança, ela vem declarada e justificada.

**Como:** eliminar código morto, duplicação e documentação desatualizada em lotes coesos. Primeiro vêm os ganhos fáceis e seguros. O que muda comportamento ou depende de decisão do Vinicius fica num bloco à parte e só entra com aprovação item a item.

**Ponto de partida:** [`baseline.md`](baseline.md), com **36.524 linhas**, 662 testes no backend, 190 no frontend, tsc e build ok, e 5 problemas de eslint que já existiam.

**Fonte dos achados:** seis auditorias somente leitura (`.superpowers/sdd/refactor-auditoria/fatia-1..6.md`). Conferi por amostragem as que sustentam os lotes.

## Regras para todos os lotes

- **Verificação depois de cada lote:**
  - backend: `set -a && . ./.env && set +a && uv run pytest -q --deselect tests/test_api_stress.py`, esperando **662 passed** (menos os testes removidos de propósito, que o lote declara);
  - frontend: `cd frontend && npx jest && npx tsc --noEmit && npx eslint src`, esperando só os 5 problemas que já existiam;
  - build: `npx next build`.
- **Se algo quebrar:** `git restore`/`git revert` do lote e reportar. Nada de remendo.
- **Commit:** um por lote, com a mensagem dizendo o que saiu e **quantas linhas** (medidas com o script do baseline, não estimadas).
- **Não mexer sem perguntar:**
  - endpoints e schemas de request/response;
  - tabelas e colunas;
  - variáveis de ambiente;
  - CLIs de produção (`scraper/run.py`, `indexing/run.py`, `python -m query.filtros.preparar`, `provimento_jev_cli`);
  - `pipeline/`, Dockerfile, compose e CI.
- **Não tocar:** `avaliacao/planilha_coleta.py` e `tests/test_avaliacao_planilha_coleta.py`, que não estão rastreados e não são deste trabalho. Por causa deles, `QueryEnricher.extract_estrutura` **fica**.
- **Sem code golf:** se uma simplificação deixar o trecho mais difícil de explicar, ela não entra.
- **Telas sem teste** (login, Revisão, Decisão, barra lateral, Home): toda mudança nelas passa por captura visual, clara e escura, antes do commit.

## Resumo

| Lote | Tipo | Linhas (estim.) | Risco | Muda comportamento? |
|---|---|---:|---|---|
| 1 | Código e dependências mortos | ~140 | baixo | não |
| 2 | Documentação desatualizada ou duplicada | ~850 | baixo (só texto) | não |
| 3 | Testes: fixtures e fakes repetidos | ~135 | baixo | não (mesmos testes, menos cópia) |
| 4 | Backend: duplicação simples coberta por teste | ~150 | baixo | não |
| 5 | Frontend: duplicação de lógica e CSS morto | ~190 | baixo-médio (CSS: visual) | não |
| 6 | Telas de login com casca única | ~230 | médio (sem teste unitário) | não (visual idêntico) |
| 7 | Molde de página e topbar únicos | ~35 | médio (sem teste) | não |
| **1–7** | **seguro** | **~1.730 (≈ 4,7%)** | | |
| 8 | decisões aprovadas (D1, D2, D3, D8, D9, D12, D13, D14) | ~600 | médio | D1/D2: some a suíte E2E e o script de carga; D8: some a migração do perfil antigo |
| 9 | otimizações | ~0 | baixo-médio | não (mesmos resultados, mais rápido) |
| **1–9** | **aprovado em 13/11** | **~2.330 (≈ 6,4%)** | | |

Aprovado em 13/11: lotes 1–7, as decisões D1, D2, D3, D8, D9, D12, D13 e D14, e as otimizações. Total ≈ **-2.330 linhas, ≈ 6,4%**.

---

## Task 1: Lote 1 — Código e dependências mortos (~140 linhas)

Cada item foi provado com grep no repo inteiro: só há uso no próprio arquivo, ou apenas em testes que existem para ele.

**Frontend**
- `frontend/src/lib/utils.ts`: apagar `cn()`, que não tem nenhum uso, e tirar do `package.json` as deps `clsx`, `tailwind-merge` e `class-variance-authority` (esta tem zero imports).
- `frontend/package.json` e `globals.css:2`: tirar `tw-animate-css`. Nenhuma classe `animate-in/out`, `fade`, `slide` ou `zoom` é usada; `animate-spin` e `animate-pulse` são do Tailwind puro.
- `frontend/public/{file,globe,next,vercel,window}.svg`: sobras do `create-next-app`, sem referência.
- `frontend/src/lib/outcome.ts:14-20`: os `case "PARCIAL"` e `case "NAO_APLICAVEL"` já caem no `default`. Tirar e encurtar o comentário duplicado.
- Atualizar o lock com `pnpm install`. O lock não entra na contagem.

**Backend**
- `query/filtros/dispositivos.py:49` `eh_dispositivo` e o teste dela: só o teste a usa.
- `processing/embeddings/poly_vector.py:72` `embed_chunk` e os 2 testes dela: a indexação usa `embed_batch`/`embed_text`.
- `processing/chunking/sac_chunker.py`: tirar `MAX_TOKENS`, que só tem a definição, e `_count_tokens`, que só o teste usa, junto com esse teste.
- `query/search/reranker_monoptt5.py:14` `PROMPT`: o prompt real é montado por pedaços, e a constante só serve à asserção do teste. Apagar as duas.
- `scraper/html_extractor.py`: `_SECTION_MAP` é um dicionário identidade, então usar `titulo in _SECTION_FIELDS`. `extract_ementa` é wrapper de uma linha de `html_to_text`. A coleta não tem teste, então conferir com `python -c "import scraper.html_extractor"` e, se possível, parsear um HTML salvo.
- `query/search/pipeline.py`: tirar `filtrar_nos_canais`, que só um teste passa, e `N_CANDIDATOS_COM_FILTRO` (versão mínima, sem tocar no contrato do `/query`). Ajustar o teste que usava o parâmetro.
- `scraper/run.py:42` `resolve_dates`: wrapper de 1 uso, vira chamada direta.
- `avaliacao/planilha_julgamento.py:286` `ler_lote`: só testes a usam. Os testes passam a chamar `_ler`.
- `run.sh:96`: tirar o download de `nomic-embed-text`. Os embeddings vêm da OpenAI, e nada usa esse modelo.

**Testes que saem por redundância**
- `tests/test_api.py::test_query_sem_filtro_usa_pool_de_rerank`: `test_pipeline.py::test_buscar_sem_filtro_nao_passa_provimento_e_usa_pool_30` cobre exatamente o mesmo.
- `tests/test_avaliacao_construir.py::test_doc_e_help_descrevem_o_pool_novo`: testa a redação de um docstring, não comportamento.

**Passos**
- [ ] Remover os itens acima.
- [ ] Rodar a verificação completa, esperando **662 − (testes removidos, contados)** no backend e 190 − 0 no front.
- [ ] Rodar o build.
- [ ] Commit: "Remove código e dependências mortos (N linhas)".

## Task 2: Lote 2 — Documentação desatualizada ou duplicada (~850 linhas)

São só texto, e cada afirmação apagada ou corrigida foi conferida no código. Não toca as RFCs.

| Arquivo | O que fazer | Linhas |
|---|---|---:|
| `auth/DESIGN_NOTES.md`, `auth/SCHEMA.md`, `query/api/AUTH_ROUTES_DESIGN_NOTES.md` (422 linhas) | Consolidar num `auth/DESIGN.md` de ~120 linhas. Eles descrevem a "peça" antes da integração ("não aplicado", "recuperação de senha fora de escopo"), e tudo isso já existe. Atualizar as menções em `auth/db.py` e no README. | -300 |
| Docstrings e comentários de `query/api/auth_routes.py`, `auth/*.py`, `conversations/*.py` | Repetem as notas acima e falam em "peça futura" e "outro agente". Fica 3–5 linhas por módulo, com o porquê não óbvio (SameSite, DUMMY_HASH, resposta igual no esqueci-senha). | -130 |
| `query/api/app.py:1-31` | O docstring cita o "Hierarchical Ranker", que foi removido, e diz que "nada é persistido", mas as conversas são salvas. Corrigir e encurtar. Juntar os imports duplicados (linhas 60/63 e 77/79). | -25 |
| `query/search/{pipeline,reranker,hybrid_search}.py` | O mesmo argumento de normalização aparece em 3 lugares, e há medições antigas em comentário. Fica o porquê em 2–3 linhas. | -55 |
| `indexing/vector_store/qdrant_store.py` | O cabeçalho cita `chroma_store.py`, que não existe, e explica o HNSW três vezes. `EMBED_DIM` passa a ser importado de `poly_vector.py`. | -35 |
| Menções a "Chroma" em `scraper/schema.py`, `db_writer.py`, `sac_chunker.py`, `doc_source.py`, `docker-compose.yml:29-31` | Corrigir. O compose diz "HNSW em disco", mas o código usa RAM. | 0 (correção) |
| `docs/Backup_Indices.md` | Descreve o BM25 como `.pkl`, mas hoje é `bm25s_index`, e metade do arquivo é da era Chroma. Reduzir a backup de Postgres, Qdrant e `bm25s_index`. | -80 |
| `docs/deploy/2026-11-01-deploy-vps.md` | Diz que Dockerfile, compose, CI e HTTPS "não existem", e todos existem. Vira um "runbook de deploy". | -100 |
| `frontend/README.md` | Fala em scaffold, "telas são placeholders" e `cn()`. Vira ~12 linhas apontando para o README raiz. | -24 |
| README · Estrutura | A árvore lista arquivos que não existem (`scraper/api.py`, `items/`, `settings.py` do Scrapy, `processing/ner`, `indexing/graph`). Trocar por uma árvore correta de 2 níveis. | -15 |
| README · Autenticação | Diz que `/esqueci-senha` não tem backend, o que é falso. Corrigir. | -4 |
| README · Testes (back e front) | As tabelas por arquivo já estão defasadas. Fica o comando e 2 linhas de política. | -18 |
| README · tabela de variáveis | Repete o `.env.example`. Ficam as obrigatórias (`DATABASE_URL`, `OPENAI_API_KEY`, `JWT_SECRET_KEY`). | -10 |
| README · Filtro restrito | Tirar os números de medição (tempos, disco, contagens), que viram dado de relatório. Ficam as regras e o comando `preparar`. | -20 |
| README · Jev | O custo aparece 2 vezes. Citar o subcomando `sincronizar`, que hoje é omitido. | -6 |
| README · Avaliação da busca (129 linhas) | Mover o manual para `docs/avaliacao/README.md`, condensado. No README ficam ~10 linhas. | -40 |
| `utils/reclassify.py`, `scraper/provimento.py`, `avaliacao/db.py:62` | Docstring longo, aviso duplicado e comentário histórico. | -18 |

- [ ] Fazer as edições.
- [ ] Rodar os links do README com `grep` para conferir os caminhos citados.
- [ ] Rodar a verificação completa (os docstrings não mudam comportamento, mas os imports de `app.py`/`qdrant_store.py` mudam).
- [ ] Commit: "Docs: tira o que descrevia código que não existe mais (N linhas)".

## Task 3: Lote 3 — Testes: fixtures e fakes repetidos (~135 linhas)

Os testes continuam sendo os mesmos e a contagem não pode mudar.

- **Postgres:** `DATABASE_URL`, `_postgres_disponivel()` e `pytestmark = skipif(...)` aparecem idênticos em 6 arquivos `*_integration.py`. Ficam uma vez em `tests/conftest.py` (`requer_postgres`). (-70)
- **`tests/fakes.py`:** `FakeReranker`, `FakeDocRetriever` e `doc()` estão copiados em `test_api.py` e `test_pipeline.py`. Hoje `test_avaliacao_sistemas.py` importa `_doc` de outro teste. Junto vão `usuario_fake()` (repetido em 6 arquivos) e `FakeOpenAI` (2). (-65)
- [ ] Rodar `uv run pytest --collect-only -q | tail -1` antes e depois e conferir que o número coletado é o mesmo.
- [ ] Rodar a suíte com e sem `DATABASE_URL`, para confirmar que os de integração pulam e rodam como antes.
- [ ] Commit.

## Task 4: Lote 4 — Backend: duplicação simples coberta por teste (~150 linhas)

Comportamento igual, provado pelos testes que já existem.

- **Conexões:** `auth/store.py` e `conversations/store.py` repetem 12 vezes `connect / try / commit / finally close`. Viram `with psycopg.connect(url) as conn:`, como já fazem `resposta_cache.py` e `uso_diario.py`. Idem em `query/search/doc_retriever.py`. (-50)
- **`/filtros` e `/query`:** o mesmo `if store is None` e `try/except FiltroIndisponivel → 503` aparece em 4 rotas. Vira um `exception_handler` com o mesmo status e a mesma mensagem, mais uma dependency obrigatória. (-16)
- **`auth_routes.py`:** os validators de strip estão duplicados. `get_current_user_publico` é wrapper de 1 linha com 1 uso e vira chamada inline. (-16)
- **`conversa_routes.py`:** o `try/except` que vira 404 se repete em 3 rotas e vira `exception_handler`. (-8)
  - `CriarConversaRequest` e `RenomearConversaRequest` são idênticas, mas **ficam**: juntá-las muda o nome do schema no OpenAPI.
- **`query/search/result_formatter.py`:** a cópia de 15 campos vira `ResultCard(**doc.model_dump(include=...), ...)`, o mesmo idioma de `get_document`. (-10)
- **`hybrid_search._dedup_ordenado`:** vira `list(dict.fromkeys(...))`. Ajustar o import em `avaliacao/sistemas.py`. (-11)
- **`query/search/pipeline.py`:** o bloco de rerank reconstrói os triplos duas vezes; montar uma vez só. (-8)
- **`provimento_jev*.py`:** `os.getenv("TYPESAFE_MODEL", MODELO_PADRAO)` aparece 5 vezes e vira `modelo_configurado()`. (-4)
- **`avaliacao/contexto.py`:** parar de carregar o `Reranker()` (FlashRank) no contexto. O `construir` não usa e o `benchmark` descarta. Isso também é otimização. (-3)
- **`indexing/doc_source.py`:** a conexão nunca é fechada e passa a usar `with`. Correção de vazamento, sem ganho de linhas.
- [ ] Rodar a verificação completa.
- [ ] Commit.

**Fora deste lote**, porque mexe em contrato ou ficaria pior de explicar:
- `DispositivoView` → `SugestaoDispositivo` (muda o nome no OpenAPI);
- unir os requests de conversa;
- `_row_para_documento` com `zip`.

## Task 5: Lote 5 — Frontend: duplicação de lógica e CSS morto (~190 linhas)

- **`globals.css`:** só 7 variáveis são usadas. Tirar os tokens card, popover, primary, secondary, muted, accent, destructive, input, chart-1..5 e sidebar-\* (`:root`, `.dark` e `@theme`). Conferir o fundo e o texto do `body` no claro e no escuro com captura. (-80)
- **`lib/api.ts`:** o mesmo bloco `{method, headers JSON, body: JSON.stringify}` aparece 12 vezes e vira um helper `enviarJson(path, method, body)`. O `api.test.ts` já confere método, header e corpo. (-30)
- **`useCopiar()`:** o "copiar e mostrar 'Copiado!' por 2 s" está escrito 5 vezes (`parecer-pesquisa`, `resultado-card` e 3 vezes em `decision-detail-page`). (-25)
- **`paraSalvo(doc, rank)` em `lib/decision-view.ts`:** o objeto `SavedDecision` é montado à mão em 2 telas. Ganha teste novo. (-10)
- **`useFecharAoClicarFora(ref, aberto, fechar)`:** aparece 2 vezes (`filtro-restrito`, `search-results-page`). (-10)
- **`MetaItem`:** uma prop `compacto` substitui os 4 overrides repetidos em 6 chamadas. (-12)
- **Datas:** `formatDateLong`, `formatDateShort` e o `formatDate` da tela de salvos duplicam `formatarData`. (-8)
- **Cores das buscas ainda escritas à mão** (Revisão, guia, painel) passam a vir de `lib/cores-busca.ts`. (-13)
- **Pequenos:**
  - em `search-session.tsx:98`, usar `{ ...emptyEstrutura(), ...version.estrutura }`;
  - na barra lateral, o clique do logo usa `novaPesquisa()`;
  - comentários colados no componente errado (4). (-6)
- [ ] Rodar a verificação completa.
- [ ] Capturar Resultados, Revisão, Decisão e Salvos no claro e no escuro.
- [ ] Commit.

## Task 6: Lote 6 — Telas de login com casca única (~230 linhas, risco médio)

As 4 telas (`login`, `register`, `forgot-password`, `reset-password`, com 683 linhas) repetem várias peças:
- logo e cartão;
- campo com ícone e input, com cerca de 330 caracteres de classe, 9 vezes;
- olho da senha, 3 vezes;
- botão primário, 5 vezes;
- caixa de erro.

A ideia é extrair `login/auth-shell.tsx` e `login/campo-auth.tsx`.

- **Cobertura de teste:** só `forgot` e `reset` têm teste unitário. `login` e `registro` passam a ter um teste de render e submit, escrito **antes** de mexer.
- [ ] Escrever os testes do login e do registro e vê-los passar no código atual.
- [ ] Refatorar.
- [ ] Rodar os mesmos testes.
- [ ] Capturar as 4 telas no claro, no escuro e a 375 px, comparando com antes.
- [ ] Commit.

## Task 7: Lote 7 — Molde de página e topbar (~35 linhas, risco médio)

- **Fundo da página:** `bg-[#F7F7F9] dark:bg-[#0E0E11]` aparece em 16 `<main>`.
- **Topbar:** guia e home copiam o header do `PageTopbar`. O `PageTopbar` passa a aceitar um slot à direita, e um `Pagina` envolve o `<main>`.
- **Decisão:** os dois `return` antecipados da `decision-detail-page` passam a usar esse molde.
- [ ] Capturar todas as telas antes e depois.
- [ ] Commit.

## Task 8: Lote 8 — Decisões aprovadas (D1, D2, D3, D8, D9, D12, D13, D14) (~600 linhas)

- **D1 Cypress:** apagar `frontend/cypress/`, `cypress.config.ts`, as deps `cypress` e `start-server-and-test`, os scripts `cypress:*` e `test:e2e`, `cypress` em `pnpm-workspace.yaml` (`onlyBuiltDependencies`), `CYPRESS_INSTALL_BINARY` (`.github/workflows/ci.yml`, `Dockerfile`), a exclusão em `jest.config.mjs` e `tsconfig.json`, e as menções no README.
- **D2:** apagar `tests/test_api_stress.py`. Tirar o `--ignore` do `ci.yml` e as menções (README, `docs/deploy`, `docs/refactor/baseline.md` fica como está, porque é registro, e o docstring de `test_auth_store_integration.py`). Daqui para a frente o comando de testes é `uv run pytest -q`.
- **D3:** apagar `requirements.txt`.
- **D8:** em `frontend/src/lib/profile.tsx` e `saved.tsx`, tirar a migração do localStorage antigo (`CHAVE_SEM_DONO`, `chaveAntigaDe`, `removeItem(CHAVE_ANTIGA)`) e os testes dela.
- **D9:** em `conversations/db.py`, tirar `_MIGRACAO_ADICIONA_VERSOES` e `_MIGRACAO_REMOVE_COLUNAS_SNAPSHOT_UNICO` e as chamadas. O `CREATE TABLE` atual já tem `versoes`.
- **D12:** README · Escalabilidade: o diário de 53 linhas vira ~15 linhas com as decisões e os números que importam (Qdrant, bm25s, reranker), apontando para os docstrings.
- **D13:** `docs/Diagramas`: manter um só C4 nível 3 do backend, o que gerou o `.svg` rastreado (conferir pelo nome e pela data). Apagar o outro.
- **D14:** em `scraper/db_writer.py`, gerar o upsert a partir de uma tupla `COLUNAS` única, mantendo o SQL legível (uma coluna por linha na tupla). **Antes**, escrever um teste que guarda o SQL atual (`_CREATE_TABLE`, `_UPSERT`) normalizado (espaços colapsados) e exige igualdade depois da troca. A coleta não tem teste, e este é o seguro.
- [ ] Rodar a verificação completa. O comando do backend perde o `--deselect`.
- [ ] Rodar o build.
- [ ] Rodar `docker build --target api .` (o Dockerfile mudou).
- [ ] Commit.

## Task 9: Lote 9 — Otimizações (aprovadas)

Cada uma com teste quando o comportamento puder ser observado. Nenhuma muda resultado de busca.
- **`query/search/reranker.py`:** o `ThreadPoolExecutor` é criado uma vez no `__init__`, não a cada chamada.
- **`query/api/app.py` `/enrich`:** `_expressoes_no_acervo` e `_dispositivos_no_acervo` rodam juntos (`asyncio.gather`), porque não dependem um do outro. O teste existente do `/enrich` precisa continuar igual.
- **`/query`:** `DocRetriever` ganha um modo que busca só as colunas usadas no card e na reordenação (ementa e metadados). `/document/{id}`, `/resposta` e `avaliacao/` continuam com o documento completo. Teste: o card da `/query` é idêntico com o modo enxuto.
- **`scraper/provimento_jev_db.py`:** `classificar_pendentes` grava o lote numa conexão só, não uma por acórdão.
- **`frontend/.../search-results-page.tsx`:** `filteredResults`, `resumoTopo` e `idsCitacao` vão para `useMemo`.
- **Bug do `TagList`** (`entity-review-page.tsx`): `key={idx}` vira chave estável. Teste: remover o 1º de 3 chips em edição não leva o estado ao item errado.
- **Respostas atrasadas:** na Revisão (`queryJurisprudencia`) e na faixa livre (`queryLivre`), uma resposta antiga é ignorada se uma busca mais nova foi disparada (contador em `useRef` ou `AbortController`). Teste com duas promessas resolvidas fora de ordem.
- **Remoção de acentos:** `query/filtros/dispositivos.py` e `expressoes.py` (NFD, iguais) passam a usar um `sem_acento()` só. **O tokenizer do BM25 (`bm25_builder.py`, NFKD), `provimento.py` e `html_extractor.py` ficam como estão**, porque mudar a normalização do índice exigiria reindexar. Teste: a mesma saída para uma amostra de 20 textos com acentos, cedilha, ordinais (º/ª) e §.
- [ ] Rodar a verificação completa.
- [ ] Commit.

---

## Decisões suas (uma por vez, nada entra sem o seu "sim")

| # | O quê | Linhas | Muda algo? | Minha recomendação | Vinicius (13/11) |
|---|---|---:|---|---|---|
| D1 | **Cypress**: os specs foram escritos para o login falso ("qualquer credencial entra"), e o login hoje é real. O CI não roda o Cypress e ninguém mexeu nele desde o `7b40068`. Apagar `cypress/`, a config, 2 deps, 3 scripts, `CYPRESS_INSTALL_BINARY` (CI e Dockerfile) e as menções no README. | -245 | sim: some a suíte E2E, que já não funciona | apagar | ✅ aprovado |
| D2 | **`tests/test_api_stress.py`**: não é teste. É um script de carga contra o portal da JT, com **cookies e token escritos no código**, já expirados. Apagar e tirar o `--ignore` do CI. | -94 | toca o CI | apagar. O token continua no histórico do git; como expirou, não exige ação. | ✅ aprovado |
| D3 | **`requirements.txt`**: duplica o `pyproject.toml` e já divergiu dele (não tem dagster). Nada o usa: Docker e CI usam o uv. | -42 | sim, para quem instala com pip | apagar | ✅ aprovado (conferido: nada cita o arquivo; Docker e CI usam uv) |
| D4 | **HTML do inventário** (`docs/superpowers/specs/2026-10-21-...html`): o mesmo conteúdo do `.md` de 503 linhas. O PDF e o artifact são os entregáveis. | -1.558 (fora da métrica: o `.html` não entra na contagem) | não | apagar, se o PDF e o artifact bastam | ❌ ainda não |
| D5 | **`docs/superpowers/`** (24 arquivos): os **planos** (10 arquivos) são passo a passo de features já entregues. Os **specs** guardam o porquê, e as 3 conferências do Jev são evidência citada no README. | -1.906 (só planos) a -3.780 (tudo) | não | apagar só os planos e manter specs e conferências | ❌ não |
| D6 | **`.claude/skills/gauntlet-loop/`**: skill pessoal sem relação com o projeto. | -133 | não | mover para `~/.claude/skills` | ❌ não |
| D7 | **Filtro de provimento e período no `/query`**: nenhuma tela envia esses campos. Removê-lo por inteiro mexe no `QueryRequest`. | -65 | sim, no contrato da API | manter (há o Lote 1 mínimo) | ❌ não |
| D8 | **Migração antiga do localStorage** (perfil e salvos de versões antigas). | -47 com testes | sim: perde dados de quem ainda tem perfil local | manter até a apresentação | ✅ aprovado |
| D9 | **Migrações caducas em `conversations/db.py`**. | -18 | sim, se a VPS ainda não migrou | só depois de conferir a VPS | ✅ aprovado (local já migrado; VPS restaurada do dump local em 01/11, depois da migração de 04/10) |
| D10 | **Colunas de probabilidade em `avaliacao/`**: sobraram do juiz-LLM e ninguém grava nem lê. | -28 | schema; as colunas ficam no banco, nulas | pode tirar | ❌ não |
| D11 | **`provimento_routes`**: 3 validators viram `Literal`. | -10 | sim: muda o texto do erro 422 | manter | ❌ não |
| D12 | **README · Escalabilidade**: diário de migração de 53 linhas, condensado em ~15. | -45 | não, mas é texto de TCC | condensar | ✅ aprovado |
| D13 | **Diagramas `.txt` duplicados**: dois C4 nível 3 do backend, ambos com Chroma. | -82 | não, mas é artefato do TCC | manter um | ✅ aprovado |
| D14 | **Upsert gerado em `db_writer.py`**: as 24 colunas aparecem 4 vezes. | -25 | não | **não fazer**: o SQL literal é mais fácil de explicar | ✅ aprovado (com teste que prova SQL idêntico) |
| D15 | **"Avança o dia" duplicado no `orchestrator.py`** (coleta, sem teste). | -12 | só o texto do log | fazer só com um teste novo da coleta | ❌ não |

## Otimizações encontradas

| O quê | Onde | Status (13/11) |
|---|---|---|
| A conexão Postgres nunca é fechada | `indexing/doc_source.py` | aprovado: Lote 4 |
| O FlashRank é carregado sem uso | `avaliacao/contexto.py` | aprovado: Lote 4 |
| Um modelo de centenas de MB é baixado à toa | `run.sh` (`nomic-embed-text`) | aprovado: Lote 1 |
| Um `ThreadPoolExecutor` é criado a cada busca | `query/search/reranker.py` | aprovado: Lote 9 |
| As consultas de expressões e dispositivos do `/enrich` rodam em sequência | `query/api/app.py` | aprovado: Lote 9 |
| A `/query` busca o documento completo para montar o card | `doc_retriever.fetch` | aprovado: Lote 9 |
| O Jev abre uma conexão por acórdão | `provimento_jev_db.py` | aprovado: Lote 9 |
| `resumoTopo` e `filteredResults` são recalculados a cada render | `search-results-page.tsx` | aprovado: Lote 9 |
| `key={idx}` em `TagList` | `entity-review-page.tsx` | aprovado: Lote 9 |
| `/query` sem `AbortController` | `lib/api.ts` | aprovado: Lote 9 |
| Remoção de acentos com NFKD em 5 cópias | `bm25_builder`, `provimento`, `html_extractor`, `dispositivos`, `expressoes` | aprovado: Lote 9 (o BM25 fica fora; ver Task 9) |

## Achados fora da redução, que valem saber para a review

- **RFC × código:** as RFCs assinadas dizem ChromaDB, `nomic-embed-text` local (RNF03, "100% local"), `rank_bm25` e ordenação por hierarquia. O código usa Qdrant, embeddings da OpenAI, `bm25s` e reranker cross-encoder, e tem o Jev e o filtro restrito, que não estão nas RFCs. **O RNF03 deixou de valer para os embeddings da consulta.** A banca pode perguntar. A lista completa está em `fatia-6-docs.md`.
- **`pyproject.toml`:** o `include` cita uma pasta `interface*`, que não existe, e não cita `auth*`, `conversations*`, `pipeline*` nem `utils*`. Funciona porque tudo roda da raiz. É contrato de build, então não mexo sem você.
- **`deploy/puxar-backups.sh`:** o IP da VPS está fixo no repositório como valor padrão.
- **eslint:** 3 dos 5 erros pré-existentes (`set-state-in-effect`) têm correção simples, mas exigem cuidado com hidratação. Não reduzem linhas. Ficam fora, a não ser que você queira.
