"""DocRetriever.fetch não guarda estado na instância (ela é compartilhada entre threads)."""
from query.search import doc_retriever
from query.search.doc_retriever import DocRetriever


class _Cursor:
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def execute(self, *a):
        pass

    def fetchall(self):
        return []


class _Conn:
    def __init__(self):
        self.fechada = False

    def cursor(self):
        return _Cursor()

    def close(self):
        self.fechada = True


def test_fetch_usa_conexao_local_e_fecha(monkeypatch):
    conexoes = []

    def _connect(url):
        conexoes.append(_Conn())
        return conexoes[-1]

    monkeypatch.setattr(doc_retriever.psycopg, "connect", _connect)
    r = DocRetriever("postgresql://x")
    estado_antes = dict(vars(r))

    assert r.fetch(["a"]) == {}
    assert r.fetch(["b"]) == {}

    assert vars(r) == estado_antes  # nenhuma conexão pendurada na instância
    assert len(conexoes) == 2 and all(c.fechada for c in conexoes)
