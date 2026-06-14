"""Web page routes — serves Jinja2 templates."""

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from starlette.templating import Jinja2Templates
import os

router = APIRouter()

templates_dir = os.path.join(os.path.dirname(__file__), "templates")
templates = Jinja2Templates(directory=templates_dir)


@router.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    """Dashboard page."""
    return templates.TemplateResponse(request, "dashboard.html")


@router.get("/traces", response_class=HTMLResponse)
async def traces_page(request: Request):
    """Trace explorer page."""
    return templates.TemplateResponse(request, "traces.html")


@router.get("/traces/{trace_id}", response_class=HTMLResponse)
async def trace_detail_page(request: Request, trace_id: str):
    """Trace detail page."""
    return templates.TemplateResponse(request, "trace_detail.html", {"trace_id": trace_id})


@router.get("/prompts", response_class=HTMLResponse)
async def prompts_page(request: Request):
    """Prompt management page."""
    return templates.TemplateResponse(request, "prompts.html")


@router.get("/datasets", response_class=HTMLResponse)
async def datasets_page(request: Request):
    """Dataset management page."""
    return templates.TemplateResponse(request, "datasets.html")


@router.get("/evaluations", response_class=HTMLResponse)
async def evaluations_page(request: Request):
    """Evaluation results page."""
    return templates.TemplateResponse(request, "evaluations.html")
