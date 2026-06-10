"""Data types for the AgentOps SDK."""

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class SpanData:
    """A span represents a single operation within a trace."""

    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    trace_id: str = ""
    parent_id: str | None = None
    name: str = ""
    type: str = "chain"  # llm | tool | chain | event

    input: dict | None = None
    output: dict | None = None
    metadata: dict = field(default_factory=dict)

    # LLM fields
    model: str | None = None
    model_parameters: dict | None = None
    prompt_tokens: int = 0
    completion_tokens: int = 0

    # Tool fields
    tool_name: str | None = None
    tool_input: dict | None = None
    tool_output: dict | None = None

    # Timing
    start_time: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    end_time: str | None = None
    latency_ms: float | None = None

    status: str = "ok"
    error: str | None = None


@dataclass
class TraceData:
    """A trace represents a complete agent execution."""

    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    project: str = "default"
    name: str = ""
    user_id: str | None = None
    session_id: str | None = None
    tags: list[str] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)
    input: dict | None = None
    output: dict | None = None

    start_time: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    end_time: str | None = None
    latency_ms: float | None = None

    status: str = "ok"
    error: str | None = None

    # Child spans
    spans: list[SpanData] = field(default_factory=list)


@dataclass
class ScoreData:
    """A score attached to a trace or span."""

    trace_id: str = ""
    span_id: str | None = None
    name: str = ""
    value: float = 0.0
    source: str = "auto"
    comment: str | None = None
    metadata: dict = field(default_factory=dict)
