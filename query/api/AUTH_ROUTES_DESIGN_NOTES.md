# Decisões de design — endpoints de autenticação (`query/api/auth_routes.py`)

**Escopo desta peça:** os endpoints HTTP (`POST /auth/registro`, `POST
/auth/login`, `POST /auth/logout`, `GET /auth/me`) e a dependency
`get_current_user` reutilizável. Constrói em cima de três peças já prontas
(`auth/db.py`, `auth/password.py`, `auth/tokens.py`) e adiciona uma quarta,
`auth/store.py` (CRUD de `auth.usuarios` via psycopg — a única peça de
acesso a dados que faltava). Não integra o router em `query/api/app.py` nem
roda `auth.db.ensure_schema()` — ambos são passos de integração deliberados,
de outra peça.

## Onde o código mora: `query/api/` para o router, `auth/store.py` para a query

`auth/` (password.py, tokens.py) é deliberadamente cego a HTTP — o próprio
docstring de `auth/__init__.py` diz isso ("Este pacote NÃO conhece... os
endpoints FastAPI"). `query/api/app.py` é onde a mistura FastAPI (`APIRouter`,
`Depends`, `Request`/`Response`, `HTTPException`, modelos Pydantic) já vive
para `/enrich` e `/query`. Colocar os endpoints de autenticação em
`query/api/auth_routes.py` mantém essa fronteira: `auth/` continua
importável/testável sem nenhum framework web, e a camada HTTP fica toda
concentrada em `query/api/`, com um único módulo (`auth_routes.py`) que
conhece as duas pontas.

A única peça nova de acesso a dados, `UsuarioStore` (CRUD de
`auth.usuarios`), foi para `auth/store.py`, não para `query/api/`: é psycopg
puro, sem nada de FastAPI, e mora ao lado de `auth/db.py` (que já criou o
schema que ela consulta) — mesma fronteira "auth/ = sem HTTP" preservada.
`query/search/doc_retriever.py` foi o modelo de estilo (conecta/cursora/
fecha por chamada, sem pool nem conexão persistente — tráfego baixo o
suficiente para não valer a complexidade de um pool aqui).

## Cookie httpOnly em vez de token no corpo (o desvio deliberado do template)

O `tiangolo/full-stack-fastapi-template` devolve `{"access_token": ...}` no
corpo de `/login/access-token` para o frontend guardar em `localStorage`.
Qualquer JS rodando na página (uma lib de terceiros comprometida, um campo
mal sanitizado) pode ler `localStorage` e exfiltrar o token — uma única
vulnerabilidade de XSS em qualquer lugar do app rouba a sessão de qualquer
usuário que a tenha acionado.

Aqui, o JWT nunca aparece no corpo de `/auth/login` nem é acessível via
`document.cookie`: ele só existe como cookie `HttpOnly`, que o navegador
anexa automaticamente e que JavaScript não consegue ler. Isso não elimina
XSS como classe (um script malicioso ainda pode fazer requisições
autenticadas *a partir* da página aberta — "confused deputy"), mas elimina a
exfiltração direta do token, que é o risco mais comum e mais grave de
localStorage. `POST /auth/login` e `GET /auth/me` nunca devolvem o token no
JSON — só os campos públicos do usuário.

### Nome do cookie

`jurisight_access_token` — prefixado com o nome do produto para não colidir
com outro cookie caso um domínio futuro venha a hospedar mais de uma
aplicação.

### `Secure`

Controlado por env var `COOKIE_SECURE` (default `"false"`), lida em
`query/api/auth_routes.py`:

```python
COOKIE_SECURE = os.getenv("COOKIE_SECURE", "false").strip().lower() == "true"
```

Dev roda em HTTP puro (frontend `localhost:3000`, backend `localhost:8000`)
— `Secure=True` faria o navegador *nunca* enviar o cookie de volta em HTTP,
quebrando login em dev silenciosamente (sem erro visível, só uma sessão que
nunca "gruda"). Por isso o default é `false`. Em um deploy real atrás de
HTTPS, setar `COOKIE_SECURE=true` no ambiente ativa a flag — sem isso, um
JWT em trânsito por uma rede não seria protegido contra downgrade para HTTP.

### `SameSite`

`Lax`. Frontend e backend são portas diferentes (`3000`/`8000`) do MESMO
host (`localhost`) — o algoritmo de "site" que `SameSite` usa considera só
esquema + domínio registrável, ignorando porta, então isso é uma requisição
**same-site** (ainda que cross-*origin*, por causa da porta). Um cookie
`Lax` é enviado normalmente em chamadas `fetch`/`XHR` same-site (com
`credentials: "include"` no frontend — o backend já habilita
`allow_credentials=True` com origens explícitas via `CORS_ORIGINS`, ver
`query/api/app.py`), então não há nenhum problema de "o cookie não chega".
`Lax` (em vez de `None`) ainda barra o cookie em navegações cross-site de
terceiros — mitigação de CSRF de baixo custo — sem depender de `Secure`
(que `SameSite=None` exigiria em navegadores modernos, e que está desligado
em dev). Se um deploy futuro colocar frontend e backend em domínios
registráveis DIFERENTES (não apenas portas diferentes do mesmo host), isso
deixa de ser same-site e precisaria virar `SameSite=None; Secure=true` — não
é o caso hoje.

### `Max-Age` / expiração

```python
_COOKIE_MAX_AGE_SECONDS = int(DEFAULT_EXPIRES_DELTA.total_seconds())  # de auth/tokens.py
```

Deriva do MESMO `DEFAULT_EXPIRES_DELTA` (30 min) que `create_access_token`
usa para o `exp` do JWT — não um número mágico duplicado. Isso garante que
cookie e token nunca dessincronizem: se o cookie durasse mais, guardaria um
JWT já expirado (o usuário veria 401 em `/auth/me` mesmo com o cookie
"presente", uma UX confusa); se durasse menos, a sessão cairia antes do
token realmente expirar, sem motivo.

## JSON, não `OAuth2PasswordRequestForm`/multipart, em `/auth/login`

O template de referência usa `OAuth2PasswordRequestForm` (form-encoded)
porque está construindo um endpoint compatível com o fluxo OAu2 genérico
que o botão "Authorize" do Swagger UI espera. O frontend do JuriSight é um
SPA Next.js fazendo `fetch` normal — não há cliente OAuth2 genérico para
satisfazer. Toda outra rota `POST` deste app já usa um corpo JSON via
`BaseModel` (`POST /query` com `QueryRequest`, em `query/api/app.py`); usar
form-encoded só em `/auth/login` seria uma inconsistência sem benefício.

**Contrato exato para o frontend:**

```
POST /auth/login
Content-Type: application/json

{"email": "usuario@example.com", "password": "..."}
```

Resposta 200: campos públicos do usuário no corpo (`id`, `email`, `nome`,
`is_active`, `criado_em`) + `Set-Cookie: jurisight_access_token=...` (não
inspecionável por JS). O frontend deve chamar com `credentials: "include"`
tanto aqui quanto em `/auth/me`/`/auth/logout` e qualquer rota futura
protegida — sem isso o navegador não envia nem recebe o cookie cross-porta.

## Evitando a condição de corrida no registro duplicado

A abordagem ingênua — `SELECT` por e-mail, e só faz `INSERT` se não achar
nada — tem uma janela de corrida (TOCTOU): duas requisições de registro
simultâneas com o mesmo e-mail podem AMBAS passar pelo `SELECT` antes de
qualquer uma commitar o `INSERT`, e as duas acabam inserindo. O índice único
`usuarios_email_lower_idx` (`auth/db.py`) impediria isso no banco, mas só se
o código realmente deixar o Postgres ser a fonte de verdade.

`UsuarioStore.create` (`auth/store.py`) não faz pré-checagem nenhuma: tenta
o `INSERT` direto e captura `psycopg.errors.UniqueViolation` — a violação
que o Postgres levanta atomicamente quando o índice único barra a segunda
inserção, sem nenhuma janela entre "checar" e "inserir". Isso é traduzido
para `EmailJaCadastradoError` (uma exceção da camada `auth/`, sem
`psycopg`/detalhes de banco vazando) e, na camada HTTP
(`query/api/auth_routes.py::registrar`), para `HTTPException(409, "E-mail
já cadastrado.")` — a mesma mensagem tanto para "já existia" quanto para "uma
requisição concorrente inseriu primeiro": não há dois caminhos de erro para
diferenciar, então não há nada para vazar.

## Dependências novas

Nenhuma além das já reportadas pelas peças anteriores — `pwdlib[argon2,bcrypt]`
e `PyJWT>=2.9` (`psycopg[binary]` já é dependência do projeto). Comandos
exatos para quem for integrar (não rodados aqui, `uv add` não foi executado):

```
uv add "pwdlib[argon2,bcrypt]"
uv add "PyJWT>=2.9"
```

Os testes desta peça (`tests/test_auth_routes.py`) foram rodados com essas
libs resolvidas de forma efêmera:

```
uv run --with "pwdlib[argon2,bcrypt]" --with "PyJWT>=2.9" python -m pytest tests/test_auth_routes.py -v
```

`email-validator` (necessário para `pydantic.EmailStr`) **não** está
instalado no projeto — por isso `RegistroRequest`/`LoginRequest` usam `str`
com uma validação manual mínima (`@` presente, sem espaços, não-vazio após
`strip()`) em vez de `EmailStr`, para não introduzir mais uma dependência só
por isto.

## Como integrar (não aplicado — próxima peça)

`auth_routes.get_usuario_store` lê `request.app.state.usuario_store`, no
mesmo padrão de `get_hybrid`/`get_doc_retriever`/`get_enricher` em
`query/api/app.py`. Quem for montar isto no app principal precisa:

1. Construir o `UsuarioStore` uma vez no `lifespan` (igual ao
   `DocRetriever`);
2. Incluir o router.

```python
from auth.store import UsuarioStore
from query.api.auth_routes import router as auth_router

# dentro de lifespan(app), junto dos outros app.state.*:
app.state.usuario_store = UsuarioStore(DATABASE_URL)

# depois de `app = FastAPI(...)`:
app.include_router(auth_router)
```

Também é o momento de (fora desta peça, de propósito):
- rodar `auth.db.ensure_schema()` na subida (ou via migração separada);
- adicionar `"auth*"` a `tool.setuptools.packages.find.include` em
  `pyproject.toml` (já apontado como pendente em `auth/DESIGN_NOTES.md`);
- definir `JWT_SECRET_KEY` e, se for deploy com HTTPS, `COOKIE_SECURE=true`
  no ambiente.

## Fora de escopo, propositalmente

- Refresh tokens / renovação de sessão (o access token é de vida curta por
  design, ver `auth/tokens.py`; um refresh token é uma peça separada).
- Recuperação de senha / verificação de e-mail (o template de referência
  tem ambos; não fazem parte do pedido desta peça).
- Rate limiting em `/auth/login` (mitigaria brute-force; a mitigação aqui é
  só contra timing/enumeração via `DUMMY_HASH`, não contra tentativas
  repetidas).
- Editar `query/api/app.py` para montar o router, e rodar
  `auth.db.ensure_schema()` contra o Postgres real — ambos deliberadamente
  deixados para a peça de integração.
