"""Async event buffer with periodic flushing."""

import asyncio
import threading
from typing import Any

import httpx
import structlog

logger = structlog.get_logger()


class EventBuffer:
    """Thread-safe event buffer that flushes to the AgentOps API."""

    def __init__(
        self,
        api_url: str,
        api_key: str = "local",
        flush_interval: float = 5.0,
        max_buffer_size: int = 100,
    ):
        self.api_url = api_url.rstrip("/")
        self.api_key = api_key
        self.flush_interval = flush_interval
        self.max_buffer_size = max_buffer_size

        self._traces: list[dict] = []
        self._spans: list[dict] = []
        self._scores: list[dict] = []
        self._lock = threading.Lock()
        self._flush_task: asyncio.Task | None = None
        self._running = False

    def start(self) -> None:
        """Start the periodic flush task."""
        self._running = True
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                self._flush_task = loop.create_task(self._periodic_flush())
        except RuntimeError:
            # No event loop running — flush will be manual
            pass

    def stop(self) -> None:
        """Stop the buffer and flush remaining events."""
        self._running = False
        if self._flush_task:
            self._flush_task.cancel()

    def add_trace(self, trace_data: dict) -> None:
        """Add a trace to the buffer."""
        with self._lock:
            self._traces.append(trace_data)
            if len(self._traces) >= self.max_buffer_size:
                self._flush_sync()

    def add_span(self, span_data: dict) -> None:
        """Add a span to the buffer."""
        with self._lock:
            self._spans.append(span_data)
            if len(self._spans) >= self.max_buffer_size:
                self._flush_sync()

    def add_score(self, score_data: dict) -> None:
        """Add a score to the buffer."""
        with self._lock:
            self._scores.append(score_data)
            if len(self._scores) >= self.max_buffer_size:
                self._flush_sync()

    def flush(self) -> None:
        """Manually flush all buffered events."""
        with self._lock:
            self._flush_sync()

    def _flush_sync(self) -> None:
        """Synchronous flush (called while holding the lock)."""
        if not self._traces and not self._spans and not self._scores:
            return

        batch = {
            "traces": self._traces.copy(),
            "spans": self._spans.copy(),
            "scores": self._scores.copy(),
        }
        self._traces.clear()
        self._spans.clear()
        self._scores.clear()

        # Try to send (fire-and-forget for sync)
        try:
            import httpx
            response = httpx.post(
                f"{self.api_url}/api/v1/ingestion",
                json=batch,
                headers={"Authorization": f"Bearer {self.api_key}"},
                timeout=10.0,
            )
            if response.status_code != 200:
                logger.warning("Flush failed", status=response.status_code)
        except Exception as e:
            logger.warning("Flush error", error=str(e))

    async def _periodic_flush(self) -> None:
        """Async periodic flush loop."""
        while self._running:
            await asyncio.sleep(self.flush_interval)
            with self._lock:
                self._flush_sync()

    @property
    def buffer_size(self) -> int:
        """Total number of buffered events."""
        with self._lock:
            return len(self._traces) + len(self._spans) + len(self._scores)
