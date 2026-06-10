"""Rule-based scorers for deterministic evaluation."""

import json
import re
from typing import Any

from src.core.scorers.base import Scorer, ScorerResult


class RuleScorer(Scorer):
    """Configurable rule-based scorer supporting multiple rule types."""

    def __init__(
        self,
        name: str = "rule_scorer",
        rules: list[dict[str, Any]] | None = None,
    ):
        self._name = name
        self.rules = rules or []

    @property
    def name(self) -> str:
        return self._name

    async def score(
        self,
        input: dict,
        output: dict,
        expected: dict | None = None,
        trace_data: dict | None = None,
    ) -> ScorerResult:
        if not self.rules:
            return ScorerResult(name=self.name, value=1.0, passed=True, comment="No rules defined")

        passed_rules = 0
        total_rules = len(self.rules)
        comments = []

        for rule in self.rules:
            rule_type = rule.get("type")
            result = self._evaluate_rule(rule, output, expected, trace_data)
            if result:
                passed_rules += 1
            else:
                comments.append(f"Failed: {rule.get('description', rule_type)}")

        value = passed_rules / total_rules if total_rules > 0 else 0.0
        return ScorerResult(
            name=self.name,
            value=value,
            passed=value >= 1.0,
            comment="; ".join(comments) if comments else None,
        )

    def _evaluate_rule(
        self, rule: dict, output: dict, expected: dict | None, trace_data: dict | None
    ) -> bool:
        """Evaluate a single rule."""
        rule_type = rule.get("type")

        if rule_type == "exact_match":
            return self._exact_match(rule, output, expected)
        elif rule_type == "contains":
            return self._contains(rule, output)
        elif rule_type == "not_contains":
            return self._not_contains(rule, output)
        elif rule_type == "regex":
            return self._regex_match(rule, output)
        elif rule_type == "json_path_exists":
            return self._json_path_exists(rule, output)
        elif rule_type == "json_path_equals":
            return self._json_path_equals(rule, output)
        elif rule_type == "tool_called":
            return self._tool_called(rule, trace_data)
        elif rule_type == "tool_not_called":
            return self._tool_not_called(rule, trace_data)
        elif rule_type == "no_hallucination_tools":
            return self._no_hallucination_tools(rule, trace_data)
        elif rule_type == "max_tool_calls":
            return self._max_tool_calls(rule, trace_data)
        elif rule_type == "output_length":
            return self._output_length(rule, output)
        else:
            return True  # Unknown rule type passes

    def _get_nested(self, data: dict, path: str) -> Any:
        """Get value from nested dict using dot notation."""
        keys = path.split(".")
        current = data
        for key in keys:
            if isinstance(current, dict) and key in current:
                current = current[key]
            else:
                return None
        return current

    def _exact_match(self, rule: dict, output: dict, expected: dict | None) -> bool:
        """Check if output field exactly matches expected."""
        field = rule.get("field", "content")
        actual = self._get_nested(output, field)
        if expected:
            exp = self._get_nested(expected, field)
            return actual == exp
        return actual == rule.get("value")

    def _contains(self, rule: dict, output: dict) -> bool:
        """Check if output contains a substring."""
        field = rule.get("field", "content")
        value = rule.get("value", "")
        actual = self._get_nested(output, field)
        if actual is None:
            return False
        return value in str(actual)

    def _not_contains(self, rule: dict, output: dict) -> bool:
        """Check if output does NOT contain a substring."""
        field = rule.get("field", "content")
        value = rule.get("value", "")
        actual = self._get_nested(output, field)
        if actual is None:
            return True
        return value not in str(actual)

    def _regex_match(self, rule: dict, output: dict) -> bool:
        """Check if output matches a regex pattern."""
        field = rule.get("field", "content")
        pattern = rule.get("pattern", "")
        actual = self._get_nested(output, field)
        if actual is None:
            return False
        return bool(re.search(pattern, str(actual)))

    def _json_path_exists(self, rule: dict, output: dict) -> bool:
        """Check if a JSON path exists in output."""
        path = rule.get("path", "")
        return self._get_nested(output, path) is not None

    def _json_path_equals(self, rule: dict, output: dict) -> bool:
        """Check if a JSON path equals a value."""
        path = rule.get("path", "")
        expected = rule.get("value")
        actual = self._get_nested(output, path)
        return actual == expected

    def _tool_called(self, rule: dict, trace_data: dict | None) -> bool:
        """Check if a specific tool was called."""
        if not trace_data:
            return False
        tool_name = rule.get("tool_name", "")
        spans = trace_data.get("spans", [])
        return any(
            s.get("type") == "tool" and s.get("tool_name") == tool_name for s in spans
        )

    def _tool_not_called(self, rule: dict, trace_data: dict | None) -> bool:
        """Check that a specific tool was NOT called."""
        return not self._tool_called(rule, trace_data)

    def _no_hallucination_tools(self, rule: dict, trace_data: dict | None) -> bool:
        """Check that no hallucinated (non-existent) tools were called."""
        if not trace_data:
            return True
        allowed_tools = set(rule.get("allowed_tools", []))
        if not allowed_tools:
            return True
        spans = trace_data.get("spans", [])
        for s in spans:
            if s.get("type") == "tool" and s.get("tool_name") not in allowed_tools:
                return False
        return True

    def _max_tool_calls(self, rule: dict, trace_data: dict | None) -> bool:
        """Check that tool calls don't exceed maximum."""
        if not trace_data:
            return True
        max_calls = rule.get("max", 10)
        spans = trace_data.get("spans", [])
        tool_calls = sum(1 for s in spans if s.get("type") == "tool")
        return tool_calls <= max_calls

    def _output_length(self, rule: dict, output: dict) -> bool:
        """Check output content length."""
        field = rule.get("field", "content")
        actual = self._get_nested(output, field)
        if actual is None:
            return False
        length = len(str(actual))
        min_len = rule.get("min", 0)
        max_len = rule.get("max", float("inf"))
        return min_len <= length <= max_len


# ─── Convenience Factory ─────────────────────────────────────────────────────


def exact_match_scorer(field: str = "content") -> RuleScorer:
    """Create a scorer that checks exact match on a field."""
    return RuleScorer(
        name="exact_match",
        rules=[{"type": "exact_match", "field": field}],
    )


def contains_scorer(value: str, field: str = "content") -> RuleScorer:
    """Create a scorer that checks if output contains a value."""
    return RuleScorer(
        name="contains",
        rules=[{"type": "contains", "field": field, "value": value}],
    )


def tool_usage_scorer(
    required_tools: list[str] | None = None,
    forbidden_tools: list[str] | None = None,
    allowed_tools: list[str] | None = None,
    max_calls: int | None = None,
) -> RuleScorer:
    """Create a scorer for tool usage patterns."""
    rules = []
    if required_tools:
        for tool in required_tools:
            rules.append({"type": "tool_called", "tool_name": tool, "description": f"Tool {tool} must be called"})
    if forbidden_tools:
        for tool in forbidden_tools:
            rules.append({"type": "tool_not_called", "tool_name": tool, "description": f"Tool {tool} must not be called"})
    if allowed_tools:
        rules.append({"type": "no_hallucination_tools", "allowed_tools": allowed_tools})
    if max_calls is not None:
        rules.append({"type": "max_tool_calls", "max": max_calls})

    return RuleScorer(name="tool_usage", rules=rules)
