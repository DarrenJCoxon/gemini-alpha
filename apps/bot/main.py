"""
Contrarian AI Trading Bot - Main Entry Point

This module initializes the FastAPI application and sets up the scheduler
for automated trading operations.
"""

import os
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from database import init_db

# Load environment variables
load_dotenv()

# Initialize scheduler
scheduler = AsyncIOScheduler()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    Application lifespan manager.
    Handles startup and shutdown events.
    """
    # Startup
    await init_db()
    scheduler.start()
    print("Contrarian AI Bot started successfully")

    yield

    # Shutdown
    scheduler.shutdown()
    print("Contrarian AI Bot stopped")


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
async def health_check() -> dict[str, str]:
    """Health check endpoint for container orchestration."""
    return {"status": "healthy"}
