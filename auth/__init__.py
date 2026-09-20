"""
auth — primitivas de segurança para autenticação real de usuários.

Este pacote substitui o mock client-side descrito em
`frontend/src/lib/auth.tsx` (uma flag booleana em localStorage, sem nenhuma
verificação de servidor) pelas duas primitivas que um backend de autenticação
real precisa:

  - `auth.password`: hashing/verificação de senha (Argon2id, com fallback de
    verificação em bcrypt) e um `DUMMY_HASH` para mitigar enumeração de
    usuários por timing attack.
  - `auth.tokens`: emissão/verificação de JWT (HS256) para tokens de acesso.

Este pacote NÃO conhece o schema do Postgres (peça de outro agente, em
paralelo) nem os endpoints FastAPI (peça futura) — são funções puras,
importáveis por qualquer camada que venha a existir por cima delas.
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
