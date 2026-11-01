# Provimento do Jev no front — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Mostrar resultado, quem recorreu, a quem favorece e as probabilidades do Jev nos cards e no detalhe da decisão, e gravar a correção que o usuário enviar.

**Architecture:** O backend lê `public.provimento_jev` em lote e anexa um campo opcional `classificacao_provimento` aos cards do `/query` e ao `/document/{id}`. Uma rota nova grava a correção em `public.provimento_correcao` (upsert por documento + usuário). No front, um componente `ProvimentoPanel` mostra os dados e o formulário de correção; os helpers de `lib/provimento.ts` dão rótulos e a regra do selo.

**Tech Stack:** FastAPI + Pydantic + psycopg (backend), Next.js 16 / React 19 / Tailwind 4 / lucide-react, Jest + Testing Library (front).

**Spec:** `docs/superpowers/specs/2026-10-25-provimento-no-front-design.md`

## Global Constraints

- Backend: identificadores e docstrings em português, psycopg puro, fakes injetados nos testes; nunca imprimir nem editar o `.env`.
- Valores aceitos = `RESULTADOS`, `RECORRENTES`, `FAVORECE` de `scraper/provimento_jev.py`; comentário ≤ 1.000 caracteres.
- Confiança: ≥ 0,8 alta, ≥ 0,5 média, abaixo baixa.
- Selo: com classificação e `confianca_favorece` ≥ 0,5 → `reclamante` = favorable, `reclamada` = unfavorable, outro valor = neutral; com classificação e confiança < 0,5 → neutral; sem classificação (campo ausente ou null) → `provimentoToOutcome(provimento)`.
- Rótulos exatamente os da tabela da spec.
- Front: cores inline em hex com variante `dark:`, como os componentes de `components/ui/`; sem dependência nova. Ler `frontend/AGENTS.md` (Next 16) antes de mexer em rota ou layout.
- Toda rota nova exige `Depends(get_current_user)`.

## Review Focus

1. Card salvo em uma conversa antiga, sem `classificacao_provimento` → a tela abre, mostra o provimento de 4 classes e não oferece correção. Testes: Task 3 (`outcomeDe` com campo ausente) e Task 4 (painel com `null`).
2. Postgres falha na consulta das classificações → `/query` e `/document` respondem 200 sem o campo. Teste: Task 2.
3. Clique dentro do painel (abrir probabilidades, selects, botões) dentro do card clicável → não navega para a decisão. Teste: Task 4.
4. Duplo clique em "Enviar correção" ou reenvio → um só registro (upsert) e botão desabilitado durante o envio. Testes: Task 1 (upsert) e Task 4 (disabled).
5. Valor fora da lista, UUID malformado, documento inexistente ou sem sessão → 422 / 404 / 404 / 401, nunca 500. Teste: Task 2.

---

### Task 1: Store das classificações e das correções

**Files:**
- Modify: `scraper/provimento_jev_db.py`
- Modify: `scraper/provimento_jev_cli.py` (subcomando `correcoes`)
- Test: `tests/test_provimento_jev_db_integration.py`, `tests/test_provimento_jev_cli.py`

**Interfaces:**
- Produces:
  - `ensure_schema_correcoes(database_url: str) -> None`: cria `public.provimento_correcao` (idempotente). Colunas: `documento_id UUID REFERENCES documentos(id) ON DELETE CASCADE`, `usuario_id UUID REFERENCES auth.usuarios(id) ON DELETE CASCADE`, `resultado`, `recorrente`, `favorece` TEXT NOT NULL, `comentario TEXT`, `jev_resultado`, `jev_recorrente`, `jev_favorece`, `modelo`, `perguntas_sha` TEXT (nulos se não houver classificação), `criado_em`, `atualizado_em` TIMESTAMPTZ DEFAULT NOW(), `PRIMARY KEY (documento_id, usuario_id)`.
  - `class DocumentoNaoEncontrado(LookupError)`.
  - `ProvimentoJevStore.detalhes(documento_ids: list[str]) -> dict[str, dict]`: para cada id com linha em `provimento_jev`, `{"resultado", "recorrente", "favorece", "probabilidades": probs, "confianca_resultado", "confianca_recorrente", "confianca_favorece", "modelo"}`. Ids sem linha ficam fora; lista vazia → `{}` sem consulta.
  - `ProvimentoJevStore.salvar_correcao(documento_id: str, usuario_id: str, resultado: str, recorrente: str, favorece: str, comentario: str | None) -> datetime`: upsert; copia as respostas, o modelo e o sha atuais do Jev; devolve `atualizado_em`. Documento inexistente (violação de FK) → `DocumentoNaoEncontrado`.
  - `ProvimentoJevStore.correcoes() -> list[dict]`: todas as correções, com as colunas acima, ordenadas por `atualizado_em`.
  - CLI: `python -m scraper.provimento_jev_cli correcoes --csv CAMINHO` grava o CSV e imprime o total e, por pergunta, quantas discordam do Jev.

- [ ] **Step 1: Testes de integração (pulam sem Postgres), no estilo de `criar_doc`**
  - `test_detalhes_devolve_probabilidades`: grava `_classif()` e confere `detalhes([doc])[doc]["probabilidades"] == {"resultado": {"nao_provido": 0.9}}`, `["favorece"] == "reclamante"` e `["modelo"] == MODELO`.
  - `test_detalhes_ignora_sem_classificacao`: doc sem linha → `detalhes([doc]) == {}`; `detalhes([]) == {}`.
  - `test_salvar_correcao_faz_upsert`: duas chamadas para o mesmo (doc, usuário) com `resultado` diferente → `correcoes()` tem 1 linha para o par, com o segundo valor e `jev_resultado == "nao_provido"`.
  - `test_salvar_correcao_documento_inexistente`: `uuid4()` → `pytest.raises(DocumentoNaoEncontrado)`.
  - Fixture `criar_usuario`: insere em `auth.usuarios` (ver colunas em `auth/db.py`) com e-mail `teste-pj-<uuid>@example.com` e apaga no fim.
- [ ] **Step 2: Teste do CLI com store fake** — `test_correcoes_grava_csv(tmp_path)`: o fake devolve 2 correções (uma igual ao Jev, outra com `favorece` diferente); depois de `main(["correcoes", "--csv", str(p)], store=fake)`, o CSV tem cabeçalho + 2 linhas e a saída contém `favorece: 1 de 2`.
- [ ] **Step 3: Rodar** `uv run pytest tests/test_provimento_jev_db_integration.py tests/test_provimento_jev_cli.py -q` → os novos falham.
- [ ] **Step 4: Implementar** as funções acima. `detalhes` usa `WHERE documento_id = ANY(%s::uuid[])`. `salvar_correcao` usa `INSERT ... SELECT ... FROM (VALUES ...) LEFT JOIN provimento_jev ... ON CONFLICT (documento_id, usuario_id) DO UPDATE` e captura `psycopg.errors.ForeignKeyViolation`.
- [ ] **Step 5: Rodar** o mesmo comando → PASS.
- [ ] **Step 6: Commit** `Adiciona leitura das classificações e registro de correções do provimento`

### Task 2: API — campo nos cards e rota de correção

**Files:**
- Modify: `query/search/result_formatter.py`, `query/api/app.py`
- Create: `query/api/provimento_routes.py`
- Test: `tests/test_provimento_routes.py` (novo), `tests/test_api.py`

**Interfaces:**
- Consumes: `ProvimentoJevStore.detalhes`, `salvar_correcao`, `DocumentoNaoEncontrado`, `ensure_schema_correcoes` (Task 1).
- Produces:
  - `ClassificacaoProvimentoView(BaseModel)`: `resultado: str`, `recorrente: str`, `favorece: str`, `probabilidades: dict[str, dict[str, float]]`, `confianca_resultado`, `confianca_recorrente`, `confianca_favorece: float | None`, `modelo: str`.
  - `ResultCard.classificacao_provimento` e `DocumentoDetalhe.classificacao_provimento`: `ClassificacaoProvimentoView | None = None`.
  - `query/api/provimento_routes.py::get_provimento_store(request) -> ProvimentoJevStore | None`: `getattr(request.app.state, "provimento_store", None)`; a rota de correção responde 503 quando ele é `None`.
  - `com_classificacao(cards, store) -> cards`: em `app.py`, preenche o campo; `store is None` ou `psycopg.Error` → devolve os cards sem mudança e registra um aviso no log.
  - `POST /provimento/{documento_id}/correcao`, corpo `{resultado, recorrente, favorece, comentario?}` → 200 `{documento_id, resultado, recorrente, favorece, comentario, atualizado_em}`.
  - Lifespan: `ensure_schema_correcoes(DATABASE_URL)` depois do `ensure_schema` do auth; `app.state.provimento_store = ProvimentoJevStore(DATABASE_URL)`.

- [ ] **Step 1: Testes da rota** (`app` real com `dependency_overrides` para `get_current_user` e `get_provimento_store`, igual a `tests/test_conversa_routes.py`):
  - `test_correcao_grava`: 200, o fake recebeu `(documento_id, str(usuario.id), "provido", "reclamante", "reclamante", "texto")`.
  - `test_correcao_valor_invalido`: `resultado="ganhou"` → 422.
  - `test_correcao_comentario_longo`: 1.001 caracteres → 422.
  - `test_correcao_documento_inexistente`: o fake levanta `DocumentoNaoEncontrado` → 404.
  - `test_correcao_uuid_malformado`: `/provimento/abc/correcao` → 404.
  - `test_correcao_sem_sessao`: sem override de `get_current_user` → 401.
- [ ] **Step 2: Testes em `tests/test_api.py`**
  - `test_query_anexa_classificacao`: com um store fake de `detalhes`, o card do doc classificado traz `classificacao_provimento.favorece == "reclamante"` e o outro vem com `null`.
  - `test_query_sem_classificacao_quando_store_falha`: `detalhes` levanta `psycopg.OperationalError` → 200, campo `null`.
  - `test_document_anexa_classificacao`: o mesmo para `GET /document/{id}`.
  - Os testes existentes que não sobrescrevem o store seguem passando, porque `get_provimento_store` devolve `None`.
- [ ] **Step 3: Rodar** `uv run pytest tests/test_provimento_routes.py tests/test_api.py -q` → os novos falham.
- [ ] **Step 4: Implementar** o modelo, o router (registrado em `app.py` com `include_router`), `com_classificacao` e o lifespan. Valide os valores com `field_validator` contra as tuplas de `scraper/provimento_jev.py`. Use `Field(max_length=1000)` no comentário.
- [ ] **Step 5: Rodar** `uv run pytest --ignore=tests/test_api_stress.py -q` → tudo PASS.
- [ ] **Step 6: Commit** `Anexa a classificação do Jev aos resultados e recebe correções`

### Task 3: Front — tipos, cliente e helpers

**Files:**
- Modify: `frontend/src/lib/api.ts`
- Create: `frontend/src/lib/provimento.ts`
- Test: `frontend/src/__tests__/lib/provimento.test.ts` (novo), `frontend/src/__tests__/lib/api.test.ts`

**Interfaces:**
- Consumes: o JSON da Task 2.
- Produces:
  - `api.ts`: `interface ClassificacaoProvimento` (espelha `ClassificacaoProvimentoView`); `ResultCard.classificacao_provimento?: ClassificacaoProvimento | null` e o mesmo em `DocumentoDetalhe`; `type ResultadoRecurso`, `Recorrente`, `Favorece` (uniões dos valores da spec); `interface CorrecaoProvimento { resultado; recorrente; favorece; comentario?: string | null }`; `enviarCorrecaoProvimento(documentoId: string, body: CorrecaoProvimento): Promise<CorrecaoProvimento & { documento_id: string; atualizado_em: string }>`.
  - `provimento.ts`: `RESULTADO_LABEL`, `RECORRENTE_LABEL`, `FAVORECE_LABEL` (textos da spec); `PERGUNTAS: { chave: "resultado" | "recorrente" | "favorece"; titulo: string }[]` com os títulos "Resultado do recurso", "Quem recorreu" e "A quem favorece"; `nivelConfianca(c: number | null | undefined): "alta" | "media" | "baixa"`; `probabilidadesOrdenadas(p: Record<string, number> | undefined): { valor: string; prob: number }[]` (decrescente; `undefined` → `[]`); `outcomeDe(d: { provimento: Provimento; classificacao_provimento?: ClassificacaoProvimento | null }): Outcome` (regra das Global Constraints); `resumoProvimento(c: ClassificacaoProvimento): string`, que devolve, por exemplo, `"Recurso da reclamada (empresa) · Não provido · Favorece: Trabalhador"`.

- [ ] **Step 1: Testes**
  - `nivelConfianca(0.8) === "alta"`, `(0.79) === "media"`, `(0.5) === "media"`, `(0.49) === "baixa"`, `(null) === "baixa"`.
  - `probabilidadesOrdenadas({a: 0.1, b: 0.7})[0].valor === "b"`; `probabilidadesOrdenadas(undefined)` → `[]`.
  - `outcomeDe`: favorece reclamante com 0,6 → `"favorable"`; reclamada com 0,9 → `"unfavorable"`; reclamante com 0,4 → `"neutral"`; `ambos_em_parte` com 0,9 → `"neutral"`; sem campo e `provimento: "NEGADO"` → `"favorable"` (heurística antiga); `classificacao_provimento: null` e `"APROVADO"` → `"unfavorable"`.
  - `resumoProvimento` com `recorrente: "reclamada"`, `resultado: "nao_provido"` e `favorece: "reclamante"` → a string do exemplo.
  - `api.test.ts`: `enviarCorrecaoProvimento("id-1", {...})` faz POST em `/provimento/id-1/correcao` com JSON e `credentials: "include"`; resposta 422 → `ApiError`.
- [ ] **Step 2: Rodar** `cd frontend && npx jest src/__tests__/lib -i` → os novos falham.
- [ ] **Step 3: Implementar.**
- [ ] **Step 4: Rodar** de novo → PASS.
- [ ] **Step 5: Commit** `Front: tipos e helpers do provimento do Jev`

### Task 4: Componente `ProvimentoPanel`

**Files:**
- Create: `frontend/src/components/provimento/provimento-panel.tsx`
- Test: `frontend/src/__tests__/components/provimento-panel.test.tsx`

**Interfaces:**
- Consumes: Task 3 (`enviarCorrecaoProvimento`, labels, `nivelConfianca`, `probabilidadesOrdenadas`, `resumoProvimento`, `PERGUNTAS`).
- Produces: `ProvimentoPanel({ documentoId: string; provimento: Provimento; classificacao?: ClassificacaoProvimento | null; compacto?: boolean })`.

Comportamento:
- **Sem classificação:** uma linha "Provimento: {provimento legível}", com a nota "ainda não classificado pela IA". Sem botões de correção.
- **Modo compacto (card):** uma faixa com o `resumoProvimento` e o ponto de confiança do resultado. O botão "Detalhes do provimento" (`aria-expanded`) abre o painel completo dentro do card.
- **Painel completo (detalhe, ou o compacto aberto):**
  - uma linha por item de `PERGUNTAS`, com o rótulo escolhido, a confiança em % e uma barra;
  - um botão "Ver probabilidades" por pergunta, que lista todas as opções com barras, da maior para a menor probabilidade;
  - o rodapé "Classificado pelo Jev ({modelo}) · pode conter erros".
- **Ações:**
  - "Está correto" envia as próprias respostas do Jev.
  - "Sugerir correção" abre três `<select>` com id estável (`correcao-resultado-{documentoId}` etc.), já preenchidos com as respostas do Jev, e um `<textarea>` opcional (`maxLength` 1000).
  - "Enviar correção" fica desabilitado enquanto envia. "Cancelar" fecha o formulário.
- **Depois do envio:** a mensagem "Obrigado! Sua correção foi registrada." e as respostas enviadas, sem novo formulário até reabrir. Em erro, a mensagem do `ApiError` em linha.
- **Cliques:** a raiz do componente chama `e.stopPropagation()` em `onClick`, para não abrir a decisão quando o painel está dentro de um card.
- **Estilo:** o mesmo dos cards, com borda `#E4E4EC`/`dark:#26262C`, títulos `#0F1117`/`dark:#ECECEF`, texto secundário `#8A8A9A`/`dark:#9494A2` e acento `#1A3A5C`/`dark:#8AB0DC`. A confiança usa as cores do `OUTCOME_CONFIG`: alta em verde, média em âmbar (`#8A5A1E`/`dark:#E0AC6C`) e baixa em neutro.

- [ ] **Step 1: Testes** (`jest.mock("@/lib/api", ...)`, mantendo os tipos reais):
  - `mostra as três respostas`: os textos "Não provido", "Reclamada (empresa)" e "Trabalhador" aparecem.
  - `abre as probabilidades`: o clique em "Ver probabilidades" do resultado mostra "Provido em parte" com o percentual.
  - `envia correção`: troca o select do resultado para `parcialmente_provido`, digita um comentário e clica em enviar → `enviarCorrecaoProvimento` chamado com `("doc-1", {resultado: "parcialmente_provido", recorrente: "reclamada", favorece: "reclamante", comentario: "..."})`, e a mensagem de sucesso aparece.
  - `está correto envia as respostas do Jev`.
  - `desabilita enviar durante o envio`: com a promessa pendente, o botão fica `disabled`.
  - `mostra erro da API`: a promessa rejeita com `new ApiError("Documento não encontrado.", 404)` → o texto aparece.
  - `sem classificação`: mostra "ainda não classificado pela IA" e não mostra "Sugerir correção".
  - `não propaga o clique`: renderizado dentro de `<div onClick={pai}>`, clicar em "Detalhes do provimento" não chama `pai`.
- [ ] **Step 2: Rodar** `cd frontend && npx jest src/__tests__/components/provimento-panel.test.tsx -i` → FAIL.
- [ ] **Step 3: Implementar.**
- [ ] **Step 4: Rodar** de novo → PASS.
- [ ] **Step 5: Commit** `Front: painel do provimento com probabilidades e correção`

### Task 5: Encaixar nas telas

**Files:**
- Modify: `frontend/src/components/resultados/search-results-page.tsx`, `frontend/src/components/decisao/decision-detail-page.tsx`

**Interfaces:**
- Consumes: `ProvimentoPanel` (Task 4), `outcomeDe`, `resumoProvimento` e `RESULTADO_LABEL` (Task 3).

- [ ] **Step 1: Resultados**
  - Troque todo `provimentoToOutcome(d.provimento)` por `outcomeDe(d)`: o selo, os filtros, as contagens do topo e o `toggleSave`.
  - Coloque `<ProvimentoPanel compacto documentoId={decision.id} provimento={decision.provimento} classificacao={decision.classificacao_provimento} />` entre a meta do cabeçalho e o resumo.
  - No chip de percentual, use `title` e `aria-label` com o texto "Relevância relativa ao melhor resultado desta busca".
  - No `exportResults`, a linha do provimento passa a usar o `resumoProvimento` quando houver classificação.
- [ ] **Step 2: Detalhe**
  - `outcome = outcomeDe(doc)`.
  - Uma seção nova com `<ProvimentoPanel documentoId={doc.id} provimento={doc.provimento} classificacao={doc.classificacao_provimento} />`, depois das entidades correspondentes e antes do Resumo. Use o mesmo `px-5 sm:px-7 py-5 border-b` e o título "Provimento" com `SectionHeading`.
  - O chip lateral do provimento (linha ~470) mostra `RESULTADO_LABEL[resultado]` quando houver classificação.
- [ ] **Step 3: Verificar**
  - `cd frontend && npx jest -i` → tudo PASS.
  - `npx tsc --noEmit` → nenhum erro novo (o de `LayoutProps` em `layout.tsx` já existia).
  - `npx eslint src/components/provimento src/components/resultados src/components/decisao src/lib/provimento.ts` → sem erro.
- [ ] **Step 4: Ver funcionando.** Com backend e front no ar, faça uma busca e confira:
  - o card mostra o resumo e abre os detalhes sem navegar;
  - uma correção enviada aparece em `public.provimento_correcao`;
  - o detalhe mostra o painel;
  - os temas claro e escuro ficam legíveis.
- [ ] **Step 5: Commit** `Front: provimento do Jev nos resultados e no detalhe da decisão`
