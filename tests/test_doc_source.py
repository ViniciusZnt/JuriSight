"""DocumentSource fecha a conexão ao fim da iteração e também quando ela para antes (`break`)."""
from indexing import doc_source
from indexing.doc_source import DocumentSource


class _Cursor:
    itersize = 0

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def execute(self, *a):
        pass

    def __iter__(self):
        return iter([("u1",), ("u2",), ("u3",)])


class _Conn:
    fechada = False

    def cursor(self, name=None):
        return _Cursor()

    def __enter__(self):
        return self

    def __exit__(self, *a):
        self.fechada = True


def _fonte(monkeypatch):
    conexoes = []
    monkeypatch.setattr(doc_source.psycopg, "connect", lambda url: conexoes.append(_Conn()) or conexoes[-1])
    fonte = DocumentSource("postgresql://x")
    monkeypatch.setattr(fonte, "_row_to_documento", lambda row: row[0])
    return fonte, conexoes


def test_fecha_a_conexao_ao_esgotar(monkeypatch):
    fonte, conexoes = _fonte(monkeypatch)
    assert [u for u, _ in fonte.iter_documents()] == ["u1", "u2", "u3"]
    assert conexoes[0].fechada


def test_fecha_a_conexao_quando_para_antes(monkeypatch):
    fonte, conexoes = _fonte(monkeypatch)
    gerador = fonte.iter_documents()
    next(gerador)
    gerador.close()  # o que o `break` de `--limit` provoca
    assert conexoes[0].fechada
