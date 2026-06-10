"""Context management for trace and span tracking using contextvars."""

import contextvars
import uuid
from datetime import datetime

from agentops.types import SpanData, TraceData

# Context variables for trace/span hierarchy
_current_trace: contextvars.ContextVar[TraceData | None] = contextvars.ContextVar(
    "agentops_trace", default=None
)
_current_span: contextvars.ContextVar[SpanData | None] = contextvars.ContextVar(
    "agentops_span", default=None
)
_span_stack: contextvars.ContextVar[list[SpanData]] = contextvars.ContextVar(
    "agentops_span_stack", default=[]
)


def get_current_trace() -> TraceData | None:
    """Get the current active trace."""
    return _current_trace.get()


def get_current_trace_id() -> str | None:
    """Get the current trace ID."""
    trace = _current_trace.get()
    return trace.id if trace else None


def get_current_span() -> SpanData | None:
    """Get the current active span."""
    return _current_span.get()


def get_current_span_id() -> str | None:
    """Get the current span ID."""
    span = _current_span.get()
    return span.id if span else None


def set_current_trace(trace: TraceData) -> contextvars.Token:
    """Set the current trace."""
    return _current_trace.set(trace)


def reset_current_trace(token: contextvars.Token) -> None:
    """Reset the current trace."""
    _current_trace.reset(token)


def push_span(span: SpanData) -> None:
    """Push a span onto the stack and set as current."""
    stack = _span_stack.get().copy()
    stack.append(span)
    _span_stack.set(stack)
    _current_span.set(span)


def pop_span() -> SpanData | None:
    """Pop the top span from the stack."""
    stack = _span_stack.get().copy()
    if not stack:
        return None
    span = stack.pop()
    _span_stack.set(stack)
    _current_span.set(stack[-1] if stack else None)
    return span


def create_child_span(
    name: str,
    span_type: str = "chain",
    input_data: dict | None = None,
) -> SpanData:
    """Create a child span of the current span or trace."""
    trace = get_current_trace()
    parent = get_current_span()

    span = SpanData(
        trace_id=trace.id if trace else "",
        parent_id=parent.id if parent else None,
        name=name,
        type=span_type,
        input=input_data,
    )
    return span
