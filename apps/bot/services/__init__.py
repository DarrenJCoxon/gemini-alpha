"""
Services module - External API integrations.

This module contains service classes for interacting with:
- Kraken API (Story 1.3) - OHLCV data fetching
- LunarCrush API (Story 1.4) - Sentiment data (TODO)
- Other external services
"""

from .kraken import (
    KrakenClient,
    get_kraken_client,
    close_kraken_client,
    SYMBOL_MAP,
)
from .scheduler import (
    get_scheduler,
    ingest_kraken_data,
    get_active_assets,
    upsert_candle,
)

__all__ = [
    # Kraken client
    "KrakenClient",
    "get_kraken_client",
    "close_kraken_client",
    "SYMBOL_MAP",
    # Scheduler
    "get_scheduler",
    "ingest_kraken_data",
    "get_active_assets",
    "upsert_candle",
]
