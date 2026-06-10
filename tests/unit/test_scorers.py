"""Unit tests for scorers."""

import pytest

from src.core.scorers.rule_scorer import RuleScorer, tool_usage_scorer
from src.core.scorers.composite import CompositeScorer


@pytest.mark.asyncio
async def test_rule_scorer_exact_match():
    scorer = RuleScorer(
        name="test",
        rules=[{"type": "exact_match", "field": "status", "value": "ok"}],
    )
    result = await scorer.score(
        input={"query": "test"},
        output={"status": "ok", "content": "done"},
    )
    assert result.passed is True
    assert result.value == 1.0


@pytest.mark.asyncio
async def test_rule_scorer_contains():
    scorer = RuleScorer(
        name="test",
        rules=[{"type": "contains", "field": "content", "value": "退款"}],
    )
    result = await scorer.score(
        input={"query": "test"},
        output={"content": "已为您发起退款申请"},
    )
    assert result.passed is True


@pytest.mark.asyncio
async def test_rule_scorer_not_contains():
    scorer = RuleScorer(
        name="test",
        rules=[{"type": "not_contains", "field": "content", "value": "sorry"}],
    )
    result = await scorer.score(
        input={"query": "test"},
        output={"content": "I cannot help with that"},
    )
    assert result.passed is True


@pytest.mark.asyncio
async def test_rule_scorer_regex():
    scorer = RuleScorer(
        name="test",
        rules=[{"type": "regex", "field": "content", "pattern": r"ORD\d+"}],
    )
    result = await scorer.score(
        input={},
        output={"content": "Your order ORD20240101 has been processed"},
    )
    assert result.passed is True


@pytest.mark.asyncio
async def test_rule_scorer_tool_called():
    scorer = RuleScorer(
        name="test",
        rules=[{"type": "tool_called", "tool_name": "get_order"}],
    )
    result = await scorer.score(
        input={},
        output={},
        trace_data={
            "spans": [
                {"type": "tool", "tool_name": "get_order"},
                {"type": "tool", "tool_name": "request_refund"},
            ]
        },
    )
    assert result.passed is True


@pytest.mark.asyncio
async def test_rule_scorer_multiple_rules():
    scorer = RuleScorer(
        name="test",
        rules=[
            {"type": "contains", "field": "content", "value": "退款"},
            {"type": "tool_called", "tool_name": "get_order"},
        ],
    )
    # Passes first rule, fails second
    result = await scorer.score(
        input={},
        output={"content": "退款申请已提交"},
        trace_data={"spans": [{"type": "tool", "tool_name": "check_status"}]},
    )
    assert result.value == 0.5  # 1/2 passed


@pytest.mark.asyncio
async def test_composite_scorer_weighted_average():
    s1 = RuleScorer(name="s1", rules=[{"type": "contains", "field": "content", "value": "ok"}])
    s2 = RuleScorer(name="s2", rules=[{"type": "contains", "field": "content", "value": "done"}])

    composite = CompositeScorer(
        name="test",
        scorers=[(s1, 0.6), (s2, 0.4)],
        pass_threshold=0.5,
    )

    result = await composite.score(
        input={},
        output={"content": "ok done"},
    )
    assert result.passed is True
    assert result.value == 1.0


@pytest.mark.asyncio
async def test_composite_scorer_all_must_pass():
    s1 = RuleScorer(name="s1", rules=[{"type": "contains", "field": "content", "value": "ok"}])
    s2 = RuleScorer(name="s2", rules=[{"type": "contains", "field": "content", "value": "missing"}])

    composite = CompositeScorer(
        name="test",
        scorers=[(s1, 1.0), (s2, 1.0)],
        aggregation="all_must_pass",
    )

    result = await composite.score(
        input={},
        output={"content": "ok"},
    )
    assert result.passed is False
