"""CLI evaluation runner."""

import asyncio
import json
import sys
from pathlib import Path

import structlog

from src.core.eval_runner import EvalRunner
from src.core.scorers import RuleScorer, LLMJudgeScorer, CompositeScorer

logger = structlog.get_logger()


async def run_eval(config_path: str) -> dict:
    """Run evaluation from a config file."""
    config_file = Path(config_path)
    if not config_file.exists():
        logger.error("Config file not found", path=config_path)
        sys.exit(1)

    with open(config_file) as f:
        config = json.load(f)

    dataset_path = config.get("dataset")
    if not dataset_path:
        logger.error("No dataset specified in config")
        sys.exit(1)

    with open(dataset_path) as f:
        dataset = json.load(f)

    # Build scorers
    scorers = []
    for scorer_config in config.get("scorers", []):
        scorer_type = scorer_config.get("type")
        if scorer_type == "rule":
            scorers.append(RuleScorer(
                name=scorer_config.get("name", "rule"),
                rules=scorer_config.get("rules", []),
            ))
        elif scorer_type == "llm_judge":
            scorers.append(LLMJudgeScorer(
                name=scorer_config.get("name", "llm_judge"),
                criteria=scorer_config.get("criteria", ""),
                threshold=scorer_config.get("threshold", 0.7),
                model=scorer_config.get("model"),
            ))

    # Run
    runner = EvalRunner(
        scorers=scorers,
        max_concurrent=config.get("max_concurrent", 5),
    )

    # Task function from config (would be imported dynamically in production)
    task_fn = config.get("task_fn")
    if not task_fn:
        logger.error("No task_fn specified in config")
        sys.exit(1)

    results = await runner.run(dataset=dataset, task_fn=task_fn, config=config)

    # Output results
    output_dir = Path(config.get("output_dir", "./eval_output"))
    output_dir.mkdir(parents=True, exist_ok=True)
    output_file = output_dir / f"eval_{results['experiment_id']}.json"

    with open(output_file, "w") as f:
        json.dump(results, f, indent=2, default=str)

    logger.info("Evaluation results saved", path=str(output_file))
    print(f"\nResults saved to: {output_file}")
    print(f"Overall score: {results['overall_score']:.3f}")
    print(f"Completed: {results['completed_items']}/{results['total_items']}")

    return results


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python -m src.eval.runner <config.json>")
        sys.exit(1)
    asyncio.run(run_eval(sys.argv[1]))
