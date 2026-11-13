# Baseline do refactor — redução de linhas

Medido em 13/11/2026 na branch `refactor/reducao-linhas`, criada a partir de `main` em `e5c6539`.

## Como foi medido

- `cloc` não está instalado: contagem com `wc -l` (linhas físicas, inclui brancos e comentários)
  sobre os arquivos **rastreados pelo git** (`git ls-files`).
- Fora da conta: arquivos de lock gerados (`uv.lock`, `frontend/pnpm-lock.yaml` — 7.814 linhas),
  binários e exportações (PDFs, `.drawio`, `.svg`, `.png`) e o `.html` de um spec.
- Fora do projeto: `avaliacao/planilha_coleta.py` e `tests/test_avaliacao_planilha_coleta.py`
  estão no disco mas **não rastreados** (não foram criados neste trabalho); não entram em nada.
- O script da medição é o mesmo para o antes e o depois.

## Tamanho

| Linguagem | Arquivos | Linhas |
|---|---:|---:|
| Python | 129 | 17.939 |
| TSX | 72 | 7.973 |
| Markdown | 35 | 7.193 |
| TypeScript | 24 | 2.115 |
| Texto | 6 | 355 |
| JSON | 4 | 288 |
| YAML | 5 | 237 |
| Shell | 3 | 183 |
| CSS | 1 | 139 |
| TOML | 1 | 58 |
| JS | 3 | 44 |
| **Total** | 283 | **36.524** |

| Pasta | Linhas |
|---|---:|
| tests | 7.796 |
| frontend/src/components | 5.954 |
| docs/superpowers | 3.780 |
| query | 3.569 |
| avaliacao | 2.411 |
| scraper | 2.096 |
| frontend/src/__tests__ | 2.031 |
| docs | 1.751 |
| frontend/src/lib | 1.656 |
| (raiz) | 1.207 |
| indexing | 848 |
| auth | 797 |
| frontend/src/app | 321 |
| conversations | 317 |
| docs/Diagramas | 313 |
| docs/deploy | 298 |
| processing | 261 |
| frontend/cypress | 257 |
| docs/avaliacao | 197 |
| frontend | 195 |
| pipeline | 137 |
| .claude | 133 |
| utils | 107 |
| .github | 71 |
| deploy | 21 |

## Testes, lint e build

| Verificação | Comando | Resultado |
|---|---|---|
| Testes backend | `uv run pytest -q --deselect tests/test_api_stress.py` | **662 passed**, 1 skipped (669 com os 7 do arquivo não rastreado) |
| Testes frontend | `cd frontend && npx jest` | **190 passed** (23 suítes) |
| Tipos | `npx tsc --noEmit` | limpo |
| Lint frontend | `npx eslint src` | **5 problemas pré-existentes** (4 erros `set-state-in-effect` em `profile-tab`, `decision-detail-page`, `theme-toggle`, `saved`; 1 aviso em `api.test.ts`) |
| Lint backend | — | **não há linter configurado** (sem ruff/flake8 no `pyproject.toml`) |
| Build | `cd frontend && npx next build` | ok, 13 rotas |
| E2E | `frontend/cypress` | existe, não roda sem o app no ar; não rodado |

`tests/test_api_stress.py` fica de fora por exigir servidor no ar (como na CI).

## Áreas sem teste (mais cautela)

Heurística: nenhum arquivo de teste importa o módulo ou cita o nome do componente.

**Backend:** a coleta inteira (`scraper/db_writer.py`, `orchestrator.py`, `web_scraper.py`,
`doc_builder.py`, `html_extractor.py`, `session_minter.py`, `delta.py`), `utils/reclassify.py`,
`indexing/doc_source.py`, `auth/envio_email.py`, `query/search/resposta_cache.py`.

**Frontend (sem teste unitário):** `revisao/entity-review-page`, `decisao/decision-detail-page`,
`sidebar`, `home/home-page`, `home/search-input`, `login/*`, `configuracoes/profile-tab`,
`salvos/saved-page`, `resultados/resultado-card`, `app-shell`, `settings/theme-toggle` e
componentes pequenos de `ui/`. São as telas grandes: mudanças nelas só com verificação visual
ou do build.
