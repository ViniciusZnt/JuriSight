"""
Endpoints de autenticação real de usuários — registro, login, logout e "quem
sou eu" — mais a dependency `get_current_user` reutilizável por qualquer
outra rota deste app que venha a precisar exigir um usuário autenticado.

Vive em `query/api/` (não em `auth/`) porque é a camada HTTP: usa FastAPI
(`APIRouter`, `Depends`, `Request`/`Response`, `HTTPException`) e Pydantic —
exatamente a mesma mistura que `query/api/app.py` já usa para `/enrich` e
`/query`. `auth/` (password.py, tokens.py, store.py) é deliberadamente cego a
HTTP — só primitivas de segurança e acesso a dados — para poder ser
importado/testado sem subir nenhum servidor. Este módulo é o único ponto do
projeto que conhece as duas pontas (FastAPI de um lado, `auth.*` do outro).

Cookie httpOnly em vez de token no corpo/localStorage
------------------------------------------------------
O template de referência (tiangolo/full-stack-fastapi-template) devolve o
JWT no corpo da resposta (`{"access_token": ..., "token_type": "bearer"}`)
para o frontend guardar em localStorage. localStorage é legível por
QUALQUER JavaScript rodando na página — uma única vulnerabilidade de XSS em
qualquer lugar do frontend (uma lib de terceiros, um campo mal sanitizado)
rouba o token de todo mundo. Aqui o access token nunca aparece no corpo da
resposta nem é acessível via `document.cookie`: ele só existe como um cookie
`HttpOnly`, que o navegador anexa automaticamente às requisições e que
JavaScript não consegue ler. Isso não elimina XSS como classe de risco (um
XSS ainda pode fazer requisições autenticadas *a partir* da página, "confused
deputy"), mas elimina a exfiltração direta do token — a melhoria real que
este desvio do template busca. Detalhes de cookie (nome, Secure, SameSite,
Max-Age) e a escolha JSON-vs-form-data do login estão documentados em
`query/api/AUTH_ROUTES_DESIGN_NOTES.md`.
"""
from __future__ import annotations

import os
from datetime import datetime

import jwt
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, Field, field_validator

from auth.password import DUMMY_HASH, hash_password, verify_password
from auth.store import EmailJaCadastradoError, Usuario, UsuarioStore
from auth.tokens import DEFAULT_EXPIRES_DELTA, create_access_token, decode_access_token

router = APIRouter(prefix="/auth", tags=["auth"])

# Defesa em profundidade contra CSRF, além do SameSite=Lax do cookie (ver
# _set_access_cookie): a proteção real hoje depende de um invariante externo
# a este módulo — CORS_ORIGINS (query/api/app.py) nunca virar "*" enquanto
# allow_credentials=True (Starlette permite essa combinação silenciosamente
# se `CORS_ORIGINS=*` for setado por engano em produção, autorizando qualquer
# origem a mandar fetch com cookie). Exigir este header em toda rota que muda
# estado é uma segunda camada independente dessa config: um POST cross-site
# "simples" (via <form>, sem preflight) não consegue setar headers
# arbitrários, então nunca vai ter X-Requested-With — só um fetch/XHR
# same-origin (ou uma origem já autorizada pelo CORS) consegue.
_REQUIRED_CSRF_HEADER = "x-requested-with"
_REQUIRED_CSRF_HEADER_VALUE = "XMLHttpRequest"


def _exigir_header_csrf(request: Request) -> None:
    if request.headers.get(_REQUIRED_CSRF_HEADER, "").lower() != _REQUIRED_CSRF_HEADER_VALUE.lower():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Header {_REQUIRED_CSRF_HEADER}: {_REQUIRED_CSRF_HEADER_VALUE} obrigatório.",
        )

# Nome do cookie: prefixado com o nome do produto para não colidir com
# nenhum outro cookie que um domínio futuro compartilhado venha a usar.
ACCESS_TOKEN_COOKIE_NAME = "jurisight_access_token"

# Secure=True exige HTTPS para o navegador enviar o cookie de volta — correto
# e obrigatório em produção, mas o dev local (frontend :3000, backend :8000)
# roda em HTTP puro, então Secure=True quebraria login em dev (o cookie
# simplesmente nunca voltaria). Por isso isto é uma env var com default
# seguro-para-produção-mas-também-funciona-em-dev: default "false" (dev),
# e quem fizer o deploy real deve setar COOKIE_SECURE=true (ver
# AUTH_ROUTES_DESIGN_NOTES.md).
COOKIE_SECURE = os.getenv("COOKIE_SECURE", "false").strip().lower() == "true"

# Minutos que o cookie deve viver — igual à expiração do próprio JWT
# (`DEFAULT_EXPIRES_DELTA`, hoje 30 min). Deriva do MESMO valor que
# `create_access_token` usa (em vez de um número mágico duplicado aqui) para
# nunca poderem dessincronizar: um cookie que dura mais que o token só
# guardaria um JWT já expirado; um cookie mais curto que o token derrubaria a
# sessão antes do token realmente expirar.
_COOKIE_MAX_AGE_SECONDS = int(DEFAULT_EXPIRES_DELTA.total_seconds())


# --------------------------------------------------------------------------- #
# Modelos Pydantic                                                             #
# --------------------------------------------------------------------------- #

def _validar_email_basico(v: str) -> str:
    """Validação mínima de formato — o `email-validator` do Pydantic
    (`EmailStr`) não está instalado neste projeto (não é dependência hoje) e
    não vale adicionar só por isto. Mantém consistência com o CHECK
    `usuarios_email_trimmed` de `auth/db.py` (trim + não-vazio) e acrescenta
    a checagem mínima de "parece um e-mail" (`@`, sem espaços)."""
    v = v.strip()
    if not v or " " in v or "@" not in v or v.startswith("@") or v.endswith("@"):
        raise ValueError("e-mail inválido")
    return v


class RegistroRequest(BaseModel):
    email: str
    # Mínimo de 8 caracteres: não é "gold-plating" (sem regras de
    # complexidade/composição, que a NIST 800-63B recomenda evitar — elas
    # incentivam senhas previsíveis tipo "Senha123!"), mas um sistema real
    # não pode aceitar senha vazia ou de 1 caractere.
    password: str = Field(min_length=8, max_length=128)
    nome: str | None = Field(default=None, max_length=255)

    @field_validator("email")
    @classmethod
    def _valida_email(cls, v: str) -> str:
        return _validar_email_basico(v)

    @field_validator("nome")
    @classmethod
    def _limpa_nome(cls, v: str | None) -> str | None:
        if v is None:
            return None
        v = v.strip()
        return v or None


class LoginRequest(BaseModel):
    """JSON (não `OAuth2PasswordRequestForm`/multipart) — ver
    AUTH_ROUTES_DESIGN_NOTES.md para o porquê. O frontend deve enviar
    `POST /auth/login` com `Content-Type: application/json` e corpo
    `{"email": ..., "password": ...}`, igual a todo outro POST deste app
    (`/query` em query/api/app.py já usa um `BaseModel` JSON)."""

    email: str
    password: str

    @field_validator("email")
    @classmethod
    def _limpa_email(cls, v: str) -> str:
        # Deliberadamente SEM validar formato aqui (diferente de
        # RegistroRequest): um e-mail malformado no login deve seguir o
        # MESMO caminho de "credenciais inválidas" que um e-mail bem
        # formado mas inexistente — nunca um 422 diferenciado, que vazaria
        # informação sobre formato antes mesmo de checar existência.
        return v.strip()


class UsuarioPublico(BaseModel):
    """Campos públicos de um usuário — nunca inclui `hashed_password`."""

    id: str
    email: str
    nome: str | None
    is_active: bool
    criado_em: datetime

    @classmethod
    def de_usuario(cls, usuario: Usuario) -> "UsuarioPublico":
        return cls(
            id=str(usuario.id),
            email=usuario.email,
            nome=usuario.nome,
            is_active=usuario.is_active,
            criado_em=usuario.criado_em,
        )


# --------------------------------------------------------------------------- #
# Dependency de acesso a dados                                                 #
# --------------------------------------------------------------------------- #

def get_usuario_store(request: Request) -> UsuarioStore:
    """Mesmo padrão de `get_hybrid`/`get_doc_retriever`/`get_enricher` em
    query/api/app.py: o singleton vive em `request.app.state`, construído uma
    vez no lifespan (ver o snippet de integração no design notes) — em teste,
    substituído via `app.dependency_overrides[get_usuario_store] = ...`."""
    return request.app.state.usuario_store


# --------------------------------------------------------------------------- #
# Cookie helpers                                                               #
# --------------------------------------------------------------------------- #

def _set_access_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key=ACCESS_TOKEN_COOKIE_NAME,
        value=token,
        max_age=_COOKIE_MAX_AGE_SECONDS,
        path="/",
        httponly=True,
        secure=COOKIE_SECURE,
        # "Lax": frontend (localhost:3000) e backend (localhost:8000) são
        # portas diferentes do MESMO host — mesmo "site" no sentido do
        # SameSite (que ignora porta, só olha esquema+domínio registrável),
        # então isto não é uma requisição cross-site e o cookie É enviado
        # normalmente em toda chamada fetch/XHR com `credentials: "include"`.
        # "Lax" (em vez de "None") ainda barra o cookie em navegações
        # cross-site de terceiros (CSRF), sem exigir Secure — importante
        # porque em dev COOKIE_SECURE é false. Ver AUTH_ROUTES_DESIGN_NOTES.md.
        samesite="lax",
    )


def _clear_access_cookie(response: Response) -> None:
    response.delete_cookie(key=ACCESS_TOKEN_COOKIE_NAME, path="/")


# --------------------------------------------------------------------------- #
# POST /auth/registro                                                         #
# --------------------------------------------------------------------------- #

@router.post(
    "/registro",
    response_model=UsuarioPublico,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(_exigir_header_csrf)],
)
def registrar(
    body: RegistroRequest,
    store: UsuarioStore = Depends(get_usuario_store),
) -> UsuarioPublico:
    hashed = hash_password(body.password)
    try:
        usuario = store.create(email=body.email, hashed_password=hashed, nome=body.nome)
    except EmailJaCadastradoError:
        # Mesma mensagem independente de o e-mail já existir "antes" ou ter
        # sido inserido por uma requisição concorrente entre nosso pré-check
        # (que nem existe, ver UsuarioStore.create) e agora — não há dois
        # caminhos de erro para diferenciar.
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="E-mail já cadastrado.")
    return UsuarioPublico.de_usuario(usuario)


# --------------------------------------------------------------------------- #
# POST /auth/login                                                             #
# --------------------------------------------------------------------------- #

_CREDENCIAIS_INVALIDAS = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED, detail="E-mail ou senha inválidos."
)


@router.post("/login", response_model=UsuarioPublico, dependencies=[Depends(_exigir_header_csrf)])
def login(
    body: LoginRequest,
    response: Response,
    store: UsuarioStore = Depends(get_usuario_store),
) -> UsuarioPublico:
    usuario = store.get_by_email(body.email)
    if usuario is None:
        # Paga o mesmo custo de CPU do Argon2id que um verify real pagaria,
        # para não vazar por timing se o e-mail existe (auth/password.py).
        verify_password(body.password, DUMMY_HASH)
        raise _CREDENCIAIS_INVALIDAS

    ok, novo_hash = verify_password(body.password, usuario.hashed_password)
    if not ok:
        raise _CREDENCIAIS_INVALIDAS
    if not usuario.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Usuário inativo.")

    if novo_hash is not None:
        # Rehash-on-verify: o hash armazenado usava algoritmo/parâmetros
        # antigos (ex.: bcrypt herdado) — atualiza silenciosamente.
        store.update_hashed_password(usuario.id, novo_hash)

    token = create_access_token(str(usuario.id))
    _set_access_cookie(response, token)
    return UsuarioPublico.de_usuario(usuario)


# --------------------------------------------------------------------------- #
# POST /auth/logout                                                           #
# --------------------------------------------------------------------------- #

@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT, dependencies=[Depends(_exigir_header_csrf)])
def logout(response: Response) -> None:
    _clear_access_cookie(response)


# --------------------------------------------------------------------------- #
# get_current_user — dependency reutilizável por outras rotas                 #
# --------------------------------------------------------------------------- #

def get_current_user(
    request: Request,
    store: UsuarioStore = Depends(get_usuario_store),
) -> Usuario:
    """Lê o cookie httpOnly, decodifica o JWT e busca o usuário no Postgres.

    Reutilizável por QUALQUER rota futura deste app que precise exigir um
    usuário autenticado — basta `Depends(get_current_user)` (ou, para pegar
    só os campos públicos, `Depends(get_current_user_publico)` abaixo).
    Levanta 401 em qualquer cenário de falha (cookie ausente, token
    adulterado/expirado, usuário não existe mais) — nunca deixa
    `MissingSecretKeyError`/`jwt.InvalidTokenError` vazarem como 500 opaco
    nem, ao contrário, engole um erro de configuração (`JWT_SECRET_KEY`
    ausente no ambiente) como se fosse "não autenticado": esse caso continua
    subindo como 500, de propósito — é um bug de deploy, não do cliente.
    """
    token = request.cookies.get(ACCESS_TOKEN_COOKIE_NAME)
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Não autenticado.")

    try:
        payload = decode_access_token(token)
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Sessão expirada.")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token inválido.")

    usuario_id = payload.get("sub")
    usuario = store.get_by_id(usuario_id) if usuario_id else None
    if usuario is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Não autenticado.")
    if not usuario.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Usuário inativo.")
    return usuario


def get_current_user_publico(usuario: Usuario = Depends(get_current_user)) -> UsuarioPublico:
    """Mesma dependency acima, mas já projetada para os campos públicos —
    conveniente para outra rota que só precisa exibir/serializar o usuário,
    sem tocar `hashed_password`."""
    return UsuarioPublico.de_usuario(usuario)


# --------------------------------------------------------------------------- #
# GET /auth/me                                                                 #
# --------------------------------------------------------------------------- #

@router.get("/me", response_model=UsuarioPublico)
def me(usuario_publico: UsuarioPublico = Depends(get_current_user_publico)) -> UsuarioPublico:
    return usuario_publico
