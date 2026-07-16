"""
Delta Control.

Evita reprocessamento: resolve a janela de coleta a partir do que já foi
coletado e mantém o estado retomável (dia/página corrente) NO BANCO.
A deduplicação fina de documentos é garantida pelo upsert do DB Writer
(`ON CONFLICT (id_documento)`).
"""
from __future__ import annotations

import logging
from datetime import date, timedelta

logger = logging.getLogger(__name__)

# Início da coleta quando o banco está vazio (sem histórico).
COLLECTION_START = date(2023, 1, 1)


class DbStateStore:
    """Estado retomável da coleta no banco (scraper_state, JSONB), por coleção.

    Substitui o checkpoint em arquivo: a fonte de verdade passa a ser o banco, que
    não dessincroniza do que foi realmente coletado. Mesma interface load()/save()
    esperada pelo Orchestrator.
    """

    def __init__(self, writer, colecao: str):
        self._writer = writer
        self._colecao = colecao

    def load(self) -> dict | None:
        return self._writer.load_state(self._colecao)

    def save(self, state: dict) -> None:
        self._writer.save_state(self._colecao, state)


def resolve_collection_window(
    from_date: date | None,
    to_date: date | None,
    last_collected: str | None,
) -> tuple[date, date]:
    """Determina o intervalo [início, fim] da coleta (delta por data).

    Args:
        from_date: início forçado pelo usuário (sobrepõe o delta).
        to_date: fim forçado; padrão = ontem.
        last_collected: maior `data_filtro` já no banco (ISO) ou None.

    Returns:
        (início, fim) — re-coleta a partir do último dia para capturar páginas
        que possam ter sido adicionadas após a coleta anterior.
    """
    end = to_date or date.today() - timedelta(days=1)

    if from_date:
        logger.info("Data de início forçada: %s", from_date)
        return from_date, end

    if last_collected:
        last = date.fromisoformat(last_collected)
        logger.info("Último dia coletado: %s — re-coletando a partir desse dia.", last)
        return last, end

    logger.info("Banco vazio — iniciando do começo: %s", COLLECTION_START)
    return COLLECTION_START, end
