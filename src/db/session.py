"""Database session management."""

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from src.config import get_settings
from src.db.models import Base

settings = get_settings()

# Determine database URL — fall back to SQLite if no PostgreSQL configured
db_url = settings.db.url
if not db_url or db_url.startswith("postgresql"):
    import os
    if not os.environ.get("DATABASE_URL"):
        db_url = "sqlite+aiosqlite:///./agentops.db"
    elif db_url.startswith("postgresql://") and "+asyncpg" not in db_url:
        db_url = db_url.replace("postgresql://", "postgresql+asyncpg://", 1)

# Use NullPool for serverless/SQLite, connection pool for PostgreSQL
is_sqlite = db_url.startswith("sqlite")
engine_kwargs: dict = {
    "echo": settings.db.echo,
    "pool_pre_ping": True,
}
if is_sqlite or settings.app_env == "production":
    engine_kwargs["poolclass"] = NullPool
else:
    engine_kwargs["pool_size"] = 10
    engine_kwargs["max_overflow"] = 20

engine = create_async_engine(db_url, **engine_kwargs)

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
