"""
AgentOps SDK — Trace your AI agents with zero boilerplate.

Usage:
    import agentops

    # Initialize
    client = agentops.init(api_key="...", project="my-project")

    # Decorate functions to create spans
    @agentops.observe(name="my-function")
    async def my_function(input_data):
        return await process(input_data)

    # Wrap OpenAI calls
    openai_client = agentops.openai_wrapper(openai.AsyncOpenAI())

    # Manual tracing
    with agentops.trace("my-task") as t:
        result = await do_something()
        t.set_output(result)

    # Score results
    agentops.score(trace_id, "accuracy", 0.95)
"""

from agentops.client import AgentOpsClient
from agentops.context import get_current_trace_id, get_current_span_id
from agentops.decorators import observe, trace
from agentops.wrappers import openai_wrapper, anthropic_wrapper
from agentops.types import TraceData, SpanData, ScoreData

# Global client instance
_client: AgentOpsClient | None = None


def init(
    api_key: str = "local",
    api_url: str = "http://localhost:8080",
    project: str = "default",
    auto_flush: bool = True,
    flush_interval: float = 5.0,
    max_buffer_size: int = 100,
) -> AgentOpsClient:
    """Initialize the AgentOps client."""
    global _client
    _client = AgentOpsClient(
        api_key=api_key,
        api_url=api_url,
        project=project,
        auto_flush=auto_flush,
        flush_interval=flush_interval,
        max_buffer_size=max_buffer_size,
    )
    return _client


def get_client() -> AgentOpsClient:
    """Get the global client instance."""
    if _client is None:
        return init()
    return _client


def score(trace_id: str, name: str, value: float, source: str = "auto", comment: str | None = None) -> None:
    """Add a score to a trace."""
    get_client().add_score(trace_id, name, value, source, comment)


def flush() -> None:
    """Flush all buffered events."""
    get_client().flush()


__all__ = [
    "AgentOpsClient",
    "init",
    "get_client",
    "observe",
    "trace",
    "openai_wrapper",
    "anthropic_wrapper",
    "score",
    "flush",
    "get_current_trace_id",
    "get_current_span_id",
    "TraceData",
    "SpanData",
    "ScoreData",
]
