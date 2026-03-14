"""
main.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Halifax Area Energy Demand Forecasting — FastAPI Application
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Main FastAPI application entry point.

Start with:
    uvicorn main:app --reload --host 0.0.0.0 --port 8000

API Docs:
    http://localhost:8000/docs
    http://localhost:8000/redoc

Author: Dylan Bray · NSCC DBAS 3090 · March 2026
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from datetime import datetime
import logging
from contextlib import asynccontextmanager

from .config import settings, get_logs_dir
from .database import check_db_connection
from .routers import actuals, predictions, model, zones, websocket
from .scheduler import start_scheduler, shutdown_scheduler

# ── Logging Setup ─────────────────────────────────────────────────────────────

log_file = get_logs_dir() / "halifaxenergy.log"

logging.basicConfig(
    level=getattr(logging, settings.log_level.upper()),
    format="%(asctime)s  %(name)-20s  %(levelname)-8s  %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(log_file, mode="a"),
    ],
)

logger = logging.getLogger(__name__)


# ── Lifespan Context Manager (Startup/Shutdown) ──────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifespan context manager for FastAPI app.
    Handles startup and shutdown events.
    """
    # Startup
    logger.info("=" * 70)
    logger.info("  Halifax Energy Forecasting API — Starting")
    logger.info("=" * 70)

    # Check database connection
    if check_db_connection():
        logger.info("  ✓ Database connection OK")
    else:
        logger.error("  ✗ Database connection FAILED")

    # Start scheduler
    try:
        start_scheduler()
        logger.info("  ✓ APScheduler started")
    except Exception as e:
        logger.error(f"  ✗ Scheduler failed to start: {e}")

    logger.info("=" * 70)

    yield  # Application runs here

    # Shutdown
    logger.info("  Shutting down...")
    try:
        shutdown_scheduler()
        logger.info("  ✓ APScheduler stopped")
    except Exception as e:
        logger.error(f"  ✗ Scheduler shutdown error: {e}")


# ── FastAPI Application ───────────────────────────────────────────────────────

app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="""
    Halifax Area Energy Demand Forecasting API

    **Features:**
    - Real-time CCEI HFED load data integration
    - XGBoost predictions with 3 forecast horizons (H1/H2/H3)
    - GeoJSON zone boundaries with predicted/actual load
    - WebSocket streaming for live data
    - Automated daily data extraction and model retraining

    **Data Sources:**
    - CCEI HFED (NS Power load)
    - Environment Canada (weather)
    - Electricity Maps (historical)

    **Author:** Dylan Bray · NSCC DBAS 3090 · March 2026
    """,
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan
)


# ── CORS Middleware ───────────────────────────────────────────────────────────

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Routers ───────────────────────────────────────────────────────────────────

app.include_router(actuals.router)
app.include_router(predictions.router)
app.include_router(model.router)
app.include_router(zones.router)
app.include_router(websocket.router)


# ── Root & Health Endpoints ───────────────────────────────────────────────────

@app.get("/")
def read_root():
    """
    API root endpoint.

    Returns welcome message and links to documentation.
    """
    return {
        "message": "Halifax Energy Forecasting API",
        "version": settings.app_version,
        "docs": "/docs",
        "redoc": "/redoc",
        "health": "/health",
        "endpoints": {
            "actuals": "/api/actuals",
            "predictions": "/api/predictions",
            "zones": "/api/zones",
            "run_model": "/api/run-model",
            "websocket": "/ws/live-actuals"
        }
    }


@app.get("/health")
def health_check():
    """
    Health check endpoint.

    Returns API status and database connectivity.
    """
    db_status = "ok" if check_db_connection() else "error"

    return {
        "status": "ok" if db_status == "ok" else "degraded",
        "database": db_status,
        "timestamp": datetime.now().isoformat(),
        "version": settings.app_version
    }


# ── Exception Handlers ────────────────────────────────────────────────────────

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """
    Global exception handler for uncaught exceptions.
    """
    logger.error(f"Unhandled exception: {exc}", exc_info=True)

    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal server error",
            "detail": str(exc),
            "timestamp": datetime.now().isoformat()
        }
    )


# ── Main Entry Point ──────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=settings.api_reload,
        log_level=settings.log_level.lower()
    )
