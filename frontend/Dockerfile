# Frontend do JuriSight (Next.js, saída standalone).
FROM node:22-slim AS build
RUN corepack enable
WORKDIR /app
COPY package.json pnpm-lock.yaml pnpm-workspace.yaml ./
# node_modules sem links simbólicos: com o layout padrão do pnpm, o standalone do Next perde
# dependências no rastreamento (ex.: @swc/helpers) e o server.js não sobe.
RUN pnpm install --frozen-lockfile --config.node-linker=hoisted
COPY . .
# O endereço da API entra no bundle do navegador na hora do build.
ARG NEXT_PUBLIC_API_URL
ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL
RUN pnpm build

FROM node:22-slim
ENV NODE_ENV=production PORT=3000 HOSTNAME=0.0.0.0
WORKDIR /app
COPY --from=build /app/.next/standalone ./
COPY --from=build /app/.next/static ./.next/static
COPY --from=build /app/public ./public
EXPOSE 3000
CMD ["node", "server.js"]
