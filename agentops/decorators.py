"""Decorators for automatic tracing."""

import functools
import inspect
import time
from contextlib import asynccontextmanager, contextmanager
from datetime import datetime
from typing import Any, Callable

from agentops.context import (
    create_child_span,
    get_current_trace,
    get_current_trace_id,
    pop_span,
    push_span,
    reset_current_trace,
    set_current_trace,
)
from agentops.types import SpanData, TraceData


def observe(
    name: str | None = None,
    type: str = "chain",
    capture_input: bool = True,
    capture_output: bool = True,
):
    """
    Decorator to automatically create a span for a function call.

    Usage:
        @agentops.observe(name="my-function")
        async def my_function(x, y):
            return x + y

        @agentops.observe(type="tool")
        def my_tool(query: str):
            return search(query)
    """

    def decorator(func: Callable) -> Callable:
        span_name = name or func.__qualname__

        if inspect.iscoroutinefunction(func):

            @functools.wraps(func)
            async def async_wrapper(*args, **kwargs):
                input_data = None
                if capture_input:
                    input_data = _serialize_args(args, kwargs)

                span = create_child_span(span_name, type, input_data)
                push_span(span)
                span.start_time = datetime.utcnow().isoformat()
                start = time.monotonic()

                try:
                    result = await func(*args, **kwargs)
                    elapsed = (time.monotonic() - start) * 1000
                    span.end_time = datetime.utcnow().isoformat()
                    span.latency_ms = elapsed
                    span.status = "ok"
                    if capture_output:
                        span.output = _serialize_output(result)
                    return result
                except Exception as e:
                    elapsed = (time.monotonic() - start) * 1000
                    span.end_time = datetime.utcnow().isoformat()
                    span.latency_ms = elapsed
                    span.status = "error"
                    span.error = str(e)
                    raise
                finally:
                    pop_span()
                    _buffer_span(span)

            return async_wrapper
        else:

            @functools.wraps(func)
            def sync_wrapper(*args, **kwargs):
                input_data = None
                if capture_input:
                    input_data = _serialize_args(args, kwargs)

                span = create_child_span(span_name, type, input_data)
                push_span(span)
                span.start_time = datetime.utcnow().isoformat()
                start = time.monotonic()

                try:
                    result = func(*args, **kwargs)
                    elapsed = (time.monotonic() - start) * 1000
                    span.end_time = datetime.utcnow().isoformat()
                    span.latency_ms = elapsed
                    span.status = "ok"
                    if capture_output:
                        span.output = _serialize_output(result)
                    return result
                except Exception as e:
                    elapsed = (time.monotonic() - start) * 1000
                    span.end_time = datetime.utcnow().isoformat()
                    span.latency_ms = elapsed
                    span.status = "error"
                    span.error = str(e)
                    raise
                finally:
                    pop_span()
                    _buffer_span(span)

            return sync_wrapper

    return decorator


@asynccontextmanager
async def trace(
    name: str,
    project: str = "default",
    user_id: str | None = None,
    session_id: str | None = None,
    tags: list[str] | None = None,
    metadata: dict | None = None,
    input_data: dict | None = None,
):
    """
    Async context manager for creating a trace.

    Usage:
        async with agentops.trace("my-task") as t:
            result = await do_something()
            t.set_output(result)
    """
    trace_data = TraceData(
        project=project,
        name=name,
        user_id=user_id,
        session_id=session_id,
        tags=tags or [],
        metadata=metadata or {},
        input=input_data,
    )

    token = set_current_trace(trace_data)
    trace_data.start_time = datetime.utcnow().isoformat()
    start = time.monotonic()

    try:
        yield trace_data
    except Exception as e:
        trace_data.status = "error"
        trace_data.error = str(e)
        raise
    finally:
        elapsed = (time.monotonic() - start) * 1000
        trace_data.end_time = datetime.utcnow().isoformat()
        trace_data.latency_ms = elapsed
        reset_current_trace(token)
        _buffer_trace(trace_data)


@contextmanager
def sync_trace(
    name: str,
    project: str = "default",
    **kwargs,
):
    """Synchronous version of trace()."""
    trace_data = TraceData(
        project=project,
        name=name,
        **kwargs,
    )

    token = set_current_trace(trace_data)
    trace_data.start_time = datetime.utcnow().isoformat()
    start = time.monotonic()

    try:
        yield trace_data
    except Exception as e:
        trace_data.status = "error"
        trace_data.error = str(e)
        raise
    finally:
        elapsed = (time.monotonic() - start) * 1000
        trace_data.end_time = datetime.utcnow().isoformat()
        trace_data.latency_ms = elapsed
        reset_current_trace(token)
        _buffer_trace(trace_data)


# ─── Helpers ──────────────────────────────────────────────────────────────────


def _serialize_args(args: tuple, kwargs: dict) -> dict:
    """Serialize function arguments for storage."""
    result = {}
    if args:
        result["args"] = [_safe_serialize(a) for a in args]
    if kwargs:
        result["kwargs"] = {k: _safe_serialize(v) for k, v in kwargs.items()}
    return result


def _serialize_output(result: Any) -> dict:
    """Serialize function output for storage."""
    if isinstance(result, dict):
        return result
    return {"result": _safe_serialize(result)}


def _safe_serialize(obj: Any) -> Any:
    """Safely serialize an object, falling back to str."""
    if isinstance(obj, (str, int, float, bool, type(None))):
        return obj
    if isinstance(obj, (list, tuple)):
        return [_safe_serialize(item) for item in obj[:10]]  # Limit list size
    if isinstance(obj, dict):
        return {k: _safe_serialize(v) for k, v in list(obj.items())[:20]}  # Limit dict size
    return str(obj)[:1000]  # Truncate long strings


def _buffer_span(span: SpanData) -> None:
    """Buffer a span for later flushing."""
    try:
        from agentops import get_client
        get_client().buffer_span(span)
    except Exception:
        pass  # Don't break the user's code if SDK isn't initialized


def _buffer_trace(trace_data: TraceData) -> None:
    """Buffer a trace for later flushing."""
    try:
        from agentops import get_client
        get_client().buffer_trace(trace_data)
    except Exception:
        pass
