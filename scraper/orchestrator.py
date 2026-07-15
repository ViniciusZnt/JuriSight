"""
Orchestrator (componente C4 — Pipeline de Ingestão).

Gerencia a execução da coleta e controla o delta: itera por data, pagina,
aplica um delay fixo entre requisições e retry simples, e persiste o checkpoint
retomável. Coordena o Web Scraper (busca) e o DB Writer (persistência).
"""
import logging
import time
from datetime import date, datetime, timedelta

from scraper.web_scraper import BlockedResponseError, TransientApiError

logger = logging.getLogger(__name__)


class Orchestrator:
    def __init__(
        self,
        api_client,
        writer,
        checkpoint_store,
        colecao="acordaos",
        delay_seconds=1.0,
        retry_delay_seconds=5.0,
        max_retries=5,
        max_page_index=19,
        page_size=10,
        sleep_fn=None,
    ):
        self.api_client          = api_client
        self.writer              = writer
        self.checkpoint_store    = checkpoint_store
        self.colecao             = colecao
        self.delay_seconds       = delay_seconds
        self.retry_delay_seconds = retry_delay_seconds
        self.max_retries         = max_retries
        self.max_page_index      = max_page_index
        self.page_size           = page_size
        self.sleep_fn            = sleep_fn or time.sleep

    def run(self, start_date_str: str, end_date_str: str) -> dict:
        start_date = self._parse_date(start_date_str)
        end_date   = self._parse_date(end_date_str)
        if end_date < start_date:
            raise ValueError("end_date não pode ser anterior a start_date")

        state           = self.checkpoint_store.load() or {}
        current_date    = self._resolve_current_date(state, start_date)
        next_page       = self._resolve_next_page(state, start_date, current_date)
        documents_saved = int(state.get("documents_saved", 0))
        requests_made   = int(state.get("requests_made", 0))

        gap = self.writer.find_first_gap(start_date.isoformat(), current_date.isoformat())
        if gap is not None:
            logger.warning(
                "Checkpoint alegava progresso até %s, mas o banco está vazio em %s "
                "(checkpoint dessincronizado — provável restore/flush perdido). "
                "Retomando a partir do gap, não do checkpoint.",
                current_date, gap,
            )
            current_date = self._parse_date(gap)
            next_page    = 0

        logger.info(
            "Iniciando coleta:  → De %s até %s (checkpoint: pág %d do dia %s)",
            start_date, end_date, next_page, current_date,
        )

        while current_date <= end_date:
            date_str = current_date.isoformat()
            try:
                payload = self._fetch_page_with_retries(date_str, next_page)
            except BlockedResponseError as exc:
                logger.error("Bloqueado pela API: %s", exc)
                return self._save(
                    completed=False, current_date=date_str, next_page=next_page,
                    documents_saved=documents_saved, requests_made=requests_made,
                    halt_reason="blocked", halt_message=str(exc),
                )
            except TransientApiError as exc:
                logger.error("Erro transitório após todas as tentativas: %s", exc)
                return self._save(
                    completed=False, current_date=date_str, next_page=next_page,
                    documents_saved=documents_saved, requests_made=requests_made,
                    halt_reason="transient_error", halt_message=str(exc),
                )

            requests_made += 1
            documents = payload.get("documentos", [])

            if not documents:
                logger.info("  %s pág %d — sem documentos, avançando dia.", date_str, next_page)
                current_date += timedelta(days=1)
                next_page = 0
                self._save(
                    completed=current_date > end_date, current_date=current_date.isoformat(),
                    next_page=next_page, documents_saved=documents_saved, requests_made=requests_made,
                )
                continue

            saved_this_page = 0
            for document in documents:
                document["_data_filtro"] = date_str
                document["_colecao"]     = self.colecao
                if self.writer.append_document(document):
                    documents_saved += 1
                    saved_this_page += 1

            logger.info(
                "  %s pág %d — %d docs salvos (total: %d)",
                date_str, next_page, saved_this_page, documents_saved,
            )

            # Página parcial = última página do dia; evita requisição extra desnecessária
            is_last_page = (
                len(documents) < self.page_size
                or next_page >= self.max_page_index
            )
            if is_last_page:
                if next_page >= self.max_page_index:
                    logger.debug("  Limite de páginas atingido para %s, avançando dia.", date_str)
                current_date += timedelta(days=1)
                next_page = 0
                self._save(
                    completed=current_date > end_date, current_date=current_date.isoformat(),
                    next_page=next_page, documents_saved=documents_saved, requests_made=requests_made,
                )
                continue

            next_page += 1
            self._save(
                completed=False, current_date=date_str, next_page=next_page,
                documents_saved=documents_saved, requests_made=requests_made,
            )

        final = self._save(
            completed=True, current_date=current_date.isoformat(), next_page=0,
            documents_saved=documents_saved, requests_made=requests_made,
        )
        logger.info(
            "Coleta concluída: %d documentos salvos em %d requisições.",
            documents_saved, requests_made,
        )
        return final

    def _fetch_page_with_retries(self, date_str: str, page: int) -> dict:
        last_error = None
        for attempt in range(1, self.max_retries + 1):
            logger.debug("  Requisição: %s pág %d (tentativa %d/%d)", date_str, page, attempt, self.max_retries)
            try:
                payload = self.api_client.search_page(date_str, page, self.colecao)
                self.sleep_fn(self.delay_seconds)
                return payload
            except (BlockedResponseError, TransientApiError) as exc:
                last_error = exc
                logger.warning("  Erro na tentativa %d/%d: %s", attempt, self.max_retries, exc)
                if attempt < self.max_retries and self.retry_delay_seconds > 0:
                    logger.info("  Aguardando %.1fs antes de tentar novamente...", self.retry_delay_seconds)
                    self.sleep_fn(self.retry_delay_seconds)
        raise last_error

    # ------------------------------------------------------------------ #
    # Helpers                                                              #
    # ------------------------------------------------------------------ #

    def _save(self, **state) -> dict:
        """Persiste o checkpoint e devolve o estado salvo."""
        self.checkpoint_store.save(state)
        return state

    @staticmethod
    def _parse_date(value) -> date:
        if isinstance(value, date):
            return value
        return datetime.strptime(value, "%Y-%m-%d").date()

    @staticmethod
    def _resolve_current_date(state: dict, start_date: date) -> date:
        raw = state.get("current_date")
        if not raw:
            return start_date
        current = datetime.strptime(raw, "%Y-%m-%d").date()
        return current if current >= start_date else start_date

    @staticmethod
    def _resolve_next_page(state: dict, start_date: date, current_date: date) -> int:
        if state.get("current_date") and current_date >= start_date:
            return int(state.get("next_page", 0))
        return 0
