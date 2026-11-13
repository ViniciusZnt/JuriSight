# Redução de linhas — resumo para a review

Branch `refactor/reducao-linhas` (de `main` em `e5c6539` até `0c21760`, mais o commit deste resumo).
Objetivo: codebase menor e mais fácil de explicar, sem mudar comportamento. O que mudou algo
está declarado na seção 5. Plano com as suas respostas: [`plano.md`](plano.md); medição de partida:
[`baseline.md`](baseline.md).

**Em uma frase:** -1.078 linhas no total (-3,0%), mas o código de produção caiu -1.704 (-6,4%);
o resto foi absorvido por +279 linhas de testes novos e +347 de docs do próprio refactor.

## 1. Linhas antes e depois

Método: `wc -l` nos arquivos rastreados pelo git, sem locks, binários e `.html` (detalhes no
[`baseline.md`](baseline.md)). O mesmo script mediu os dois lados (antes = worktree de `e5c6539`).
As medições do depois foram feitas antes de este resumo ser adicionado.

| | Antes | Depois | Diferença |
|---|---:|---:|---:|
| **Total** | 36.524 | 35.446 | **-1.078** (-3,0%) |
| Total sem `docs/refactor/` (não existia antes) | 36.524 | 35.099 | -1.425 (-3,9%) |
| Só código de produção (sem `docs/refactor/`, `tests/`, `frontend/src/__tests__/`) | 26.697 | 24.993 | **-1.704** (-6,4%) |
| Testes (`tests/` + `frontend/src/__tests__/`) | 9.827 | 10.106 | +279 |

"Produção" aqui inclui docs, README e Cypress (que saiu). Não é só `.py/.tsx`.

| Linguagem | Antes | Depois |
|---|---:|---:|
| Python | 17.939 | 17.330 |
| TSX | 7.973 | 8.132 |
| Markdown | 7.193 | 6.996 |
| TypeScript | 2.115 | 1.924 |
| Texto | 355 | 230 |
| JSON | 288 | 267 |
| YAML | 237 | 233 |
| CSS | 139 | 49 |
| Shell / TOML / JS | 285 | 285 |

TSX e Python-testes crescem por causa dos testes novos (login, hooks, otimizações), e não por código novo.

| Pasta | Antes | Depois |
|---|---:|---:|
| `tests` | 7.796 | 7.681 |
| `frontend/src/components` | 5.954 | 5.805 |
| `docs/superpowers` | 3.780 | 3.780 |
| `query` | 3.569 | 3.146 |
| `frontend/src/__tests__` | 2.031 | 2.425 |
| `avaliacao` | 2.411 | 2.396 |
| `scraper` | 2.096 | 2.094 |
| `docs` (raiz da pasta) | 1.751 | 1.682 |
| `frontend/src/lib` | 1.656 | 1.635 |
| (raiz do repo) | 1.207 | 951 |
| `auth` | 797 | 584 |
| `frontend/cypress` | 257 | 0 |
| `docs/Diagramas` | 313 | 230 |
| `docs/deploy` | 298 | 253 |
| `docs/refactor` | 0 | 347 |

Por lote (medido em cada commit): L1 código morto -168; L2 docs -850 (≈ -834 na conta do ledger);
L3 testes -122; L4 backend -63; L5 frontend -74; L6 login -75 em produção (+153 de testes);
L7 pulado; L8 decisões -560; L9 otimizações +273 (testes e código novos).

## 2. Testes, lint e build

Refeitos agora, no HEAD `0c21760`.

| Verificação | Baseline | Depois |
|---|---|---|
| Backend (`uv run pytest -q`) | 662 passed, 1 skipped (rastreados) | **682 passed, 1 skipped** rastreados (689 brutos − 7 do arquivo não rastreado) |
| Frontend (`npx jest`) | 190 passed, 23 suítes | **215 passed**, 29 suítes |
| `tsc --noEmit` | limpo | limpo |
| `eslint src` | 5 problemas pré-existentes | os mesmos 5 (4 erros `set-state-in-effect`, 1 aviso) |
| `next build` | ok, 13 rotas | ok, 13 rotas |
| Lint backend | não há | não há |
| E2E (Cypress) | existia, nunca rodado | removido (D1) |

O baseline usava `--deselect tests/test_api_stress.py`; o arquivo saiu, então o comando agora é só
`uv run pytest -q`. Saldo: backend +20 testes e frontend +25 (L1 removeu 8 testes por serem código morto ou redundantes, L8 removeu 3 da migração
do localStorage; as otimizações, o login, os hooks e o D14 acrescentaram os novos).

## 3. Os refactors mais relevantes

### 3.1 `with psycopg.connect` nos stores (L4, `c397edf`)
Por quê: 12 repetições de `connect / try / commit / finally close`; o `with` faz commit, rollback e close.

```python
# antes (auth/store.py)
conn = psycopg.connect(self.database_url)
try:
    with conn.cursor() as cur:
        cur.execute(_SELECT_BY_ID, (usuario_id,))
        row = cur.fetchone()
finally:
    conn.close()
```
```python
# depois
with psycopg.connect(self.database_url) as conn, conn.cursor() as cur:
    cur.execute(_SELECT_BY_ID, (usuario_id,))
    row = cur.fetchone()
```
Prova: testes de integração dos stores contra o Postgres local; OpenAPI idêntico byte a byte.

### 3.2 Exception handler para 503 e 404 (L4)
Por quê: o mesmo `try/except FiltroIndisponivel` em 4 rotas e o `except` que vira 404 em 3. Mesmo status e mesma mensagem.

```python
# antes (/query)
if filtro_store is None:
    raise filtro_indisponivel()
try:
    ids = await run_in_threadpool(filtro_store.elegiveis, ...)
except FiltroIndisponivel as exc:
    raise filtro_indisponivel() from exc
```
```python
# depois
app.add_exception_handler(FiltroIndisponivel, tratar_filtro_indisponivel)
...
if filtro_store is None:
    raise FiltroIndisponivel()
ids = await run_in_threadpool(filtro_store.elegiveis, ...)
```
A primeira versão checava o 503 antes da validação do corpo (422); a revisão pegou e corrigiu (`a69ab7e`), com teste.

### 3.3 `enviarJson` em `api.ts` (L5, `7186593`)
Por quê: o bloco `method + header JSON + stringify` estava escrito 14 vezes.

```ts
// antes
return request<ResultCard[]>("/query", {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify(body),
});
```
```ts
// depois
return enviarJson<ResultCard[]>("/query", "POST", body);
```

### 3.4 `useCopiar` (L5)
Por quê: "copiar e mostrar 'Copiado!' por 2 s" estava escrito 5 vezes em 3 arquivos.

```tsx
// antes
const [copiada, setCopiada] = useState(false);
onClick={() =>
  copiarTexto(respostaParaCopiar(frases, porNumero)).then(() => {
    setCopiada(true);
    setTimeout(() => setCopiada(false), 2000);
  })
}
```
```tsx
// depois
const [copiada, copiar] = useCopiar();
onClick={() => copiar(respostaParaCopiar(frases, porNumero))}
```

### 3.5 `AuthShell` e `CampoAuth` nas telas de login (L6, `2d61ece`)
Por quê: logo, cartão, campo com ícone (~330 caracteres de classe), olho da senha e caixa de erro repetidos em 4 telas.
O ganho foi menor que o estimado (seção 6), mas as classes agora têm uma fonte só.

```tsx
// antes: ~100 linhas por tela, como esta (um campo)
<label className="block mb-1.5 text-[#4A4A5A] dark:text-[#C4C4CE]" ...>E-mail</label>
<div className="relative">
  <Mail className="absolute left-3 top-1/2 ... " />
  <input type="email" ... className="w-full pl-9 pr-3 py-2.5 rounded-xl border ... (330 caracteres)" />
</div>
```
```tsx
// depois
<AuthShell titulo="JuriSight" subtitulo="Pesquisa contextual..." rodape={...}>
  <CampoAuth icone={Mail} rotulo="E-mail" type="email" ... />
```
Login 683 → 608 linhas. Como não havia teste, os 13 testes de login e cadastro foram escritos antes
(`a72d5bd`) e passaram no código antigo e no novo. Capturas antes/depois (12, claro/escuro/375 px): diferença zero de pixels.

### 3.6 `requer_postgres` no conftest e `tests/fakes.py` (L3, `008d71a`)
Por quê: `DATABASE_URL`, `_postgres_disponivel()` e o `skipif` estavam copiados em 6 arquivos; os fakes em 2 a 6.

```python
# antes (em cada *_integration.py)
DATABASE_URL = os.getenv("DATABASE_URL")
def _postgres_disponivel() -> bool: ...   # 10 linhas
pytestmark = pytest.mark.skipif(not _postgres_disponivel(), reason="...")
```
```python
# depois
from tests.conftest import DATABASE_URL, requer_postgres
pytestmark = requer_postgres
```
`FakeReranker`, `FakeDocRetriever`, `FakeOpenAI`, `documento_fake` e `usuario_fake` foram para `tests/fakes.py`. Coletados: 663 antes e depois.

### 3.7 `_UPSERT` gerado de `COLUNAS`, com teste de SQL idêntico (L8, D14, `e6c4517`)
Por quê: as 24 colunas apareciam 4 vezes, e uma coluna nova exigia editar 4 lugares. Este lote **aumentou** 49 linhas
por causa do teste. A coleta não tem testes; o seguro foi escrever antes um teste que guarda o SQL (espaços colapsados) e passa igual depois.

```python
# antes: tipo_documento = EXCLUDED.tipo_documento, ... (24 linhas) + 2 listas de colunas
# depois
COLUNAS = ("id_documento", "tipo_documento", ..., "scraped_at")
_ATUALIZACOES = ",\n    ".join(f"{c} = EXCLUDED.{c}" for c in COLUNAS[1:])
_UPSERT = f"""INSERT INTO documentos ({", ".join(COLUNAS)}) VALUES (...) ON CONFLICT ... DO UPDATE SET {_ATUALIZACOES};"""
```
`_CREATE_TABLE` ficou literal (leva o tipo de cada coluna). O plano recomendava não fazer; você aprovou.

### 3.8 Documentação de auth consolidada (L2, `8409b4d`)
`auth/DESIGN_NOTES.md`, `auth/SCHEMA.md` e `query/api/AUTH_ROUTES_DESIGN_NOTES.md` (422 linhas) viraram `auth/DESIGN.md` (126).
Os três descreviam a peça antes da integração ("não aplicado", "recuperação de senha fora de escopo"). Cada afirmação foi conferida no código
(Argon2 sem fallback bcrypt, `redefinicoes_senha` só com sha256, 503 quando o e-mail não está configurado). Também: Backup_Indices, runbook de deploy, README
(árvore real, Estrutura, Autenticação) e docstrings. A tabela de latência S0–S6, que a primeira passada apagou, foi restaurada em `docs/avaliacao` (`1fb9739`).

### 3.9 Remoção do Cypress (L8, D1, `76a883c`)
-285 linhas: specs escritos para o login falso ("qualquer credencial entra"), nunca rodados na CI, sem mexida desde `7b40068`.
Saíram `frontend/cypress/`, a config, 2 dependências, 3 scripts, `CYPRESS_INSTALL_BINARY` (CI e `frontend/Dockerfile`). A imagem do front foi reconstruída para provar.

## 4. Otimizações

Feitas (Lote 9, um commit cada, nenhuma muda resultado de busca):

| O quê | Onde | Efeito esperado |
|---|---|---|
| `ThreadPoolExecutor(8)` criado uma vez no `__init__` | `reranker.py` | não cria e destrói 8 threads por busca |
| `asyncio.gather` das duas conferências no acervo | `/enrich` em `app.py` | as duas consultas rodam juntas, não em sequência |
| `DocRetriever.fetch(ids, completo=False)` | `/query` | busca só as colunas do card e da ementa (as outras vêm `NULL`); `/document`, `/resposta` e `avaliacao/` seguem completos. Teste: `ResultCard` idêntico |
| Jev grava o lote em 1 conexão (autocommit) | `provimento_jev_db.py` | não abre uma conexão por acórdão |
| `useMemo` em `filteredResults`, `resumoTopo`, `idsCitacao` | `search-results-page.tsx` | não recalcula a cada render |
| `sem_acento` único para dispositivos e expressões | `query/filtros/` | menos código; mesma saída em 20 textos (acentos, cedilha, º ª, §) |
| Chave estável no `TagList` | `entity-review-page.tsx` | corrige bug de reuso de DOM (teste falha com `key={idx}`) |

Feitas nos lotes anteriores: conexão do `doc_source` agora fecha (era vazamento); `avaliacao/contexto` não carrega mais o FlashRank sem uso;
`run.sh` não baixa mais o `nomic-embed-text` (centenas de MB; os embeddings vêm da OpenAI).

Encontradas e **não feitas**:
- **NFKD no BM25 (`bm25_builder`), `provimento.py` e `html_extractor.py`:** unificar mudaria a normalização do índice e exigiria reindexar. Só as duas cópias NFD de `query/filtros/` foram unificadas.
- **`N_CANDIDATOS_COM_FILTRO`:** o plano mandava tirar; o filtro de período ainda usa o pool de 80, então ficou.
- **`DispositivoView` → `SugestaoDispositivo`, unir os requests de conversa, `_row_para_documento` com `zip`:** mudam nomes no OpenAPI ou pioram a explicação.
- Não medi ganhos de tempo: os efeitos acima são esperados pelo desenho, não benchmarkados.

## 5. Mudanças de comportamento

Todas, mesmo as pequenas:

1. **Salvos, data (bug corrigido):** `new Date("yyyy-mm-dd")` lia em UTC e mostrava o dia anterior no Brasil; data vazia mostrava "Invalid Date". Agora usa `formatarData` ("Data não informada" quando vazia). Teste em `America/Sao_Paulo`.
2. **Revisão:** sair da tela durante o salvamento (`addVersion`) não navega mais depois.
3. **Revisão e faixa livre:** `AbortController` opcional em `queryJurisprudencia`/`queryLivre`; sair da tela cancela a busca em andamento.
4. **Cypress removido** (D1) e **`tests/test_api_stress.py` removido** (D2, era script de carga com cookies e token no código, já expirados; o token continua no histórico do git).
5. **`requirements.txt` removido** (D3): Docker e CI usam uv; duplicava o `pyproject.toml` e já divergia.
6. **Migração do localStorage legado removida** (D8): quem ainda tem perfil ou salvos do formato antigo perde essa migração.
7. **Migrações legadas de `conversas` removidas** (D9): `ADD COLUMN versoes` e `DROP COLUMN` das 6 colunas do snapshot único.
8. **Testes de integração leem o `.env` pelo conftest.** Com `.env`, os 6 arquivos de integração rodam sempre; sem `DATABASE_URL`, todos pulam (o CI não tem `.env`, então igual). Antes, 20 deles rodavam por acaso, via `load_dotenv` de outros imports.
9. **Executor do reranker compartilhado:** buscas simultâneas dividem 8 threads (antes, 8 por busca). Menos custo por busca; sob muita concorrência, mais fila.
10. **Jev:** o lote usa uma conexão aberta o tempo todo; cada linha ainda é gravada na hora (autocommit).
11. **Docstring de `query/api/app.py`:** corrigida a atribuição de OpenAI. `/query/explicacao` só monta textos com o `query_builder`; só `/resposta` chama a OpenAI. Este é o único trecho de `app.py` que mudou no commit deste resumo.
12. Menores: `/filtros` com store ausente valida o pedido antes (422) e só então dá 503, como antes; `avaliacao/` não carrega mais o FlashRank; a linha do `nomic-embed-text` saiu do `run.sh`.

**O que não mudou:** endpoints e schemas (OpenAPI comparado byte a byte, igual salvo 1 docstring); tabelas e colunas; variáveis de ambiente;
CLIs (`scraper/run.py`, `indexing/run.py`, `query.filtros.preparar`, `provimento_jev_cli`); `pipeline/` (Dagster), Dockerfile, compose e CI (exceto o `--ignore` do stress e o `CYPRESS_INSTALL_BINARY`).

## 6. Riscos conhecidos e o que ficou de fora

**Decisões que você não aprovou** (ficam como estão): D4 HTML do inventário; D5 `docs/superpowers/` (3.780 linhas, o maior bloco restante);
D6 `.claude/skills/gauntlet-loop/`; D7 filtro de provimento/período no `/query`; D10 colunas de probabilidade em `avaliacao/`; D11 `Literal` em `provimento_routes`; D15 "avança o dia" no `orchestrator.py`.

**Lote 7 pulado** (molde de página e topbar): a topbar de home e guia tem outra cor, então exigiria uma flag de variante; o `<main>` igual só existe
em 5 pontos, e um componente `Pagina` daria saldo negativo. Não valia mexer em telas sem teste.

**Estimativas que não se confirmaram:** login -75 (estimado -230): as telas já eram enxutas, o ganho é a fonte única de classes; frontend L5 -74 (estimado -190): a auditoria superestimou.
O total aprovado era ≈ -2.330 (6,4%); o realizado foi -1.078 (3,0%) no total e -1.704 só em produção, porque o L9 e os testes de segurança (login, D14) somam linhas.
Os números do plano eram estimativas; os deste documento são medidos.

**Dívidas pequenas conhecidas (adiadas na revisão):**
- Os `<label>` de `CampoAuth` não têm `htmlFor`/`useId` (já era assim; follow-up de acessibilidade barato).
- A conexão do Jev fica aberta o lote inteiro: uma queda de rede falha as gravações seguintes (antes também abortava no primeiro erro).
- Os 8 threads do reranker são compartilhados entre buscas simultâneas.
- `TAG_TERMOS` repete cores de `BUSCA.termos.chip`; o snapshot de SQL do D14 exige editar o literal quando uma coluna muda de propósito.
- Linhas em branco sobrando em `tests/test_doc_retriever.py`.
- As medições do filtro restrito (tempos, disco, contagens) saíram do README e só existem no histórico do git.

**D9 na VPS: inferido, não lido.** O acesso à VPS estava bloqueado nesta sessão. Raciocínio: o banco local já estava migrado; a VPS foi restaurada
do dump local em 01/11, depois da migração de 04/10; a API rodava as migrações a cada subida. Para conferir antes da review:
`docker compose -f docker-compose.prod.yml exec postgres psql -U postgres -d jurisight -c "\d conversas"` deve mostrar a coluna `versoes` (jsonb)
e nenhuma de `estrutura`, `has_file`, `file_name`, `pdf_extraido`, `aviso`, `resultados`. Se aparecer alguma delas, a VPS ficou para trás e o deploy novo não a migra.

**RFC × código (a banca pode perguntar).** As RFCs dizem ChromaDB, `nomic-embed-text` local, `rank_bm25` e ordenação por hierarquia; o código usa Qdrant, embeddings da OpenAI,
`bm25s` e reranker cross-encoder, e tem o Jev e o filtro restrito, que não estão nas RFCs. **O RNF03 ("100% local") não vale mais:** cada consulta manda o texto
para a OpenAI gerar o embedding, e `/resposta` manda as ementas para gerar a resposta curta. O README ainda não diz que toda consulta faz 1 chamada de embedding (adiado).

**Fora do refactor:** `pyproject.toml` cita `interface*` (não existe) e omite `auth*`, `conversations*`, `pipeline*`, `utils*` (funciona porque tudo roda da raiz);
`deploy/puxar-backups.sh` tem o IP da VPS como padrão; 3 dos 5 erros de eslint têm correção simples.

**Fora do trabalho:** `avaliacao/planilha_coleta.py`, `tests/test_avaliacao_planilha_coleta.py` (+7 testes na contagem bruta) e o PDF do inventário continuam não rastreados e intocados.
