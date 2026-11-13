"""
Autenticação: hashing de senha (`auth.password`, Argon2id), JWT (`auth.tokens`, HS256),
schema (`auth.db`) e acesso a dados (`auth.store`). Nada aqui conhece HTTP; as rotas
ficam em `query/api/auth_routes.py`. Decisões em `auth/DESIGN.md`.
"""

from auth.password import DUMMY_HASH, PasswordVerification, hash_password, verify_password
from auth.tokens import MissingSecretKeyError, create_access_token, decode_access_token

__all__ = [
    "DUMMY_HASH",
    "PasswordVerification",
    "hash_password",
    "verify_password",
    "MissingSecretKeyError",
    "create_access_token",
    "decode_access_token",
]
