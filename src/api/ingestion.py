"""Ingestion API — receives traces, spans, and scores from SDK."""

import uuid
from datetime import datetime

import structlog
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db import get_db
from src.db.models import Score, ScoreSource, Span, SpanType, Trace

logger = structlog.get_logger()
router = APIRouter()


# ─── Request Models ───────────────────────────────────────────────────────────


class CreateTraceRequest(BaseModel):
    id: uuid.UUID | None = None
    project: str = "default"
    name: str
    user_id: str | None = None
    session_id: str | None = None
    tags: list[str] = Field(default_factory=list)
    metadata: dict | None = None
    input: dict | None = None
    output: dict | None = None


class CreateSpanRequest(BaseModel):
    id: uuid.UUID | None = None
    trace_id: uuid.UUID
    parent_id: uuid.UUID | None = None
    name: str
    type: SpanType = SpanType.CHAIN
    input: dict | None = None
    output: dict | None = None
    metadata: dict | None = None

    # LLM fields
    model: str | None = None
    model_parameters: dict | None = None
    prompt_tokens: int = 0
    completion_tokens: int = 0

    # Tool fields
    tool_name: str | None = None
    tool_input: dict | None = None
    tool_output: dict | None = None

    status: str = "ok"
    error: str | None = None


class CreateScoreRequest(BaseModel):
    trace_id: uuid.UUID
    span_id: uuid.UUID | None = None
    name: str
    value: float
    source: ScoreSource = ScoreSource.RULE
    comment: str | None = None
    metadata: dict | None = None


class IngestionBatch(BaseModel):
    """Batch ingestion request — accepts multiple events in one call."""

    traces: list[CreateTraceRequest] = Field(default_factory=list)
    spans: list[CreateSpanRequest] = Field(default_factory=list)
    scores: list[CreateScoreRequest] = Field(default_factory=list)


class IngestionResponse(BaseModel):
    trace_ids: list[uuid.UUID] = Field(default_factory=list)
    span_ids: list[uuid.UUID] = Field(default_factory=list)
    score_ids: list[uuid.UUID] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)


# ─── Endpoints ────────────────────────────────────────────────────────────────


@router.post("/ingestion", response_model=IngestionResponse)
async def ingest_batch(batch: IngestionBatch, db: AsyncSession = Depends(get_db)):
    """Batch ingestion: accepts traces, spans, and scores in a single call."""
    response = IngestionResponse()

    # Process traces
    for req in batch.traces:
        try:
            trace = Trace(
                id=req.id or uuid.uuid4(),
                project=req.project,
                name=req.name,
                user_id=req.user_id,
                session_id=req.session_id,
                tags=req.tags,
                metadata_=req.metadata,
                input_=req.input,
                output_=req.output,
            )
            db.add(trace)
            await db.flush()
            response.trace_ids.append(trace.id)
        except Exception as e:
            response.errors.append(f"trace {req.name}: {e!s}")

    # Process spans
    for req in batch.spans:
        try:
            span = Span(
                id=req.id or uuid.uuid4(),
                trace_id=req.trace_id,
                parent_id=req.parent_id,
                name=req.name,
                type=req.type,
                input_=req.input,
                output_=req.output,
                metadata_=req.metadata,
                model=req.model,
                model_parameters=req.model_parameters,
                prompt_tokens=req.prompt_tokens,
                completion_tokens=req.completion_tokens,
                total_tokens=req.prompt_tokens + req.completion_tokens,
                tool_name=req.tool_name,
                tool_input=req.tool_input,
                tool_output=req.tool_output,
                status=req.status,
                error=req.error,
            )
            db.add(span)
            await db.flush()
            response.span_ids.append(span.id)
        except Exception as e:
            response.errors.append(f"span {req.name}: {e!s}")

    # Process scores
    for req in batch.scores:
        try:
            score = Score(
                trace_id=req.trace_id,
                span_id=req.span_id,
                name=req.name,
                value=req.value,
                source=req.source,
                comment=req.comment,
                metadata_=req.metadata,
            )
            db.add(score)
            await db.flush()
            response.score_ids.append(score.id)
        except Exception as e:
            response.errors.append(f"score {req.name}: {e!s}")

    await db.commit()

    logger.info(
        "Ingestion batch processed",
        traces=len(response.trace_ids),
        spans=len(response.span_ids),
        scores=len(response.score_ids),
        errors=len(response.errors),
    )

    return response


@router.post("/traces", response_model=dict)
async def create_trace(req: CreateTraceRequest, db: AsyncSession = Depends(get_db)):
    """Create a single trace."""
    trace = Trace(
        id=req.id or uuid.uuid4(),
        project=req.project,
        name=req.name,
        user_id=req.user_id,
        session_id=req.session_id,
        tags=req.tags,
        metadata_=req.metadata,
        input_=req.input,
        output_=req.output,
    )
    db.add(trace)
    await db.commit()
    return {"id": str(trace.id)}


@router.post("/spans", response_model=dict)
async def create_span(req: CreateSpanRequest, db: AsyncSession = Depends(get_db)):
    """Create a single span."""
    span = Span(
        id=req.id or uuid.uuid4(),
        trace_id=req.trace_id,
        parent_id=req.parent_id,
        name=req.name,
        type=req.type,
        input_=req.input,
        output_=req.output,
        metadata_=req.metadata,
        model=req.model,
        model_parameters=req.model_parameters,
        prompt_tokens=req.prompt_tokens,
        completion_tokens=req.completion_tokens,
        total_tokens=req.prompt_tokens + req.completion_tokens,
        tool_name=req.tool_name,
        tool_input=req.tool_input,
        tool_output=req.tool_output,
        status=req.status,
        error=req.error,
    )
    db.add(span)
    await db.commit()
    return {"id": str(span.id)}


@router.post("/scores", response_model=dict)
async def create_score(req: CreateScoreRequest, db: AsyncSession = Depends(get_db)):
    """Create a single score."""
    score = Score(
        trace_id=req.trace_id,
        span_id=req.span_id,
        name=req.name,
        value=req.value,
        source=req.source,
        comment=req.comment,
        metadata_=req.metadata,
    )
    db.add(score)
    await db.commit()
    return {"id": str(score.id)}
