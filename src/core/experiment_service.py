"""Execute dataset evaluations and persist their observable results."""

import asyncio
from datetime import datetime, timezone
import uuid

from src.config import get_settings
from src.core.eval_runner import EvalRunner
from src.core.scorers.base import Scorer, ScorerResult
from src.core.scorers.rule_scorer import RuleScorer
from src.db.models import ExperimentStatus, Score, Span, Trace


class ExpectedOutputScorer(Scorer):
    name = "expected_match"

    async def score(self, input, output, expected=None, trace_data=None):
        passed = bool(expected) and all(output.get(k) == v for k, v in expected.items())
        return ScorerResult(self.name, float(passed), passed)


def build_task(config):
    task_name = config.get("task", "echo")
    if task_name not in {"echo", "recorded_output", "llm"}:
        raise ValueError("task must be echo, recorded_output, or llm")
    if task_name == "llm" and not get_settings().llm.openai_api_key:
        raise ValueError("Configure OPENAI_API_KEY before running an LLM evaluation")

    async def task(input_data):
        if task_name == "recorded_output":
            output = input_data.get("output")
            if not isinstance(output, dict):
                raise ValueError("recorded_output requires an input.output object")
            return output
        content = str(input_data.get("query", input_data.get("content", "")))
        if task_name == "echo":
            return {"content": content}
        from openai import AsyncOpenAI
        async with AsyncOpenAI(api_key=get_settings().llm.openai_api_key) as client:
            response = await client.chat.completions.create(
                model=get_settings().llm.openai_model,
                messages=[{"role": "user", "content": content}],
            )
            return {"content": response.choices[0].message.content or ""}

    return task


async def execute_experiment(db, experiment, items, config):
    task = build_task(config)
    rules = config.get("rules")
    scorers = [RuleScorer(name="rules", rules=rules)] if rules else [ExpectedOutputScorer()]
    runner = EvalRunner(scorers=scorers, max_concurrent=min(max(int(config.get("max_concurrent", 3)), 1), 10))
    experiment.status = ExperimentStatus.RUNNING
    experiment.started_at = datetime.now(timezone.utc)
    await db.commit()
    try:
        summary = await asyncio.wait_for(runner.run(
            dataset=[{"input": item.input_, "expected_output": item.expected_output} for item in items],
            task_fn=task, config=config,
        ), timeout=120)
        trace_ids = []
        for row in summary["results"]:
            trace_id = uuid.uuid4()
            trace_ids.append(str(trace_id))
            db.add(Trace(id=trace_id, project="evaluations", name=experiment.name,
                         input_=row["input"], output_=row["output"],
                         status=row["status"], error=row.get("error"),
                         metadata_={"experiment_id": str(experiment.id)},
                         end_time=datetime.now(timezone.utc)))
            db.add(Span(trace_id=trace_id, name="dataset task", input_=row["input"],
                        output_=row["output"], status=row["status"], error=row.get("error")))
            for name, score in row["scores"].items():
                db.add(Score(trace_id=trace_id, name=name, value=score["value"], comment=score.get("comment")))
        experiment.trace_ids = trace_ids
        experiment.completed_items = summary["completed_items"]
        experiment.failed_items = summary["failed_items"]
        experiment.aggregate_scores = {"overall_score": summary["overall_score"],
                                       "scorers": summary["scorer_aggregates"]}
        experiment.status = ExperimentStatus.COMPLETED if not summary["failed_items"] else ExperimentStatus.FAILED
    except Exception as exc:
        experiment.status = ExperimentStatus.FAILED
        experiment.aggregate_scores = {"error": type(exc).__name__}
        experiment.failed_items = experiment.total_items
    experiment.completed_at = datetime.now(timezone.utc)
    await db.commit()
    return experiment
