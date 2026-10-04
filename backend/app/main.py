"""
SecureStego — FastAPI Application Entrypoint

Main application factory. Includes all routers, startup/shutdown events,
Prometheus metrics middleware, and the health check endpoint.
"""

import json
import logging
import sys
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles

from app.api import auth, decode, encode, operations
from app.config import get_settings
from app.db.mongo import close_mongo_client
from app.db.postgres import create_tables
from app.services.storage_service import initialize_storage
from app.monitoring.metrics import PrometheusMiddleware, get_metrics_response

settings = get_settings()


# ---------------------------------------------------------------------------
# Structured JSON logging (Rule 5.1: never log plaintext, passwords, keys)
# ---------------------------------------------------------------------------

class JSONFormatter(logging.Formatter):
    """Structured JSON log formatter.

    Each log line is a JSON object with: timestamp, level, logger, message.
    Never includes request body, passwords, or private keys (Rule 5.1).
    """

    def format(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info and record.exc_info[0] is not None:
            log_entry["exception"] = self.formatException(record.exc_info)
        return json.dumps(log_entry)


def _configure_logging() -> None:
    """Set up structured JSON logging for production, or readable format for dev."""
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG if settings.debug else logging.INFO)

    handler = logging.StreamHandler(sys.stdout)
    if settings.debug:
        handler.setFormatter(logging.Formatter(
            "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
        ))
    else:
        handler.setFormatter(JSONFormatter())

    root_logger.handlers = [handler]


_configure_logging()
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan — startup and shutdown hooks."""
    logger.info("Starting SecureStego API...")

    # Create database tables (dev/test mode — production uses Alembic)
    await create_tables()

    # Initialize configured storage (creates local dir or MinIO bucket)
    initialize_storage()

    logger.info("SecureStego API ready.")
    yield

    # Shutdown hooks
    await close_mongo_client()
    logger.info("Shutting down SecureStego API.")


app = FastAPI(
    title="SecureStego API",
    description="Security-first image steganography platform with encrypted message embedding.",
    version="0.5.0",
    lifespan=lifespan,
)

# CORS — allow all origins in dev (tighten in production)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Prometheus metrics middleware — instruments all requests
app.add_middleware(PrometheusMiddleware)

# Include routers
app.include_router(auth.router)
app.include_router(encode.router)
app.include_router(decode.router)
app.include_router(operations.router)


# --- Health check endpoint (for load balancer) ---

@app.get("/health", tags=["system"])
async def health_check():
    """Health check endpoint for load balancer probes."""
    return {"status": "ok", "service": "securestego"}


@app.get("/metrics", tags=["system"], include_in_schema=False)
async def metrics():
    """Prometheus metrics endpoint.

    Scraped by Prometheus every 15 seconds (see infra/prometheus/prometheus.yml).
    Exposes: request count, latency histogram, error count — all labeled by
    endpoint and method.
    """
    body, content_type = get_metrics_response()
    return Response(content=body, media_type=content_type)


# --- Storage file serving (local backend fallback) ---

@app.get("/storage/{storage_key}", tags=["storage"])
async def serve_stored_file(storage_key: str):
    """Serve a file from local storage.

    Used when STORAGE_BACKEND=local. When STORAGE_BACKEND=s3,
    the /encode response returns a pre-signed S3 URL instead.
    """
    storage_dir = Path(settings.storage_local_dir)
    file_path = storage_dir / storage_key

    if not file_path.exists():
        from fastapi import HTTPException, status
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File not found.",
        )

    return FileResponse(
        path=str(file_path),
        filename=storage_key,
        media_type="image/png",
    )


# ---------------------------------------------------------------------------
# Serve React frontend (built via `npm run build` in /frontend)
# The compiled output is copied to /app/static during Docker build.
# All unknown routes fall through to index.html so React Router works.
# ---------------------------------------------------------------------------

_STATIC_DIR = Path(__file__).parent.parent / "static"
_INDEX_HTML = _STATIC_DIR / "index.html"

if _STATIC_DIR.exists():
    # Mount assets (JS/CSS/images) at /assets
    app.mount("/assets", StaticFiles(directory=str(_STATIC_DIR / "assets")), name="assets")

    @app.get("/{full_path:path}", response_class=HTMLResponse, include_in_schema=False)
    async def serve_spa(full_path: str):
        """Catch-all: serve the React SPA for any non-API route.

        React Router handles client-side routing — FastAPI just
        always returns index.html for unknown paths.
        """
        return HTMLResponse(content=_INDEX_HTML.read_text(), status_code=200)
