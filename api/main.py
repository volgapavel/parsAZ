"""FastAPI application for ClearPic Media Monitoring."""
import os
import sys
from pathlib import Path

# Add model directory to path
sys.path.insert(0, str(Path(__file__).parent.parent / "model"))

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse

from api.routers import search, stats, process

app = FastAPI(
    title="ClearPic Media Monitoring API",
    description="API для мониторинга азербайджанских СМИ, поиска персон и анализа рисков",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Static files and templates
BASE_DIR = Path(__file__).parent.parent
app.mount("/static", StaticFiles(directory=BASE_DIR / "website" / "static"), name="static")
templates = Jinja2Templates(directory=BASE_DIR / "website" / "templates")

# Include routers
app.include_router(search.router, prefix="/api/v1", tags=["Search"])
app.include_router(stats.router, prefix="/api/v1", tags=["Statistics"])
app.include_router(process.router, prefix="/api/v1", tags=["Process"])


# HTML Pages
@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/search", response_class=HTMLResponse)
async def search_page(request: Request):
    return templates.TemplateResponse("search.html", {"request": request})


@app.get("/process", response_class=HTMLResponse)
async def process_page(request: Request):
    return templates.TemplateResponse("process.html", {"request": request})


@app.get("/entities", response_class=HTMLResponse)
async def entities_page(request: Request):
    return templates.TemplateResponse("entities.html", {"request": request})


@app.get("/stats", response_class=HTMLResponse)
async def stats_page(request: Request):
    return templates.TemplateResponse("stats.html", {"request": request})


@app.get("/health")
async def health_check():
    return {"status": "ok", "service": "clearpic-api"}

