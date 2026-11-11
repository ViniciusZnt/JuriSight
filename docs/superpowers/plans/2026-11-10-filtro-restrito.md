# Filtro restrito por dispositivos e expressões — plano de implementação

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Criar a busca com filtro restrito por dispositivos legais e expressões obrigatórias, com duas faixas na tela de resultados: a restrita aberta e a livre fechada.

**Architecture:**
- Um pacote novo, `query/filtros/`, com funções puras (códigos de dispositivo e montagem de `tsquery`) e um `FiltroStore` que consulta o Postgres: autocompletar, contagens e a lista de ids elegíveis.
- Um script idempotente, `python -m query.filtros.preparar`, monta a tabela de dispositivos e o índice de texto.
- O `/query` com filtro passa os ids elegíveis aos três canais da busca: Qdrant via `MatchAny` em `documento_id` e BM25 via máscara.
- A faixa livre vem de `/query/livre`, chamado só quando o advogado abre a faixa.

**Tech Stack:** FastAPI, psycopg 3, Postgres (extensão `unaccent`, índice GIN `tsvector`), Qdrant, bm25s, Next.js 16 + Jest.

**Spec:** `docs/superpowers/specs/2026-11-10-filtro-restrito-design.md`

## Global Constraints

- Código, comentários, mensagens e textos de tela em português, no estilo dos módulos vizinhos (docstrings com Input/Returns quando o módulo já usa).
- Nenhuma dependência Python ou npm nova. Usa só a extensão `unaccent` do Postgres (contrib, já disponível na imagem).
- Entre filtros vale sempre "E": a decisão precisa citar todos os dispositivos e conter todas as expressões.
- A faixa restrita mostra no máximo `N_RESULTS_FINAL` (20) cards, e nunca um card que não cumpre o filtro.
- `/filtros/*` e `/query/livre` exigem login (`get_current_user`) e não usam `limite_diario`.
- Metas: cada contagem e cada sugestão respondem em menos de 1 s; a busca com filtro leva no máximo cerca de 2 s a mais que a busca de hoje.
- Conversas salvas antes da mudança precisam continuar abrindo: campos novos têm padrão vazio, e card sem `faixa` vale como `"livre"`.
- Código mínimo. O Vinicius pediu explicitamente para não exagerar em abstrações.
- Nunca ler nem editar `.env` com segredos.

## Review Focus

1. **Expressão com maiúsculas e acentos** ("Indenização por Dano Moral Coletivo" ou "indenizacao por dano moral coletivo") deve trazer as mesmas decisões. É testado na Task 2 (unaccent no Python) e na Task 3 (integração).
2. **Expressão com caracteres especiais da `tsquery`** (`&`, `|`, `!`, `:`, `(`, `'`) ou só com conectivos ("de da") não pode gerar erro SQL. A expressão é ignorada (`None`), e a API responde normalmente. É testado na Task 2 e na Task 5.
3. **Código de dispositivo que não existe no acervo** enviado direto ao `/query` (chip antigo, conversa reaberta) vale como filtro com zero decisões: 200 com lista vazia, não 500. É testado na Task 5.
4. **Filtro sem preparo** (tabela `public.dispositivo` ausente): `/filtros/*` e `/query` com filtro respondem 503, com a mensagem de rodar o preparo; `/query` sem filtro funciona normalmente. É testado na Task 5.
5. **Conversa antiga:** uma estrutura sem `dispositivos`/`expressoes` e cards sem `faixa` abrem sem erro. É testado na Task 5 (backend) e na Task 7 (front).

---

## Arquivos

| Arquivo | Responsabilidade |
|---|---|
| `query/filtros/__init__.py` | pacote (vazio) |
| `query/filtros/dispositivos.py` | códigos do acervo ↔ texto: níveis, rótulo legível, conversão de texto, tokens do autocompletar |
| `query/filtros/expressoes.py` | expressão → `tsquery` com singular/plural, sem acento |
| `query/filtros/store.py` | `FiltroStore` (sugestões, contagem, elegíveis, existentes) e `preparar()` |
| `query/filtros/preparar.py` | CLI: `python -m query.filtros.preparar` |
| `query/api/filtros_routes.py` | `GET /filtros/dispositivos`, `POST /filtros/contagem` |
| `indexing/vector_store/qdrant_store.py` | `_build_filter` aceita lista → `MatchAny` |
| `indexing/lexical/bm25_builder.py` | `LoadedBM25.search(..., documento_ids=)` |
| `query/search/hybrid_search.py` | `search(..., documento_ids=)` repassa aos três canais |
| `query/search/pipeline.py` | `buscar(..., documento_ids=)` |
| `query/enrichment/schema.py` | `dispositivos`, `expressoes` |
| `query/enrichment/query_builder.py` | BM25 recebe rótulos dos dispositivos e as expressões |
| `query/search/result_formatter.py` | `ResultCard.faixa` |
| `query/api/app.py` | `/query` restrito, `/query/livre`, conversão das normas no `/enrich`, `FiltroStore` no lifespan |
| `frontend/src/lib/api.ts` | tipos e chamadas novas |
| `frontend/src/lib/search-session.tsx` | guarda `dispositivosIa` |
| `frontend/src/components/revisao/filtro-restrito.tsx` | campos "Dispositivos legais" e "Expressões obrigatórias" + contagem |
| `frontend/src/components/revisao/entity-review-page.tsx` | usa os campos novos; lápis nos chips |
| `frontend/src/components/resultados/search-results-page.tsx` | faixas restrita e livre |
| `README.md` | seção do filtro restrito e do preparo |

---

### Task 1: Códigos de dispositivo

**Files:**
- Create: `query/filtros/__init__.py`, `query/filtros/dispositivos.py`
- Test: `tests/test_filtros_dispositivos.py`

**Interfaces:**
- Produces:
  - `niveis(codigo: str) -> list[str]`: o próprio código e todos os níveis acima, do mais específico ao artigo, súmula, OJ, convenção ou lei. Lista vazia se não for dispositivo.
  - `eh_dispositivo(codigo: str) -> bool`
  - `rotulo(codigo: str) -> str`
  - `codigo_de_texto(texto: str) -> str | None`
  - `tokens_da_busca(texto: str) -> list[str]`

**Regras do formato do acervo** (`referencia_legislativa`):
- **Âncora:** o primeiro token entre `art`, `sumula`, `oj`, `convencao`, `lei`. Sem âncora, não é dispositivo (`trt9`, `adct`, `clt`).
- **Prefixos antes da âncora** são as unidades de detalhe: `prgf_<n>` e `prgf_unico` valem como uma unidade de dois tokens; `caput`, os incisos romanos (`i`, `ii`, `xxii`…) e as alíneas (uma letra) valem uma unidade cada.
- **Níveis:** tirar unidades da esquerda, uma por vez.

- [ ] **Step 1: Escrever os testes**

```python
import pytest
from query.filtros.dispositivos import niveis, eh_dispositivo, rotulo, codigo_de_texto, tokens_da_busca

@pytest.mark.parametrize("codigo,esperado", [
    ("b_ii_art_10_adct", ["b_ii_art_10_adct", "ii_art_10_adct", "art_10_adct"]),
    ("prgf_2_art_791_clt", ["prgf_2_art_791_clt", "art_791_clt"]),
    ("prgf_unico_art_456_clt", ["prgf_unico_art_456_clt", "art_456_clt"]),
    ("caput_art_60_clt", ["caput_art_60_clt", "art_60_clt"]),
    ("vi_sumula_85_tst", ["vi_sumula_85_tst", "sumula_85_tst"]),
    ("art_15_clt", ["art_15_clt"]),
    ("prgf_5_art_28_lei_8078_90", ["prgf_5_art_28_lei_8078_90", "art_28_lei_8078_90"]),
    ("trt9", []), ("adct", []),
])
def test_niveis(codigo, esperado):
    assert niveis(codigo) == esperado

def test_eh_dispositivo():
    assert eh_dispositivo("oj_394_sdi1_tst") and eh_dispositivo("lei_13467_17") and eh_dispositivo("convencao_155_oit")
    assert not eh_dispositivo("trt9") and not eh_dispositivo("clt")

@pytest.mark.parametrize("codigo,esperado", [
    ("art_15_clt", "CLT art. 15"),
    ("b_ii_art_10_adct", "ADCT art. 10, II, b"),
    ("prgf_2_art_791_clt", "CLT art. 791, § 2º"),
    ("prgf_unico_art_456_clt", "CLT art. 456, parágrafo único"),
    ("caput_art_60_clt", "CLT art. 60, caput"),
    ("art_186_ccb", "CC art. 186"),
    ("sumula_85_tst", "Súmula 85 do TST"),
    ("vi_sumula_85_tst", "Súmula 85 do TST, VI"),
    ("oj_394_sdi1_tst", "OJ 394 da SDI-1 do TST"),
    ("oj_394_tst", "OJ 394 do TST"),
    ("convencao_155_oit", "Convenção 155 da OIT"),
    ("lei_13467_17", "Lei 13.467/17"),
    ("art_28_lei_8078_90", "Lei 8.078/90 art. 28"),
    ("algo_estranho", "algo_estranho"),
])
def test_rotulo(codigo, esperado):
    assert rotulo(codigo) == esperado

@pytest.mark.parametrize("texto,esperado", [
    ("CLT art. 192", "art_192_clt"),
    ("art. 192 da CLT", "art_192_clt"),
    ("Art. 5º, V, da CF", "v_art_5_cf"),
    ("ADCT art. 10, II, b", "b_ii_art_10_adct"),
    ("CLT art. 791, § 2º", "prgf_2_art_791_clt"),
    ("CLT art. 456, parágrafo único", "prgf_unico_art_456_clt"),
    ("Súmula 85 do TST", "sumula_85_tst"),
    ("OJ 394 da SDI-1 do TST", "oj_394_sdi1_tst"),
    ("Lei 8.078/90, art. 28, § 5º", "prgf_5_art_28_lei_8078_90"),
    ("CC art. 186", "art_186_ccb"),
    ("art. 186", None),        # sem lei: não converte (spec: conversão conservadora)
    ("NR-15", None),
    ("", None),
])
def test_codigo_de_texto(texto, esperado):
    assert codigo_de_texto(texto) == esperado

def test_codigo_de_texto_e_rotulo_sao_inversos():
    for c in ["art_15_clt", "b_ii_art_10_adct", "prgf_2_art_791_clt", "sumula_85_tst", "oj_394_sdi1_tst"]:
        assert codigo_de_texto(rotulo(c)) == c

@pytest.mark.parametrize("texto,esperado", [
    ("clt 15", ["clt", "15"]),
    ("Art. 15 CLT", ["art", "15", "clt"]),
    ("§ 2º art 791", ["prgf", "2", "art", "791"]),
    ("Súmula 85", ["sumula", "85"]),
    ("lei 8.078/90", ["lei", "8078", "90"]),
    ("CC 186", ["ccb", "186"]),
])
def test_tokens_da_busca(texto, esperado):
    assert tokens_da_busca(texto) == esperado
```

- [ ] **Step 2:** Rodar `uv run pytest tests/test_filtros_dispositivos.py -q`. Esperado: FAIL (módulo não existe).
- [ ] **Step 3: Implementar `query/filtros/dispositivos.py`**
  - Siglas: `clt→CLT`, `cf→CF`, `adct→ADCT`, `cpc→CPC`, `ccb→CC`, `cp→CP`, `cdc→CDC`. As desconhecidas vão para maiúsculas.
  - Em `codigo_de_texto` e `tokens_da_busca`: tirar acento e normalizar `art.`/`artigo` → `art`, `§`/`parágrafo`/`paragrafo` → `prgf`, `súmula` → `sumula`, `º`/`ª` → nada, número com ponto (`8.078`) → sem ponto, `/` → separador, "CC" → `ccb`, "SDI-1" → `sdi1`.
  - `codigo_de_texto` só devolve código quando acha âncora e lei/órgão. Fora dos casos da tabela, devolve `None`.
- [ ] **Step 4:** Rodar o mesmo comando. Esperado: PASS.
- [ ] **Step 5:** Commit: `git add query/filtros tests/test_filtros_dispositivos.py && git commit -m "Códigos de dispositivo: níveis, rótulo e conversão de texto"`

---

### Task 2: Expressão → tsquery

**Files:**
- Create: `query/filtros/expressoes.py`
- Test: `tests/test_filtros_expressoes.py`

**Interfaces:**
- Produces:
  - `sem_acento(texto: str) -> str`: minúsculas, sem acento.
  - `variantes(palavra: str) -> list[str]`: ordenada, sem repetição.
  - `tsquery_da_expressao(expressao: str) -> str | None`: texto para `to_tsquery('simple', %s)`. `None` quando não sobra palavra útil.

**Regras de `variantes`** (palavra já sem acento):
- Conectivos (`de da do das dos e em por para a o no na ao`) → só a própria palavra.
- As regras específicas valem primeiro e substituem a genérica: `…ais`↔`…al`, `…eis`↔`…el`, `…oes`↔`…ao`, `…res|zes`↔`…r|z`.
- Genérica: terminada em `s` → também sem `s`; senão → também com `s`.

- [ ] **Step 1: Escrever os testes**

```python
from query.filtros.expressoes import sem_acento, variantes, tsquery_da_expressao

def test_sem_acento():
    assert sem_acento("Indenização POR Dano") == "indenizacao por dano"

def test_variantes():
    assert variantes("moral") == ["morais", "moral"]
    assert variantes("morais") == ["morais", "moral"]
    assert variantes("dano") == ["dano", "danos"]
    assert variantes("indenizacao") == ["indenizacao", "indenizacoes"]
    assert variantes("indenizacoes") == ["indenizacao", "indenizacoes"]
    assert variantes("trabalhadores") == ["trabalhador", "trabalhadores"]
    assert variantes("coletivos") == ["coletivo", "coletivos"]
    assert variantes("de") == ["de"]

def test_tsquery_frase_com_plural():
    assert tsquery_da_expressao("Dano Moral Coletivo") == "(dano | danos) <-> (morais | moral) <-> (coletivo | coletivos)"

def test_tsquery_mantem_conectivo_na_sequencia():
    assert tsquery_da_expressao("adicional de insalubridade") == "(adicionais | adicional) <-> de <-> (insalubridade | insalubridades)"

def test_tsquery_ignora_caracteres_especiais_e_vazio():
    assert tsquery_da_expressao("dano & moral | (coletivo)!") == tsquery_da_expressao("dano moral coletivo")
    assert tsquery_da_expressao("  ") is None
    assert tsquery_da_expressao("de da") is None   # só conectivos
    assert tsquery_da_expressao("':*") is None
```

- [ ] **Step 2:** `uv run pytest tests/test_filtros_expressoes.py -q`. Esperado: FAIL.
- [ ] **Step 3:** Implementar. As palavras são `re.findall(r"[a-z0-9]+", sem_acento(expr))`; cada palavra vira `(v1 | v2)` ou a palavra solta quando só há uma variante; o separador é ` <-> `. Se todas as palavras forem conectivos, devolver `None`.
- [ ] **Step 4:** Mesmo comando. Esperado: PASS.
- [ ] **Step 5:** Commit: `git commit -am "Expressão obrigatória vira tsquery com singular e plural"` (incluir o arquivo novo com `git add`).

---

### Task 3: FiltroStore e preparo do banco

**Files:**
- Create: `query/filtros/store.py`, `query/filtros/preparar.py`
- Test: `tests/test_filtros_store_integration.py` (pulado sem Postgres, no mesmo molde de `tests/test_uso_diario_integration.py`)

**Interfaces:**
- Consumes: `niveis`, `eh_dispositivo`, `rotulo`, `tokens_da_busca` (Task 1); `tsquery_da_expressao` (Task 2).
- Produces:
  - `class FiltroIndisponivel(Exception)`: o preparo não rodou.
  - `@dataclass SugestaoDispositivo(codigo: str, rotulo: str, total: int)`
  - `@dataclass ContagemFiltros(total: int, dispositivos: list[SugestaoDispositivo], expressoes: list[tuple[str, int]])`
  - `class FiltroStore(database_url)` com:
    - `sugerir(texto: str, limite: int = 10) -> list[SugestaoDispositivo]`
    - `contar(dispositivos: list[str], expressoes: list[str]) -> ContagemFiltros`
    - `elegiveis(dispositivos: list[str], expressoes: list[str]) -> list[str]` (UUIDs como str)
    - `existentes(codigos: list[str]) -> set[str]`
  - `preparar(database_url: str) -> None` (idempotente), também como CLI `python -m query.filtros.preparar`.

**O que `preparar` cria:**
- `CREATE EXTENSION IF NOT EXISTS unaccent`, e a função `public.jurisight_unaccent(text) RETURNS text IMMUTABLE` = `public.unaccent('public.unaccent', $1)`.
- `public.documento_dispositivo (documento_id uuid, codigo text, PRIMARY KEY (codigo, documento_id))`: para cada valor de `referencia_legislativa`, todos os `niveis()`. Preenchida em Python: lê `id, referencia_legislativa`, faz `COPY` ou `executemany` em lote. Recria com `TRUNCATE` + carga numa transação.
- `public.dispositivo (codigo text PRIMARY KEY, total int)`: `SELECT codigo, count(*) FROM documento_dispositivo GROUP BY codigo`.
- `CREATE INDEX IF NOT EXISTS documentos_texto_fts ON documentos USING gin (to_tsvector('simple', public.jurisight_unaccent(coalesce(ementa,'') || ' ' || coalesce(fundamentacao,''))))`. As consultas precisam usar exatamente essa expressão, ou o índice não é usado.
- No fim, imprimir quantos dispositivos e quantas linhas foram gravados.

**Consultas:**
- `sugerir`: com `t = tokens_da_busca(texto)`, todos os tokens menos o último precisam existir em `string_to_array(codigo, '_')` (`@>`), e o último é prefixo de algum token (`EXISTS (SELECT 1 FROM unnest(string_to_array(codigo,'_')) x WHERE x LIKE %s || '%%')`). Ordena por `total DESC` e limita. Texto vazio → `[]`.
- `elegiveis` e `contar.total`: `SELECT d.id FROM documentos d WHERE` + um `EXISTS (… documento_dispositivo … codigo = %s)` por dispositivo + um `to_tsvector(<expressão do índice>) @@ to_tsquery('simple', %s)` por expressão. Expressão com `tsquery` `None` é ignorada. Sem nenhum filtro válido → `[]` / `total=0`.
- `contar.dispositivos`: `total` vem de `public.dispositivo` (0 se não existir); `contar.expressoes`: `count(*)` por expressão.
- Tabela `public.dispositivo` ausente (`psycopg.errors.UndefinedTable`) → `FiltroIndisponivel`.

- [ ] **Step 1: Escrever os testes de integração**

Montar o próprio cenário num schema temporário não é viável, porque `preparar` usa `documentos`. Os testes rodam contra o banco real local (69 mil decisões) e conferem com SQL direto:

```python
def test_preparar_e_idempotente(store):
    preparar(DATABASE_URL); preparar(DATABASE_URL)   # não falha na segunda vez

def test_niveis_entram_na_tabela(store):
    # quem cita b_ii_art_10_adct também aparece em art_10_adct
    c = store.contar(["art_10_adct"], []).total
    assert c >= store.contar(["b_ii_art_10_adct"], []).total > 0

def test_sugerir_por_tokens_em_qualquer_ordem(store):
    a = [s.codigo for s in store.sugerir("clt 15")]
    b = [s.codigo for s in store.sugerir("15 clt")]
    assert "art_15_clt" in a and a == b
    assert len(store.sugerir("art", limite=10)) == 10
    assert store.sugerir("") == []

def test_sugerir_prefixo_no_ultimo_token(store):
    assert "art_15_clt" in [s.codigo for s in store.sugerir("clt art 1")]

def test_expressao_singular_plural_e_acento(store):
    a = store.contar([], ["dano moral coletivo"]).total
    b = store.contar([], ["Danos Morais Coletivos"]).total
    assert a == b and a >= 100      # banco local: 137 pela regex do design

def test_elegiveis_cumprem_todos_os_filtros(store):
    ids = store.elegiveis(["art_186_ccb"], ["dano moral coletivo"])
    assert 0 < len(ids) == store.contar(["art_186_ccb"], ["dano moral coletivo"]).total
    # conferência independente: todo id cita um nível de art_186_ccb e tem a frase no texto
    with psycopg.connect(DATABASE_URL) as conn:
        ruins = conn.execute(
            """SELECT count(*) FROM documentos WHERE id = ANY(%s::uuid[]) AND NOT (
                 EXISTS (SELECT 1 FROM unnest(referencia_legislativa) r WHERE r = 'art_186_ccb' OR r LIKE '%%\\_art_186_ccb')
                 AND coalesce(ementa,'') || ' ' || coalesce(fundamentacao,'') ~* 'danos? mora(l|is) coletivos?')""",
            (ids,)).fetchone()[0]
    assert ruins == 0

def test_codigo_inexistente_da_zero(store):
    assert store.elegiveis(["art_99999_clt"], []) == []

def test_existentes(store):
    assert store.existentes(["art_15_clt", "art_99999_clt"]) == {"art_15_clt"}
```

- [ ] **Step 2:** Rodar `uv run pytest tests/test_filtros_store_integration.py -q` com `DATABASE_URL` do Postgres local. Esperado: FAIL (módulo não existe).
- [ ] **Step 3:** Implementar `store.py` e `preparar.py`, e rodar `uv run python -m query.filtros.preparar` no banco local. Anotar no relatório quanto tempo levou e o tamanho do índice (`pg_size_pretty(pg_relation_size('documentos_texto_fts'))`).
- [ ] **Step 4:** Rodar os testes. Esperado: PASS. Medir `contar` e `sugerir` (precisam ficar abaixo de 1 s) e registrar no relatório.
- [ ] **Step 5:** Commit: `git add query/filtros tests/test_filtros_store_integration.py && git commit -m "FiltroStore: autocompletar, contagem e elegíveis no Postgres"`

---

### Task 4: Canais de busca restritos a uma lista de ids

**Files:**
- Modify: `indexing/vector_store/qdrant_store.py` (`_build_filter`), `indexing/lexical/bm25_builder.py` (`LoadedBM25.search`), `query/search/hybrid_search.py` (`HybridSearch.search`), `query/search/pipeline.py` (`buscar`)
- Test: `tests/test_hybrid_search.py`, `tests/test_bm25.py`, `tests/test_pipeline.py`, `tests/test_qdrant_provimento.py` (ou onde `_build_filter` já é testado)

**Interfaces:**
- Produces:
  - `_build_filter({"documento_id": [..]})` → `FieldCondition(key="documento_id", match=MatchAny(any=[..]))`. Valor escalar continua `MatchValue`.
  - `LoadedBM25.search(query, n=20, provimento=None, documento_ids: set[str] | None = None)`: máscara 1.0 nos chunks cujo `chunk_id.rsplit(":",1)[0]` está no conjunto, multiplicada pela de provimento; descarta score ≤ 0, como já faz com o provimento.
  - `HybridSearch.search(..., documento_ids: list[str] | None = None)`: põe a lista em `where["documento_id"]` e passa `documento_ids=set(...)` ao BM25 **só quando não é None**, como já é feito com o provimento (fakes e índices antigos não conhecem o kwarg).
  - `buscar(..., documento_ids: list[str] | None = None)`: com lista, usa o pool `N_CANDIDATOS_COM_FILTRO` e repassa ao `hybrid.search`. Lista vazia → devolve `[]` sem chamar a busca.

- [ ] **Step 1: Testes**
  - `test_build_filter_lista_vira_match_any`
  - `test_bm25_restringe_aos_documentos` (índice pequeno de teste: só chunks dos ids pedidos voltam, nenhum com score 0)
  - `test_bm25_ids_e_provimento_juntos`
  - `test_hybrid_repassa_ids_aos_tres_canais` (fakes de store e bm25 registram `where` e kwargs)
  - `test_hybrid_sem_ids_nao_passa_kwarg_ao_bm25`
  - `test_buscar_com_ids_usa_pool_com_filtro` (`hybrid.calls[0]["n_results"] == N_CANDIDATOS_COM_FILTRO` e ids repassados; o `_FakeHybrid` do arquivo ganha o kwarg `documento_ids=None`)
  - `test_buscar_com_lista_vazia_nao_busca`
- [ ] **Step 2:** `uv run pytest tests/test_hybrid_search.py tests/test_bm25.py tests/test_pipeline.py -q`. Esperado: os testes novos falham.
- [ ] **Step 3:** Implementar. O array de documento por chunk do BM25 é montado uma vez, na primeira busca com `documento_ids`, e guardado na instância.
- [ ] **Step 4:** `uv run pytest -q`. Esperado: tudo passa.
- [ ] **Step 5:** Commit: `"Busca híbrida restrita a uma lista de documentos"`

---

### Task 5: Schema, rotas e /query com faixas

**Files:**
- Modify: `query/enrichment/schema.py`, `query/enrichment/query_builder.py`, `query/search/result_formatter.py`, `query/api/app.py`
- Create: `query/api/filtros_routes.py`
- Test: `tests/test_api.py`, `tests/test_query_builder.py`, `tests/test_filtros_routes.py`

**Interfaces:**
- Consumes: `FiltroStore`, `FiltroIndisponivel`, `SugestaoDispositivo`, `ContagemFiltros` (Task 3); `codigo_de_texto`, `rotulo` (Task 1); `buscar(..., documento_ids=)` (Task 4).
- Produces:
  - `EstruturaArgumentativa.dispositivos: list[str] = []` (códigos) e `.expressoes: list[str] = []`.
  - `ResultCard.faixa: Literal["restrita", "livre"] = "livre"`.
  - `EnrichResponse.dispositivos_ia: list[str] = []`.
  - `get_filtro_store(request) -> FiltroStore | None` (em `app.state.filtro_store`).
  - Rotas:
    - `GET /filtros/dispositivos?q=` → `[{codigo, rotulo, total}]` (até 10);
    - `POST /filtros/contagem {dispositivos, expressoes}` → `{total, dispositivos: [{codigo, rotulo, total}], expressoes: [{texto, total}]}`;
    - `POST /query` (mesmo corpo de hoje);
    - `POST /query/livre` (mesmo corpo do `/query`).

**Comportamento:**
- **`build_bm25_query`:** acrescenta `rotulo(c)` de cada dispositivo e cada expressão aos termos de hoje.
- **`/query`:**
  - **Com filtro** (`estrutura.dispositivos or estrutura.expressoes`): pega `ids = store.elegiveis(...)`. Se vier vazio, devolve `[]`. Senão chama `buscar(..., documento_ids=ids)` e marca os cards com `faixa="restrita"`.
  - **Sem filtro:** igual a hoje, com cards `"livre"`.
  - **Erros:** store `None` ou `FiltroIndisponivel` com filtro → 503 `"Filtro restrito indisponível. Rode python -m query.filtros.preparar no servidor."`.
- **`/query/livre`:** só `get_current_user`, sem `limite_diario`. Roda `buscar` ignorando dispositivos e expressões (eles continuam só no texto do BM25), com os mesmos filtros de provimento e período, e cards `"livre"`.
- **`/enrich`:** depois de extrair, converte cada `normas[i]` com `codigo_de_texto`. Os códigos que existem (`store.existentes`) vão para `estrutura.dispositivos` e para `dispositivos_ia`, e saem de `normas`; o resto fica em `normas`. Se o store falhar, segue sem converter, com log de aviso.
- **`/filtros/*`:** 503 com a mesma mensagem quando o store está indisponível; 401 sem sessão.

- [ ] **Step 1: Testes** (os fakes de `tests/test_api.py` ganham um `_FakeFiltroStore` com `elegiveis`, `existentes`, `sugerir`, `contar` fixos)
  - `test_query_com_filtro_passa_elegiveis_e_marca_restrita`
  - `test_query_com_filtro_sem_elegiveis_devolve_lista_vazia_sem_buscar`
  - `test_query_com_codigo_inexistente_devolve_200_vazio` (Review Focus 3)
  - `test_query_com_filtro_sem_store_503` e `test_query_sem_filtro_sem_store_funciona` (Review Focus 4)
  - `test_query_livre_ignora_filtro_e_nao_consome_limite` (com `UsoDiario` fake contando chamadas)
  - `test_query_livre_sem_sessao_401`
  - `test_enrich_converte_normas_existentes_em_dispositivos` ("CLT art. 192" existe → `dispositivos == ["art_192_clt"]`, `dispositivos_ia` igual, `normas` sem ele; "NR-15" fica em `normas`)
  - `test_estrutura_e_card_antigos_validam` (JSON sem `dispositivos`/`expressoes`/`faixa` → defaults) (Review Focus 5)
  - `test_filtros_contagem_expressao_so_com_simbolos_nao_quebra` (Review Focus 2: `"&|!"` → 200)
  - `test_filtros_sugestoes_401_sem_sessao`, `test_filtros_503_sem_store`
  - `test_bm25_query_inclui_rotulos_e_expressoes`
- [ ] **Step 2:** `uv run pytest tests/test_api.py tests/test_filtros_routes.py tests/test_query_builder.py -q`. Esperado: os novos falham.
- [ ] **Step 3:** Implementar. O `FiltroStore` é criado no lifespan como os outros stores, sem rodar o preparo; o preparo é só o CLI.
- [ ] **Step 4:** `uv run pytest -q`. Esperado: tudo passa.
- [ ] **Step 5:** Commit: `"API do filtro restrito: /filtros, /query com faixas e /query/livre"`

---

### Task 6: Front — Revisão de Contexto

**Files:**
- Modify: `frontend/src/lib/api.ts`, `frontend/src/lib/search-session.tsx`, `frontend/src/components/revisao/entity-review-page.tsx`
- Create: `frontend/src/components/revisao/filtro-restrito.tsx`
- Test: `frontend/src/__tests__/components/filtro-restrito.test.tsx`, `frontend/src/__tests__/lib/api.test.ts`

**Interfaces:**
- Consumes: as rotas da Task 5.
- Produces (`api.ts`):
  - `EstruturaArgumentativa` ganha `dispositivos: string[]` e `expressoes: string[]`; `emptyEstrutura()` traz os dois vazios. Ao ler uma estrutura salva sem eles, completar com `[]`, no mesmo lugar onde a conversa é carregada.
  - `ResultCard.faixa?: "restrita" | "livre"`.
  - `EnrichResponse.dispositivos_ia?: string[]`.
  - `interface SugestaoDispositivo { codigo: string; rotulo: string; total: number }`.
  - `interface ContagemFiltros { total: number; dispositivos: SugestaoDispositivo[]; expressoes: { texto: string; total: number }[] }`.
  - `sugerirDispositivos(q: string): Promise<SugestaoDispositivo[]>`.
  - `contarFiltros(dispositivos: string[], expressoes: string[]): Promise<ContagemFiltros>`.
  - `queryLivre(body: QueryRequestBody): Promise<ResultCard[]>`.
  - `temFiltroRestrito(e: EstruturaArgumentativa): boolean` (dispositivos ou expressões não vazios).
- Produces (session): `dispositivosIa: string[]`, preenchido a partir de `EnrichResponse.dispositivos_ia` e zerado numa nova consulta.
- Produces (componente):

  ```tsx
  FiltroRestrito({ dispositivos, expressoes, dispositivosIa, onChange }: {
    dispositivos: string[]; expressoes: string[]; dispositivosIa: string[];
    onChange: (patch: { dispositivos?: string[]; expressoes?: string[] }) => void })
  ```

**Comportamento:**
- **Bloco de filtros:** um bloco com o título "Filtro restrito" e a frase: "Só entram decisões que citam todos os dispositivos e contêm todas as expressões. Os outros campos orientam a busca livre."
- **Campo "Dispositivos legais":**
  - o input dispara `sugerirDispositivos` com debounce de ~250 ms;
  - a lista mostra `rotulo · N decisões`, e escolher uma opção adiciona o código;
  - o chip mostra o rótulo, que vem de `contarFiltros().dispositivos`, ou o código enquanto o rótulo não chega;
  - chips com código em `dispositivosIa` levam o selo "sugestão da IA";
  - texto digitado sem escolher da lista não vira chip.
- **Campo "Expressões obrigatórias":** Enter adiciona; cada chip mostra `· N decisões` (de `contarFiltros().expressoes`).
- **Contagem combinada:** a linha "Com todos os filtros: N decisões" é atualizada com debounce a cada mudança. Com N = 0, aparece o aviso: "Nenhuma decisão do acervo cumpre todos os filtros. A faixa restrita virá vazia." Se der erro (503), mostra "Filtro restrito indisponível no momento" e não trava o botão de buscar.
- **"Normas jurídicas":** continua existindo para o que não converteu, com a descrição "Texto livre para a busca livre (não filtra)".
- **Lápis:** o `TagList` ganha um botão com o ícone `Pencil` em cada chip (`aria-label="Editar <item>"`), visível sem hover, que abre a mesma edição do duplo clique.

- [ ] **Step 1: Testes** (mockando `@/lib/api`)
  - `sugere e adiciona o código escolhido, mostrando o rótulo`
  - `texto sem escolher da lista não vira chip`
  - `chip de dispositivo da IA mostra "sugestão da IA"`
  - `expressão adicionada com Enter mostra a contagem`
  - `contagem zero mostra o aviso de faixa vazia`
  - `erro na contagem mostra indisponível sem quebrar`
  - em `api.test.ts`: `temFiltroRestrito` e `emptyEstrutura` com os campos novos
- [ ] **Step 2:** `cd frontend && npx jest src/__tests__/components/filtro-restrito.test.tsx src/__tests__/lib/api.test.ts`. Esperado: FAIL.
- [ ] **Step 3:** Implementar e ligar na `EntityReviewPage` (logo abaixo de "Pedido principal"). Também `entidadesConfirmadas` passa a contar dispositivos e expressões.
- [ ] **Step 4:** `npx jest` e `npx next build`. Esperado: tudo passa.
- [ ] **Step 5:** Commit: `"Revisão de Contexto: filtro restrito com autocompletar e contagem; lápis nos chips"`

---

### Task 7: Front — faixas na tela de resultados

**Files:**
- Modify: `frontend/src/components/resultados/search-results-page.tsx`
- Create: `frontend/src/components/resultados/faixa-livre.tsx` (se o card for extraído, `resultado-card.tsx`)
- Test: `frontend/src/__tests__/components/faixas-resultado.test.tsx`

**Interfaces:**
- Consumes: `temFiltroRestrito`, `contarFiltros`, `queryLivre` (Task 6).

**Comportamento:**
- **Sem filtro restrito:** a tela fica como hoje, mais uma linha discreta: "Busca só semântica. Para restringir, informe dispositivos ou expressões na Revisão de Contexto."
- **Com filtro restrito:**
  - **Faixa "Filtro restrito":** o banner de resumo vira o cabeçalho dela: "N decisões citam CLT art. X e contêm 'Y'", com `N = contarFiltros().total` e os rótulos de `contarFiltros().dispositivos`. Os cards de `resultados` aparecem como hoje.
  - **Faixa restrita vazia:** "Nenhuma decisão do acervo (≈70 mil acórdãos de 2025) cita … e contém …". A resposta gerada não é pedida, e o lugar dela mostra "Sem decisões no filtro restrito, a resposta não é gerada."
  - **Faixa "Busca livre (semântica)":** vem fechada, com um botão que abre e fecha. Na primeira abertura, chama `queryLivre` com a mesma estrutura e os mesmos filtros de provimento e período da versão. Depois remove os ids que já estão na faixa restrita e mostra os cards com o mesmo visual dos cards da faixa restrita. Os cards da faixa livre não entram em `resultados`, não são salvos na conversa e não alimentam a resposta gerada.
  - Abaixo do título da faixa livre: "Decisões parecidas, sem garantia de citar os dispositivos ou conter as expressões."
- **Resposta gerada:** usa só `resultados`, que já são da faixa restrita quando há filtro. O `useRespostaGerada` já não chama com lista vazia; basta mostrar o texto acima no lugar.
- **Conversa antiga** (cards sem `faixa`, estrutura sem os campos novos): abre como hoje, sem faixas.

- [ ] **Step 1: Testes** (mockando `@/lib/api` e a sessão)
  - `sem filtro mostra a lista sem faixas e a dica`
  - `com filtro mostra a contagem no cabeçalho da faixa restrita`
  - `faixa livre começa fechada e só chama queryLivre ao abrir`
  - `faixa livre remove os ids que já estão na restrita`
  - `faixa restrita vazia mostra o aviso com o acervo e não pede resposta`
- [ ] **Step 2:** `npx jest src/__tests__/components/faixas-resultado.test.tsx`. Esperado: FAIL.
- [ ] **Step 3:** Implementar. Extrair o JSX do card de `search-results-page.tsx` para um componente reaproveitado pelas duas faixas é o caminho esperado.
- [ ] **Step 4:** `npx jest` e `npx next build`. Esperado: tudo passa.
- [ ] **Step 5:** Commit: `"Resultados em duas faixas: filtro restrito e busca livre sob demanda"`

---

### Task 8: Verificação de ponta a ponta, README e deploy

**Files:**
- Modify: `README.md` (seção "Filtro restrito": o que faz, como rodar `python -m query.filtros.preparar`, quanto tempo leva e quanto espaço ocupa)

- [ ] **Step 1:** Com a API local e o preparo feito, rodar os casos do spec via HTTP (sessão de teste) e registrar o resultado no relatório:
  - **Dano moral coletivo:** expressão "dano moral coletivo" → todos os cards da faixa restrita contêm a frase no singular ou no plural (conferir com regex sobre ementa + fundamentação) e `contar().total` bate com `SELECT count(*) … ~* 'danos? mora(l|is) coletivos?'` dentro de ±2. Diferenças de acento e quebra de linha são esperadas; explicar se houver.
  - **Gestante:** `["b_ii_art_10_adct"]` → todos citam o código; `["art_10_adct"]` → total ≥ o anterior.
  - **Sem filtro:** a mesma lista de ids de antes da mudança (comparar com `git stash` ou com a `main`).
  - **Latência:** medir `/query` sem filtro, com "dano moral coletivo" e com `["art_791_clt"]` (cerca de 11 mil ids), 3 vezes cada. Se o caso CLT 791 passar de +2 s sobre o sem filtro, anotar como pendência (o spec prevê gravar `dispositivos` no payload nesse caso) e **não** implementar agora.
- [ ] **Step 2:** Atualizar o README e fazer o commit: `"README: filtro restrito e preparo do banco"`.
- [ ] **Step 3:** Deploy na VPS, feito pelo controlador junto com o Vinicius, não pelo subagente:
  - depois do merge, conferir o disco com `df -h`, porque o índice de texto ocupa algumas centenas de MB;
  - rodar `docker compose -f docker-compose.prod.yml exec api python -m query.filtros.preparar`;
  - testar os mesmos três casos em produção.

  O SSH usa o agente com a chave do Vinicius: pedir `ssh-add` antes. Nunca pedir senha.
