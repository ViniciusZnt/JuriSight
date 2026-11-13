"""
Acesso a `auth.usuarios` e `auth.redefinicoes_senha`, em psycopg puro (conecta,
usa e fecha a cada chamada), sem FastAPI/Pydantic. A camada HTTP mapeia
`EmailJaCadastradoError` para 409.
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
    # Perfil (issue #15): opcionais, preenchidos na aba Perfil das configurações.
    telefone: str | None = None
    oab: str | None = None
    papel: str | None = None


class EmailJaCadastradoError(Exception):
    """Levantado por `UsuarioStore.create` quando o e-mail já existe (ver o porquê em `create`)."""


_SELECT_COLUNAS = "id, email, hashed_password, nome, is_active, criado_em, telefone, oab, papel"

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

_UPDATE_PERFIL = f"""
UPDATE auth.usuarios SET telefone = %s, oab = %s, papel = %s, atualizado_em = NOW() WHERE id = %s
RETURNING {_SELECT_COLUNAS}
"""

# No máximo um link por minuto por conta: evita que alguém lote a caixa de outra pessoa.
_INSERT_REDEFINICAO = """
INSERT INTO auth.redefinicoes_senha (usuario_id, token_hash, expira_em)
SELECT %s, %s, %s
WHERE NOT EXISTS (
    SELECT 1 FROM auth.redefinicoes_senha
    WHERE usuario_id = %s AND criado_em > NOW() - INTERVAL '1 minute'
)
"""

_CONSUMIR_REDEFINICAO = """
UPDATE auth.redefinicoes_senha SET usado_em = NOW()
WHERE token_hash = %s AND usado_em IS NULL AND expira_em > NOW()
RETURNING usuario_id
"""

_INVALIDAR_REDEFINICOES = """
UPDATE auth.redefinicoes_senha SET usado_em = NOW() WHERE usuario_id = %s AND usado_em IS NULL
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
        telefone=row[6],
        oab=row[7],
        papel=row[8],
    )


class UsuarioStore:
    """CRUD de `auth.usuarios`. Uma conexão por chamada: o tráfego é baixo demais para um pool."""

    def __init__(self, database_url: str) -> None:
        self.database_url = database_url

    def create(self, *, email: str, hashed_password: str, nome: str | None) -> Usuario:
        """Insere um novo usuário. Levanta `EmailJaCadastradoError` se o e-mail
        (sem diferenciar maiúsculas) já existir.

        Sem `SELECT` de pré-checagem: duas requisições simultâneas passariam as
        duas por ela (TOCTOU). A fonte de verdade é o índice único
        `usuarios_email_lower_idx`; tentamos o INSERT e traduzimos a `UniqueViolation`.
        """
        email = email.strip()
        try:
            with psycopg.connect(self.database_url) as conn, conn.cursor() as cur:
                cur.execute(_INSERT, (email, hashed_password, nome))
                row = cur.fetchone()
        except psycopg.errors.UniqueViolation:
            raise EmailJaCadastradoError(email) from None
        return _row_para_usuario(row)

    def get_by_email(self, email: str) -> Usuario | None:
        with psycopg.connect(self.database_url) as conn, conn.cursor() as cur:
            cur.execute(_SELECT_BY_EMAIL, (email.strip(),))
            row = cur.fetchone()
        return _row_para_usuario(row) if row else None

    def get_by_id(self, usuario_id: str) -> Usuario | None:
        with psycopg.connect(self.database_url) as conn, conn.cursor() as cur:
            cur.execute(_SELECT_BY_ID, (usuario_id,))
            row = cur.fetchone()
        return _row_para_usuario(row) if row else None

    def update_perfil(
        self, usuario_id: uuid.UUID, *, telefone: str | None, oab: str | None, papel: str | None
    ) -> Usuario:
        """Grava telefone, OAB e papel; devolve o usuário atualizado."""
        with psycopg.connect(self.database_url) as conn, conn.cursor() as cur:
            cur.execute(_UPDATE_PERFIL, (telefone, oab, papel, usuario_id))
            row = cur.fetchone()
        return _row_para_usuario(row)

    def criar_redefinicao(self, usuario_id: uuid.UUID, token_hash: str, expira_em: datetime) -> bool:
        """Registra um link de redefinição. False se a conta já pediu um no último minuto."""
        with psycopg.connect(self.database_url) as conn, conn.cursor() as cur:
            cur.execute(_INSERT_REDEFINICAO, (usuario_id, token_hash, expira_em, usuario_id))
            criado = cur.rowcount == 1
        return criado

    def consumir_redefinicao(self, token_hash: str) -> uuid.UUID | None:
        """Usa o link (se existe, não expirou e não foi usado) e invalida os outros links abertos
        da mesma conta. Devolve o id da conta, ou None."""
        with psycopg.connect(self.database_url) as conn, conn.cursor() as cur:
            cur.execute(_CONSUMIR_REDEFINICAO, (token_hash,))
            row = cur.fetchone()
            if row is not None:
                cur.execute(_INVALIDAR_REDEFINICOES, (row[0],))
        return row[0] if row else None

    def update_hashed_password(self, usuario_id: uuid.UUID, novo_hash: str) -> None:
        """Persiste um hash re-calculado (rehash-on-verify, ver
        `auth/password.py::verify_password`) — chamado no login quando o hash
        armazenado usava parâmetros/algoritmo desatualizados."""
        with psycopg.connect(self.database_url) as conn, conn.cursor() as cur:
            cur.execute(_UPDATE_HASHED_PASSWORD, (novo_hash, usuario_id))
