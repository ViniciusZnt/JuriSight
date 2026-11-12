# Normas num campo só, NR/Tema/SV filtráveis, tribunal e fase — plano de implementação

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deixar o advogado restringir a busca por tribunal e fase do processo, juntar os dois campos de norma da Revisão num só e tornar NRs, Temas e Súmulas vinculantes filtráveis.

**Architecture:**
- **Tribunal e fase:** vêm das colunas `documentos.tribunal` e `documentos.sigla_classe` e entram como condições extras do `FiltroStore` (elegíveis e contagem), com a lista de classes de cada fase num módulo só.
- **NR, Tema e SV:** viram códigos no formato do acervo (`nr_15`, `tema_1046`, `sv_4`), extraídos por regex do texto no `preparar` e gravados em `documento_dispositivo`. Daí em diante funcionam como qualquer dispositivo.
- **Front:** o bloco "Filtro restrito" da Revisão ganha tribunal e fase e passa a ter um campo único de normas, com chips que filtram (códigos) e chips "só busca livre" (`estrutura.normas`).

**Tech Stack:** FastAPI, psycopg 3, Postgres, Next.js 16 + Jest.

**Spec:** `docs/superpowers/specs/2026-11-13-filtros-normas-tribunal-fase-design.md`

## Global Constraints

- **Português:** código, comentários e textos de tela em português, no estilo dos vizinhos. Código mínimo: o Vinicius não quer abstração além do necessário. Nenhuma dependência nova.
- **"E" e "OU":** entre tipos de filtro vale "E"; entre os tribunais escolhidos vale "OU"; a fase é uma só.
- **Fases:**
  - Conhecimento = ROT, RORSum, RO, RemNecRO, RemNecTrab, AIRO;
  - Execução = AP, AIAP;
  - Outras = todo o resto, inclusive `sigla_classe` vazia ou nula.
- **Rótulos:** tribunal "TRT-4" (o valor gravado é o do acervo, "TRT4"); fases "Conhecimento", "Execução" e "Outras".
- **Códigos novos:**
  - `nr_<n>` com rótulo "NR-<n>";
  - `tema_<n>` com rótulo "Tema <n>";
  - `sv_<n>` com rótulo "Súmula Vinculante <n>".

  Súmula vinculante só quando o texto diz "vinculante" ou "SV" colado ao número.
- **`EstruturaArgumentativa`:** `tribunais: list[str] = []` e `fase: Literal["conhecimento","execucao","outras"] | None = None`. Os padrões vazios mantêm conversas antigas e a chave do cache da resposta (`exclude_defaults`) como estão.
- **Tribunal e fase sozinhos** já tornam a busca restrita.
- **Busca sem nenhum filtro restrito** continua igual à de hoje.
- **Desempenho:** contagem e elegíveis abaixo de 1 s.
- **Testes de integração:** `cd /home/vini/JuriSight && set -a && . ./.env && set +a && uv run pytest …`. Nunca imprimir o `.env`. O teste que roda `preparar` é opt-in (`JURISIGHT_TESTAR_PREPARO=1`).

## Review Focus

1. **Tribunal escolhido sem decisões que cumpram o resto:** contagem 0 e faixa vazia, sem erro (Task 1).
2. **"Súmula 4 do STF" não pode virar `sv_4`; "tema central" não pode virar Tema:** testes de extração (Task 4).
3. **Conversa antiga sem `tribunais` e `fase`:** valida e abre, e a chave do cache não muda (Task 1).
4. **Texto livre igual a um código** ("NR-15" digitado e Enter, sem escolher da lista): vira chip "só busca livre" e não filtra, conforme o spec (Task 3).
5. **Celular:** o seletor de tribunal com 25 itens não pode estourar a largura (Task 2, conferido no build e com classe `max-w-full`).

---

### Task 1: Backend — tribunal e fase como filtro restrito

**Files:**
- Create: `query/filtros/fases.py`
- Modify:
  - `query/filtros/store.py` (`_filtros`, `elegiveis`, `contar`, método novo `tribunais`)
  - `query/enrichment/schema.py`
  - `query/api/filtros_routes.py` (`ContagemRequest`, rota nova `GET /filtros/tribunais`)
  - `query/api/app.py` (portão do `/query`)
- Test:
  - `tests/test_filtros_fases.py`
  - `tests/test_filtros_store_integration.py`
  - `tests/test_filtros_routes.py`
  - `tests/test_api.py`

**Interfaces:**
- Produces:
  - `fases.py`: `Fase = Literal["conhecimento","execucao","outras"]`; `CLASSES: dict[str, tuple[str, ...]]` (só conhecimento e execução); `condicao_fase(fase: Fase) -> tuple[str, list]`, que devolve SQL sobre a coluna `x.sigla_classe` e os parâmetros. "Outras" é `x.sigla_classe IS NULL OR NOT (x.sigla_classe = ANY(%s))` com as duas listas juntas.
  - `FiltroStore.elegiveis(dispositivos, expressoes, tribunais: list[str] = [], fase: Fase | None = None) -> list[str]`; `contar(...)` com os mesmos dois parâmetros novos. `ContagemFiltros` não muda: o total combinado já considera tribunal e fase.
  - `FiltroStore.tribunais() -> list[tuple[str, int]]`, com tribunal e total, ordenado numericamente (TRT1, TRT2… TRT24, depois os demais).
  - `EstruturaArgumentativa.tribunais` e `.fase` (ver Global Constraints).
  - `tem_filtro_restrito(e: EstruturaArgumentativa) -> bool` em `query/filtros/fases.py`. Fica aqui para não criar mais um módulo; é usado pelo `/query`.
  - API:
    - `POST /filtros/contagem` aceita `tribunais: list[str]` (máximo 25) e `fase`;
    - `GET /filtros/tribunais` devolve `[{"tribunal": "TRT4", "rotulo": "TRT-4", "total": 4634}]`, exige login e não conta no limite diário;
    - o `/query` usa `tem_filtro_restrito` e repassa tribunais e fase ao `elegiveis`;
    - o `/query/livre` ignora os dois.

- [ ] **Step 1: Testes**
  - **`test_filtros_fases.py`:**
    - `condicao_fase("execucao")` cobre AP e AIAP;
    - "outras" exclui ROT e AP e inclui nulo;
    - `tem_filtro_restrito` é verdadeiro só com `tribunais=["TRT4"]` e só com `fase="execucao"`, e falso com a estrutura vazia.
  - **Integração (banco real):**
    - `elegiveis([], [], ["TRT4"], "conhecimento")`: todos os ids têm tribunal TRT4 e classe nas de conhecimento (conferir por SQL);
    - `contar([], [], ["TRT4"], None).total` é igual a `SELECT count(*) FROM documentos WHERE tribunal='TRT4'`;
    - `elegiveis(["art_10_adct"], [], ["TRT99"], None) == []`;
    - `tribunais()` traz TRT2 com 13.073.
  - **Rotas:**
    - `/filtros/tribunais` responde 200 com rótulo, 401 sem sessão e 503 sem store;
    - a contagem repassa tribunais e fase (fake);
    - mais de 25 tribunais dá 422.
  - **`test_api`:**
    - `/query` só com `{"tribunais":["TRT4"]}` chama `elegiveis` e marca as faixas como restritas;
    - uma estrutura antiga, sem os campos, valida;
    - `chave_da_resposta` de uma estrutura sem tribunal e fase é igual à de antes.
- [ ] **Step 2:** Rodar `uv run pytest tests/test_filtros_fases.py tests/test_filtros_routes.py tests/test_api.py -q` e a integração. Esperado: os testes novos falham.
- [ ] **Step 3:** Implementar. No SQL do store, juntar tribunal e fase com `EXISTS (SELECT 1 FROM public.documentos x WHERE x.id = d.id AND …)`.
- [ ] **Step 4:** `uv run pytest -q` (sem o `test_api_stress`) e a integração. Medir `contar([], [], ["TRT2"], None)` e `elegiveis` sozinho com TRT2 (13 mil ids), e anotar os tempos no relatório.
- [ ] **Step 5:** Commit: `"Filtro restrito por tribunal e fase do processo"`.

### Task 2: Front — tribunal e fase na Revisão e nos resultados

**Files:**
- Modify:
  - `frontend/src/lib/api.ts`
  - `frontend/src/components/revisao/filtro-restrito.tsx`
  - `frontend/src/components/revisao/entity-review-page.tsx`
  - `frontend/src/components/resultados/search-results-page.tsx` (itens do filtro passados ao `ParecerPesquisa` e grupos do `ResumoDecisoes`)
  - `frontend/src/lib/search-session.tsx` (completar `tribunais: []` e `fase: null` em versões antigas)
- Test:
  - `frontend/src/__tests__/components/filtro-restrito.test.tsx`
  - `frontend/src/__tests__/components/faixas-resultado.test.tsx`
  - `frontend/src/__tests__/lib/api.test.ts`

**Interfaces:**
- Consumes: as rotas da Task 1.
- Produces:
  - `EstruturaArgumentativa.tribunais: string[]`, `.fase: "conhecimento" | "execucao" | "outras" | null` (com `emptyEstrutura` atualizado);
  - `contarFiltros(f: { dispositivos: string[]; expressoes: string[]; tribunais: string[]; fase: Fase | null })`. A assinatura passa a ser um objeto; atualizar os dois chamadores;
  - `listarTribunais(): Promise<{ tribunal: string; rotulo: string; total: number }[]>`;
  - `temFiltroRestrito` passa a contar tribunais e fase;
  - `ROTULO_FASE: Record<Fase, string>` ("Conhecimento", "Execução", "Outras").

**Comportamento:**
- **Na Revisão (bloco Filtro restrito), abaixo das expressões:**
  - **Tribunal:** um botão "Todos os tribunais" que abre uma lista com os 25 e os totais, para escolher vários; cada escolhido vira chip "TRT-4" com o "×". Com nenhum escolhido, vale todos.
  - **Fase do processo:** controle segmentado Todas · Conhecimento · Execução · Outras, no estilo dos segmentos da barra de resultados.
  - **Contagem:** a contagem combinada considera os dois.
- **Nos resultados:** os itens do filtro no "Como esta busca foi feita" e os grupos do resumo incluem os rótulos dos tribunais e a fase. No resumo, ex.: grupo `{verbo: "do", itens: ["TRT-4"]}` (ou "dos", para mais de um) e `{verbo: "na fase de", itens: ["execução"]}`.

- [ ] **Step 1: Testes**
  - **Seleção:** escolher TRT-4 na lista cria o chip e chama `onChange({ tribunais: ["TRT4"] })`; o segmento "Execução" chama `onChange({ fase: "execucao" })`.
  - **Contagem:** `contarFiltros` recebe tribunais e fase.
  - **Validação:** `temFiltroRestrito({...vazia, fase: "execucao"})` é verdadeiro.
  - **Resultados:** com `tribunais: ["TRT4"]` e `fase: "execucao"`, o card mostra "TRT-4" e "Execução".
- [ ] **Step 2:** `cd frontend && npx jest` com os arquivos acima. Esperado: os testes novos falham.
- [ ] **Step 3:** Implementar.
- [ ] **Step 4:** `npx jest`, `npx tsc --noEmit` e `npx next build`. Esperado: tudo passa.
- [ ] **Step 5:** Commit: `"Revisão e resultados com tribunal e fase do processo"`.

### Task 3: Front — campo único "Normas e dispositivos"

**Files:**
- Modify: `frontend/src/components/revisao/filtro-restrito.tsx`, `frontend/src/components/revisao/entity-review-page.tsx` (sai o card "Outras normas")
- Test: `frontend/src/__tests__/components/filtro-restrito.test.tsx`

**Interfaces:**
- Produces: `FiltroRestrito` recebe também `normas: string[]` e o `onChange` aceita `normas`.

**Comportamento:**
- **Rótulo:** o campo passa a se chamar "Normas e dispositivos".
- **Da lista:** escolher uma opção do autocompletar continua criando um chip sólido (código, filtra).
- **Texto livre:** Enter com texto que não foi escolhido da lista vira chip contornado (borda tracejada) com a etiqueta "só busca livre" e entra em `normas`. Vale mesmo se o texto bater com um código (Review Focus 4).
- **Chips:** os dois tipos têm lápis e "×".
- **Card antigo:** sai da Revisão.
- **Explicação do bloco:** a frase passa a mencionar que normas "só busca livre" não filtram.

- [ ] **Step 1: Testes**
  - "NR 99" + Enter cria o chip "só busca livre" e chama `onChange({ normas: [...] })`;
  - escolher da lista continua criando o chip sólido;
  - remover um chip "só busca livre" atualiza `normas`;
  - a Revisão não tem mais o rótulo "Outras normas".
- [ ] **Step 2:** Rodar e ver os testes novos falharem.
- [ ] **Step 3:** Implementar. O antigo teste "texto sem escolher da lista não vira chip" muda de sentido e passa a esperar o chip "só busca livre".
- [ ] **Step 4:** `npx jest`, `tsc` e `next build`.
- [ ] **Step 5:** Commit: `"Normas e dispositivos num campo só"`.

### Task 4: Backend — NR, Tema e Súmula vinculante filtráveis

**Files:**
- Modify: `query/filtros/dispositivos.py`, `query/filtros/preparar.py`
- Test: `tests/test_filtros_dispositivos.py`, `tests/test_filtros_store_integration.py`

**Interfaces:**
- Produces:
  - `codigos_do_texto(texto: str) -> set[str]`, com os códigos `nr_<n>`, `tema_<n>` e `sv_<n>` citados no texto;
  - `rotulo`, `codigo_de_texto`, `tokens_da_busca`, `niveis` e `eh_dispositivo` passam a tratar os três formatos;
  - `preparar` grava esses códigos em `documento_dispositivo` (texto = ementa + fundamentação), além dos níveis de `referencia_legislativa`.

- [ ] **Step 1: Testes**

```python
@pytest.mark.parametrize("texto,esperado", [
    ("nos termos da NR-15, anexo 1", {"nr_15"}),
    ("conforme NR 16 e a Norma Regulamentadora nº 17", {"nr_16", "nr_17"}),
    ("NR 06 do MTE", {"nr_6"}),
    ("Tema 1046 da repercussão geral", {"tema_1046"}),
    ("tema nº 725 do STF", {"tema_725"}),
    ("o tema central do recurso", set()),
    ("Súmula Vinculante 4", {"sv_4"}), ("Súmula Vinculante nº 40", {"sv_40"}), ("SV 13", {"sv_13"}),
    ("Súmula 4 do STF e Súmula 85 do TST", set()),
    ("CNR 15 e NRA-2", set()),  # NR dentro de outra sigla
])
def test_codigos_do_texto(texto, esperado): assert codigos_do_texto(texto) == esperado

def test_rotulo_dos_codigos_novos():
    assert rotulo("nr_15") == "NR-15" and rotulo("tema_1046") == "Tema 1046" and rotulo("sv_4") == "Súmula Vinculante 4"

def test_conversao_e_busca_dos_codigos_novos():
    assert codigo_de_texto("NR-15") == "nr_15" and codigo_de_texto("Tema 1046") == "tema_1046" and codigo_de_texto("Súmula Vinculante 4") == "sv_4"
    assert codigo_de_texto("Súmula 4 do STF") != "sv_4"
    assert tokens_da_busca("nr 15") == ["nr", "15"]
    assert tokens_da_busca("súmula vinculante 4") == ["sv", "4"] and tokens_da_busca("vinculante 4") == ["sv", "4"]
    assert niveis("nr_15") == ["nr_15"] and eh_dispositivo("tema_1046")
```

  Integração, depois do preparo:
  - `sugerir("nr 15")[0].codigo == "nr_15"`, com total entre 2.500 e 3.500;
  - `sugerir("tema 1046")` traz `tema_1046`;
  - `elegiveis(["nr_15"], ["adicional de insalubridade"])` só traz ids cujo texto cita NR-15 (conferir por regex no SQL).
- [ ] **Step 2:** Rodar e ver os testes falharem.
- [ ] **Step 3:** Implementar. Rodar `uv run python -m query.filtros.preparar` no banco local, medir o tempo e registrar no relatório quanto a etapa de dispositivos passou a levar.
- [ ] **Step 4:** `uv run pytest -q` e a integração.
- [ ] **Step 5:** Commit: `"NR, Tema e Súmula vinculante extraídos do texto e filtráveis"`.

### Task 5: Verificação de ponta a ponta e README

**Files:** Modify `README.md` (seção "Filtro restrito": tribunal e fase, campo único, códigos novos e o tempo do preparo)

- [ ] **Step 1:** Com o banco local preparado, rodar em processo (como na verificação anterior: `FiltroStore` mais `buscar(documento_ids=…)`) e registrar:
  - **TRT-4 + Conhecimento:** os 20 cards da faixa restrita são do TRT4 e de classe de conhecimento;
  - **NR-15 + "adicional de insalubridade":** os 20 cards citam a NR-15 no texto;
  - **Tema 1046:** a faixa restrita não vem vazia;
  - **Sem filtro:** os mesmos ids da `main`;
  - **Latência:** `/query` só com TRT2, que tem mais de 13 mil ids.
- [ ] **Step 2:** Atualizar o README e fazer o commit: `"README: tribunal, fase e normas filtráveis"`.
- [ ] **Step 3** (controlador, depois do merge, com o Vinicius): rodar o `preparar` na VPS, fora do horário de uso, e conferir "nr 15" no autocompletar de produção.
