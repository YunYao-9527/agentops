"""Evaluation API."""

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.db import get_db
from src.db.models import Dataset, Experiment, ExperimentStatus

router = APIRouter()


# ─── Request/Response Models ─────────────────────────────────────────────────


class RunEvaluationRequest(BaseModel):
    name: str
    dataset_id: uuid.UUID
    config: dict | None = None  # model, prompt version, params


class ExperimentResponse(BaseModel):
    id: str
    name: str
    dataset_id: str
    status: str
    config: dict | None
    total_items: int
    completed_items: int
    failed_items: int
    aggregate_scores: dict | None
    trace_ids: list[str]
    started_at: str | None
    completed_at: str | None
    created_at: str


# ─── Endpoints ────────────────────────────────────────────────────────────────


@router.get("/evaluations", response_model=list[ExperimentResponse])
async def list_experiments(
    dataset_id: uuid.UUID | None = None, db: AsyncSession = Depends(get_db)
):
    """List evaluation experiments."""
    query = select(Experiment).order_by(Experiment.created_at.desc())
    if dataset_id:
        query = query.where(Experiment.dataset_id == dataset_id)

    result = await db.execute(query)
    experiments = result.scalars().all()

    return [
        ExperimentResponse(
            id=str(e.id),
            name=e.name,
            dataset_id=str(e.dataset_id),
            status=e.status.value if hasattr(e.status, "value") else e.status,
            config=e.config,
            total_items=e.total_items,
            completed_items=e.completed_items,
            failed_items=e.failed_items,
            aggregate_scores=e.aggregate_scores,
            trace_ids=[str(tid) for tid in (e.trace_ids or [])],
            started_at=e.started_at.isoformat() if e.started_at else None,
            completed_at=e.completed_at.isoformat() if e.completed_at else None,
            created_at=e.created_at.isoformat() if e.created_at else "",
        )
        for e in experiments
    ]


@router.post("/evaluations/run", response_model=dict)
async def run_evaluation(req: RunEvaluationRequest, db: AsyncSession = Depends(get_db)):
    """Create and start an evaluation experiment."""
    # Verify dataset exists
    result = await db.execute(
        select(Dataset).where(Dataset.id == req.dataset_id).options(selectinload(Dataset.items))
    )
    dataset = result.scalar_one_or_none()
    if not dataset:
        raise HTTPException(status_code=404, detail="Dataset not found")

    if not dataset.items:
        raise HTTPException(status_code=400, detail="Dataset has no items")

    experiment = Experiment(
        name=req.name,
        dataset_id=req.dataset_id,
        status=ExperimentStatus.PENDING,
        config=req.config,
        total_items=len(dataset.items),
    )
    db.add(experiment)
    await db.commit()

    # NOTE: Actual evaluation execution is handled by src/core/eval_runner.py
    # This endpoint just creates the experiment record.
    # Use `make eval` or the CLI to actually run evaluations.

    return {
        "id": str(experiment.id),
        "name": experiment.name,
        "status": experiment.status.value,
        "total_items": experiment.total_items,
        "message": "Experiment created. Use the eval runner to execute.",
    }


@router.get("/evaluations/{experiment_id}", response_model=ExperimentResponse)
async def get_experiment(experiment_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """Get evaluation experiment details."""
    result = await db.execute(select(Experiment).where(Experiment.id == experiment_id))
    experiment = result.scalar_one_or_none()
    if not experiment:
        raise HTTPException(status_code=404, detail="Experiment not found")

    return ExperimentResponse(
        id=str(experiment.id),
        name=experiment.name,
        dataset_id=str(experiment.dataset_id),
        status=experiment.status.value if hasattr(experiment.status, "value") else experiment.status,
        config=experiment.config,
        total_items=experiment.total_items,
        completed_items=experiment.completed_items,
        failed_items=experiment.failed_items,
        aggregate_scores=experiment.aggregate_scores,
        trace_ids=[str(tid) for tid in (experiment.trace_ids or [])],
        started_at=experiment.started_at.isoformat() if experiment.started_at else None,
        completed_at=experiment.completed_at.isoformat() if experiment.completed_at else None,
        created_at=experiment.created_at.isoformat() if experiment.created_at else "",
    )
