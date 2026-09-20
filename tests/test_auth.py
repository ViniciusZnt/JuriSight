"""
Testes das primitivas de autenticação (auth/password.py, auth/tokens.py).

Puramente determinístico — sem mocks, sem Postgres, sem rede. `JWT_SECRET_KEY`
é setada/removida via `monkeypatch.setenv`/`monkeypatch.delenv` em cada teste
que precisa dela, para não depender (nem poluir) o ambiente real.
"""
import time
from datetime import timedelta

import jwt
import pytest

from auth.password import DUMMY_HASH, hash_password, verify_password
from auth.tokens import MissingSecretKeyError, create_access_token, decode_access_token


# --------------------------------------------------------------------------- #
# hash_password / verify_password                                             #
# --------------------------------------------------------------------------- #

def test_hash_password_gera_hash_diferente_da_senha_em_texto_puro():
    hashed = hash_password("uma-senha-bem-forte-123")
    assert hashed != "uma-senha-bem-forte-123"
    assert hashed.startswith("$argon2")


def test_hash_password_senha_vazia_levanta_erro():
    with pytest.raises(ValueError):
        hash_password("")


def test_verify_password_round_trip_senha_correta():
    hashed = hash_password("correta-horse-battery-staple")
    valido, novo_hash = verify_password("correta-horse-battery-staple", hashed)
    assert valido is True
    # Argon2id com os parâmetros atuais não precisa de rehash.
    assert novo_hash is None


def test_verify_password_rejeita_senha_errada():
    hashed = hash_password("senha-certa")
    valido, _ = verify_password("senha-errada", hashed)
    assert valido is False


def test_verify_password_duas_senhas_iguais_geram_hashes_diferentes():
    # Salt aleatório por hash — propriedade básica de um KDF de senha correto.
    h1 = hash_password("mesma-senha")
    h2 = hash_password("mesma-senha")
    assert h1 != h2
    assert verify_password("mesma-senha", h1)[0] is True
    assert verify_password("mesma-senha", h2)[0] is True


def test_verify_password_resultado_nao_pode_ser_testado_como_bool():
    # Regressão: uma tupla comum é sempre truthy quando não-vazia, então
    # `if verify_password(errada, hash):` autenticaria qualquer senha errada
    # silenciosamente. PasswordVerification.__bool__ precisa levantar.
    hashed = hash_password("senha-certa")
    resultado = verify_password("senha-errada", hashed)
    assert resultado.ok is False
    with pytest.raises(TypeError):
        bool(resultado)
    with pytest.raises(TypeError):
        if resultado:
            pass


def test_dummy_hash_verifica_como_invalido_sem_levantar_erro():
    # DUMMY_HASH existe para mitigação de timing attack (ver docstring em
    # auth/password.py): precisa pagar o mesmo custo de CPU de um verify
    # real, mas nunca deve "bater" com nenhuma senha real.
    valido, _ = verify_password("qualquer-senha-tentada", DUMMY_HASH)
    assert valido is False


# --------------------------------------------------------------------------- #
# create_access_token / decode_access_token                                   #
# --------------------------------------------------------------------------- #

def test_jwt_round_trip(monkeypatch):
    monkeypatch.setenv("JWT_SECRET_KEY", "segredo-de-teste-nao-usar-em-producao")
    token = create_access_token("usuario@example.com")
    payload = decode_access_token(token)
    assert payload["sub"] == "usuario@example.com"
    assert "exp" in payload and "iat" in payload


def test_jwt_expirado_e_rejeitado(monkeypatch):
    monkeypatch.setenv("JWT_SECRET_KEY", "segredo-de-teste-nao-usar-em-producao")
    token = create_access_token("usuario@example.com", expires_delta=timedelta(seconds=-1))
    with pytest.raises(jwt.ExpiredSignatureError):
        decode_access_token(token)


def test_jwt_adulterado_e_rejeitado(monkeypatch):
    monkeypatch.setenv("JWT_SECRET_KEY", "segredo-de-teste-nao-usar-em-producao")
    token = create_access_token("usuario@example.com")
    # Adultera o último caractere da assinatura.
    adulterado = token[:-1] + ("A" if token[-1] != "A" else "B")
    with pytest.raises(jwt.InvalidTokenError):
        decode_access_token(adulterado)


def test_jwt_assinado_com_outro_segredo_e_rejeitado(monkeypatch):
    monkeypatch.setenv("JWT_SECRET_KEY", "segredo-A")
    token = create_access_token("usuario@example.com")

    monkeypatch.setenv("JWT_SECRET_KEY", "segredo-B")
    with pytest.raises(jwt.InvalidTokenError):
        decode_access_token(token)


def test_jwt_sem_secret_key_falha_ao_criar(monkeypatch):
    monkeypatch.delenv("JWT_SECRET_KEY", raising=False)
    with pytest.raises(MissingSecretKeyError):
        create_access_token("usuario@example.com")


def test_jwt_sem_secret_key_falha_ao_decodificar(monkeypatch):
    # Emite o token com a chave presente, depois a remove: decode_access_token
    # não deve silenciosamente aceitar nem cair para nenhum segredo padrão.
    monkeypatch.setenv("JWT_SECRET_KEY", "segredo-de-teste-nao-usar-em-producao")
    token = create_access_token("usuario@example.com")

    monkeypatch.delenv("JWT_SECRET_KEY", raising=False)
    with pytest.raises(MissingSecretKeyError):
        decode_access_token(token)


def test_jwt_expiracao_padrao_eh_usada_quando_nao_especificada(monkeypatch):
    monkeypatch.setenv("JWT_SECRET_KEY", "segredo-de-teste-nao-usar-em-producao")
    antes = time.time()
    token = create_access_token("usuario@example.com")
    payload = decode_access_token(token)
    # DEFAULT_EXPIRES_DELTA = 30 min — margem generosa para não ser flaky.
    assert 29 * 60 < (payload["exp"] - antes) <= 30 * 60 + 5


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
