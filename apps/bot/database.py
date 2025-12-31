"""
Database connection and session management using SQLModel.

This module provides database connectivity for the trading bot,
connecting to the same PostgreSQL database as the Next.js frontend.
"""

import os
from typing import AsyncGenerator

from dotenv import load_dotenv
from sqlmodel import SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlalchemy.ext.asyncio import create_async_engine, AsyncEngine

# Load environment variables
load_dotenv()

# Get database URL from environment
DATABASE_URL = os.getenv("DATABASE_URL", "")

# Convert postgres:// to postgresql+asyncpg:// for async support
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql+asyncpg://", 1)
elif DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://", 1)

# Create async engine
engine: AsyncEngine | None = None


def get_engine() -> AsyncEngine:
    """Get or create the database engine."""
    global engine
    if engine is None:
        if not DATABASE_URL:
            raise ValueError("DATABASE_URL environment variable is not set")
        engine = create_async_engine(
            DATABASE_URL,
            echo=os.getenv("DEBUG", "").lower() == "true",
            pool_pre_ping=True,
        )
    return engine


async def init_db() -> None:
    """
    Initialize the database connection.
    Note: Schema migrations are handled by Prisma in the database package.
    """
    try:
        engine = get_engine()
        # Test connection
        async with engine.begin() as conn:
            await conn.run_sync(lambda _: None)
        print("Database connection established")
    except Exception as e:
        print(f"Warning: Could not connect to database: {e}")
        print("Bot will continue without database connection")


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Provide a database session for dependency injection.

    Usage:
        @app.get("/items")
        async def get_items(session: AsyncSession = Depends(get_session)):
            ...
    """
    engine = get_engine()
    async with AsyncSession(engine) as session:
        yield session
