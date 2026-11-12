"""Etapas do pipeline como funções chamáveis (scraper, indexação, filtros), sem infra real."""
import os
import uuid
from datetime import date

import psycopg
import pytest

import indexing.run as indexing_run
import scraper.run as scraper_run
from query.filtros.preparar import preparar


class _FakeWriter:
    def __init__(self, *a, **k):
        self.fechado = False

    def connect(self): pass
    def close(self): self.fechado = True
    def get_last_collected_date(self): return None
    def find_all_gaps(self, a, b): return []


def _patch_scraper(monkeypatch, resultado):
    monkeypatch.setattr(scraper_run, "PostgresWriter", _FakeWriter)
    monkeypatch.setattr(scraper_run, "WebScraper", lambda: object())
    monkeypatch.setattr(scraper_run, "DbStateStore", lambda w, c: object())

    class _Orch:
        def __init__(self, **k): pass
        def run(self, inicio, fim): return dict(resultado)

    monkeypatch.setattr(scraper_run, "Orchestrator", _Orch)


def test_coletar_devolve_resultado(monkeypatch):
    _patch_scraper(monkeypatch, {"completed": True, "documents_saved": 7, "requests_made": 3})
    r = scraper_run.coletar(date(2025, 1, 1), date(2025, 1, 2))
    assert r["completed"] is True and r["documents_saved"] == 7
    assert r["inicio"] == "2025-01-01" and r["fim"] == "2025-01-02"


def test_coletar_interrompida_nao_levanta(monkeypatch):
    _patch_scraper(monkeypatch, {"completed": False, "documents_saved": 1, "requests_made": 1,
                                 "halt_reason": "blocked", "halt_message": "x"})
    r = scraper_run.coletar(date(2025, 1, 1), date(2025, 1, 2))
    assert r["completed"] is False and r["halt_reason"] == "blocked"


def test_coletar_sem_nada_a_coletar(monkeypatch):
    _patch_scraper(monkeypatch, {})
    r = scraper_run.coletar(date(2025, 1, 5), date(2025, 1, 2))
    assert r["completed"] is True and r["documents_saved"] == 0


def test_main_do_scraper_sai_com_2_quando_interrompida(monkeypatch, capsys):
    monkeypatch.setattr("sys.argv", ["run.py"])
    monkeypatch.setattr(scraper_run, "coletar", lambda *a, **k: {
        "completed": False, "documents_saved": 0, "requests_made": 1,
        "inicio": "2025-01-01", "fim": "2025-01-02", "halt_reason": "blocked", "halt_message": "x"})
    with pytest.raises(SystemExit) as e:
        scraper_run.main()
    assert e.value.code == 2
    assert "blocked" in capsys.readouterr().out


def test_indexar_devolve_contagens(monkeypatch):
    class _Fonte:
        def __init__(self, *a): pass
        def iter_documents(self): return iter(())

    class _Store:
        def __init__(self, *a): pass
        def documento_ids_indexados(self): return set()

    monkeypatch.setattr(indexing_run, "QdrantClient", lambda **k: object())
    monkeypatch.setattr(indexing_run, "DocumentSource", _Fonte)
    monkeypatch.setattr(indexing_run, "SACChunker", lambda: object())
    monkeypatch.setattr(indexing_run, "PolyVectorEmbedder", lambda: object())
    monkeypatch.setattr(indexing_run, "QdrantStore", _Store)
    monkeypatch.setattr(indexing_run, "BM25Builder", lambda: object())
    r = indexing_run.indexar()
    assert set(r) >= {"docs", "chunks", "novos", "falhas", "bm25_salvo", "tempo_s"}
    assert r["docs"] == 0 and r["bm25_salvo"] is False


def test_preparar_banco_vazio_devolve_zeros():
    url = os.getenv("DATABASE_URL")
    if not url:
        pytest.skip("Requer DATABASE_URL.")
    nome = f"jurisight_teste_{uuid.uuid4().hex[:8]}"
    try:
        admin = psycopg.connect(url, autocommit=True, connect_timeout=2)
    except psycopg.OperationalError:
        pytest.skip("Postgres indisponível.")
    try:
        admin.execute(f'CREATE DATABASE "{nome}"')
    except psycopg.Error:
        admin.close()
        pytest.skip("Sem permissão para criar banco de teste.")
    try:
        url_teste = psycopg.conninfo.make_conninfo(url, dbname=nome)
        with psycopg.connect(url_teste) as conn:
            conn.execute("CREATE TABLE public.documentos (id uuid PRIMARY KEY, ementa text, "
                         "fundamentacao text, referencia_legislativa text[])")
        r = preparar(url_teste)
        assert r["dispositivos"] == 0 and r["pares"] == 0
        assert r["por_familia"] == {"nr": 0, "tema": 0, "sv": 0}
    finally:
        admin.execute(f'DROP DATABASE "{nome}" WITH (FORCE)')
        admin.close()
