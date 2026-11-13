"""
Emissão e verificação de JWT (access tokens), via PyJWT.

HS256 e não RS256: um único backend emite e valida os próprios tokens. A chave vem
só de `JWT_SECRET_KEY`, sem valor padrão: faltando, levanta `MissingSecretKeyError`
em vez de usar um segredo previsível. Porquês em `auth/DESIGN.md`.
"""
from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from typing import Any

import jwt

ALGORITHM = "HS256"

# Vida curta limita o estrago de um token vazado; não há refresh token.
DEFAULT_EXPIRES_DELTA = timedelta(minutes=30)


class MissingSecretKeyError(RuntimeError):
    """`JWT_SECRET_KEY` não está definida no ambiente.

    Levantado em vez de usar um segredo padrão: um fallback hardcoded (tipo
    "changeme") tornaria qualquer token forjável por quem lê o código-fonte.
    """


def _get_secret_key() -> str:
    secret = os.getenv("JWT_SECRET_KEY")
    if not secret:
        raise MissingSecretKeyError(
            "JWT_SECRET_KEY não está definida no ambiente. Defina uma chave "
            "secreta forte (ex.: `openssl rand -hex 32`) antes de emitir ou "
            "validar tokens — não existe valor padrão por segurança."
        )
    return secret


def create_access_token(subject: str, expires_delta: timedelta = DEFAULT_EXPIRES_DELTA) -> str:
    """
    Cria um JWT de acesso para `subject` (tipicamente o id/e-mail do usuário).

    Levanta `MissingSecretKeyError` se `JWT_SECRET_KEY` não estiver no
    ambiente.
    """
    secret = _get_secret_key()
    now = datetime.now(timezone.utc)
    payload: dict[str, Any] = {
        "sub": subject,
        "iat": now,
        "exp": now + expires_delta,
    }
    return jwt.encode(payload, secret, algorithm=ALGORITHM)


def decode_access_token(token: str) -> dict[str, Any]:
    """
    Decodifica e valida um JWT de acesso, devolvendo o payload (`sub`, `iat`,
    `exp`, ...).

    Levanta:
      - `MissingSecretKeyError` se `JWT_SECRET_KEY` não estiver no ambiente.
      - `jwt.ExpiredSignatureError` se o token expirou.
      - `jwt.InvalidTokenError` (ou subclasses, ex. `InvalidSignatureError`)
        se o token foi adulterado, tem assinatura inválida, ou está malformado.

    Deliberadamente não engolimos essas exceções aqui: quem chama (a peça de
    endpoints) decide o mapeamento para HTTP 401 e a mensagem exibida.
    """
    secret = _get_secret_key()
    return jwt.decode(token, secret, algorithms=[ALGORITHM])
