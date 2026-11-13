"""Fakes e fábricas compartilhados pelos testes (nenhuma infra real)."""
import uuid
from datetime import datetime, timezone
from types import SimpleNamespace

from auth.store import Usuario
from scraper.schema import DocumentoJuridico, Provimento, TipoDocumento


class FakeReranker:
    """Passthrough: scores estritamente decrescentes na ordem de entrada, então o
    sort por score não muda a ordem que já veio do (fake) RRF."""

    def rerank_scores(self, query: str, passagens: list[str]) -> list[float]:
        return [1.0 - i * 0.01 for i in range(len(passagens))]


class FakeDocRetriever:
    def __init__(self, docs: dict[str, DocumentoJuridico]):
        self._docs = docs

    def fetch(self, ids, completo=True):
        return {i: self._docs[i] for i in ids if i in self._docs}


class FakeOpenAI:
    """client.chat.completions.parse devolvendo `parsed` (ou levantando `erro`)."""

    def __init__(self, parsed=None, erro: Exception | None = None):
        self.chamadas: list[dict] = []
        self.chat = SimpleNamespace(completions=SimpleNamespace(parse=self._parse))
        self._parsed = parsed
        self._erro = erro

    def _parse(self, **kwargs):
        self.chamadas.append(kwargs)
        if self._erro:
            raise self._erro
        msg = SimpleNamespace(parsed=self._parsed, refusal=None)
        return SimpleNamespace(choices=[SimpleNamespace(message=msg)])


def documento_fake(**kwargs) -> DocumentoJuridico:
    base = dict(
        id_documento="x",
        tipo_documento=TipoDocumento.ACORDAO,
        hierarquia_categoria=4,
        numero_processo="RR-1-2021",
        tribunal="TST",
        relator="Min. Fulano",
        ementa="Ementa.",
        provimento=Provimento.APROVADO,
    )
    base.update(kwargs)
    return DocumentoJuridico(**base)


def usuario_fake(email: str = "a@example.com", nome: str = "A") -> Usuario:
    return Usuario(
        id=uuid.uuid4(), email=email, hashed_password="x",
        nome=nome, is_active=True, criado_em=datetime.now(timezone.utc),
    )
