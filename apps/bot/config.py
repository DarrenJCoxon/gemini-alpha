"""
Configuration management for the Contrarian AI Trading Bot.

This module provides centralized configuration loading from environment
variables with validation and sensible defaults.
"""

import os
from dataclasses import dataclass, field
from typing import Optional

from dotenv import load_dotenv

# Load environment variables
load_dotenv()


@dataclass
class DatabaseConfig:
    """Database connection configuration."""

    url: str = field(default_factory=lambda: os.getenv("DATABASE_URL", ""))
    pool_size: int = field(
        default_factory=lambda: int(os.getenv("DATABASE_POOL_SIZE", "10"))
    )
    debug: bool = field(
        default_factory=lambda: os.getenv("DEBUG", "").lower() == "true"
    )

    def get_async_url(self) -> str:
        """Convert URL to async-compatible format."""
        url = self.url
        if url.startswith("postgres://"):
            url = url.replace("postgres://", "postgresql+asyncpg://", 1)
        elif url.startswith("postgresql://"):
            url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
        return url


@dataclass
class KrakenConfig:
    """Kraken API configuration."""

    api_key: Optional[str] = field(
        default_factory=lambda: os.getenv("KRAKEN_API_KEY")
    )
    api_secret: Optional[str] = field(
        default_factory=lambda: os.getenv("KRAKEN_API_SECRET")
    )
    rate_limit_ms: int = field(
        default_factory=lambda: int(os.getenv("KRAKEN_RATE_LIMIT_MS", "500"))
    )
    enable_rate_limit: bool = True
    retry_count: int = 3
    retry_min_wait: int = 2
    retry_max_wait: int = 10


@dataclass
class SchedulerConfig:
    """APScheduler configuration."""

    timezone: str = "UTC"
    # Cron expression for 15-minute intervals: 0, 15, 30, 45 minutes
    ingest_cron_minutes: str = "0,15,30,45"
    # Run immediate ingestion on startup
    run_on_startup: bool = field(
        default_factory=lambda: os.getenv("RUN_INGESTION_ON_STARTUP", "false").lower() == "true"
    )


@dataclass
class Config:
    """Main application configuration."""

    database: DatabaseConfig = field(default_factory=DatabaseConfig)
    kraken: KrakenConfig = field(default_factory=KrakenConfig)
    scheduler: SchedulerConfig = field(default_factory=SchedulerConfig)
    web_url: str = field(default_factory=lambda: os.getenv("WEB_URL", ""))
    debug: bool = field(
        default_factory=lambda: os.getenv("DEBUG", "").lower() == "true"
    )


# Global configuration instance
config = Config()


def get_config() -> Config:
    """Get the global configuration instance."""
    return config
