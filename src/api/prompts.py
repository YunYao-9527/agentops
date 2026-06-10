"""Prompt management API."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.db import get_db
from src.db.models import Prompt, PromptVersion

router = APIRouter()


# ─── Request/Response Models ─────────────────────────────────────────────────


class CreatePromptRequest(BaseModel):
    name: str
    description: str | None = None


class CreatePromptVersionRequest(BaseModel):
    type: str = "text"  # text | chat
    content: str
    config: dict | None = None
    labels: list[str] = Field(default_factory=list)
    commit_message: str | None = None


class PromptVersionResponse(BaseModel):
    id: str
    version: int
    type: str
    content: str
    config: dict | None
    labels: list[str]
    commit_message: str | None
    created_at: str


class PromptResponse(BaseModel):
    id: str
    name: str
    description: str | None
    latest_version: int
    labels: dict[str, int]  # label -> version number
    created_at: str
    updated_at: str


class PromptDetailResponse(PromptResponse):
    versions: list[PromptVersionResponse] = []


# ─── Endpoints ────────────────────────────────────────────────────────────────


@router.get("/prompts", response_model=list[PromptResponse])
async def list_prompts(db: AsyncSession = Depends(get_db)):
    """List all prompts with their latest versions."""
    result = await db.execute(select(Prompt).options(selectinload(Prompt.versions)).order_by(Prompt.name))
    prompts = result.scalars().all()

    items = []
    for p in prompts:
        latest = max((v.version for v in p.versions), default=0)
        labels = {}
        for v in p.versions:
            for label in (v.labels or []):
                labels[label] = v.version
        items.append(
            PromptResponse(
                id=str(p.id),
                name=p.name,
                description=p.description,
                latest_version=latest,
                labels=labels,
                created_at=p.created_at.isoformat() if p.created_at else "",
                updated_at=p.updated_at.isoformat() if p.updated_at else "",
            )
        )
    return items


@router.post("/prompts", response_model=dict)
async def create_prompt(req: CreatePromptRequest, db: AsyncSession = Depends(get_db)):
    """Create a new prompt."""
    existing = await db.execute(select(Prompt).where(Prompt.name == req.name))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail=f"Prompt '{req.name}' already exists")

    prompt = Prompt(name=req.name, description=req.description)
    db.add(prompt)
    await db.commit()
    return {"id": str(prompt.id), "name": prompt.name}


@router.get("/prompts/{name}", response_model=PromptDetailResponse)
async def get_prompt(name: str, db: AsyncSession = Depends(get_db)):
    """Get prompt with all versions."""
    result = await db.execute(
        select(Prompt).where(Prompt.name == name).options(selectinload(Prompt.versions))
    )
    prompt = result.scalar_one_or_none()
    if not prompt:
        raise HTTPException(status_code=404, detail=f"Prompt '{name}' not found")

    versions = sorted(prompt.versions, key=lambda v: v.version, reverse=True)
    latest = max((v.version for v in versions), default=0)
    labels = {}
    for v in versions:
        for label in (v.labels or []):
            labels[label] = v.version

    return PromptDetailResponse(
        id=str(prompt.id),
        name=prompt.name,
        description=prompt.description,
        latest_version=latest,
        labels=labels,
        created_at=prompt.created_at.isoformat() if prompt.created_at else "",
        updated_at=prompt.updated_at.isoformat() if prompt.updated_at else "",
        versions=[
            PromptVersionResponse(
                id=str(v.id),
                version=v.version,
                type=v.type,
                content=v.content,
                config=v.config,
                labels=v.labels or [],
                commit_message=v.commit_message,
                created_at=v.created_at.isoformat() if v.created_at else "",
            )
            for v in versions
        ],
    )


@router.post("/prompts/{name}/versions", response_model=dict)
async def create_prompt_version(
    name: str, req: CreatePromptVersionRequest, db: AsyncSession = Depends(get_db)
):
    """Add a new version to a prompt."""
    result = await db.execute(select(Prompt).where(Prompt.name == name))
    prompt = result.scalar_one_or_none()
    if not prompt:
        raise HTTPException(status_code=404, detail=f"Prompt '{name}' not found")

    # Get next version number
    max_version = (
        await db.execute(
            select(func.max(PromptVersion.version)).where(PromptVersion.prompt_id == prompt.id)
        )
    ).scalar() or 0

    version = PromptVersion(
        prompt_id=prompt.id,
        version=max_version + 1,
        type=req.type,
        content=req.content,
        config=req.config,
        labels=req.labels,
        commit_message=req.commit_message,
    )
    db.add(version)
    await db.commit()

    return {"id": str(version.id), "version": version.version}


@router.get("/prompts/{name}/resolve")
async def resolve_prompt(name: str, label: str = "production", db: AsyncSession = Depends(get_db)):
    """Resolve a prompt by name and label (for SDK runtime fetching)."""
    result = await db.execute(
        select(Prompt).where(Prompt.name == name).options(selectinload(Prompt.versions))
    )
    prompt = result.scalar_one_or_none()
    if not prompt:
        raise HTTPException(status_code=404, detail=f"Prompt '{name}' not found")

    # Find the latest version with the given label
    matching = [v for v in prompt.versions if label in (v.labels or [])]
    if not matching:
        raise HTTPException(status_code=404, detail=f"No version with label '{label}'")

    version = max(matching, key=lambda v: v.version)
    return {
        "name": name,
        "version": version.version,
        "type": version.type,
        "content": version.content,
        "config": version.config,
        "labels": version.labels,
    }
