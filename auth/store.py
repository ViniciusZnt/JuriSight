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
    # Perfil (issue #15): opcionais, preenchidos na aba Perfil das configurações.
    telefone: str | None = None
    oab: str | None = None
    papel: str | None = None


class EmailJaCadastradoError(Exception):
    """Levantado por `UsuarioStore.create` quando o e-mail já existe.

    Não distingue "já existia antes do INSERT" de "outra requisição inseriu o
    mesmo e-mail entre nosso pré-check e nosso INSERT" — de propósito: ver
    docstring de `UsuarioStore.create` para o porquê disso importar (evitar
    condição de corrida).
    """


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

    def update_perfil(
        self, usuario_id: uuid.UUID, *, telefone: str | None, oab: str | None, papel: str | None
    ) -> Usuario:
        """Grava telefone, OAB e papel; devolve o usuário atualizado."""
        conn = psycopg.connect(self.database_url)
        try:
            with conn.cursor() as cur:
                cur.execute(_UPDATE_PERFIL, (telefone, oab, papel, usuario_id))
                row = cur.fetchone()
            conn.commit()
        finally:
            conn.close()
        return _row_para_usuario(row)

    def criar_redefinicao(self, usuario_id: uuid.UUID, token_hash: str, expira_em: datetime) -> bool:
        """Registra um link de redefinição. False se a conta já pediu um no último minuto."""
        conn = psycopg.connect(self.database_url)
        try:
            with conn.cursor() as cur:
                cur.execute(_INSERT_REDEFINICAO, (usuario_id, token_hash, expira_em, usuario_id))
                criado = cur.rowcount == 1
            conn.commit()
        finally:
            conn.close()
        return criado

    def consumir_redefinicao(self, token_hash: str) -> uuid.UUID | None:
        """Usa o link (se existe, não expirou e não foi usado) e invalida os outros links abertos
        da mesma conta. Devolve o id da conta, ou None."""
        conn = psycopg.connect(self.database_url)
        try:
            with conn.cursor() as cur:
                cur.execute(_CONSUMIR_REDEFINICAO, (token_hash,))
                row = cur.fetchone()
                if row is not None:
                    cur.execute(_INVALIDAR_REDEFINICOES, (row[0],))
            conn.commit()
        finally:
            conn.close()
        return row[0] if row else None

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
