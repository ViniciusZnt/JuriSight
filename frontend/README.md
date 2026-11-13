# JuriSight — Frontend

Interface web do JuriSight (RFC §4): Next.js 16 (App Router), React 19, TypeScript,
Tailwind 4 e pnpm, consumindo a API de busca híbrida. Pré-requisitos, comandos de teste e a estrutura geral
do projeto estão no [README da raiz](../README.md).

```bash
pnpm install
pnpm dev      # http://localhost:3000
pnpm build    # build de produção
```

- `src/app/(app)/` — telas com a barra lateral; `src/app/(auth)/` — login, cadastro e
  redefinição de senha, sem ela. Os parênteses não aparecem na URL.
- `src/components/` — componentes por tela (`resultados`, `revisao`, `provimento`, `home`, ...).
- `src/lib/` — cliente da API (`api.ts`), tipos e funções puras de apresentação.
