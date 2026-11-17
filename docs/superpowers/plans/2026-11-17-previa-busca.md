# Prévia da busca na Revisão — plano de implementação

> **Para agentes:** SUB-SKILL OBRIGATÓRIA: use superpowers:executing-plans. Os passos usam checkbox (`- [ ]`).

**Objetivo:** mostrar na Revisão o que a busca vai usar — os termos (BM25), a frase da busca semântica e o que é exigido — antes de buscar.

**Arquitetura:**
- `POST /query/explicacao` ganha os rótulos dos dispositivos.
- O componente `PreviaBusca` chama a rota com uma espera depois da edição e monta as três linhas.

**Stack:** FastAPI/pytest; React/Jest.

**Spec:** `docs/superpowers/specs/2026-11-17-previa-busca-design.md`

## Restrições globais

- Textos fixos:
  - "O que esta busca vai usar"
  - "Pelos termos"
  - "Pelo sentido"
  - "Exige"
  - "Nada é exigido: todo o acervo entra"
  - "Preencha a tese central ou o pedido principal para buscar"
- Espera de 400 ms após a última edição.
- Erro que não seja 422: o quadro some.

## Foco da revisão

1. **Resposta atrasada sobrescreve a mais nova:** uma edição rápida dispara duas chamadas, e a primeira chega por último. Esperado: vale só a última. → Task 2, `resposta atrasada de edição anterior é ignorada`.
2. **Estrutura vazia:** o servidor responde 422. Esperado: o aviso aparece e nada quebra. → Task 2, `sem tese nem pedido mostra o aviso`.
3. **Explicação fora do ar:** esperado: o quadro some e o botão de buscar continua funcionando. → Task 2, `erro esconde o quadro`.

---

### Task 1: `/query/explicacao` devolve os rótulos dos dispositivos

**Arquivos:**
- Modificar: `query/api/app.py` (`ExplicacaoResponse`, `query_explicacao`)
- Modificar: `frontend/src/lib/api.ts` (`ExplicacaoBusca`)
- Teste: `tests/test_api.py`

**Interfaces:**
- Produz: `ExplicacaoResponse.dispositivos: list[str]` (rótulos via `query.filtros.dispositivos.rotulo`, na ordem da estrutura); `ExplicacaoBusca.dispositivos: string[]` no front.

- [ ] **Passo 1: teste.** Em `test_query_explicacao_devolve_texto_semantico_e_termos`, a resposta passa a incluir `"dispositivos": ["ADCT art. 10, II, b"]`.
- [ ] **Passo 2: rodar e ver falhar.** `uv run pytest tests/test_api.py -q -k explicacao` → FAIL (campo ausente).
- [ ] **Passo 3: implementar** o campo na resposta e no tipo do front.
- [ ] **Passo 4: rodar e ver passar.** `uv run pytest -q` → PASS.
- [ ] **Passo 5: commit.** `git commit -m "Explicação da busca devolve os rótulos dos dispositivos exigidos"`

### Task 2: Componente `PreviaBusca` na Revisão

**Arquivos:**
- Criar: `frontend/src/components/revisao/previa-busca.tsx`
- Criar: `frontend/src/__tests__/components/previa-busca.test.tsx`
- Modificar: `frontend/src/components/revisao/entity-review-page.tsx` (render logo antes do bloco `{submitting && …}`)

**Interfaces:**
- Consome: `explicarBusca(estrutura) -> Promise<{ semantica: string; termos: string[]; dispositivos: string[] }>`; `rotuloTribunal`; `ROTULO_FASE`; `ApiError`.
- Produz: `export function PreviaBusca({ estrutura }: { estrutura: EstruturaArgumentativa })`.

- [ ] **Passo 1: testes** (fake timers; `explicarBusca` mockado):

```ts
test("mostra termos, sentido e o que é exigido")
// termos ["calor","NR-15"], semantica "Tese X", dispositivos ["CLT art. 192"], estrutura com tribunais ["TRT12"], fase "conhecimento"
// → "Pelos termos" com "calor" e "NR-15"; "Pelo sentido" com "Tese X"; "Exige" com "CLT art. 192", rotuloTribunal("TRT12"), "Conhecimento"
test("sem filtro diz que nada é exigido")
test("espera 400 ms depois da edição para chamar")    // rerender 2x em < 400 ms → 1 chamada, com a última estrutura
test("resposta atrasada de edição anterior é ignorada")
test("sem tese nem pedido mostra o aviso")            // rejeita ApiError(…, 422)
test("erro esconde o quadro")                          // rejeita ApiError(…, 500)
```

- [ ] **Passo 2: rodar e ver falhar.** `cd frontend && corepack pnpm test -- src/__tests__/components/previa-busca.test.tsx` → FAIL (módulo não existe).
- [ ] **Passo 3: implementar.**
  - A chave do efeito é `JSON.stringify(estrutura)`.
  - `setTimeout` de 400 ms; a limpeza do efeito invalida a resposta anterior.
  - Expressões: entre aspas.
  - Fase: `ROTULO_FASE[fase]`.
- [ ] **Passo 4: rodar e ver passar**, mais `corepack pnpm test` inteiro, `npx tsc --noEmit -p .` e `corepack pnpm lint`. A contagem do lint não pode subir de 5.
- [ ] **Passo 5: commit.** `git commit -m "Revisão: prévia do que a busca vai usar"`
