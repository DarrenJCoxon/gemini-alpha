"""
Contrarian AI Trading Bot - Main Entry Point

This module initializes the FastAPI application and sets up the scheduler
for automated trading operations.

Story 1.3: Added Kraken ingestion scheduler and manual trigger endpoint.
"""

import logging
import os
from contextlib import asynccontextmanager
from typing import Any, AsyncGenerator

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from config import get_config
from database import init_db
from services.kraken import close_kraken_client, get_kraken_client
from services.scheduler import get_scheduler, ingest_kraken_data

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
)
logger = logging.getLogger("contrarian_bot")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    Application lifespan manager.
    Handles startup and shutdown events including scheduler lifecycle.
    """
    config = get_config()
    scheduler = get_scheduler()

    # Startup
    await init_db()
    scheduler.start()
    logger.info("Scheduler started")

    # Optional: Run immediate ingestion on startup
    if config.scheduler.run_on_startup:
        logger.info("Running initial Kraken ingestion on startup...")
        try:
            await ingest_kraken_data()
        except Exception as e:
            logger.error(f"Initial ingestion failed: {e}")

    logger.info("Contrarian AI Bot started successfully")

    yield

    # Shutdown
    logger.info("Shutting down...")
    scheduler.shutdown(wait=False)
    await close_kraken_client()
    logger.info("Contrarian AI Bot stopped")


# Initialize FastAPI app
app = FastAPI(
    title="Contrarian AI Trading Bot",
    description="AI-powered cryptocurrency trading bot with contrarian sentiment analysis",
    version="0.1.0",
    lifespan=lifespan,
)

# Configure CORS for development
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",  # Next.js development
        os.getenv("WEB_URL", ""),  # Production web URL
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def root() -> dict[str, str]:
    """Root endpoint returning API status."""
    return {"status": "ok", "service": "contrarian-ai-bot"}


@app.get("/health")
async def health_check() -> dict[str, Any]:
    """
    Health check endpoint for container orchestration.

    Returns scheduler status and basic health info.
    """
    scheduler = get_scheduler()
    return {
        "status": "healthy",
        "scheduler_running": scheduler.running,
        "scheduled_jobs": len(scheduler.get_jobs()),
    }


@app.post("/api/ingest/kraken")
async def trigger_kraken_ingestion() -> dict[str, Any]:
    """
    Manually trigger Kraken OHLCV data ingestion.

    Useful for testing and backfilling data.
    This endpoint bypasses the scheduler and runs ingestion immediately.

    Returns:
        Dict with ingestion statistics including success/failure counts.
    """
    logger.info("Manual Kraken ingestion triggered via API")
    try:
        stats = await ingest_kraken_data()
        return {
            "status": "completed",
            "stats": stats,
        }
    except Exception as e:
        logger.error(f"Manual ingestion failed: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Ingestion failed: {str(e)}",
        )


@app.get("/api/ingest/status")
async def get_ingestion_status() -> dict[str, Any]:
    """
    Get the status of scheduled ingestion jobs.

    Returns information about the scheduler and next run times.
    """
    scheduler = get_scheduler()
    jobs = scheduler.get_jobs()

    job_info = []
    for job in jobs:
        job_info.append({
            "id": job.id,
            "name": job.name,
            "next_run_time": job.next_run_time.isoformat() if job.next_run_time else None,
        })

    return {
        "scheduler_running": scheduler.running,
        "jobs": job_info,
    }


@app.get("/api/kraken/test")
async def test_kraken_connection() -> dict[str, Any]:
    """
    Test connectivity to Kraken exchange.

    Returns connection status and exchange info.
    """
    try:
        client = get_kraken_client()
        is_connected = await client.test_connection()

        return {
            "status": "connected" if is_connected else "disconnected",
            "exchange": "kraken",
        }
    except Exception as e:
        logger.error(f"Kraken connection test failed: {e}")
        raise HTTPException(
            status_code=503,
            detail=f"Connection test failed: {str(e)}",
        )
