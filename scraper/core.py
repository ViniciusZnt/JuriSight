"""
Lógica de coleta — baseada em teste/src/jt_scraper/scraper.py.
Única adição: injeta _data_filtro em cada documento antes de salvar,
para que o PostgresStore saiba qual data associar ao registro.
"""
import logging
import time
from datetime import date, datetime, timedelta

from scraper.api import BlockedResponseError, TransientApiError

logger = logging.getLogger(__name__)


class Scraper:
    def __init__(
        self,
        api_client,
        store,
        checkpoint_store,
        colecao="acordaos",
        min_delay_seconds=2.0,
        max_delay_seconds=30.0,
        max_retries=5,
        max_page_index=19,
        page_size=10,
        slow_response_seconds=8.0,
        sleep_fn=None,
        monotonic_fn=None,
    ):
        self.api_client           = api_client
        self.store                = store
        self.checkpoint_store     = checkpoint_store
        self.colecao              = colecao
        self.min_delay_seconds    = min_delay_seconds
        self.max_delay_seconds    = max_delay_seconds
        self.max_retries          = max_retries
        self.max_page_index       = max_page_index
        self.page_size            = page_size
        self.slow_response_seconds = slow_response_seconds
        self.sleep_fn             = sleep_fn or time.sleep
        self.monotonic_fn         = monotonic_fn or time.monotonic
        self.current_delay_seconds = min_delay_seconds
        self.adaptive_delay_enabled = min_delay_seconds > 0

    def run(self, start_date_str: str, end_date_str: str) -> dict:
        start_date = self._parse_date(start_date_str)
        end_date   = self._parse_date(end_date_str)
        if end_date < start_date:
            raise ValueError("end_date não pode ser anterior a start_date")

        state            = self.checkpoint_store.load() or {}
        current_date     = self._resolve_current_date(state, start_date)
        next_page        = self._resolve_next_page(state, start_date, current_date)
        documents_saved  = int(state.get("documents_saved", 0))
        requests_made    = int(state.get("requests_made", 0))
        self.current_delay_seconds = float(
            state.get("current_delay_seconds", self.min_delay_seconds)
        )

        logger.info(
            "Iniciando coleta: %s → %s (checkpoint: pág %d do dia %s)",
            start_date, end_date, next_page, current_date,
        )

        while current_date <= end_date:
            date_str = current_date.isoformat()
            try:
                payload = self._fetch_page_with_retries(date_str, next_page)
            except BlockedResponseError as exc:
                logger.error("Bloqueado pela API: %s", exc)
                halted = {
                    "completed":              False,
                    "current_date":           date_str,
                    "current_delay_seconds":  self.current_delay_seconds,
                    "documents_saved":        documents_saved,
                    "halt_reason":            "blocked",
                    "halt_message":           str(exc),
                    "next_page":              next_page,
                    "requests_made":          requests_made,
                }
                self.checkpoint_store.save(halted)
                return halted
            except TransientApiError as exc:
                logger.error("Erro transitório após todas as tentativas: %s", exc)
                halted = {
                    "completed":              False,
                    "current_date":           date_str,
                    "current_delay_seconds":  self.current_delay_seconds,
                    "documents_saved":        documents_saved,
                    "halt_reason":            "transient_error",
                    "halt_message":           str(exc),
                    "next_page":              next_page,
                    "requests_made":          requests_made,
                }
                self.checkpoint_store.save(halted)
                return halted

            requests_made += 1
            documents = payload.get("documentos", [])

            if not documents:
                logger.info("  %s pág %d — sem documentos, avançando dia.", date_str, next_page)
                current_date = current_date + timedelta(days=1)
                next_page    = 0
                self.checkpoint_store.save({
                    "completed":             current_date > end_date,
                    "current_date":          current_date.isoformat(),
                    "current_delay_seconds": self.current_delay_seconds,
                    "documents_saved":       documents_saved,
                    "next_page":             next_page,
                    "requests_made":         requests_made,
                })
                continue

            saved_this_page = 0
            for document in documents:
                document["_data_filtro"] = date_str
                document["_colecao"]     = self.colecao
                if self.store.append_document(document):
                    documents_saved += 1
                    saved_this_page += 1

            logger.info(
                "  %s pág %d — %d docs salvos (total: %d, delay: %.1fs)",
                date_str, next_page, saved_this_page, documents_saved, self.current_delay_seconds,
            )

            # Página parcial = última página do dia; evita requisição extra desnecessária
            is_last_page = (
                len(documents) < self.page_size
                or next_page >= self.max_page_index
            )
            if is_last_page:
                if next_page >= self.max_page_index:
                    logger.debug("  Limite de páginas atingido para %s, avançando dia.", date_str)
                current_date = current_date + timedelta(days=1)
                next_page    = 0
                self.checkpoint_store.save({
                    "completed":             current_date > end_date,
                    "current_date":          current_date.isoformat(),
                    "current_delay_seconds": self.current_delay_seconds,
                    "documents_saved":       documents_saved,
                    "next_page":             next_page,
                    "requests_made":         requests_made,
                })
                continue

            next_page += 1
            self.checkpoint_store.save({
                "completed":             False,
                "current_date":          date_str,
                "current_delay_seconds": self.current_delay_seconds,
                "documents_saved":       documents_saved,
                "next_page":             next_page,
                "requests_made":         requests_made,
            })

        final = {
            "completed":             True,
            "current_date":          current_date.isoformat(),
            "current_delay_seconds": self.current_delay_seconds,
            "documents_saved":       documents_saved,
            "next_page":             0,
            "requests_made":         requests_made,
        }
        self.checkpoint_store.save(final)
        logger.info(
            "Coleta concluída: %d documentos salvos em %d requisições.",
            documents_saved, requests_made,
        )
        return final

    # ------------------------------------------------------------------ #
    # Retry + delay adaptativo (idêntico ao teste)                        #
    # ------------------------------------------------------------------ #

    def _fetch_page_with_retries(self, date_str: str, page: int) -> dict:
        last_error = None
        for attempt in range(self.max_retries):
            if attempt:
                retry_delay = self._compute_retry_delay(attempt)
                if retry_delay > 0:
                    logger.info(
                        "  Aguardando %.1fs antes de tentar novamente (tentativa %d/%d)...",
                        retry_delay, attempt + 1, self.max_retries,
                    )
                    self.sleep_fn(retry_delay)

            logger.debug("  Requisição: %s pág %d (tentativa %d/%d)", date_str, page, attempt + 1, self.max_retries)
            started_at = self.monotonic_fn()
            try:
                payload = self.api_client.search_page(date_str, page, self.colecao)
                elapsed = self.monotonic_fn() - started_at
                self._decrease_delay_on_fast_success(elapsed)
                if self.current_delay_seconds > 0:
                    self.sleep_fn(self.current_delay_seconds)
                return payload
            except (BlockedResponseError, TransientApiError) as exc:
                logger.warning("  Erro na tentativa %d/%d: %s", attempt + 1, self.max_retries, exc)
                last_error = exc
                self._increase_delay()
        raise last_error

    def _compute_retry_delay(self, attempt: int) -> float:
        if not self.adaptive_delay_enabled:
            return 0
        base  = self.current_delay_seconds or self.min_delay_seconds or 0.5
        delay = base * (2 ** (attempt - 1))
        return min(delay, self.max_delay_seconds)

    def _increase_delay(self) -> None:
        if not self.adaptive_delay_enabled:
            self.current_delay_seconds = 0
            return
        base = self.current_delay_seconds or self.min_delay_seconds or 0.5
        self.current_delay_seconds = min(max(base * 2, 0.5), self.max_delay_seconds)

    def _decrease_delay_on_fast_success(self, elapsed: float) -> None:
        if not self.adaptive_delay_enabled:
            self.current_delay_seconds = 0
            return
        if elapsed >= self.slow_response_seconds:
            self._increase_delay()
            return
        if self.current_delay_seconds > self.min_delay_seconds:
            self.current_delay_seconds = max(
                self.min_delay_seconds,
                round(self.current_delay_seconds * 0.9, 3),
            )

    # ------------------------------------------------------------------ #
    # Helpers                                                              #
    # ------------------------------------------------------------------ #

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
