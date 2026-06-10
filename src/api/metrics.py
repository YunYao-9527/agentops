"""Metrics and dashboard API."""

from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db import get_db
from src.db.models import Score, Span, Trace

router = APIRouter()


# ─── Response Models ─────────────────────────────────────────────────────────


class DashboardMetrics(BaseModel):
    total_traces: int
    total_spans: int
    total_scores: int
    avg_latency_ms: float | None
    p95_latency_ms: float | None
    p99_latency_ms: float | None
    total_tokens: int
    total_cost_usd: float
    success_rate: float
    avg_score: float | None

    # Time series (last N days)
    daily_traces: list[dict] = []
    daily_costs: list[dict] = []

    # By model
    model_usage: list[dict] = []

    # By status
    status_distribution: dict = {}


class ModelMetrics(BaseModel):
    model: str
    total_calls: int
    total_tokens: int
    total_cost_usd: float
    avg_latency_ms: float | None
    avg_prompt_tokens: float | None
    avg_completion_tokens: float | None


# ─── Endpoints ────────────────────────────────────────────────────────────────


@router.get("/metrics/dashboard", response_model=DashboardMetrics)
async def get_dashboard_metrics(
    project: str = "default",
    days: int = Query(7, ge=1, le=90),
    db: AsyncSession = Depends(get_db),
):
    """Get dashboard metrics for a project."""
    since = datetime.utcnow() - timedelta(days=days)

    # Total counts
    trace_count = (
        await db.execute(
            select(func.count()).where(Trace.project == project, Trace.start_time >= since)
        )
    ).scalar() or 0

    span_count = (
        await db.execute(
            select(func.count())
            .select_from(Span)
            .join(Trace)
            .where(Trace.project == project, Trace.start_time >= since)
        )
    ).scalar() or 0

    score_count = (
        await db.execute(
            select(func.count())
            .select_from(Score)
            .join(Trace)
            .where(Trace.project == project, Trace.start_time >= since)
        )
    ).scalar() or 0

    # Latency stats
    latency_stats = (
        await db.execute(
            select(
                func.avg(Trace.latency_ms),
                func.percentile_cont(0.95).within_group(Trace.latency_ms),
                func.percentile_cont(0.99).within_group(Trace.latency_ms),
            ).where(Trace.project == project, Trace.start_time >= since, Trace.latency_ms.isnot(None))
        )
    ).first()

    avg_latency = float(latency_stats[0]) if latency_stats and latency_stats[0] else None
    p95_latency = float(latency_stats[1]) if latency_stats and latency_stats[1] else None
    p99_latency = float(latency_stats[2]) if latency_stats and latency_stats[2] else None

    # Token and cost totals
    token_cost = (
        await db.execute(
            select(
                func.sum(Trace.total_tokens),
                func.sum(Trace.total_cost_usd),
            ).where(Trace.project == project, Trace.start_time >= since)
        )
    ).first()

    total_tokens = int(token_cost[0]) if token_cost and token_cost[0] else 0
    total_cost = float(token_cost[1]) if token_cost and token_cost[1] else 0.0

    # Success rate
    success_count = (
        await db.execute(
            select(func.count()).where(
                Trace.project == project, Trace.start_time >= since, Trace.status == "ok"
            )
        )
    ).scalar() or 0

    success_rate = success_count / trace_count if trace_count > 0 else 0.0

    # Average score
    avg_score_result = (
        await db.execute(
            select(func.avg(Score.value))
            .select_from(Score)
            .join(Trace)
            .where(Trace.project == project, Trace.start_time >= since)
        )
    ).scalar()

    # Status distribution
    status_rows = (
        await db.execute(
            select(Trace.status, func.count())
            .where(Trace.project == project, Trace.start_time >= since)
            .group_by(Trace.status)
        )
    ).all()
    status_distribution = {row[0]: row[1] for row in status_rows}

    # Model usage
    model_rows = (
        await db.execute(
            select(
                Span.model,
                func.count(),
                func.sum(Span.total_tokens),
                func.sum(Span.cost_usd),
            )
            .join(Trace)
            .where(Trace.project == project, Trace.start_time >= since, Span.model.isnot(None))
            .group_by(Span.model)
        )
    ).all()

    model_usage = [
        {
            "model": row[0],
            "calls": row[1],
            "tokens": int(row[2] or 0),
            "cost_usd": float(row[3] or 0),
        }
        for row in model_rows
    ]

    return DashboardMetrics(
        total_traces=trace_count,
        total_spans=span_count,
        total_scores=score_count,
        avg_latency_ms=avg_latency,
        p95_latency_ms=p95_latency,
        p99_latency_ms=p99_latency,
        total_tokens=total_tokens,
        total_cost_usd=total_cost,
        success_rate=success_rate,
        avg_score=float(avg_score_result) if avg_score_result else None,
        status_distribution=status_distribution,
        model_usage=model_usage,
    )


@router.get("/metrics/models", response_model=list[ModelMetrics])
async def get_model_metrics(
    project: str = "default",
    days: int = Query(7, ge=1, le=90),
    db: AsyncSession = Depends(get_db),
):
    """Get per-model usage metrics."""
    since = datetime.utcnow() - timedelta(days=days)

    rows = (
        await db.execute(
            select(
                Span.model,
                func.count(),
                func.sum(Span.total_tokens),
                func.sum(Span.cost_usd),
                func.avg(Span.latency_ms),
                func.avg(Span.prompt_tokens),
                func.avg(Span.completion_tokens),
            )
            .join(Trace)
            .where(Trace.project == project, Trace.start_time >= since, Span.model.isnot(None))
            .group_by(Span.model)
        )
    ).all()

    return [
        ModelMetrics(
            model=row[0],
            total_calls=row[1],
            total_tokens=int(row[2] or 0),
            total_cost_usd=float(row[3] or 0),
            avg_latency_ms=float(row[4]) if row[4] else None,
            avg_prompt_tokens=float(row[5]) if row[5] else None,
            avg_completion_tokens=float(row[6]) if row[6] else None,
        )
        for row in rows
    ]
