"""Dataset management API."""

import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.db import get_db
from src.db.models import Dataset, DatasetItem

router = APIRouter()


# ─── Request/Response Models ─────────────────────────────────────────────────


class CreateDatasetRequest(BaseModel):
    name: str
    description: str | None = None
    metadata: dict | None = None


class AddDatasetItemRequest(BaseModel):
    input: dict
    expected_output: dict | None = None
    metadata: dict | None = None


class DatasetItemResponse(BaseModel):
    id: str
    input: dict
    expected_output: dict | None
    metadata: dict | None


class DatasetResponse(BaseModel):
    id: str
    name: str
    description: str | None
    item_count: int
    created_at: str
    updated_at: str


class DatasetDetailResponse(DatasetResponse):
    items: list[DatasetItemResponse] = []


# ─── Endpoints ────────────────────────────────────────────────────────────────


@router.get("/datasets", response_model=list[DatasetResponse])
async def list_datasets(db: AsyncSession = Depends(get_db)):
    """List all datasets."""
    result = await db.execute(select(Dataset).order_by(Dataset.name))
    datasets = result.scalars().all()

    items = []
    for d in datasets:
        count = (
            await db.execute(select(func.count()).where(DatasetItem.dataset_id == d.id))
        ).scalar() or 0
        items.append(
            DatasetResponse(
                id=str(d.id),
                name=d.name,
                description=d.description,
                item_count=count,
                created_at=d.created_at.isoformat() if d.created_at else "",
                updated_at=d.updated_at.isoformat() if d.updated_at else "",
            )
        )
    return items


@router.post("/datasets", response_model=dict)
async def create_dataset(req: CreateDatasetRequest, db: AsyncSession = Depends(get_db)):
    """Create a new dataset."""
    existing = await db.execute(select(Dataset).where(Dataset.name == req.name))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail=f"Dataset '{req.name}' already exists")

    dataset = Dataset(name=req.name, description=req.description, metadata_=req.metadata)
    db.add(dataset)
    await db.commit()
    return {"id": str(dataset.id), "name": dataset.name}


@router.get("/datasets/{dataset_id}", response_model=DatasetDetailResponse)
async def get_dataset(dataset_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """Get dataset with all items."""
    result = await db.execute(
        select(Dataset)
        .where(Dataset.id == dataset_id)
        .options(selectinload(Dataset.items))
    )
    dataset = result.scalar_one_or_none()
    if not dataset:
        raise HTTPException(status_code=404, detail="Dataset not found")

    return DatasetDetailResponse(
        id=str(dataset.id),
        name=dataset.name,
        description=dataset.description,
        item_count=len(dataset.items),
        created_at=dataset.created_at.isoformat() if dataset.created_at else "",
        updated_at=dataset.updated_at.isoformat() if dataset.updated_at else "",
        items=[
            DatasetItemResponse(
                id=str(item.id),
                input=item.input_,
                expected_output=item.expected_output,
                metadata=item.metadata_,
            )
            for item in dataset.items
        ],
    )


@router.post("/datasets/{dataset_id}/items", response_model=dict)
async def add_dataset_item(
    dataset_id: uuid.UUID, req: AddDatasetItemRequest, db: AsyncSession = Depends(get_db)
):
    """Add an item to a dataset."""
    result = await db.execute(select(Dataset).where(Dataset.id == dataset_id))
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Dataset not found")

    item = DatasetItem(
        dataset_id=dataset_id,
        input_=req.input,
        expected_output=req.expected_output,
        metadata_=req.metadata,
    )
    db.add(item)
    await db.commit()
    return {"id": str(item.id)}


@router.post("/datasets/{dataset_id}/items/bulk", response_model=dict)
async def bulk_add_items(
    dataset_id: uuid.UUID,
    items: list[AddDatasetItemRequest],
    db: AsyncSession = Depends(get_db),
):
    """Bulk add items to a dataset."""
    result = await db.execute(select(Dataset).where(Dataset.id == dataset_id))
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Dataset not found")

    created = []
    for req in items:
        item = DatasetItem(
            dataset_id=dataset_id,
            input_=req.input,
            expected_output=req.expected_output,
            metadata_=req.metadata,
        )
        db.add(item)
        created.append(item)

    await db.commit()
    return {"count": len(created)}
