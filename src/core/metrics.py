"""Metrics collector for real-time cost and latency tracking."""

from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class SpanMetrics:
    """Metrics for a single span."""

    model: str | None = None
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    cost_usd: float = 0.0
    latency_ms: float = 0.0


@dataclass
class TraceMetrics:
    """Aggregated metrics for a trace."""

    trace_id: str = ""
    total_spans: int = 0
    llm_spans: int = 0
    tool_spans: int = 0
    total_tokens: int = 0
    total_cost_usd: float = 0.0
    total_latency_ms: float = 0.0
    model_breakdown: dict[str, SpanMetrics] = field(default_factory=dict)


class MetricsCollector:
    """Collects and aggregates metrics from traces and spans."""

    # Approximate cost per 1K tokens (USD) — simplified
    COST_TABLE: dict[str, tuple[float, float]] = {
        # model: (input_cost_per_1k, output_cost_per_1k)
        "gpt-4o": (0.0025, 0.01),
        "gpt-4o-mini": (0.00015, 0.0006),
        "gpt-4-turbo": (0.01, 0.03),
        "gpt-3.5-turbo": (0.0005, 0.0015),
        "claude-sonnet-4-20250514": (0.003, 0.015),
        "claude-haiku-4-5-20251001": (0.00025, 0.00125),
        "claude-opus-4-20250514": (0.015, 0.075),
    }

    def calculate_cost(self, model: str, prompt_tokens: int, completion_tokens: int) -> float:
        """Calculate approximate cost in USD."""
        if model in self.COST_TABLE:
            input_cost, output_cost = self.COST_TABLE[model]
            return (prompt_tokens * input_cost + completion_tokens * output_cost) / 1000
        # Default estimate
        return (prompt_tokens * 0.003 + completion_tokens * 0.015) / 1000

    def aggregate_trace(self, spans: list[dict]) -> TraceMetrics:
        """Aggregate metrics from a list of spans."""
        metrics = TraceMetrics()

        for span in spans:
            metrics.total_spans += 1
            span_type = span.get("type", "")

            if span_type == "llm":
                metrics.llm_spans += 1
                model = span.get("model", "unknown")
                prompt_tokens = span.get("prompt_tokens", 0)
                completion_tokens = span.get("completion_tokens", 0)
                total_tokens = span.get("total_tokens", prompt_tokens + completion_tokens)
                cost = span.get("cost_usd") or self.calculate_cost(model, prompt_tokens, completion_tokens)

                metrics.total_tokens += total_tokens
                metrics.total_cost_usd += cost

                if model not in metrics.model_breakdown:
                    metrics.model_breakdown[model] = SpanMetrics(model=model)
                mb = metrics.model_breakdown[model]
                mb.prompt_tokens += prompt_tokens
                mb.completion_tokens += completion_tokens
                mb.total_tokens += total_tokens
                mb.cost_usd += cost

            elif span_type == "tool":
                metrics.tool_spans += 1

            latency = span.get("latency_ms", 0)
            metrics.total_latency_ms += latency

        return metrics
