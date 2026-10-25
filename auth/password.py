"""
Hashing e verificação de senha.

Algoritmo: Argon2id (via `pwdlib[argon2]`) — o KDF memory-hard recomendado
atualmente pela OWASP, resistente a ataques por GPU/ASIC muito melhor que
bcrypt/PBKDF2. Sistema novo, sem usuários herdados de outro backend: não há
hash em outro algoritmo pra verificar, então só Argon2id existe aqui (nada de
fallback de verificação para um formato que nunca vai aparecer).

Este módulo não faz lookup de usuário nem toca banco — isso é responsabilidade
de uma peça futura (endpoints). O único acoplamento esperado é: o caller passa
uma senha em texto puro e um hash armazenado, e recebe de volta se bateu (e,
opcionalmente, um novo hash para persistir, se os parâmetros de custo do
Argon2 mudarem no futuro — "rehash on verify" via `verify_and_update`).
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


# Hash Argon2id válido de uma senha aleatória e descartada — NÃO é a senha de
# nenhum usuário real. Existe só para mitigar enumeração de usuários por
# timing attack: a lógica de autenticação (peça futura, quando o lookup no
# Postgres existir) deve seguir o padrão:
#
#     user = lookup_by_email(email)
#     if user is None:
#         verify_password(password, DUMMY_HASH)   # paga o mesmo custo de CPU
#         raise InvalidCredentials()               # mesma mensagem/latência
#     ok, novo_hash = verify_password(password, user.hashed_password)
#     if not ok:
#         raise InvalidCredentials()               # mesma mensagem/latência
#
# Sem isso, um endpoint de login que só faz "senha errada" quando o usuário
# EXISTE (pulando o hash quando não existe) vaza, pelo tempo de resposta,
# se um e-mail está cadastrado ou não.
#
# Calculado em import-time (em vez de hardcoded como string) para garantir
# que o custo pago aqui seja sempre o mesmo custo do Argon2Hasher atual —
# uma string fixa corre o risco de ficar com parâmetros (m/t/p) diferentes
# dos usados por `hash_password` se a lib for atualizada, o que quebraria a
# propriedade de "mesmo custo" que essa mitigação depende.
DUMMY_HASH = _password_hash.hash("dummy-password-for-timing-attack-mitigation-only")
