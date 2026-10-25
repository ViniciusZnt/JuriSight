# Schema `auth` — desenho e justificativa

Peça isolada: só o schema/tabela Postgres para contas de usuário. Nenhuma rota
FastAPI, hashing ou sessão é implementada aqui — isso é a peça seguinte.

## Por que um schema novo (`auth`), não `public`

`public` hoje é só `documentos` e `scraper_state` (scraper/db_writer.py) — dados
de jurisprudência coletados, tratados como fonte de verdade do pipeline de
scraping/indexação. Contas de usuário são um domínio completamente diferente
(cadastro/login, não coleta), então:

- **Zero risco de colisão/acidente.** Um `DROP TABLE`/reset de dev na área de
  contas (ex.: recriar `usuarios` do zero em teste) nunca pode encostar em
  `documentos`/`scraper_state`, e vice-versa — são namespaces diferentes.
- **Permissões futuras mais simples.** Se um dia o app quiser um role de DB
  com acesso só a credenciais (ou só a jurisprudência), `GRANT`/`REVOKE` por
  schema é direto; misturado em `public` isso exigiria grants tabela a tabela.
- **Nome `auth`** (em vez de `users`/`accounts`): é o nome mais imediatamente
  reconhecível para "tudo relacionado a autenticação" (padrão usado por várias
  stacks, ex. Supabase usa `auth.users`), e evita nomear o schema com uma
  palavra que colide com o nome de tabela mais óbvio (`user`/`users`).

## Por que a tabela se chama `usuarios` (não `users`)

O resto do projeto nomeia tabelas/colunas em português (`documentos`,
`tipo_documento`, `data_julgamento`, etc.) — o único nome em inglês existente é
`scraper_state`, que é infraestrutura interna, não um substantivo de domínio.
O enunciado desta peça já pediu as colunas em português (`nome`, `criado_em`),
então `auth.usuarios` mantém a tabela coerente com essa convenção de domínio.

## E-mail case-insensitive: `lower(email)` em vez de `citext`

Duas opções válidas; escolhi índice funcional sobre `citext`:

- **`citext`** exigiria `CREATE EXTENSION citext` no banco. Funciona no
  `postgres:16-alpine` do docker-compose (contrib vem compilado na imagem
  oficial), mas é uma dependência de infraestrutura nova que nada mais no
  projeto usa — a única coisa "extra" que `documentos` usa é
  `gen_random_uuid()`, que é função nativa do Postgres >= 13 (não extensão).
  Adicionar `citext` também impacta ferramentas de dump/restore, exige a
  extensão existir em qualquer ambiente (CI, prod) e é mais um passo de
  operação que pode falhar silenciosamente se o role não tiver permissão de
  criar extensões.
- **Índice único funcional em `lower(email)`** não precisa de extensão,
  funciona com qualquer role, e é explícito: qualquer leitura/escrita que
  precise ser case-insensitive faz `WHERE lower(email) = lower(%s)` (a mesma
  filosofia "SQL explícito, sem mágica" que `scraper/db_writer.py` já segue —
  psycopg puro, sem ORM). O trade-off é que esse `lower()` precisa ser
  lembrado em toda query de login/cadastro na peça seguinte (API); documentado
  aqui e no comentário acima do índice em `db.py` para não se perder.

A coluna `email` em si guarda o valor exatamente como o usuário digitou
(capitalização preservada, útil pra exibição/recibos), só a comparação/
unicidade é normalizada via o índice.

**Revisão pós-crítica:** o índice único em `lower(email)` sozinho não bloqueia
`" user@x.com"` vs `"user@x.com"` — são strings diferentes para `lower()`
também, então os dois passariam como "e-mails distintos", furando a garantia
de unicidade que o índice existe para dar (o cadastro futuro ainda deveria
normalizar/`strip()` antes do INSERT, mas o schema não pode depender disso).
Adicionado `CONSTRAINT usuarios_email_trimmed CHECK (email = btrim(email) AND
email <> '')` na `CREATE TABLE` — rejeita no banco, não só na aplicação.

## Colunas — o que entrou e por quê

| Coluna             | Motivo                                                              |
|--------------------|-----------------------------------------------------------------------|
| `id` UUID          | Mesmo padrão de `documentos.id` — PK opaca, `gen_random_uuid()`.       |
| `email`             | Identificador de login. `NOT NULL`; unicidade via índice (acima).     |
| `hashed_password`  | Nunca senha em texto puro. `TEXT` (hash bcrypt/argon2 cabe folgado).  |
| `nome`             | Nome de exibição — qualquer produto com login precisa disso na UI.     |
| `is_active`        | Flag mínima para desativar conta sem apagar histórico/FKs futuras (ex.: soft-disable em vez de DELETE, que é o padrão mais seguro para um recurso com potenciais dependentes). |
| `criado_em`        | Auditoria básica — quando a conta foi criada. Mesmo padrão de `documentos.created_at`. |
| `atualizado_em`    | Quando o registro mudou pela última vez (ex.: troca de senha/nome) — útil já de cara para invalidar sessões antigas na peça de auth futura. Atualizado pela aplicação, sem trigger — mesmo padrão de `scraper_state.updated_at`, que também é mantido manualmente pelo código, não por trigger de banco. |

## O que ficou deliberadamente de fora (e por quê)

- **`is_superuser` / roles.** JuriSight não tem hoje nenhuma noção de
  admin/permissões diferenciadas (é uma ferramenta de busca jurídica, não um
  painel multiusuário com papéis). Adicionar agora seria especular sobre um
  requisito que não existe; mais barato adicionar depois (`ALTER TABLE ...
  ADD COLUMN`, idempotente) quando a peça de autorização de fato precisar.
- **Verificação de e-mail (`email_verificado`, tokens).** Nenhuma peça deste
  gauntlet pediu fluxo de confirmação de e-mail; adicionar a coluna sem o
  fluxo ao redor é gold-plating morto.
- **Rate limiting / lockout (`tentativas_falhas`, `bloqueado_ate`).** Também
  fora de escopo desta peça — é uma decisão de política de segurança que
  pertence à peça de API/login, não ao schema base.
- **Tabela de sessões/refresh tokens.** Depende de decisão de arquitetura
  (JWT stateless vs. sessão em banco) que é da peça de API, não desta.
- **Trigger para `atualizado_em`.** O projeto não usa nenhuma trigger de
  banco hoje (mesmo `scraper_state` atualiza `updated_at` explicitamente na
  query); manter esse padrão evita introduzir uma ferramenta nova
  (trigger/function PL/pgSQL) só para esta tabela.

## Dependências

Nenhuma dependência Python nova — `psycopg[binary]` já está em
`pyproject.toml`. Nenhuma extensão Postgres nova (ver seção `citext` acima).

Uma observação não-bloqueante: `pyproject.toml` (`[tool.setuptools.packages.find]`)
lista explicitamente `scraper*, processing*, query*, indexing*, interface*` —
`auth*` não está nessa lista, então um `pip install -e .` empacotado não
incluiria este módulo. Isso não afeta o dev atual (todo o projeto roda via
`sys.path.insert` nos scripts `run.py`, não via instalação do pacote — `utils/`
já não está na lista nem é instalada). Se a peça de API optar por importar
`auth.db` via pacote instalado em vez de `sys.path`, `auth*` precisa ser
adicionado a essa lista — não fiz isso aqui porque a instrução desta peça foi
não tocar em arquivos existentes.

## Não executado

Este schema **não foi aplicado** ao Postgres rodando (`jurisight` em
`localhost:5432`) — só `auth/db.py` foi escrito e validado estaticamente
(`ast.parse`). Uma peça de integração futura decide quando chamar
`auth.db.ensure_schema()` (ex.: no `lifespan` da API de auth, no mesmo
espírito de `PostgresWriter.connect()` em `scraper/db_writer.py`).
