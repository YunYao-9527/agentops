"""Wrappers for LLM client libraries that auto-trace calls."""

import functools
import time
from datetime import datetime
from typing import Any

from agentops.context import create_child_span, get_current_trace, push_span, pop_span


def openai_wrapper(client: Any) -> Any:
    """
    Wrap an OpenAI client to automatically trace chat completions.

    Usage:
        import openai
        import agentops

        client = agentops.openai_wrapper(openai.AsyncOpenAI())
        response = await client.chat.completions.create(...)  # Auto-traced
    """
    original_create = client.chat.completions.create

    if hasattr(original_create, "_agentops_wrapped"):
        return client  # Already wrapped

    if _is_async(original_create):
        client.chat.completions.create = _async_wrap_openai(original_create)
    else:
        client.chat.completions.create = _sync_wrap_openai(original_create)

    client.chat.completions.create._agentops_wrapped = True
    return client


def anthropic_wrapper(client: Any) -> Any:
    """
    Wrap an Anthropic client to automatically trace messages.

    Usage:
        import anthropic
        import agentops

        client = agentops.anthropic_wrapper(anthropic.AsyncAnthropic())
        response = await client.messages.create(...)  # Auto-traced
    """
    original_create = client.messages.create

    if hasattr(original_create, "_agentops_wrapped"):
        return client

    if _is_async(original_create):
        client.messages.create = _async_wrap_anthropic(original_create)
    else:
        client.messages.create = _sync_wrap_anthropic(original_create)

    client.messages.create._agentops_wrapped = True
    return client


# ─── OpenAI Wrappers ─────────────────────────────────────────────────────────


def _async_wrap_openai(original_create):
    @functools.wraps(original_create)
    async def wrapped(*args, **kwargs):
        model = kwargs.get("model", "unknown")
        messages = kwargs.get("messages", [])

        span = create_child_span(
            name=f"openai.chat.{model}",
            span_type="llm",
            input_data={"messages": messages, "model": model},
        )
        span.model = model
        span.model_parameters = {
            k: v for k, v in kwargs.items()
            if k not in ("messages", "model") and v is not None
        }
        push_span(span)
        span.start_time = datetime.utcnow().isoformat()
        start = time.monotonic()

        try:
            response = await original_create(*args, **kwargs)
            elapsed = (time.monotonic() - start) * 1000

            span.end_time = datetime.utcnow().isoformat()
            span.latency_ms = elapsed
            span.status = "ok"

            # Extract usage
            if hasattr(response, "usage") and response.usage:
                span.prompt_tokens = response.usage.prompt_tokens or 0
                span.completion_tokens = response.usage.completion_tokens or 0

            # Extract output
            if hasattr(response, "choices") and response.choices:
                content = response.choices[0].message.content
                span.output = {"content": content}

            return response
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

    return wrapped


def _sync_wrap_openai(original_create):
    @functools.wraps(original_create)
    def wrapped(*args, **kwargs):
        model = kwargs.get("model", "unknown")
        messages = kwargs.get("messages", [])

        span = create_child_span(
            name=f"openai.chat.{model}",
            span_type="llm",
            input_data={"messages": messages, "model": model},
        )
        span.model = model
        push_span(span)
        span.start_time = datetime.utcnow().isoformat()
        start = time.monotonic()

        try:
            response = original_create(*args, **kwargs)
            elapsed = (time.monotonic() - start) * 1000

            span.end_time = datetime.utcnow().isoformat()
            span.latency_ms = elapsed
            span.status = "ok"

            if hasattr(response, "usage") and response.usage:
                span.prompt_tokens = response.usage.prompt_tokens or 0
                span.completion_tokens = response.usage.completion_tokens or 0

            if hasattr(response, "choices") and response.choices:
                content = response.choices[0].message.content
                span.output = {"content": content}

            return response
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

    return wrapped


# ─── Anthropic Wrappers ──────────────────────────────────────────────────────


def _async_wrap_anthropic(original_create):
    @functools.wraps(original_create)
    async def wrapped(*args, **kwargs):
        model = kwargs.get("model", "unknown")
        messages = kwargs.get("messages", [])

        span = create_child_span(
            name=f"anthropic.messages.{model}",
            span_type="llm",
            input_data={"messages": messages, "model": model},
        )
        span.model = model
        push_span(span)
        span.start_time = datetime.utcnow().isoformat()
        start = time.monotonic()

        try:
            response = await original_create(*args, **kwargs)
            elapsed = (time.monotonic() - start) * 1000

            span.end_time = datetime.utcnow().isoformat()
            span.latency_ms = elapsed
            span.status = "ok"

            if hasattr(response, "usage") and response.usage:
                span.prompt_tokens = response.usage.input_tokens or 0
                span.completion_tokens = response.usage.output_tokens or 0

            if hasattr(response, "content") and response.content:
                span.output = {"content": response.content[0].text if response.content else ""}

            return response
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

    return wrapped


def _sync_wrap_anthropic(original_create):
    @functools.wraps(original_create)
    def wrapped(*args, **kwargs):
        model = kwargs.get("model", "unknown")
        messages = kwargs.get("messages", [])

        span = create_child_span(
            name=f"anthropic.messages.{model}",
            span_type="llm",
            input_data={"messages": messages, "model": model},
        )
        span.model = model
        push_span(span)
        span.start_time = datetime.utcnow().isoformat()
        start = time.monotonic()

        try:
            response = original_create(*args, **kwargs)
            elapsed = (time.monotonic() - start) * 1000

            span.end_time = datetime.utcnow().isoformat()
            span.latency_ms = elapsed
            span.status = "ok"

            if hasattr(response, "usage") and response.usage:
                span.prompt_tokens = response.usage.input_tokens or 0
                span.completion_tokens = response.usage.output_tokens or 0

            return response
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

    return wrapped


# ─── Helpers ──────────────────────────────────────────────────────────────────


def _is_async(func) -> bool:
    """Check if a function is async."""
    import asyncio
    return asyncio.iscoroutinefunction(func)


def _buffer_span(span) -> None:
    """Buffer span via the global client."""
    try:
        from agentops import get_client
        get_client().buffer_span(span)
    except Exception:
        pass
