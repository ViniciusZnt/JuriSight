# Autenticação — decisões de design

Cobre `auth/` (senha, JWT, schema, store) e `query/api/auth_routes.py` (endpoints).
`auth/` não conhece HTTP: é importável e testável sem FastAPI. A camada HTTP
fica toda em `query/api/auth_routes.py`, o único módulo que conhece as duas pontas.

## Endpoints

`POST /auth/registro`, `/login`, `/logout`, `/esqueci-senha`, `/redefinir-senha`;
`GET /auth/me`; `PATCH /auth/me/perfil`. A dependency `get_current_user` serve
a qualquer rota que exija usuário autenticado. O router é incluído em
`query/api/app.py`, onde o `lifespan` também chama `auth.db.ensure_schema()`.

## Senha: Argon2id

`auth/password.py` usa só Argon2id (`pwdlib`), o KDF memory-hard recomendado
pela OWASP, muito mais caro de atacar em GPU/ASIC que bcrypt ou PBKDF2.

- `verify_password` devolve `PasswordVerification(ok, novo_hash)`. `novo_hash`
  não é `None` quando o hash guardado usa parâmetros desatualizados, e o login
  grava o novo (rehash ao verificar). `__bool__` levanta `TypeError` de
  propósito: uma tupla não vazia é sempre verdadeira, e `if verify_password(...)`
  autenticaria qualquer senha.
- `DUMMY_HASH` é um hash Argon2id de uma senha descartada, calculado ao
  importar o módulo (não é string fixa, para o custo acompanhar os parâmetros
  da lib). O login o verifica quando o e-mail não existe, para que "usuário
  inexistente" e "senha errada" demorem o mesmo e o tempo não revele quais
  e-mails estão cadastrados.

## JWT: HS256, sem valor padrão para a chave

HS256 em vez de RS256 porque um único backend emite e valida os próprios
tokens. Chave assimétrica só compensa quando outro serviço, sem a chave
privada, precisa validar.

- `JWT_SECRET_KEY` vem só do ambiente. Sem ela, `create_access_token` e
  `decode_access_token` levantam `MissingSecretKeyError`. Um padrão como
  `"changeme"` deixaria qualquer pessoa que lê o código forjar tokens.
- Expiração de 30 minutos (`DEFAULT_EXPIRES_DELTA`): token de vida curta limita
  o estrago de um vazamento. Não há refresh token.
- `decode_access_token` não engole as exceções do `jwt`; `get_current_user` as
  converte em 401. `MissingSecretKeyError` sobe como 500 de propósito, porque é
  erro de deploy, não do cliente.

## Cookie httpOnly em vez de token no corpo

O template de referência (`tiangolo/full-stack-fastapi-template`) devolve o JWT
no corpo para o frontend guardar em `localStorage`, onde qualquer JavaScript da
página o lê (um XSS rouba todas as sessões). Aqui o token só existe como cookie
`jurisight_access_token` `HttpOnly`. Isso não elimina o XSS, que ainda faz
requisições autenticadas a partir da página, mas impede a exfiltração do token.
`/auth/login` e `/auth/me` devolvem só os campos públicos do usuário.

- **`Secure`**: controlado por `COOKIE_SECURE`, ligado por padrão. Só `false`
  desliga, e só o dev local em HTTP (e `tests/conftest.py`) faz isso. Esquecer a
  variável no deploy não pode deixar o cookie sem a flag.
- **`SameSite=Lax`**: frontend (`:3000`) e backend (`:8000`) são portas
  diferentes do mesmo host. `SameSite` ignora a porta, então a requisição é
  same-site e o cookie segue em `fetch` com `credentials: "include"`. `Lax`
  ainda barra o cookie em navegação cross-site de terceiros (CSRF) sem exigir
  `Secure`, ao contrário de `None`. Se frontend e backend passarem a ter domínios
  registráveis diferentes, vira `SameSite=None; Secure`. O CORS usa origens
  explícitas (`CORS_ORIGINS`) com `allow_credentials=True`, e o app não sobe com
  `*` nesse caso.
- **`Max-Age`**: derivado do mesmo `DEFAULT_EXPIRES_DELTA` do JWT, para cookie e
  token nunca dessincronizarem.

## Login em JSON, não em formulário OAuth2

`POST /auth/login` recebe `{"email", "password"}` em JSON, como os demais POST do
app. O formulário do `OAuth2PasswordRequestForm` só serve ao botão "Authorize"
do Swagger, e o frontend é um SPA com `fetch`. O e-mail do login não é
validado no formato: e-mail malformado segue o mesmo caminho de "credenciais
inválidas", sem um 422 que vazaria informação.

## Schema `auth`, separado de `public`

`public` guarda `documentos` e `scraper_state`, a fonte de verdade do pipeline.
Contas de usuário são outro domínio, então vivem no schema `auth`: um reset de
`auth.usuarios` em teste nunca encosta na jurisprudência, e `GRANT`/`REVOKE`
por schema fica simples. A tabela é `auth.usuarios` (em português, como o resto
do domínio). Há também `auth.redefinicoes_senha`.

| Coluna | Motivo |
|---|---|
| `id` UUID | PK opaca, `gen_random_uuid()` (nativo desde o PG 13), como `documentos.id`. |
| `email` | Login. Guarda o que a pessoa digitou; só a comparação é normalizada. |
| `hashed_password` | Nunca texto puro. |
| `nome` | Nome de exibição. |
| `is_active` | Desativa a conta sem apagar histórico. |
| `criado_em`, `atualizado_em` | Auditoria. `atualizado_em` é mantido pela aplicação, sem trigger (como `scraper_state.updated_at`). |
| `telefone`, `oab`, `papel` | Perfil, para aparecer em qualquer navegador. |

### E-mail sem diferença de maiúsculas: `lower(email)`, não `citext`

`citext` exigiria `CREATE EXTENSION`, que nada mais no projeto usa, e é mais um
passo que pode falhar se o role não puder criar extensões, além de afetar
dump/restore. O índice único `usuarios_email_lower_idx` em `lower(email)` não
precisa de extensão. O custo é que toda consulta de login ou cadastro faz
`WHERE lower(email) = lower(%s)`. O `CHECK usuarios_email_trimmed`
(`email = btrim(email) AND email <> ''`) rejeita no banco `" a@x.com"` contra
`"a@x.com"`, que o índice sozinho trataria como e-mails diferentes.

### Cadastro duplicado sem condição de corrida

`UsuarioStore.create` não faz `SELECT` antes: tenta o `INSERT` e captura
`psycopg.errors.UniqueViolation`, que o Postgres levanta de forma atômica quando
o índice barra a segunda inserção. A exceção vira `EmailJaCadastradoError` e, na
rota, um 409 com a mesma mensagem nos dois casos. Uma pré-checagem teria uma janela
em que duas requisições passam juntas.

## Redefinição de senha

`/esqueci-senha` responde igual exista ou não a conta, e o e-mail sai depois da
resposta (`BackgroundTasks`): nem a mensagem nem o tempo revelam quais e-mails
estão cadastrados. O token é aleatório, vale 30 minutos e é de uso único. No
banco fica só o SHA-256 dele, então quem ler a tabela não consegue usar um link.
Sem SMTP configurado (`auth/envio_email.py`), responde 503.

## Fora de escopo

- Verificação de e-mail, papéis e permissões (`is_superuser`) e refresh token.
- Limite de tentativas no login: o `DUMMY_HASH` protege contra timing e
  enumeração, não contra força bruta.
- Validação de e-mail com `pydantic.EmailStr`, que exigiria `email-validator`.
  Há uma checagem mínima (`@`, sem espaços, não vazio) no cadastro.
