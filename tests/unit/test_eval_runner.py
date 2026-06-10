"""Unit tests for the evaluation runner."""

import pytest

from src.core.eval_runner import EvalRunner
from src.core.scorers.rule_scorer import RuleScorer


@pytest.mark.asyncio
async def test_eval_runner_basic():
    """Test basic evaluation flow."""

    async def mock_task(input_data: dict) -> dict:
        return {"content": f"Processed: {input_data.get('query', '')}"}

    scorer = RuleScorer(
        name="contains_check",
        rules=[{"type": "contains", "field": "content", "value": "Processed"}],
    )

    runner = EvalRunner(scorers=[scorer], max_concurrent=2)
    dataset = [
        {"input": {"query": "hello"}, "expected_output": {"content": "Processed: hello"}},
        {"input": {"query": "world"}, "expected_output": {"content": "Processed: world"}},
    ]

    results = await runner.run(dataset=dataset, task_fn=mock_task)

    assert results["total_items"] == 2
    assert results["completed_items"] == 2
    assert results["failed_items"] == 0
    assert results["overall_score"] == 1.0
    assert len(results["results"]) == 2


@pytest.mark.asyncio
async def test_eval_runner_with_failure():
    """Test evaluation with task failures."""

    call_count = 0

    async def failing_task(input_data: dict) -> dict:
        nonlocal call_count
        call_count += 1
        if call_count == 2:
            raise RuntimeError("Simulated failure")
        return {"content": "ok"}

    scorer = RuleScorer(
        name="test",
        rules=[{"type": "contains", "field": "content", "value": "ok"}],
    )

    runner = EvalRunner(scorers=[scorer])
    dataset = [
        {"input": {"q": "1"}},
        {"input": {"q": "2"}},
        {"input": {"q": "3"}},
    ]

    results = await runner.run(dataset=dataset, task_fn=failing_task)

    assert results["total_items"] == 3
    assert results["completed_items"] == 2
    assert results["failed_items"] == 1
