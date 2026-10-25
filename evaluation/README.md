# Avaliação de KPIs

Mede os KPIs de recuperação da RFC (§1.6, Tabela 3) contra o índice real.

## O que é medido

| KPI | Meta | Precisa de rótulo? |
|-----|------|:---:|
| Precision@5 / @10 | ≥0.70 / ≥0.60 | **sim** |
| Latência por consulta | <30s (meta <15s) | não |
| Filtro por provimento | ≥0.90 | não |
| Citação com fonte real | 100% | não |
| Cobertura de tipos | 100% | não |

Faithfulness e Answer Relevance (RAGAS) **não** entram: o sistema é retrieval-only
(retorna documentos, não gera resposta). Ficam para quando existir a etapa de geração.

## Fluxo

1. **Ver os candidatos** de cada query para rotular:
   ```bash
   uv run python evaluation/run_eval.py --show
   ```
2. **Rotular** — em [golden.toml](golden.toml), preencha `relevantes` de cada query
   com os `documento_id` (UUID) que de fato ajudam a tese. Idealmente com a
   especialista. Query sem rótulo não entra no Precision@K (as demais métricas rodam).
3. **Rodar a avaliação**:
   ```bash
   uv run python evaluation/run_eval.py
   ```

Requer o ambiente de produção: `OPENAI_API_KEY` (embedding), ChromaDB indexado e
PostgreSQL (as vars do `.env`).

## Estrutura

- `metrics.py` — funções puras dos KPIs (testadas offline em `tests/test_evaluation.py`).
- `dataset.py` — carrega o `golden.toml`.
- `golden.toml` — as queries e seus rótulos de relevância.
- `run_eval.py` — roda a busca real e imprime o relatório vs. metas.
