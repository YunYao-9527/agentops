"""FastAPI application entry point."""

from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from src.config import get_settings
from src.db.session import init_db

logger = structlog.get_logger()
settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifecycle: startup and shutdown."""
    logger.info("Starting AgentOps", env=settings.app_env)
    await init_db()
    logger.info("Database initialized")
    yield
    logger.info("Shutting down AgentOps")


app = FastAPI(
    title="AgentOps",
    description="Agent Evaluation & Observability Platform",
    version="0.1.0",
    lifespan=lifespan,
)

# Static files and templates
import os

static_dir = os.path.join(os.path.dirname(__file__), "web", "static")
templates_dir = os.path.join(os.path.dirname(__file__), "web", "templates")

if os.path.isdir(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

templates = Jinja2Templates(directory=templates_dir)

# Register API routers
from src.api.ingestion import router as ingestion_router
from src.api.traces import router as traces_router
from src.api.prompts import router as prompts_router
from src.api.datasets import router as datasets_router
from src.api.evaluations import router as evaluations_router
from src.api.metrics import router as metrics_router
from src.web.routes import router as web_router

app.include_router(ingestion_router, prefix="/api/v1", tags=["ingestion"])
app.include_router(traces_router, prefix="/api/v1", tags=["traces"])
app.include_router(prompts_router, prefix="/api/v1", tags=["prompts"])
app.include_router(datasets_router, prefix="/api/v1", tags=["datasets"])
app.include_router(evaluations_router, prefix="/api/v1", tags=["evaluations"])
app.include_router(metrics_router, prefix="/api/v1", tags=["metrics"])
app.include_router(web_router, tags=["web"])


@app.get("/health")
async def health():
    return {"status": "ok", "version": "0.1.0"}
