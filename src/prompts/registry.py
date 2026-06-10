"""Prompt version registry with label-based resolution."""

import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import Prompt, PromptVersion

logger = structlog.get_logger()


class PromptRegistry:
    """
    Manages versioned prompts with label-based resolution.

    Usage:
        registry = PromptRegistry(db)

        # Create a prompt
        await registry.create("customer-greeting", "Customer greeting prompt")

        # Add versions
        await registry.add_version("customer-greeting", "Hello! How can I help?", labels=["production"])
        await registry.add_version("customer-greeting", "Hi there! What can I do for you?", labels=["staging"])

        # Resolve by label
        prompt = await registry.resolve("customer-greeting", label="production")
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, name: str, description: str | None = None) -> Prompt:
        """Create a new prompt container."""
        prompt = Prompt(name=name, description=description)
        self.db.add(prompt)
        await self.db.commit()
        await self.db.refresh(prompt)
        logger.info("Prompt created", name=name)
        return prompt

    async def add_version(
        self,
        name: str,
        content: str,
        type: str = "text",
        config: dict | None = None,
        labels: list[str] | None = None,
        commit_message: str | None = None,
    ) -> PromptVersion:
        """Add a new version to an existing prompt."""
        result = await self.db.execute(select(Prompt).where(Prompt.name == name))
        prompt = result.scalar_one_or_none()
        if not prompt:
            raise ValueError(f"Prompt '{name}' not found")

        max_version = (
            await self.db.execute(
                select(func.max(PromptVersion.version)).where(PromptVersion.prompt_id == prompt.id)
            )
        ).scalar() or 0

        version = PromptVersion(
            prompt_id=prompt.id,
            version=max_version + 1,
            type=type,
            content=content,
            config=config,
            labels=labels or [],
            commit_message=commit_message,
        )
        self.db.add(version)
        await self.db.commit()
        await self.db.refresh(version)

        logger.info("Prompt version added", name=name, version=version.version, labels=labels)
        return version

    async def resolve(self, name: str, label: str = "production") -> dict:
        """
        Resolve a prompt by name and label.

        Returns the latest version that has the specified label.
        """
        result = await self.db.execute(
            select(Prompt).where(Prompt.name == name)
        )
        prompt = result.scalar_one_or_none()
        if not prompt:
            raise ValueError(f"Prompt '{name}' not found")

        # Find latest version with the label
        result = await self.db.execute(
            select(PromptVersion)
            .where(PromptVersion.prompt_id == prompt.id)
            .order_by(PromptVersion.version.desc())
        )
        versions = result.scalars().all()

        for v in versions:
            if label in (v.labels or []):
                return {
                    "name": name,
                    "version": v.version,
                    "type": v.type,
                    "content": v.content,
                    "config": v.config,
                    "labels": v.labels,
                }

        raise ValueError(f"No version of '{name}' with label '{label}'")

    async def get_latest(self, name: str) -> dict:
        """Get the latest version of a prompt (ignoring labels)."""
        result = await self.db.execute(
            select(Prompt).where(Prompt.name == name)
        )
        prompt = result.scalar_one_or_none()
        if not prompt:
            raise ValueError(f"Prompt '{name}' not found")

        result = await self.db.execute(
            select(PromptVersion)
            .where(PromptVersion.prompt_id == prompt.id)
            .order_by(PromptVersion.version.desc())
            .limit(1)
        )
        version = result.scalar_one_or_none()
        if not version:
            raise ValueError(f"No versions for prompt '{name}'")

        return {
            "name": name,
            "version": version.version,
            "type": version.type,
            "content": version.content,
            "config": version.config,
            "labels": version.labels,
        }

    async def list_prompts(self) -> list[dict]:
        """List all prompts with their version info."""
        result = await self.db.execute(select(Prompt))
        prompts = result.scalars().all()

        items = []
        for p in prompts:
            versions_result = await self.db.execute(
                select(PromptVersion)
                .where(PromptVersion.prompt_id == p.id)
                .order_by(PromptVersion.version.desc())
            )
            versions = versions_result.scalars().all()

            latest = versions[0] if versions else None
            labels = {}
            for v in versions:
                for label in (v.labels or []):
                    if label not in labels:
                        labels[label] = v.version

            items.append({
                "name": p.name,
                "description": p.description,
                "latest_version": latest.version if latest else 0,
                "labels": labels,
                "total_versions": len(versions),
            })

        return items

    async def add_label(self, name: str, version: int, label: str) -> None:
        """Add a label to a specific version."""
        result = await self.db.execute(
            select(Prompt).where(Prompt.name == name)
        )
        prompt = result.scalar_one_or_none()
        if not prompt:
            raise ValueError(f"Prompt '{name}' not found")

        result = await self.db.execute(
            select(PromptVersion).where(
                PromptVersion.prompt_id == prompt.id,
                PromptVersion.version == version,
            )
        )
        pv = result.scalar_one_or_none()
        if not pv:
            raise ValueError(f"Version {version} not found for prompt '{name}'")

        labels = pv.labels or []
        if label not in labels:
            labels.append(label)
            pv.labels = labels
            await self.db.commit()
            logger.info("Label added", name=name, version=version, label=label)
