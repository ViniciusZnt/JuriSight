"""
Testes de POST /auth/registro, POST /auth/login, POST /auth/logout e
GET /auth/me (query/api/auth_routes.py).

Mesmo espírito de tests/test_api.py: nenhuma infra real (Postgres) é usada —
`UsuarioStore` é substituído por `_FakeUsuarioStore` (em memória) via
`app.dependency_overrides[get_usuario_store]`, igual a `_FakeDocRetriever`
naquele arquivo. Como `auth_routes.router` não está montado no `app` de
query/api/app.py (isso é integração futura, fora do escopo desta peça),
criamos aqui um FastAPI() mínimo só com esse router — TestClient não precisa
do lifespan real (Qdrant/Ollama/Postgres) do app principal.

JWT_SECRET_KEY é setada via fixture autouse (monkeypatch), igual ao padrão
de tests/test_auth.py.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import query.api.auth_routes as auth_routes
from auth.password import DUMMY_HASH, hash_password
from auth.store import EmailJaCadastradoError, Usuario
from auth.tokens import create_access_token
from query.api.auth_routes import ACCESS_TOKEN_COOKIE_NAME, get_usuario_store, router


class _FakeUsuarioStore:
    """Substitui UsuarioStore — dict em memória, mesma interface pública."""

    def __init__(self) -> None:
        self._por_id: dict[str, Usuario] = {}

    def create(self, *, email: str, hashed_password: str, nome: str | None) -> Usuario:
        email = email.strip()
        if any(u.email.lower() == email.lower() for u in self._por_id.values()):
            raise EmailJaCadastradoError(email)
        usuario = Usuario(
            id=uuid.uuid4(),
            email=email,
            hashed_password=hashed_password,
            nome=nome,
            is_active=True,
            criado_em=datetime.now(timezone.utc),
        )
        self._por_id[str(usuario.id)] = usuario
        return usuario

    def get_by_email(self, email: str) -> Usuario | None:
        email = email.strip().lower()
        for u in self._por_id.values():
            if u.email.lower() == email:
                return u
        return None

    def get_by_id(self, usuario_id: str) -> Usuario | None:
        return self._por_id.get(str(usuario_id))

    def update_hashed_password(self, usuario_id, novo_hash: str) -> None:
        usuario = self._por_id[str(usuario_id)]
        self._por_id[str(usuario_id)] = usuario.__class__(
            id=usuario.id,
            email=usuario.email,
            hashed_password=novo_hash,
            nome=usuario.nome,
            is_active=usuario.is_active,
            criado_em=usuario.criado_em,
        )

    # Helper só de teste (não existe em UsuarioStore real).
    def inserir_direto(self, usuario: Usuario) -> None:
        self._por_id[str(usuario.id)] = usuario

    def desativar(self, usuario_id) -> None:
        usuario = self._por_id[str(usuario_id)]
        self._por_id[str(usuario_id)] = usuario.__class__(
            id=usuario.id,
            email=usuario.email,
            hashed_password=usuario.hashed_password,
            nome=usuario.nome,
            is_active=False,
            criado_em=usuario.criado_em,
        )


@pytest.fixture(autouse=True)
def _jwt_secret(monkeypatch):
    monkeypatch.setenv("JWT_SECRET_KEY", "segredo-de-teste-nao-usar-em-producao")


@pytest.fixture
def store() -> _FakeUsuarioStore:
    return _FakeUsuarioStore()


@pytest.fixture
def client(store: _FakeUsuarioStore) -> TestClient:
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_usuario_store] = lambda: store
    client = TestClient(app)
    # POST/registro/login/logout exigem X-Requested-With (defesa em profundidade
    # contra CSRF, ver auth_routes._exigir_header_csrf) — setado aqui uma vez
    # para todo o client, já que é o comportamento normal de um frontend real
    # (fetch/XHR same-origin), não algo que cada teste deva repetir.
    client.headers.update({"X-Requested-With": "XMLHttpRequest"})
    return client


# --------------------------------------------------------------------------- #
# POST /auth/registro                                                         #
# --------------------------------------------------------------------------- #

def test_registro_sucesso_nao_devolve_hash(client: TestClient):
    resp = client.post(
        "/auth/registro",
        json={"email": "ana@example.com", "password": "senha-forte-123", "nome": "Ana"},
    )

    assert resp.status_code == 201
    body = resp.json()
    assert body["email"] == "ana@example.com"
    assert body["nome"] == "Ana"
    assert body["is_active"] is True
    assert "id" in body and "hashed_password" not in body and "password" not in body


def test_registro_senha_curta_422(client: TestClient):
    resp = client.post("/auth/registro", json={"email": "ana@example.com", "password": "curta"})
    assert resp.status_code == 422


def test_registro_email_invalido_422(client: TestClient):
    resp = client.post("/auth/registro", json={"email": "nao-e-email", "password": "senha-forte-123"})
    assert resp.status_code == 422


def test_registro_sem_header_csrf_e_rejeitado_403(client: TestClient):
    # Regressão: um POST cross-site "simples" (via <form>, sem preflight) não
    # consegue setar X-Requested-With — só um fetch/XHR same-origin (ou de uma
    # origem já autorizada pelo CORS) consegue. Simula esse ataque removendo o
    # header que o fixture `client` normalmente injeta.
    resp = client.post(
        "/auth/registro",
        json={"email": "sem-header@example.com", "password": "senha-forte-123"},
        headers={"X-Requested-With": ""},
    )
    assert resp.status_code == 403


def test_registro_email_duplicado_409(client: TestClient):
    client.post("/auth/registro", json={"email": "dup@example.com", "password": "senha-forte-123"})

    # Mesmo e-mail, capitalização diferente — a checagem é case-insensitive,
    # igual ao índice `usuarios_email_lower_idx` de auth/db.py.
    resp = client.post("/auth/registro", json={"email": "DUP@example.com", "password": "outra-senha-123"})

    assert resp.status_code == 409
    assert "cadastrado" in resp.json()["detail"].lower()


# --------------------------------------------------------------------------- #
# POST /auth/login                                                             #
# --------------------------------------------------------------------------- #

def test_login_sucesso_seta_cookie_httponly_e_nao_devolve_token_no_corpo(client: TestClient):
    client.post(
        "/auth/registro",
        json={"email": "login@example.com", "password": "senha-forte-123", "nome": "Login"},
    )

    resp = client.post("/auth/login", json={"email": "login@example.com", "password": "senha-forte-123"})

    assert resp.status_code == 200
    body = resp.json()
    assert body["email"] == "login@example.com"
    assert "access_token" not in body and "token" not in body

    cookie = resp.cookies.get(ACCESS_TOKEN_COOKIE_NAME)
    assert cookie is not None
    set_cookie_header = resp.headers.get("set-cookie", "")
    assert "httponly" in set_cookie_header.lower()
    assert "samesite=lax" in set_cookie_header.lower()


def test_login_senha_errada_401(client: TestClient):
    client.post("/auth/registro", json={"email": "senha@example.com", "password": "senha-forte-123"})

    resp = client.post("/auth/login", json={"email": "senha@example.com", "password": "senha-errada-123"})

    assert resp.status_code == 401
    assert ACCESS_TOKEN_COOKIE_NAME not in resp.cookies


def test_login_usuario_inexistente_401_e_paga_custo_dummy_hash(client: TestClient, monkeypatch):
    chamadas: list[str] = []
    original_verify = auth_routes.verify_password

    def _verify_espiao(plain, hashed):
        chamadas.append(hashed)
        return original_verify(plain, hashed)

    monkeypatch.setattr(auth_routes, "verify_password", _verify_espiao)

    resp = client.post("/auth/login", json={"email": "nao-existe@example.com", "password": "qualquer-coisa"})

    assert resp.status_code == 401
    # Prova que o caminho de "usuário não encontrado" ainda chama
    # verify_password contra o DUMMY_HASH (mitigação de timing attack de
    # auth/password.py), em vez de retornar imediatamente sem pagar o custo.
    assert chamadas == [DUMMY_HASH]


def test_login_usuario_inativo_403(client: TestClient, store: _FakeUsuarioStore):
    resp = client.post("/auth/registro", json={"email": "inativo@example.com", "password": "senha-forte-123"})
    usuario_id = resp.json()["id"]
    store.desativar(usuario_id)

    resp = client.post("/auth/login", json={"email": "inativo@example.com", "password": "senha-forte-123"})

    assert resp.status_code == 403


# --------------------------------------------------------------------------- #
# POST /auth/logout                                                           #
# --------------------------------------------------------------------------- #

def test_logout_limpa_cookie(client: TestClient):
    client.post("/auth/registro", json={"email": "logout@example.com", "password": "senha-forte-123"})
    client.post("/auth/login", json={"email": "logout@example.com", "password": "senha-forte-123"})
    assert client.cookies.get(ACCESS_TOKEN_COOKIE_NAME) is not None

    resp = client.post("/auth/logout")

    assert resp.status_code == 204
    # TestClient aplica o Set-Cookie de expiração no seu próprio jar.
    assert not client.cookies.get(ACCESS_TOKEN_COOKIE_NAME)


# --------------------------------------------------------------------------- #
# GET /auth/me                                                                 #
# --------------------------------------------------------------------------- #

def test_me_com_cookie_valido(client: TestClient):
    client.post(
        "/auth/registro",
        json={"email": "me@example.com", "password": "senha-forte-123", "nome": "Eu Mesmo"},
    )
    client.post("/auth/login", json={"email": "me@example.com", "password": "senha-forte-123"})

    resp = client.get("/auth/me")

    assert resp.status_code == 200
    assert resp.json()["email"] == "me@example.com"
    assert resp.json()["nome"] == "Eu Mesmo"


def test_me_sem_cookie_401(client: TestClient):
    resp = client.get("/auth/me")
    assert resp.status_code == 401


def test_me_cookie_invalido_401(client: TestClient):
    client.cookies.set(ACCESS_TOKEN_COOKIE_NAME, "token-adulterado-nao-e-um-jwt-valido")
    resp = client.get("/auth/me")
    assert resp.status_code == 401


def test_me_cookie_expirado_401(client: TestClient):
    token_expirado = create_access_token("algum-id", expires_delta=timedelta(seconds=-1))
    client.cookies.set(ACCESS_TOKEN_COOKIE_NAME, token_expirado)

    resp = client.get("/auth/me")

    assert resp.status_code == 401
    assert "expirad" in resp.json()["detail"].lower()


def test_me_usuario_nao_existe_mais_401(client: TestClient):
    # Token válido (assinatura ok), mas o "sub" não corresponde a nenhum
    # usuário no store (ex.: usuário deletado após o token ser emitido).
    token = create_access_token(str(uuid.uuid4()))
    client.cookies.set(ACCESS_TOKEN_COOKIE_NAME, token)

    resp = client.get("/auth/me")

    assert resp.status_code == 401


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
