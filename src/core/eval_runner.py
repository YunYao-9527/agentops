"""Evaluation runner — orchestrates dataset evaluation with scorers."""

import asyncio
import json
import uuid
from datetime import datetime
from typing import Any, Callable, Coroutine

import structlog

from src.core.scorers.base import Scorer, ScorerResult

logger = structlog.get_logger()


class EvalRunner:
    """
    Runs a task function against a dataset and scores the results.

    Usage:
        runner = EvalRunner(scorers=[rule_scorer, llm_judge])
        results = await runner.run(
            dataset=[{"input": {...}, "expected_output": {...}}, ...],
            task_fn=my_agent_function,
            max_concurrent=5,
        )
    """

    def __init__(
        self,
        scorers: list[Scorer] | None = None,
        max_concurrent: int = 5,
    ):
        self.scorers = scorers or []
        self.max_concurrent = max_concurrent

    async def run(
        self,
        dataset: list[dict[str, Any]],
        task_fn: Callable[[dict], Coroutine[Any, Any, dict]],
        config: dict | None = None,
    ) -> dict[str, Any]:
        """
        Run evaluation on a dataset.

        Args:
            dataset: List of {"input": {...}, "expected_output": {...}}
            task_fn: Async function that takes input dict and returns output dict
            config: Optional config snapshot for the experiment

        Returns:
            Evaluation results with per-item scores and aggregates
        """
        experiment_id = str(uuid.uuid4())
        started_at = datetime.utcnow()

        logger.info(
            "Starting evaluation",
            experiment_id=experiment_id,
            dataset_size=len(dataset),
            scorers=[s.name for s in self.scorers],
        )

        semaphore = asyncio.Semaphore(self.max_concurrent)
        results: list[dict[str, Any]] = []

        async def evaluate_item(index: int, item: dict) -> dict[str, Any]:
            async with semaphore:
                input_data = item["input"]
                expected = item.get("expected_output")
                item_id = item.get("id", str(index))

                # Run the task
                try:
                    output = await task_fn(input_data)
                    status = "ok"
                    error = None
                except Exception as e:
                    output = {}
                    status = "error"
                    error = str(e)
                    logger.error("Task failed", item_id=item_id, error=str(e))

                # Run all scorers
                scores: dict[str, ScorerResult] = {}
                for scorer in self.scorers:
                    try:
                        result = await scorer.score(
                            input=input_data,
                            output=output,
                            expected=expected,
                        )
                        scores[scorer.name] = result
                    except Exception as e:
                        logger.error("Scorer failed", scorer=scorer.name, item_id=item_id, error=str(e))
                        scores[scorer.name] = ScorerResult(
                            name=scorer.name, value=0.0, passed=False, comment=f"Error: {e!s}"
                        )

                return {
                    "item_id": item_id,
                    "input": input_data,
                    "output": output,
                    "expected": expected,
                    "status": status,
                    "error": error,
                    "scores": {name: {"value": r.value, "passed": r.passed, "comment": r.comment} for name, r in scores.items()},
                }

        # Run all items concurrently (with semaphore limiting)
        tasks = [evaluate_item(i, item) for i, item in enumerate(dataset)]
        results = await asyncio.gather(*tasks, return_exceptions=False)

        # Compute aggregates
        completed_at = datetime.utcnow()
        total = len(results)
        succeeded = sum(1 for r in results if r["status"] == "ok")
        failed = total - succeeded

        # Per-scorer aggregates
        scorer_aggregates: dict[str, dict] = {}
        for scorer in self.scorers:
            scorer_scores = [
                r["scores"][scorer.name]["value"]
                for r in results
                if scorer.name in r["scores"]
            ]
            if scorer_scores:
                scorer_aggregates[scorer.name] = {
                    "mean": sum(scorer_scores) / len(scorer_scores),
                    "min": min(scorer_scores),
                    "max": max(scorer_scores),
                    "pass_rate": sum(
                        1 for r in results
                        if scorer.name in r["scores"] and r["scores"][scorer.name]["passed"]
                    ) / len(scorer_scores),
                }

        # Overall score (average of all scorer means)
        overall_scores = [agg["mean"] for agg in scorer_aggregates.values()]
        overall = sum(overall_scores) / len(overall_scores) if overall_scores else 0.0

        summary = {
            "experiment_id": experiment_id,
            "config": config,
            "total_items": total,
            "completed_items": succeeded,
            "failed_items": failed,
            "overall_score": overall,
            "scorer_aggregates": scorer_aggregates,
            "started_at": started_at.isoformat(),
            "completed_at": completed_at.isoformat(),
            "duration_seconds": (completed_at - started_at).total_seconds(),
            "results": results,
        }

        logger.info(
            "Evaluation complete",
            experiment_id=experiment_id,
            overall_score=f"{overall:.3f}",
            succeeded=succeeded,
            failed=failed,
        )

        return summary


# ─── Convenience Functions ────────────────────────────────────────────────────


async def quick_eval(
    dataset: list[dict],
    task_fn: Callable,
    scorers: list[Scorer] | None = None,
    max_concurrent: int = 5,
) -> dict:
    """Quick evaluation with default scorers."""
    runner = EvalRunner(scorers=scorers or [], max_concurrent=max_concurrent)
    return await runner.run(dataset=dataset, task_fn=task_fn)
