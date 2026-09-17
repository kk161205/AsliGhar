import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api.scan import router as scan_router
from app.core.health import check_dependencies
from app.core.logging import configure_logging
from app.models.db import init_db
from app.services.image_host import STATIC_DIR

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging()
    await init_db()
    status = await check_dependencies()
    if all(status.values()):
        logger.info("Startup verification passed — SerpApi and Groq keys are live. Ready to serve.")
    else:
        logger.error(
            "Startup verification found unusable API keys: %s — "
            "requests depending on them will fail until this is fixed.",
            status,
        )
    yield


app = FastAPI(title="AsliGhar API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(scan_router)
app.mount("/static/scans", StaticFiles(directory=STATIC_DIR), name="scans")


@app.get("/health")
async def health() -> dict:
    dependencies = await check_dependencies()
    return {
        "status": "ok" if all(dependencies.values()) else "degraded",
        "dependencies": dependencies,
    }
