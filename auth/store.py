"""
Acesso a `auth.usuarios` (CRUD de usuários) — camada de persistência para a
peça de endpoints FastAPI (`query/api/auth_routes.py`).

Continua a mesma convenção de `query/search/doc_retriever.py`: psycopg puro,
sem ORM, conecta/cursora/fecha a cada chamada (nenhuma conexão persistente
mantida entre requisições). `auth/db.py` já é quem cria o schema; este módulo
só lê/escreve linhas nele.

Deliberadamente sem nenhum import de FastAPI/Pydantic — mesma fronteira que
`auth/password.py` e `auth/tokens.py` já seguem (funções/classes puras,
importáveis por qualquer camada HTTP que exista por cima). A camada HTTP
decide o mapeamento de `EmailJaCadastradoError` para um HTTPException.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime

import psycopg


@dataclass(frozen=True)
class Usuario:
    """Uma linha de `auth.usuarios`. `hashed_password` NUNCA deve vazar para
    fora da camada de autenticação (a peça de endpoints projeta isso para um
    modelo público antes de devolver via HTTP)."""

    id: uuid.UUID
    email: str
    hashed_password: str
    nome: str | None
    is_active: bool
    criado_em: datetime


class EmailJaCadastradoError(Exception):
    """Levantado por `UsuarioStore.create` quando o e-mail já existe.

    Não distingue "já existia antes do INSERT" de "outra requisição inseriu o
    mesmo e-mail entre nosso pré-check e nosso INSERT" — de propósito: ver
    docstring de `UsuarioStore.create` para o porquê disso importar (evitar
    condição de corrida).
    """


_SELECT_COLUNAS = "id, email, hashed_password, nome, is_active, criado_em"

_SELECT_BY_EMAIL = f"""
SELECT {_SELECT_COLUNAS} FROM auth.usuarios WHERE lower(email) = lower(%s)
"""

_SELECT_BY_ID = f"""
SELECT {_SELECT_COLUNAS} FROM auth.usuarios WHERE id = %s
"""

_INSERT = f"""
INSERT INTO auth.usuarios (email, hashed_password, nome)
VALUES (%s, %s, %s)
RETURNING {_SELECT_COLUNAS}
"""

_UPDATE_HASHED_PASSWORD = """
UPDATE auth.usuarios SET hashed_password = %s, atualizado_em = NOW() WHERE id = %s
"""


def _row_para_usuario(row) -> Usuario:
    return Usuario(
        id=row[0],
        email=row[1],
        hashed_password=row[2],
        nome=row[3],
        is_active=row[4],
        criado_em=row[5],
    )


class UsuarioStore:
    """CRUD de `auth.usuarios` via psycopg. Uma conexão nova por chamada,
    igual a `DocRetriever` — este é um serviço de baixo tráfego (registro/
    login/me), não vale a complexidade de um pool aqui."""

    def __init__(self, database_url: str) -> None:
        self.database_url = database_url

    def create(self, *, email: str, hashed_password: str, nome: str | None) -> Usuario:
        """Insere um novo usuário. Levanta `EmailJaCadastradoError` se o
        e-mail (case-insensitive) já existir.

        Deliberadamente NÃO faz um SELECT de pré-checagem antes do INSERT:
        duas requisições de registro simultâneas com o mesmo e-mail
        passariam ambas por um pré-check "não existe" antes que qualquer uma
        tivesse commitado (TOCTOU) — o índice único `usuarios_email_lower_idx`
        (auth/db.py) só é verificado pelo Postgres no INSERT em si, então
        confiamos NELE como a fonte de verdade: tentamos o INSERT direto e
        traduzimos a `UniqueViolation` que o Postgres levanta (atomicamente,
        sem essa janela de corrida) para `EmailJaCadastradoError`.
        """
        email = email.strip()
        conn = psycopg.connect(self.database_url)
        try:
            try:
                with conn.cursor() as cur:
                    cur.execute(_INSERT, (email, hashed_password, nome))
                    row = cur.fetchone()
                conn.commit()
            except psycopg.errors.UniqueViolation:
                conn.rollback()
                raise EmailJaCadastradoError(email) from None
        finally:
            conn.close()
        return _row_para_usuario(row)

    def get_by_email(self, email: str) -> Usuario | None:
        conn = psycopg.connect(self.database_url)
        try:
            with conn.cursor() as cur:
                cur.execute(_SELECT_BY_EMAIL, (email.strip(),))
                row = cur.fetchone()
        finally:
            conn.close()
        return _row_para_usuario(row) if row else None

    def get_by_id(self, usuario_id: str) -> Usuario | None:
        conn = psycopg.connect(self.database_url)
        try:
            with conn.cursor() as cur:
                cur.execute(_SELECT_BY_ID, (usuario_id,))
                row = cur.fetchone()
        finally:
            conn.close()
        return _row_para_usuario(row) if row else None

    def update_hashed_password(self, usuario_id: uuid.UUID, novo_hash: str) -> None:
        """Persiste um hash re-calculado (rehash-on-verify, ver
        `auth/password.py::verify_password`) — chamado no login quando o hash
        armazenado usava parâmetros/algoritmo desatualizados."""
        conn = psycopg.connect(self.database_url)
        try:
            with conn.cursor() as cur:
                cur.execute(_UPDATE_HASHED_PASSWORD, (novo_hash, usuario_id))
            conn.commit()
        finally:
            conn.close()
