"""
Endpoints de autenticação (registro, login, logout, "quem sou eu", perfil e
redefinição de senha) e a dependency `get_current_user`, reutilizável por qualquer
rota que exija usuário autenticado.

O JWT vai num cookie HttpOnly, nunca no corpo da resposta, para que um XSS não
leia o token (diferente do template de referência, que usa localStorage). Cookie,
Secure, SameSite, login em JSON e demais decisões estão em `auth/DESIGN.md`.
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

# CSRF: cookie SameSite=Lax (ver _set_access_cookie) + allowlist explícita de
# CORS_ORIGINS em query/api/app.py (nunca "*" com allow_credentials=True; o app
# não sobe assim). Sem segunda camada de header, de propósito.

ACCESS_TOKEN_COOKIE_NAME = "jurisight_access_token"

# Secure é o padrão: esquecer a variável no deploy não pode deixar o cookie sem a flag
# (issue #17). Só o dev local em HTTP desliga, com COOKIE_SECURE=false (.env.example).
def _cookie_secure(valor: str | None) -> bool:
    """Só `false` (sem diferenciar maiúsculas) desliga; ausente ou qualquer outro valor liga."""
    return (valor or "true").strip().lower() != "false"


COOKIE_SECURE = _cookie_secure(os.getenv("COOKIE_SECURE"))

# Mesma duração do JWT (`DEFAULT_EXPIRES_DELTA`), para cookie e token não dessincronizarem.
_COOKIE_MAX_AGE_SECONDS = int(DEFAULT_EXPIRES_DELTA.total_seconds())


# --------------------------------------------------------------------------- #
# Modelos Pydantic                                                             #
# --------------------------------------------------------------------------- #

def _validar_email_basico(v: str) -> str:
    """Validação mínima (sem `EmailStr`, que exigiria `email-validator`): trim e não vazio,
    como o CHECK `usuarios_email_trimmed` de `auth/db.py`, mais `@` e sem espaços."""
    v = v.strip()
    if not v or " " in v or "@" not in v or v.startswith("@") or v.endswith("@"):
        raise ValueError("e-mail inválido")
    return v


class RegistroRequest(BaseModel):
    email: str
    # Só o tamanho mínimo: regras de composição incentivam "Senha123!" (NIST 800-63B).
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
    """JSON, não `OAuth2PasswordRequestForm` (ver auth/DESIGN.md)."""

    email: str
    password: str

    @field_validator("email")
    @classmethod
    def _limpa_email(cls, v: str) -> str:
        # Sem validar o formato (ao contrário do cadastro): e-mail malformado segue o mesmo
        # caminho de "credenciais inválidas", sem um 422 que o diferencie.
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
    """O singleton vive em `request.app.state` (criado no lifespan de app.py); em teste,
    é trocado por `app.dependency_overrides[get_usuario_store]`."""
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
        # Lax: localhost:3000 e :8000 são o mesmo "site" (SameSite ignora a porta), então o
        # cookie segue nos fetch com credentials. Barra navegação cross-site de terceiros
        # (CSRF) sem exigir Secure, desligado no dev local. Ver auth/DESIGN.md.
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
        # Mesma mensagem se já existia ou se uma requisição concorrente inseriu antes.
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
        # Gasta o mesmo tempo de uma verificação real, para o timing não revelar se o e-mail existe.
        verify_password(body.password, DUMMY_HASH)
        raise _CREDENCIAIS_INVALIDAS

    ok, novo_hash = verify_password(body.password, usuario.hashed_password)
    if not ok:
        raise _CREDENCIAIS_INVALIDAS
    if not usuario.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Usuário inativo.")

    if novo_hash is not None:
        # O hash guardado tinha parâmetros antigos: atualiza em silêncio.
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
    """Lê o cookie httpOnly, decodifica o JWT e busca o usuário. Levanta 401 se o cookie
    faltar, o token for inválido ou expirado, ou o usuário não existir mais.
    `MissingSecretKeyError` (JWT_SECRET_KEY ausente) sobe como 500 de propósito: é erro de deploy."""
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
    """`get_current_user` já projetado nos campos públicos (sem `hashed_password`)."""
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
