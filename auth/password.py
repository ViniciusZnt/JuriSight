"""
Hashing e verificação de senha com Argon2id (`pwdlib`). Não toca o banco: recebe a
senha em texto puro e o hash guardado, e devolve se bateu e, se os parâmetros de
custo mudaram, um novo hash para o chamador gravar (rehash ao verificar).
"""
from __future__ import annotations

from typing import NamedTuple

from pwdlib import PasswordHash
from pwdlib.hashers.argon2 import Argon2Hasher

_password_hash = PasswordHash((Argon2Hasher(),))


class PasswordVerification(NamedTuple):
    """Resultado de `verify_password` — SEMPRE desempacote, nunca teste como bool.

    Uma tupla comum tem `bool(t) == True` sempre que não-vazia, mesmo quando
    `ok=False` — então `if verify_password(...):` autenticaria QUALQUER senha
    errada silenciosamente (bypass de autenticação). `__bool__` levanta de
    propósito para tornar esse erro impossível de passar despercebido: o
    caller é forçado a escrever `ok, novo_hash = verify_password(...)` e
    testar `ok` explicitamente.
    """

    ok: bool
    novo_hash: str | None

    def __bool__(self) -> bool:
        raise TypeError(
            "PasswordVerification não deve ser testado como bool (sempre truthy "
            "como tupla, mesmo com ok=False). Desempacote: "
            "`ok, novo_hash = verify_password(...)` e teste `ok`."
        )


def hash_password(password: str) -> str:
    """Hasheia uma senha em texto puro com Argon2id. Nunca armazene texto puro."""
    if not password:
        raise ValueError("senha vazia não pode ser hasheada")
    return _password_hash.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> PasswordVerification:
    """
    Verifica `plain_password` contra `hashed_password`.

    Devolve um `PasswordVerification(ok, novo_hash)` — SEMPRE desempacote,
    nunca teste o retorno como bool (ver docstring de `PasswordVerification`):
      - `ok`: True se a senha bate com o hash armazenado.
      - `novo_hash`: não-None quando o hash armazenado usava um algoritmo ou
        parâmetros desatualizados (ex.: bcrypt, ou Argon2 com custo antigo) —
        nesse caso o caller deve persistir `novo_hash` no lugar do hash
        antigo (upgrade transparente no login). None quando o hash já está
        no formato/custo atual e não precisa ser trocado.
    """
    return PasswordVerification(*_password_hash.verify_and_update(plain_password, hashed_password))


# Hash de uma senha descartada. O login o verifica quando o e-mail não existe, para
# gastar o mesmo tempo de uma verificação real e não revelar por timing quais e-mails
# estão cadastrados. Calculado ao importar (não é string fixa) para o custo acompanhar
# os parâmetros atuais do Argon2.
DUMMY_HASH = _password_hash.hash("dummy-password-for-timing-attack-mitigation-only")
