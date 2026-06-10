"""Composite scorer that combines multiple scorers."""

from src.core.scorers.base import Scorer, ScorerResult


class CompositeScorer(Scorer):
    """Combines multiple scorers with configurable weights and aggregation."""

    def __init__(
        self,
        name: str = "composite",
        scorers: list[tuple[Scorer, float]] | None = None,
        aggregation: str = "weighted_average",  # weighted_average | all_must_pass | any_must_pass
        pass_threshold: float = 0.7,
    ):
        self._name = name
        self.scorers = scorers or []
        self.aggregation = aggregation
        self.pass_threshold = pass_threshold

    @property
    def name(self) -> str:
        return self._name

    def add_scorer(self, scorer: Scorer, weight: float = 1.0) -> None:
        """Add a scorer with weight."""
        self.scorers.append((scorer, weight))

    async def score(
        self,
        input: dict,
        output: dict,
        expected: dict | None = None,
        trace_data: dict | None = None,
    ) -> ScorerResult:
        if not self.scorers:
            return ScorerResult(name=self.name, value=1.0, passed=True, comment="No scorers configured")

        results: list[tuple[ScorerResult, float]] = []

        for scorer, weight in self.scorers:
            result = await scorer.score(input, output, expected, trace_data)
            results.append((result, weight))

        if self.aggregation == "weighted_average":
            return self._weighted_average(results)
        elif self.aggregation == "all_must_pass":
            return self._all_must_pass(results)
        elif self.aggregation == "any_must_pass":
            return self._any_must_pass(results)
        else:
            return self._weighted_average(results)

    def _weighted_average(self, results: list[tuple[ScorerResult, float]]) -> ScorerResult:
        """Compute weighted average of all scores."""
        total_weight = sum(w for _, w in results)
        if total_weight == 0:
            return ScorerResult(name=self.name, value=0.0, passed=False)

        weighted_sum = sum(r.value * w for r, w in results)
        value = weighted_sum / total_weight

        comments = [f"{r.name}={r.value:.2f}" for r, _ in results if r.comment]
        return ScorerResult(
            name=self.name,
            value=value,
            passed=value >= self.pass_threshold,
            comment=" | ".join(comments) if comments else None,
            metadata={"scorer_results": {r.name: r.value for r, _ in results}},
        )

    def _all_must_pass(self, results: list[tuple[ScorerResult, float]]) -> ScorerResult:
        """All scorers must pass."""
        all_passed = all(r.passed for r, _ in results)
        min_value = min(r.value for r, _ in results)
        failed = [r.name for r, _ in results if not r.passed]

        return ScorerResult(
            name=self.name,
            value=min_value,
            passed=all_passed,
            comment=f"Failed: {', '.join(failed)}" if failed else None,
            metadata={"scorer_results": {r.name: r.value for r, _ in results}},
        )

    def _any_must_pass(self, results: list[tuple[ScorerResult, float]]) -> ScorerResult:
        """At least one scorer must pass."""
        any_passed = any(r.passed for r, _ in results)
        max_value = max(r.value for r, _ in results)

        return ScorerResult(
            name=self.name,
            value=max_value,
            passed=any_passed,
            comment="No scorer passed" if not any_passed else None,
            metadata={"scorer_results": {r.name: r.value for r, _ in results}},
        )
