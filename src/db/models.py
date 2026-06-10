"""SQLAlchemy ORM models for AgentOps."""

import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


# ─── Enums ────────────────────────────────────────────────────────────────────


class SpanType(str, enum.Enum):
    TRACE = "trace"
    LLM = "llm"
    TOOL = "tool"
    CHAIN = "chain"
    EVENT = "event"


class ScoreSource(str, enum.Enum):
    RULE = "rule"
    LLM_JUDGE = "llm_judge"
    HUMAN = "human"


class ExperimentStatus(str, enum.Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


# ─── Trace & Span ─────────────────────────────────────────────────────────────


class Trace(Base):
    """Top-level execution trace."""

    __tablename__ = "traces"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project: Mapped[str] = mapped_column(String(128), index=True, default="default")
    name: Mapped[str] = mapped_column(String(256), index=True)
    user_id: Mapped[str | None] = mapped_column(String(128), index=True)
    session_id: Mapped[str | None] = mapped_column(String(128), index=True)
    tags: Mapped[list | None] = mapped_column(JSONB, default=list)
    metadata_: Mapped[dict | None] = mapped_column("metadata", JSONB, default=dict)
    input_: Mapped[dict | None] = mapped_column("input", JSONB)
    output_: Mapped[dict | None] = mapped_column("output", JSONB)

    # Timing
    start_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    end_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    latency_ms: Mapped[float | None] = mapped_column(Float)

    # Aggregated costs (sum of all child LLM spans)
    total_tokens: Mapped[int] = mapped_column(Integer, default=0)
    prompt_tokens: Mapped[int] = mapped_column(Integer, default=0)
    completion_tokens: Mapped[int] = mapped_column(Integer, default=0)
    total_cost_usd: Mapped[float] = mapped_column(Float, default=0.0)

    # Status
    status: Mapped[str] = mapped_column(String(32), default="ok")  # ok | error
    error: Mapped[str | None] = mapped_column(Text)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    spans: Mapped[list["Span"]] = relationship(back_populates="trace", cascade="all, delete-orphan")
    scores: Mapped[list["Score"]] = relationship(
        back_populates="trace", cascade="all, delete-orphan", foreign_keys="Score.trace_id"
    )

    __table_args__ = (
        Index("ix_traces_project_start", "project", "start_time"),
        Index("ix_traces_tags", "tags", postgresql_using="gin"),
    )


class Span(Base):
    """Individual operation within a trace (tree-structured)."""

    __tablename__ = "spans"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    trace_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("traces.id", ondelete="CASCADE"), index=True
    )
    parent_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("spans.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(256))
    type: Mapped[SpanType] = mapped_column(Enum(SpanType), default=SpanType.SPAN)

    # Input/Output
    input_: Mapped[dict | None] = mapped_column("input", JSONB)
    output_: Mapped[dict | None] = mapped_column("output", JSONB)
    metadata_: Mapped[dict | None] = mapped_column("metadata", JSONB, default=dict)

    # Timing
    start_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    end_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    latency_ms: Mapped[float | None] = mapped_column(Float)

    # LLM-specific fields
    model: Mapped[str | None] = mapped_column(String(128))
    model_parameters: Mapped[dict | None] = mapped_column(JSONB)
    prompt_tokens: Mapped[int] = mapped_column(Integer, default=0)
    completion_tokens: Mapped[int] = mapped_column(Integer, default=0)
    total_tokens: Mapped[int] = mapped_column(Integer, default=0)
    cost_usd: Mapped[float] = mapped_column(Float, default=0.0)

    # Tool-specific fields
    tool_name: Mapped[str | None] = mapped_column(String(128))
    tool_input: Mapped[dict | None] = mapped_column(JSONB)
    tool_output: Mapped[dict | None] = mapped_column(JSONB)

    # Status
    status: Mapped[str] = mapped_column(String(32), default="ok")  # ok | error
    error: Mapped[str | None] = mapped_column(Text)

    # Level (for nesting depth)
    level: Mapped[int] = mapped_column(Integer, default=0)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    trace: Mapped["Trace"] = relationship(back_populates="spans")
    children: Mapped[list["Span"]] = relationship(back_populates="parent", cascade="all, delete-orphan")
    parent: Mapped["Span | None"] = relationship(
        back_populates="children", remote_side="Span.id", foreign_keys=[parent_id]
    )
    scores: Mapped[list["Score"]] = relationship(
        back_populates="span", cascade="all, delete-orphan", foreign_keys="Score.span_id"
    )

    __table_args__ = (Index("ix_spans_trace_type", "trace_id", "type"),)


# ─── Score ────────────────────────────────────────────────────────────────────


class Score(Base):
    """Evaluation score attached to a trace or span."""

    __tablename__ = "scores"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    trace_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("traces.id", ondelete="CASCADE"), index=True
    )
    span_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("spans.id", ondelete="SET NULL"), index=True
    )
    name: Mapped[str] = mapped_column(String(128), index=True)
    value: Mapped[float] = mapped_column(Float)
    source: Mapped[ScoreSource] = mapped_column(Enum(ScoreSource), default=ScoreSource.RULE)
    comment: Mapped[str | None] = mapped_column(Text)
    metadata_: Mapped[dict | None] = mapped_column("metadata", JSONB)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    trace: Mapped["Trace"] = relationship(back_populates="scores")
    span: Mapped["Span | None"] = relationship(back_populates="scores")


# ─── Prompt Registry ─────────────────────────────────────────────────────────


class Prompt(Base):
    """Prompt container with versioning."""

    __tablename__ = "prompts"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(256), unique=True, index=True)
    description: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    versions: Mapped[list["PromptVersion"]] = relationship(
        back_populates="prompt", cascade="all, delete-orphan"
    )


class PromptVersion(Base):
    """A specific version of a prompt."""

    __tablename__ = "prompt_versions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    prompt_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("prompts.id", ondelete="CASCADE"), index=True
    )
    version: Mapped[int] = mapped_column(Integer)
    type: Mapped[str] = mapped_column(String(32), default="text")  # text | chat
    content: Mapped[str] = mapped_column(Text)  # For chat: JSON array of messages
    config: Mapped[dict | None] = mapped_column(JSONB)  # model params, etc.
    labels: Mapped[list | None] = mapped_column(JSONB, default=list)  # ["production", "staging"]
    commit_message: Mapped[str | None] = mapped_column(String(512))

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    prompt: Mapped["Prompt"] = relationship(back_populates="versions")

    __table_args__ = (
        Index("ix_prompt_versions_prompt_version", "prompt_id", "version", unique=True),
        Index("ix_prompt_versions_labels", "labels", postgresql_using="gin"),
    )


# ─── Dataset & Evaluation ────────────────────────────────────────────────────


class Dataset(Base):
    """Evaluation dataset."""

    __tablename__ = "datasets"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(256), unique=True, index=True)
    description: Mapped[str | None] = mapped_column(Text)
    metadata_: Mapped[dict | None] = mapped_column("metadata", JSONB)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    items: Mapped[list["DatasetItem"]] = relationship(back_populates="dataset", cascade="all, delete-orphan")
    experiments: Mapped[list["Experiment"]] = relationship(back_populates="dataset")


class DatasetItem(Base):
    """A single test case in a dataset."""

    __tablename__ = "dataset_items"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    dataset_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("datasets.id", ondelete="CASCADE"), index=True
    )
    input_: Mapped[dict] = mapped_column("input", JSONB)
    expected_output: Mapped[dict | None] = mapped_column(JSONB)
    metadata_: Mapped[dict | None] = mapped_column("metadata", JSONB)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    dataset: Mapped["Dataset"] = relationship(back_populates="items")


class Experiment(Base):
    """An evaluation experiment run."""

    __tablename__ = "experiments"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(256), index=True)
    dataset_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("datasets.id", ondelete="CASCADE"), index=True
    )
    status: Mapped[ExperimentStatus] = mapped_column(
        Enum(ExperimentStatus), default=ExperimentStatus.PENDING
    )

    # Config snapshot (model, prompt version, params)
    config: Mapped[dict | None] = mapped_column(JSONB)

    # Aggregate results
    total_items: Mapped[int] = mapped_column(Integer, default=0)
    completed_items: Mapped[int] = mapped_column(Integer, default=0)
    failed_items: Mapped[int] = mapped_column(Integer, default=0)
    aggregate_scores: Mapped[dict | None] = mapped_column(JSONB)  # {"accuracy": 0.85, ...}

    # Linked trace IDs
    trace_ids: Mapped[list | None] = mapped_column(JSONB, default=list)

    # Timing
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    dataset: Mapped["Dataset"] = relationship(back_populates="experiments")
