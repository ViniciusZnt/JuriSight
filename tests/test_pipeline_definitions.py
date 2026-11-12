"""Assets e jobs do Dagster: as etapas reais são trocadas por espiões."""

import dagster as dg
import pytest

from pipeline.definitions import acervo, defs, jev_classificacoes


def test_defs_tem_assets_e_jobs():
    assets = {a.key.to_user_string() for a in defs.assets}
    assert assets == {
        "acervo", "indices", "filtros",
        "jev_classificacoes", "jev_provimento", "jev_sincronizado",
    }
    assert {j.name for j in defs.jobs} == {"full", "coleta", "indexacao", "so_filtros", "jev"}


def test_acervo_vira_metadados(monkeypatch):
    chamadas = []

    def falso(from_date, to_date, colecao="acordaos", database_url=None):
        chamadas.append((from_date, to_date, colecao))
        return {"completed": True, "documents_saved": 7, "requests_made": 3,
                "inicio": "2024-01-01", "fim": "2024-01-31"}

    monkeypatch.setattr("scraper.run.coletar", falso)
    cfg = {"ops": {"acervo": {"config": {"data_inicio": "2024-01-01", "data_fim": "2024-01-31"}}}}
    r = dg.materialize([acervo], run_config=cfg)
    assert r.success
    meta = r.asset_materializations_for_node("acervo")[0].metadata
    assert meta["documentos_salvos"].value == 7
    assert str(chamadas[0][0]) == "2024-01-01"


def test_acervo_falha_com_coleta_interrompida(monkeypatch):
    monkeypatch.setattr(
        "scraper.run.coletar",
        lambda *a, **k: {"completed": False, "documents_saved": 2, "requests_made": 5,
                         "inicio": "x", "fim": "y", "halt_reason": "r", "halt_message": "parou"},
    )
    r = dg.materialize([acervo], raise_on_error=False)
    assert not r.success


def test_data_invalida_e_erro_de_config():
    cfg = {"ops": {"acervo": {"config": {"data_inicio": "2024-13-01"}}}}
    with pytest.raises(Exception):
        dg.materialize([acervo], run_config=cfg)


def test_jev_limite_zero_vira_none(monkeypatch):
    vistos = []

    def espiao(store, classificador, limite, lote=500, max_workers=8):
        vistos.append(limite)
        return {"ok": 0, "falhas": 0, "tentados": 0, "pendentes": 0,
                "estimativa_tokens": 0, "modelo": "m"}

    monkeypatch.setattr("scraper.provimento_jev_cli.classificar", espiao)
    monkeypatch.setattr("scraper.provimento_jev_cli._construir_store", lambda: object())
    cfg = {"ops": {"jev_classificacoes": {"config": {"limite": 0}}}}
    assert dg.materialize([jev_classificacoes], run_config=cfg).success
    assert dg.materialize([jev_classificacoes]).success
    assert vistos == [None, 500]
