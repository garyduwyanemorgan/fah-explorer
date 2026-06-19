"""FAH Explorer API entrypoint.

Run locally:  uvicorn fah.main:app --reload --app-dir backend
Docs at /docs.
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from fah.api import (
    routes_extraction,
    routes_layers,
    routes_map,
    routes_pages,
    routes_projects,
    routes_risk,
    routes_translate,
    routes_upload,
)
from fah.config import PROJECT_ROOT, configure_logging, get_settings
from fah.db.session import init_db

configure_logging()
logger = logging.getLogger("fah.main")
settings = get_settings()


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    init_db()
    logger.info("%s v%s ready", settings.app_name, settings.version)
    yield


app = FastAPI(
    title=settings.app_name,
    version=settings.version,
    description=(
        "Forensic Asset Hydrogeology Explorer — translates geotechnical reports into "
        "groundwater behaviour and asset-risk intelligence."
    ),
    lifespan=lifespan,
)

app.include_router(routes_projects.router)
app.include_router(routes_upload.router)
app.include_router(routes_extraction.router)
app.include_router(routes_translate.router)
app.include_router(routes_risk.router)
app.include_router(routes_layers.router)
app.include_router(routes_map.router)
app.include_router(routes_pages.router)

app.mount(
    "/static",
    StaticFiles(directory=str(PROJECT_ROOT / "frontend" / "static")),
    name="static",
)


@app.get("/health", tags=["meta"])
def health() -> dict[str, str]:
    return {"status": "ok", "app": settings.app_name, "version": settings.version}
