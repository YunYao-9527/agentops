"""Base scorer interface."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class ScorerResult:
    """Result of a scoring operation."""

    name: str
    value: float  # 0.0 - 1.0 for normalized scores
    passed: bool
    comment: str | None = None
    metadata: dict = field(default_factory=dict)


class Scorer(ABC):
    """Base class for all scorers."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Scorer name for identification."""
        ...

    @abstractmethod
    async def score(
        self,
        input: dict,
        output: dict,
        expected: dict | None = None,
        trace_data: dict | None = None,
    ) -> ScorerResult:
        """
        Score an agent output.

        Args:
            input: The input to the agent
            output: The actual output from the agent
            expected: The expected output (if available)
            trace_data: Full trace data for context (spans, tool calls, etc.)

        Returns:
            ScorerResult with value in [0, 1] and pass/fail
        """
        ...
