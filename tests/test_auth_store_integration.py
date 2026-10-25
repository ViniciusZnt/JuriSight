"""
Testes de integração de auth/store.py contra um Postgres DE VERDADE.

Diferente do resto da suíte (tests/test_auth.py, tests/test_auth_routes.py),
que roda 100% mockado/em memória — este arquivo existe especificamente porque
UsuarioStore.create() faz uma alegação de segurança que só é verdade contra o
Postgres real: que a condição de corrida de dois cadastros simultâneos com o
mesmo e-mail é fechada pelo índice único do banco (`usuarios_email_lower_idx`,
auth/db.py), não por uma pré-checagem em Python (que teria uma janela TOCTOU).
Um fake em memória não consegue provar isso — só o banco real pode.

Requer DATABASE_URL apontando para um Postgres no ar; roda `auth.db.ensure_schema()`
antes de cada teste (idempotente, só cria o schema/tabela/índice se não existirem)
e limpa só as linhas que ele mesmo inseriu ao final (nunca faz DROP/TRUNCATE —
essa tabela pode ter dados de outros testes/uso manual rodando em paralelo).

Pulado automaticamente se DATABASE_URL não estiver definida ou o Postgres não
responder — mesmo espírito de tests/test_api_stress.py (só roda contra infra
real, sob demanda), não faz parte do `uv run pytest` "padrão" que o resto da
suíte espera rodar sem nenhuma infra.
"""
from __future__ import annotations

import os
import uuid
from concurrent.futures import ThreadPoolExecutor

import psycopg
import pytest

from auth.db import ensure_schema
from auth.store import EmailJaCadastradoError, UsuarioStore

DATABASE_URL = os.getenv("DATABASE_URL")


def _postgres_disponivel() -> bool:
    if not DATABASE_URL:
        return False
    try:
        psycopg.connect(DATABASE_URL, connect_timeout=2).close()
        return True
    except psycopg.OperationalError:
        return False


pytestmark = pytest.mark.skipif(
    not _postgres_disponivel(),
    reason="Requer DATABASE_URL apontando para um Postgres real e acessível.",
)


@pytest.fixture(autouse=True)
def _schema_pronto():
    ensure_schema(DATABASE_URL)


@pytest.fixture
def store() -> UsuarioStore:
    return UsuarioStore(DATABASE_URL)


def _email_unico(prefixo: str) -> str:
    # UUID no e-mail garante que testes rodando em paralelo/repetidos nunca
    # colidem entre si nem com dados reais deixados na tabela.
    return f"{prefixo}-{uuid.uuid4().hex}@teste-integracao.invalid"


def _limpar(email: str) -> None:
    conn = psycopg.connect(DATABASE_URL)
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM auth.usuarios WHERE lower(email) = lower(%s)", (email,))
        conn.commit()
    finally:
        conn.close()


def test_create_e_get_by_email_round_trip(store: UsuarioStore):
    email = _email_unico("roundtrip")
    try:
        criado = store.create(email=email, hashed_password="hash-fake-de-teste", nome="Teste")
        assert criado.email == email
        assert criado.is_active is True

        encontrado = store.get_by_email(email)
        assert encontrado is not None
        assert encontrado.id == criado.id
        assert encontrado.hashed_password == "hash-fake-de-teste"
    finally:
        _limpar(email)


def test_get_by_email_e_case_insensitive_contra_o_indice_real(store: UsuarioStore):
    email = _email_unico("CaseTest")
    try:
        store.create(email=email, hashed_password="hash", nome=None)
        # Busca com capitalização diferente — prova que usuarios_email_lower_idx
        # (auth/db.py) está sendo usado corretamente por _SELECT_BY_EMAIL.
        assert store.get_by_email(email.upper()) is not None
        assert store.get_by_email(email.lower()) is not None
    finally:
        _limpar(email)


def test_create_email_duplicado_levanta_erro_contra_indice_real(store: UsuarioStore):
    email = _email_unico("dup")
    try:
        store.create(email=email, hashed_password="hash1", nome=None)
        with pytest.raises(EmailJaCadastradoError):
            store.create(email=email.upper(), hashed_password="hash2", nome=None)
    finally:
        _limpar(email)


def test_email_com_espaco_e_rejeitado_pelo_check_constraint_no_banco():
    # auth/db.py: CONSTRAINT usuarios_email_trimmed CHECK (email = btrim(email) ...).
    # UsuarioStore.create() já faz .strip() em Python antes do INSERT (por
    # isso este teste não chama store.create() — ele nunca deixaria um espaço
    # chegar ao banco). O CHECK existe como rede de segurança NO BANCO,
    # independente da camada Python — este teste faz um INSERT bruto via
    # psycopg, ignorando store.py de propósito, pra provar que o banco em si
    # rejeita, e não só a aplicação.
    email_com_espaco = "  " + _email_unico("espaco")
    conn = psycopg.connect(DATABASE_URL)
    try:
        with pytest.raises(psycopg.errors.CheckViolation):
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO auth.usuarios (email, hashed_password) VALUES (%s, %s)",
                    (email_com_espaco, "hash"),
                )
    finally:
        conn.rollback()
        conn.close()


def test_cadastros_concorrentes_mesmo_email_so_um_sucede(store: UsuarioStore):
    """A alegação central de UsuarioStore.create(): sem pré-checagem em Python,
    o índice único do Postgres é a única linha de defesa contra a corrida —
    e ele é atômico. 10 threads tentam cadastrar o MESMO e-mail ao mesmo
    tempo; exatamente uma deve suceder, as outras nove devem levantar
    EmailJaCadastradoError (nunca uma exceção diferente/inesperada)."""
    email = _email_unico("race")
    n = 10
    try:
        def _tentar_cadastrar(i: int) -> str:
            try:
                store.create(email=email, hashed_password=f"hash-{i}", nome=None)
                return "sucesso"
            except EmailJaCadastradoError:
                return "duplicado"

        with ThreadPoolExecutor(max_workers=n) as executor:
            resultados = list(executor.map(_tentar_cadastrar, range(n)))

        assert resultados.count("sucesso") == 1
        assert resultados.count("duplicado") == n - 1

        # Confirma que só existe UMA linha no banco pra esse e-mail — a
        # corrida não deixou duas linhas "quase simultâneas" passarem.
        conn = psycopg.connect(DATABASE_URL)
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT count(*) FROM auth.usuarios WHERE lower(email) = lower(%s)", (email,))
                (total,) = cur.fetchone()
        finally:
            conn.close()
        assert total == 1
    finally:
        _limpar(email)


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
