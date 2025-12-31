"""
Services module - External API integrations.

This module contains service classes for interacting with:
- Kraken API (Story 1.3) - OHLCV data fetching
- LunarCrush API (Story 1.4) - Sentiment data
- Bluesky/Telegram (Story 1.4) - Social media scraping
- Other external services
"""

from .kraken import (
    KrakenClient,
    get_kraken_client,
    close_kraken_client,
    SYMBOL_MAP,
)
from .lunarcrush import (
    LunarCrushClient,
    MockLunarCrushClient,
    LunarCrushMetrics,
    get_lunarcrush_client,
    get_or_create_lunarcrush_client,
    close_lunarcrush_client,
    convert_to_lunarcrush_symbol,
    convert_from_lunarcrush_symbol,
)
from .sentiment import (
    SentimentService,
    get_sentiment_service,
    close_sentiment_service,
    AggregatedSentiment,
    AssetRotator,
    calculate_aggregated_score,
    save_sentiment_log,
    upsert_sentiment_log,
)
from .scheduler import (
    get_scheduler,
    ingest_kraken_data,
    ingest_sentiment_data,
    get_active_assets,
    upsert_candle,
)

__all__ = [
    # Kraken client
    "KrakenClient",
    "get_kraken_client",
    "close_kraken_client",
    "SYMBOL_MAP",
    # LunarCrush client
    "LunarCrushClient",
    "MockLunarCrushClient",
    "LunarCrushMetrics",
    "get_lunarcrush_client",
    "get_or_create_lunarcrush_client",
    "close_lunarcrush_client",
    "convert_to_lunarcrush_symbol",
    "convert_from_lunarcrush_symbol",
    # Sentiment service
    "SentimentService",
    "get_sentiment_service",
    "close_sentiment_service",
    "AggregatedSentiment",
    "AssetRotator",
    "calculate_aggregated_score",
    "save_sentiment_log",
    "upsert_sentiment_log",
    # Scheduler
    "get_scheduler",
    "ingest_kraken_data",
    "ingest_sentiment_data",
    "get_active_assets",
    "upsert_candle",
]
