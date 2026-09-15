"""
Emissão e verificação de JWT (access tokens), via PyJWT.

Algoritmo: HS256 (HMAC-SHA256), não RS256/assimétrico. JuriSight é um backend
único (um processo FastAPI que emite e valida seus próprios tokens) — RS256
só compensa quando um serviço EMITE tokens e outro(s) serviço(s), sem acesso
à chave privada, precisam apenas VALIDAR (ex.: microserviços, ou validação
por um gateway/terceiro). Não é o caso aqui: adicionar um par de chaves
assimétricas seria complexidade sem benefício de segurança real para este
sistema, então HS256 com um segredo forte é a escolha certa (mesma escolha
do template de referência tiangolo/full-stack-fastapi-template).

Chave secreta: OBRIGATORIAMENTE via variável de ambiente `JWT_SECRET_KEY`,
sem fallback hardcoded. Um default tipo "changeme" é uma vulnerabilidade real
(qualquer um lendo o código forjaria tokens válidos) — por isso este módulo
falha alto (`MissingSecretKeyError`) no momento em que a chave é necessária,
em vez de silenciosamente usar um segredo previsível. Gere uma chave forte
com, por exemplo, `openssl rand -hex 32` e defina `JWT_SECRET_KEY` no `.env`
(fora deste piece — cabe a quem for integrar isto ao restante do app).
"""
from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from typing import Any

import jwt

ALGORITHM = "HS256"

# Expiração padrão quando o caller não passa `expires_delta` explicitamente.
# 30 minutos: um access token de vida curta é a prática recomendada (OWASP) —
# limita a janela de uso de um token vazado/roubado. Sessões mais longas
# devem ser feitas com um refresh token (fora do escopo deste piece), não
# alongando o access token.
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
