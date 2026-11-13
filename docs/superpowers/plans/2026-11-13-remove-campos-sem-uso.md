# Remover setor, cargo e empresa_ciente — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Tirar de vez os campos `setor`, `cargo` e `empresa_ciente` (esquema, extração da IA, Revisão de Contexto).

**Architecture:** Remoção pura: o esquema pydantic perde os campos (chaves extras de conversas antigas são ignoradas), o prompt de extração deixa de pedi-los, o front deixa de tipá-los e mostrá-los.

**Tech Stack:** Python/pydantic, Next.js/TypeScript, pytest, jest.

**Spec:** `docs/superpowers/specs/2026-11-13-remove-campos-sem-uso-design.md`

## Global Constraints

- Nunca imprimir ou editar o `.env`. Backend: `set -a && . ./.env && set +a && uv run pytest -q --deselect tests/test_api_stress.py` (hoje 661 passed, 1 skipped). Front: `cd frontend && npx jest && npx tsc --noEmit` (hoje 178 passed).
- Conversas antigas (JSON com `setor`/`cargo`/`empresa_ciente`) continuam abrindo.
- Texto da decisão, onde citada: "removidos — não ajudam a achar jurisprudência; a ciência da empresa é questão de mérito, que o advogado avalia na decisão".
- pt-BR; mínimo.

## Review Focus

1. Estrutura antiga com os três campos chega ao backend (`/query`, `/filtros/contagem`, conversa salva) → validada sem erro, campos ignorados. (teste na Task 1)
2. O llama devolve os três campos mesmo sem pedir (modelo pequeno repete o few-shot antigo em cache) → ignorados, sem erro de validação. (coberto pelo mesmo teste: `model_validate` com chaves extras)
3. Front abre versão antiga de conversa com os campos → tela renderiza sem eles. (coberto pelo tsc + o tipo não ter os campos; sem teste novo)

---

### Task 1: Remover os três campos

**Files:**
- Modify: `query/enrichment/schema.py:31-33` (tirar os campos; docstring da classe ganha a linha da decisão)
- Modify: `query/enrichment/query_enrichment.py` (exemplo few-shot linhas ~31-45 e descrição ~62-64 e ~78)
- Modify: `query/enrichment/query_builder.py:22` (docstring: tirar a menção a setor/cargo)
- Modify: `frontend/src/lib/api.ts` (tipo `EstruturaArgumentativa` e valores padrão ~40-42, ~64-66)
- Modify: `frontend/src/components/revisao/entity-review-page.tsx:504-517` (a grade de 3 cards some inteira; o `BooleanToggle` sai se ficar sem uso)
- Modify: `README.md` (onde lista os campos da estrutura, se listar: tirar os três e pôr a linha da decisão)
- Test: `tests/test_query_enrichment.py`, `tests/test_query_builder.py`, `tests/test_avaliacao_geracao.py`, `frontend/src/__tests__/lib/api.test.ts`

- [ ] **Step 1: Teste que falha** em `tests/test_query_enrichment.py`:

```python
def test_estrutura_ignora_campos_removidos():
    e = EstruturaArgumentativa.model_validate(
        {"tese_central": "x", "setor": "metalurgia", "cargo": "operador", "empresa_ciente": True}
    )
    assert e.tese_central == "x"
    assert not hasattr(e, "setor") and not hasattr(e, "cargo") and not hasattr(e, "empresa_ciente")
    assert "setor" not in e.model_dump()
```

E: o JSON do schema enviado ao llama (`_SaidaLLM.model_json_schema()["properties"]`) não tem `setor`, `cargo` nem `empresa_ciente`.

- [ ] **Step 2: Rodar e ver falhar** — `uv run pytest tests/test_query_enrichment.py -q`.
- [ ] **Step 3: Remover** dos arquivos acima; ajustar os testes existentes que montam/asseram esses campos (tirar os campos das fixtures; `test_build_bm25_query_exclui_tese_central_e_setor_cargo` vira `..._exclui_tese_central`).
- [ ] **Step 4: Suítes verdes** — backend e front (comandos nas Global Constraints); `grep -rn "empresa_ciente\|\.setor\|\.cargo" query frontend/src --include=*.py --include=*.ts --include=*.tsx` → nada (fora de comentários de decisão).
- [ ] **Step 5: Commit** — `"Remove setor, cargo e empresa_ciente (não entravam na busca)"`.
