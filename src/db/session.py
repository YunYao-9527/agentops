"""Database session management."""

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from src.config import get_settings
from src.db.models import Base

settings = get_settings()

# Ensure async URL format
db_url = settings.db.url
if db_url.startswith("postgresql://") and "+asyncpg" not in db_url:
    db_url = db_url.replace("postgresql://", "postgresql+asyncpg://", 1)

# Use NullPool for serverless environments (Render free tier)
engine = create_async_engine(
    db_url,
    echo=settings.db.echo,
    pool_pre_ping=True,
    poolclass=NullPool if settings.app_env == "production" else None,
    pool_size=10 if settings.app_env != "production" else None,
    max_overflow=20 if settings.app_env != "production" else None,
)

async_session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def init_db() -> None:
    """Create all tables."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency injection for database sessions."""
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def get_db_session() -> AsyncSession:
    """Direct session factory call."""
    return async_session_factory()
