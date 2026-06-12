"""
Delta Control (componente C4 — Pipeline de Ingestão).

Evita reprocessamento: resolve a janela de coleta a partir do que já foi
coletado e mantém o checkpoint retomável (dia/página corrente) em disco.
A deduplicação fina de documentos é garantida pelo upsert do DB Writer
(`ON CONFLICT (id_documento)`).
"""
from __future__ import annotations

import json
import logging
from datetime import date, datetime, timedelta
from pathlib import Path

logger = logging.getLogger(__name__)

# Início da coleta quando o banco está vazio (sem histórico).
COLLECTION_START = date(2023, 1, 1)


class CheckpointStore:
    """Salva o progresso em arquivo para permitir retomada após interrupção."""

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def load(self) -> dict | None:
        if not self.path.exists():
            return None
        return json.loads(self.path.read_text(encoding="utf-8"))

    def save(self, state: dict) -> None:
        payload = dict(state)
        payload["updated_at"] = datetime.utcnow().isoformat() + "Z"
        self.path.write_text(
            json.dumps(payload, indent=2, sort_keys=True),
            encoding="utf-8",
        )


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
