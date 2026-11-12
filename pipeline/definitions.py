"""Pipeline de dados como assets e jobs do Dagster.

Os imports das etapas são tardios: a UI carrega sem puxar playwright/embedder.
Nenhum asset expõe reset.
"""

import os
from datetime import date
from typing import Literal

import dagster as dg
from pydantic import field_validator


class AcervoConfig(dg.Config):
    data_inicio: str | None = None
    data_fim: str | None = None
    colecao: Literal["acordaos", "sumulas", "precedentes", "ojs"] = "acordaos"

    @field_validator("data_inicio", "data_fim")
    @classmethod
    def _data_iso(cls, v):
        if v is not None:
            date.fromisoformat(v)  # ValueError vira erro de config legível
        return v


def _data(v: str | None) -> date | None:
    return date.fromisoformat(v) if v else None


@dg.asset
def acervo(config: AcervoConfig) -> dg.MaterializeResult:
    """Coleta decisões novas no tribunal."""
    from scraper.run import coletar

    r = coletar(_data(config.data_inicio), _data(config.data_fim), colecao=config.colecao)
    meta = {
        "documentos_salvos": r["documents_saved"],
        "requisicoes": r["requests_made"],
        "inicio": str(r["inicio"]),
        "fim": str(r["fim"]),
    }
    if not r["completed"]:
        raise dg.Failure(description=r.get("halt_message") or "coleta interrompida", metadata=meta)
    return dg.MaterializeResult(metadata=meta)


@dg.asset(deps=[acervo])
def indices() -> dg.MaterializeResult:
    """Indexa os documentos novos (Qdrant + BM25), sem reset."""
    from indexing.run import indexar

    r = indexar()
    return dg.MaterializeResult(
        metadata={
            **r,
            "lembrete": "docker compose -f docker-compose.prod.yml restart api (recarrega o BM25)",
        }
    )


@dg.asset(deps=[indices])
def filtros() -> dg.MaterializeResult:
    """Prepara as tabelas do filtro restrito."""
    from query.filtros.preparar import preparar

    return dg.MaterializeResult(metadata=preparar(os.environ["DATABASE_URL"]))


class JevClassificacoesConfig(dg.Config):
    limite: int = 500  # 0 = sem limite
    lote: int = 500
    max_workers: int = 8


@dg.asset
def jev_classificacoes(config: JevClassificacoesConfig) -> dg.MaterializeResult:
    """Classifica o provimento com o Jev (retomável)."""
    from scraper.provimento_jev_cli import _construir_store, classificar

    r = classificar(
        _construir_store(), None, config.limite or None, config.lote, config.max_workers
    )
    if r["tentados"] > 0 and r["ok"] == 0:
        raise dg.Failure(
            description=f"Jev falhou em todos os {r['tentados']} itens tentados",
            metadata=r,
        )
    return dg.MaterializeResult(metadata=r)


class JevProvimentoConfig(dg.Config):
    confianca_min: float = 0.8


@dg.asset(deps=[jev_classificacoes])
def jev_provimento(config: JevProvimentoConfig) -> dg.MaterializeResult:
    """Escreve o provimento do Jev em documentos."""
    from scraper.provimento_jev_cli import _construir_store, aplicar

    r = aplicar(_construir_store(), config.confianca_min, confirmar=True)
    return dg.MaterializeResult(
        metadata={k: r[k] for k in ("transicoes", "abaixo_limite", "aplicadas")}
    )


@dg.asset(deps=[jev_provimento])
def jev_sincronizado() -> dg.MaterializeResult:
    """Leva documentos.provimento ao Qdrant e ao BM25."""
    from scraper.provimento_jev_cli import _construir_qdrant, _construir_store, sincronizar

    r = sincronizar(_construir_store(), _construir_qdrant())
    return dg.MaterializeResult(metadata=r)


full = dg.define_asset_job("full", selection=["acervo", "indices", "filtros"])
coleta = dg.define_asset_job("coleta", selection="acervo")
indexacao = dg.define_asset_job("indexacao", selection="indices")
so_filtros = dg.define_asset_job("so_filtros", selection="filtros")
jev = dg.define_asset_job(
    "jev", selection=["jev_classificacoes", "jev_provimento", "jev_sincronizado"]
)

defs = dg.Definitions(
    assets=[acervo, indices, filtros, jev_classificacoes, jev_provimento, jev_sincronizado],
    jobs=[full, coleta, indexacao, so_filtros, jev],
)
