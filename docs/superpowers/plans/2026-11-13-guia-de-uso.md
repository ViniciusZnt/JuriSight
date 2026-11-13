# Guia de uso + cores das buscas — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Página `/guia` (didática, sequência vertical, mockup v5 com a paleta A), acesso pela tela inicial, e a paleta A aplicada no app (painel dos resultados, marquinhas dos cartões, Revisão).

**Architecture:** As cores das três buscas viram constantes num módulo só (`lib/cores-busca.ts`), usado pelo guia, pelo painel, pelos cartões e pela Revisão. O guia é um componente estático (`components/guia/guia-page.tsx`) numa rota do grupo `(app)`, com Tailwind + lucide-react e variantes `dark:`.

**Tech Stack:** Next.js (app router), React, Tailwind, lucide-react, jest + Testing Library.

**Spec:** `docs/superpowers/specs/2026-11-13-guia-de-uso-design.md`

## Global Constraints

- Paleta A: Filtro restrito `#1A3A5C`; Busca semântica `#6D4FC2`; Busca por termos `#0E8A80`. Sobre o marinho do painel, tons claros: semântica `#B6A5F0`, termos `#5FCFC4`.
- Nenhum `#6E8FB5` nem `#C47A2D` sobra em `frontend/src` (fora de testes).
- Nomes exatos: "Filtro restrito", "Busca semântica", "Busca por termos" (os do painel dos resultados).
- Números do acervo: 69.349 acórdãos; 96% julgados em 2025; abr/2024 → mai/2026; 25 tribunais; sem súmulas, OJs ou sentenças. 69.349 vem de uma constante única `TOTAL_ACERVO`.
- Textos do guia: os do mockup `.superpowers/brainstorm/39874-1794590503/content/guia-vertical-v5.html` (conteúdo e ordem), em pt-BR.
- Modo escuro como o resto do app; sem rolagem horizontal a 375 px.
- Front: `cd frontend && npx jest && npx tsc --noEmit && npx eslint src` (hoje 178 passed).

## Review Focus

1. Modo escuro: cada cor do guia tem par `dark:` legível (texto claro sobre fundo escuro). (verificação visual no Task 3, captura clara e escura)
2. Celular (375 px): a trilha, o funil e as grades de 2 colunas viram 1 coluna sem estourar. (captura a 375 px no Task 3)
3. Usuário não logado abrindo `/guia` → mesmo comportamento das outras páginas do grupo `(app)` (o layout já cuida; nada a fazer além de pôr a rota no grupo). (conferir no Task 2 que a rota está em `src/app/(app)/guia/`)
4. Leitor de tela: a trilha é uma lista ordenada (`<ol>`) e os ícones são decorativos (`aria-hidden`). (teste no Task 2)

---

### Task 1: Cores das buscas num lugar só, aplicadas no app

**Files:**
- Create: `frontend/src/lib/cores-busca.ts`
- Modify: `frontend/src/components/resultados/parecer-pesquisa.tsx` (TOTAL_ACERVO passa a vir do módulo novo; semântica/termos com as cores novas)
- Modify: `frontend/src/components/resultados/resultado-card.tsx:114` (marquinha de canal)
- Modify: `frontend/src/components/revisao/entity-review-page.tsx` (esquema `amber`/`green` dos chips de Fatos e Condutas → um esquema `termos` verde-água; `FieldLabel` ganha prop opcional `busca?: "termos" | "semantica"` que mostra uma etiqueta pequena "Busca por termos"/"Busca semântica"; Pedido, Fatos, Condutas = termos; Tese central = semântica)
- Test: `frontend/src/__tests__/components/parecer-pesquisa.test.tsx`, `frontend/src/__tests__/lib/cores-busca.test.ts` (novo)

**Interfaces (Produces):**
- `cores-busca.ts` exporta `TOTAL_ACERVO = 69349` e `BUSCA` com, para `filtro`, `semantica`, `termos`: `nome` (os três nomes exatos), `cor` (hex da paleta), `corSobreMarinho` (hex claro; filtro = `#FFFFFF`), e classes Tailwind prontas `chip` (fundo/borda/texto claro + `dark:`), `etiqueta` (para a etiqueta do FieldLabel). Classes escritas por extenso no arquivo (o Tailwind só gera classes que aparecem literalmente).

- [ ] **Step 1: Testes que falham** — `cores-busca.test.ts`: `BUSCA.semantica.cor === "#6D4FC2"`, `BUSCA.termos.cor === "#0E8A80"`, `BUSCA.filtro.cor === "#1A3A5C"`, nomes exatos, `TOTAL_ACERVO === 69349`. Em `parecer-pesquisa.test.tsx`: o marcador de "Busca semântica" tem a classe com `#B6A5F0` e o de "Busca por termos" `#5FCFC4` (via `container.querySelector` no span ao lado do texto).
- [ ] **Step 2: Rodar e ver falhar** — `npx jest cores-busca parecer-pesquisa`.
- [ ] **Step 3: Implementar** o módulo e trocar as cores nos três componentes; etiqueta no FieldLabel dos quatro campos.
- [ ] **Step 4: Verde** — `npx jest && npx tsc --noEmit && npx eslint src`; `grep -rn "6E8FB5\|C47A2D" src --include=*.tsx --include=*.ts | grep -v __tests__` → vazio.
- [ ] **Step 5: Commit** — `"Paleta das buscas: semântica violeta, termos verde-água, num módulo só"`.

### Task 2: Página `/guia` e acesso pela tela inicial

**Files:**
- Create: `frontend/src/components/guia/guia-page.tsx`, `frontend/src/app/(app)/guia/page.tsx`
- Modify: `frontend/src/components/home/home-page.tsx` (topo: botão "Como usar" à direita, ícone `BookOpen`, leva a `/guia`; sob o subtítulo: "Primeira vez? Veja como tirar o melhor da busca →" ligando a `/guia`)
- Test: `frontend/src/__tests__/components/guia-page.test.tsx` (novo)

**Interfaces:** Consumes `BUSCA`, `TOTAL_ACERVO` de `lib/cores-busca.ts` (Task 1). `GuiaPage()` sem props.

- [ ] **Step 1: Testes que falham** em `guia-page.test.tsx`:
  - renderiza o título "Como tirar o melhor do JuriSight" e "69.349";
  - a trilha é um `<ol>` com 7 `<li>` (Conte o caso … Limites desta versão);
  - os nomes "Busca semântica", "Busca por termos" e "Filtro restrito" aparecem;
  - o botão final leva a `/` (link com `href="/"`);
  - todo `svg` dentro da página tem `aria-hidden="true"`.
  E na tela inicial (teste existente da home, se houver; senão no mesmo arquivo renderizando `HomePage` com os mocks de roteador já usados nos testes): link "Como usar" com `href="/guia"`.
- [ ] **Step 2: Rodar e ver falhar.**
- [ ] **Step 3: Implementar** o guia fiel ao mockup v5 (estrutura, textos, ícones lucide equivalentes: BookOpen, Database, Calendar, Clock, Landmark, Ban, FileText, Upload, MessageSquare, ShieldCheck, Sparkles, PencilLine, Star, Target, List, Building2, Quote, Compass, Search, Check, X, Filter, Scale, Type, Layers, Hash, Route, ArrowDown, ArrowDownWideNarrow, ChartNoAxesColumn, Info, AlertTriangle, ArrowRight), cores só via `BUSCA`/marinho do app, variantes `dark:`, grades `grid-cols-1 sm:grid-cols-2`. Links com `next/link`.
- [ ] **Step 4: Verde** — suíte, tsc, eslint.
- [ ] **Step 5: Commit** — `"Guia de uso em /guia e acesso pela tela inicial"`.

### Task 3: Conferência visual e README

**Files:**
- Modify: `README.md` (seção curta "Guia de uso" com a rota e a paleta das buscas)

- [ ] **Step 1: Capturas** do `/guia` com o app rodando localmente (Playwright headless): claro a 1280 px, escuro a 1280 px, claro a 375 px; e da Revisão e do painel dos resultados com as cores novas. Expected: sem rolagem horizontal a 375 px; texto legível no escuro; mesma composição do mockup v5.
- [ ] **Step 2: Corrigir** o que as capturas mostrarem (cada correção com nova captura).
- [ ] **Step 3: README** e commit — `"README: guia de uso e cores das buscas"`.
