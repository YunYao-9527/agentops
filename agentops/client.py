"""AgentOps client — the main entry point for the SDK."""

import atexit
from typing import Any

from agentops.buffer import EventBuffer
from agentops.types import ScoreData, SpanData, TraceData


class AgentOpsClient:
    """
    The AgentOps client manages buffering and sending traces, spans, and scores
    to the AgentOps platform.
    """

    def __init__(
        self,
        api_key: str = "local",
        api_url: str = "http://localhost:8080",
        project: str = "default",
        auto_flush: bool = True,
        flush_interval: float = 5.0,
        max_buffer_size: int = 100,
    ):
        self.api_key = api_key
        self.api_url = api_url
        self.project = project

        self.buffer = EventBuffer(
            api_url=api_url,
            api_key=api_key,
            flush_interval=flush_interval,
            max_buffer_size=max_buffer_size,
        )

        if auto_flush:
            self.buffer.start()
            atexit.register(self.flush)

    def buffer_trace(self, trace: TraceData) -> None:
        """Buffer a trace for sending."""
        self.buffer.add_trace(_trace_to_dict(trace))

    def buffer_span(self, span: SpanData) -> None:
        """Buffer a span for sending."""
        self.buffer.add_span(_span_to_dict(span))

    def add_score(
        self,
        trace_id: str,
        name: str,
        value: float,
        source: str = "auto",
        comment: str | None = None,
    ) -> None:
        """Add a score to the buffer."""
        self.buffer.add_score(
            {
                "trace_id": trace_id,
                "name": name,
                "value": value,
                "source": source,
                "comment": comment,
            }
        )

    def flush(self) -> None:
        """Flush all buffered events to the API."""
        self.buffer.flush()

    @property
    def pending_events(self) -> int:
        """Number of events waiting to be flushed."""
        return self.buffer.buffer_size


def _trace_to_dict(trace: TraceData) -> dict:
    """Convert TraceData to API-compatible dict."""
    return {
        "id": trace.id,
        "project": trace.project,
        "name": trace.name,
        "user_id": trace.user_id,
        "session_id": trace.session_id,
        "tags": trace.tags,
        "metadata": trace.metadata,
        "input": trace.input,
        "output": trace.output,
    }


def _span_to_dict(span: SpanData) -> dict:
    """Convert SpanData to API-compatible dict."""
    return {
        "id": span.id,
        "trace_id": span.trace_id,
        "parent_id": span.parent_id,
        "name": span.name,
        "type": span.type,
        "input": span.input,
        "output": span.output,
        "metadata": span.metadata,
        "model": span.model,
        "model_parameters": span.model_parameters,
        "prompt_tokens": span.prompt_tokens,
        "completion_tokens": span.completion_tokens,
        "tool_name": span.tool_name,
        "tool_input": span.tool_input,
        "tool_output": span.tool_output,
        "status": span.status,
        "error": span.error,
    }
