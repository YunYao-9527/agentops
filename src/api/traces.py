"""Trace query API."""

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.db import get_db
from src.db.models import Score, Span, Trace

router = APIRouter()


# ─── Response Models ──────────────────────────────────────────────────────────


class SpanResponse(BaseModel):
    id: str
    parent_id: str | None
    name: str
    type: str
    input: dict | None
    output: dict | None
    metadata: dict | None
    model: str | None
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    cost_usd: float
    tool_name: str | None
    tool_input: dict | None
    tool_output: dict | None
    latency_ms: float | None
    status: str
    error: str | None
    level: int
    start_time: str
    end_time: str | None

    class Config:
        from_attributes = True


class ScoreResponse(BaseModel):
    id: str
    trace_id: str
    span_id: str | None
    name: str
    value: float
    source: str
    comment: str | None
    created_at: str

    class Config:
        from_attributes = True


class TraceResponse(BaseModel):
    id: str
    project: str
    name: str
    user_id: str | None
    session_id: str | None
    tags: list[str]
    metadata: dict | None
    input: dict | None
    output: dict | None
    start_time: str
    end_time: str | None
    latency_ms: float | None
    total_tokens: int
    prompt_tokens: int
    completion_tokens: int
    total_cost_usd: float
    status: str
    error: str | None
    span_count: int = 0
    score_count: int = 0

    class Config:
        from_attributes = True


class TraceDetailResponse(TraceResponse):
    spans: list[SpanResponse] = []
    scores: list[ScoreResponse] = []


class TraceListResponse(BaseModel):
    items: list[TraceResponse]
    total: int
    page: int
    page_size: int


# ─── Endpoints ────────────────────────────────────────────────────────────────


@router.get("/traces", response_model=TraceListResponse)
async def list_traces(
    project: str = "default",
    user_id: str | None = None,
    session_id: str | None = None,
    status: str | None = None,
    tag: str | None = None,
    search: str | None = None,
    start_from: datetime | None = None,
    start_to: datetime | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
):
    """List traces with filtering and pagination."""
    query = select(Trace).where(Trace.project == project)

    if user_id:
        query = query.where(Trace.user_id == user_id)
    if session_id:
        query = query.where(Trace.session_id == session_id)
    if status:
        query = query.where(Trace.status == status)
    if search:
        query = query.where(Trace.name.ilike(f"%{search}%"))
    if start_from:
        query = query.where(Trace.start_time >= start_from)
    if start_to:
        query = query.where(Trace.start_time <= start_to)

    # Count
    count_query = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_query)).scalar() or 0

    # Paginate
    query = query.order_by(Trace.start_time.desc())
    query = query.offset((page - 1) * page_size).limit(page_size)

    result = await db.execute(query)
    traces = result.scalars().all()

    items = []
    for t in traces:
        # Get span and score counts
        span_count = (await db.execute(select(func.count()).where(Span.trace_id == t.id))).scalar() or 0
        score_count = (await db.execute(select(func.count()).where(Score.trace_id == t.id))).scalar() or 0

        items.append(
            TraceResponse(
                id=str(t.id),
                project=t.project,
                name=t.name,
                user_id=t.user_id,
                session_id=t.session_id,
                tags=t.tags or [],
                metadata=t.metadata_,
                input=t.input_,
                output=t.output_,
                start_time=t.start_time.isoformat() if t.start_time else "",
                end_time=t.end_time.isoformat() if t.end_time else None,
                latency_ms=t.latency_ms,
                total_tokens=t.total_tokens,
                prompt_tokens=t.prompt_tokens,
                completion_tokens=t.completion_tokens,
                total_cost_usd=t.total_cost_usd,
                status=t.status,
                error=t.error,
                span_count=span_count,
                score_count=score_count,
            )
        )

    return TraceListResponse(items=items, total=total, page=page, page_size=page_size)


@router.get("/traces/{trace_id}", response_model=TraceDetailResponse)
async def get_trace(trace_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """Get trace detail with full span tree and scores."""
    result = await db.execute(
        select(Trace).where(Trace.id == trace_id).options(selectinload(Trace.spans), selectinload(Trace.scores))
    )
    trace = result.scalar_one_or_none()
    if not trace:
        raise HTTPException(status_code=404, detail="Trace not found")

    spans = [
        SpanResponse(
            id=str(s.id),
            parent_id=str(s.parent_id) if s.parent_id else None,
            name=s.name,
            type=s.type.value if hasattr(s.type, "value") else s.type,
            input=s.input_,
            output=s.output_,
            metadata=s.metadata_,
            model=s.model,
            prompt_tokens=s.prompt_tokens,
            completion_tokens=s.completion_tokens,
            total_tokens=s.total_tokens,
            cost_usd=s.cost_usd,
            tool_name=s.tool_name,
            tool_input=s.tool_input,
            tool_output=s.tool_output,
            latency_ms=s.latency_ms,
            status=s.status,
            error=s.error,
            level=s.level,
            start_time=s.start_time.isoformat() if s.start_time else "",
            end_time=s.end_time.isoformat() if s.end_time else None,
        )
        for s in trace.spans
    ]

    scores = [
        ScoreResponse(
            id=str(s.id),
            trace_id=str(s.trace_id),
            span_id=str(s.span_id) if s.span_id else None,
            name=s.name,
            value=s.value,
            source=s.source.value if hasattr(s.source, "value") else s.source,
            comment=s.comment,
            created_at=s.created_at.isoformat() if s.created_at else "",
        )
        for s in trace.scores
    ]

    return TraceDetailResponse(
        id=str(trace.id),
        project=trace.project,
        name=trace.name,
        user_id=trace.user_id,
        session_id=trace.session_id,
        tags=trace.tags or [],
        metadata=trace.metadata_,
        input=trace.input_,
        output=trace.output_,
        start_time=trace.start_time.isoformat() if trace.start_time else "",
        end_time=trace.end_time.isoformat() if trace.end_time else None,
        latency_ms=trace.latency_ms,
        total_tokens=trace.total_tokens,
        prompt_tokens=trace.prompt_tokens,
        completion_tokens=trace.completion_tokens,
        total_cost_usd=trace.total_cost_usd,
        status=trace.status,
        error=trace.error,
        spans=spans,
        scores=scores,
    )


@router.get("/traces/{trace_id}/spans", response_model=list[SpanResponse])
async def list_trace_spans(trace_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """Get all spans for a trace."""
    result = await db.execute(
        select(Span).where(Span.trace_id == trace_id).order_by(Span.start_time)
    )
    spans = result.scalars().all()
    return [
        SpanResponse(
            id=str(s.id),
            parent_id=str(s.parent_id) if s.parent_id else None,
            name=s.name,
            type=s.type.value if hasattr(s.type, "value") else s.type,
            input=s.input_,
            output=s.output_,
            metadata=s.metadata_,
            model=s.model,
            prompt_tokens=s.prompt_tokens,
            completion_tokens=s.completion_tokens,
            total_tokens=s.total_tokens,
            cost_usd=s.cost_usd,
            tool_name=s.tool_name,
            tool_input=s.tool_input,
            tool_output=s.tool_output,
            latency_ms=s.latency_ms,
            status=s.status,
            error=s.error,
            level=s.level,
            start_time=s.start_time.isoformat() if s.start_time else "",
            end_time=s.end_time.isoformat() if s.end_time else None,
        )
        for s in spans
    ]
