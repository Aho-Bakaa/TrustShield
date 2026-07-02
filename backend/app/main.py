"""TrustShield FastAPI application."""
from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .config import get_settings
from .llm import llm_status
from .log import get_logger, setup_logging
from .routes import analyze, health

settings = get_settings()
setup_logging()
_log = get_logger("app")


@asynccontextmanager
async def lifespan(app: FastAPI):
    s = llm_status()
    _log.info("TrustShield up | text-model=%s (%s) | vision=%s (%s) | render=%s network=%s",
              s["model"], s["mode"], settings.llm_vision_model,
              "on" if s["vision_available"] else "off",
              settings.render_enabled, settings.network_enabled)
    yield


app = FastAPI(
    title="TrustShield API",
    version="0.1.0",
    description="Multimodal trust & verification layer for securities-market communications.",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(analyze.router)

_FIXTURES = Path(__file__).parent / "fixtures"
app.mount("/fixtures", StaticFiles(directory=str(_FIXTURES), html=True), name="fixtures")


@app.get("/")
async def root():
    return {
        "name": "TrustShield",
        "docs": "/docs",
        "endpoints": ["/health", "/api/analyze/text", "/api/analyze/audio",
                      "/api/analyze/image", "/api/recent", "/fixtures"],
    }
