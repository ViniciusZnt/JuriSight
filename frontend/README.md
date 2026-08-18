# JuriSight — Frontend

Interface web do JuriSight (RFC §4). Next.js + React consumindo a API de busca híbrida.

## Stack

Next 16 (App Router), React 19, TypeScript, Tailwind 4, pnpm. Design system portado do export do Figma.

## Setup

```bash
pnpm install
pnpm dev      # http://localhost:3000
pnpm build    # build de produção
```

Scaffold original:

```bash
pnpm create next-app@latest frontend --ts --eslint --tailwind \
  --src-dir --app --no-turbopack --import-alias "@/*" --use-pnpm
pnpm add lucide-react clsx tailwind-merge class-variance-authority tw-animate-css
```

## Estrutura

- `src/app/(app)/` — telas **com** a sidebar fixa: home, `revisao`, `resultados`, `decisao/[id]`.
- `src/app/(auth)/` — `login`, **sem** a sidebar fixa.
- `src/components/` — `Sidebar`, `AppShell`.
- `src/lib/utils.ts` — `cn()`.

`(app)` e `(auth)` só agrupam as telas que compartilham (ou não) a sidebar; os parênteses não aparecem na URL (`/`, `/login`).

## Branches

Uma feature branch por tela, a partir de `frontend` (`feat/home`, `feat/login`, …). Telas atuais são placeholders.
