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

import hashlib
import logging
import os
import secrets
import smtplib
from datetime import datetime, timedelta, timezone
from typing import Literal

import jwt
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, Field, field_validator

from auth import envio_email
from auth.password import DUMMY_HASH, hash_password, verify_password
from auth.store import EmailJaCadastradoError, Usuario, UsuarioStore
from auth.tokens import DEFAULT_EXPIRES_DELTA, create_access_token, decode_access_token

router = APIRouter(prefix="/auth", tags=["auth"])
logger = logging.getLogger(__name__)

# Proteção contra CSRF: cookie SameSite=Lax (ver _set_access_cookie) + a
# allowlist explícita de CORS_ORIGINS em query/api/app.py (nunca "*" com
# allow_credentials=True — o app falha ao subir se isso acontecer). Isso já
# barra um POST cross-site de terceiro mandando o cookie; não há uma segunda
# camada de header aqui de propósito (mantém o cliente simples).

# Nome do cookie: prefixado com o nome do produto para não colidir com
# nenhum outro cookie que um domínio futuro compartilhado venha a usar.
ACCESS_TOKEN_COOKIE_NAME = "jurisight_access_token"

# Secure=True exige HTTPS para o navegador enviar o cookie de volta — obrigatório
# em produção. Por isso é o padrão: esquecer a variável no deploy não pode deixar
# o cookie de sessão sem a flag (issue #17), assim como faltar JWT_SECRET_KEY não
# deixa a API subir. Só o ambiente local em HTTP puro desliga, explicitamente, com
# COOKIE_SECURE=false (.env.example). Ver AUTH_ROUTES_DESIGN_NOTES.md.
def _cookie_secure(valor: str | None) -> bool:
    """Só `false` (sem diferenciar maiúsculas) desliga; ausente ou qualquer outro valor liga."""
    return (valor or "true").strip().lower() != "false"


COOKIE_SECURE = _cookie_secure(os.getenv("COOKIE_SECURE"))

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
    telefone: str | None = None
    oab: str | None = None
    papel: str | None = None

    @classmethod
    def de_usuario(cls, usuario: Usuario) -> "UsuarioPublico":
        return cls(
            id=str(usuario.id),
            email=usuario.email,
            nome=usuario.nome,
            is_active=usuario.is_active,
            criado_em=usuario.criado_em,
            telefone=usuario.telefone,
            oab=usuario.oab,
            papel=usuario.papel,
        )


class PerfilRequest(BaseModel):
    """Dados de perfil da aba Perfil (issue #15). Texto vazio vira None."""

    telefone: str | None = Field(default=None, max_length=30)
    oab: str | None = Field(default=None, max_length=30)
    papel: Literal["Advogado", "Assistente Jurídica"] | None = None

    @field_validator("telefone", "oab")
    @classmethod
    def _limpa(cls, v: str | None) -> str | None:
        return (v or "").strip() or None


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
        # porque no dev local COOKIE_SECURE=false. Ver AUTH_ROUTES_DESIGN_NOTES.md.
        samesite="lax",
    )


def _clear_access_cookie(response: Response) -> None:
    response.delete_cookie(key=ACCESS_TOKEN_COOKIE_NAME, path="/")


# --------------------------------------------------------------------------- #
# POST /auth/registro                                                         #
# --------------------------------------------------------------------------- #

@router.post("/registro", response_model=UsuarioPublico, status_code=status.HTTP_201_CREATED)
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


@router.post("/login", response_model=UsuarioPublico)
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

@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
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


@router.patch("/me/perfil", response_model=UsuarioPublico)
def atualizar_perfil(
    body: PerfilRequest,
    usuario: Usuario = Depends(get_current_user),
    store: UsuarioStore = Depends(get_usuario_store),
) -> UsuarioPublico:
    """Telefone, OAB e papel ficam na conta, e não no navegador: aparecem em qualquer
    navegador ou computador em que a pessoa entrar (issue #15)."""
    atualizado = store.update_perfil(usuario.id, telefone=body.telefone, oab=body.oab, papel=body.papel)
    return UsuarioPublico.de_usuario(atualizado)



# --------------------------------------------------------------------------- #
# Esqueci minha senha (issue #14)                                              #
# --------------------------------------------------------------------------- #

VALIDADE_REDEFINICAO = timedelta(minutes=30)
_MSG_LINK_ENVIADO = (
    "Se houver uma conta com esse e-mail, enviamos um link para redefinir a senha. "
    "Ele vale por 30 minutos."
)


class EsqueciSenhaRequest(BaseModel):
    email: str

    @field_validator("email")
    @classmethod
    def _limpa_email(cls, v: str) -> str:
        return v.strip()


class RedefinirSenhaRequest(BaseModel):
    token: str = Field(min_length=1, max_length=200)
    password: str = Field(min_length=8, max_length=128)  # mesma regra do cadastro


def get_correio():
    """Quem envia o e-mail (auth/envio_email.py); em teste, um falso via dependency_overrides."""
    return envio_email


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _url_do_app() -> str:
    """Endereço do front para o link: APP_URL ou, sem ela, a primeira origem do CORS."""
    url = os.getenv("APP_URL") or (os.getenv("CORS_ORIGINS") or "http://localhost:3000").split(",")[0]
    return url.strip().rstrip("/")


def _enviar_link(correio, para: str, link: str) -> None:
    texto = (
        "Recebemos um pedido para redefinir a senha da sua conta no JuriSight.\n\n"
        f"Para criar uma senha nova, abra este link (vale por 30 minutos e só pode ser usado uma vez):\n{link}\n\n"
        "Se não foi você, ignore este e-mail: sua senha continua a mesma."
    )
    try:
        correio.enviar(para, "Redefinição de senha — JuriSight", texto)
    except (smtplib.SMTPException, OSError) as exc:
        logger.warning("E-mail de redefinição de senha não foi enviado: %s", exc)


@router.post("/esqueci-senha", status_code=status.HTTP_202_ACCEPTED)
def esqueci_senha(
    body: EsqueciSenhaRequest,
    tarefas: BackgroundTasks,
    store: UsuarioStore = Depends(get_usuario_store),
    correio=Depends(get_correio),
) -> dict:
    """A resposta é a mesma exista ou não a conta, e o e-mail sai depois da resposta: nem a
    mensagem nem o tempo de resposta revelam quais e-mails estão cadastrados."""
    if not correio.configurado():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="A recuperação de senha por e-mail ainda não está disponível. Fale com o administrador do JuriSight.",
        )
    usuario = store.get_by_email(body.email)
    if usuario is not None and usuario.is_active:
        token = secrets.token_urlsafe(32)
        expira_em = datetime.now(timezone.utc) + VALIDADE_REDEFINICAO
        if store.criar_redefinicao(usuario.id, _hash_token(token), expira_em):
            tarefas.add_task(_enviar_link, correio, usuario.email, f"{_url_do_app()}/redefinir-senha?token={token}")
    return {"detail": _MSG_LINK_ENVIADO}


@router.post("/redefinir-senha", status_code=status.HTTP_204_NO_CONTENT)
def redefinir_senha(
    body: RedefinirSenhaRequest,
    store: UsuarioStore = Depends(get_usuario_store),
) -> None:
    usuario_id = store.consumir_redefinicao(_hash_token(body.token))
    if usuario_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Este link é inválido, expirou ou já foi usado. Peça um novo em \"Esqueci minha senha\".",
        )
    store.update_hashed_password(usuario_id, hash_password(body.password))
