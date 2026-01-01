"""
Services module - External API integrations.

This module contains service classes for interacting with:
- Kraken API (Story 1.3) - OHLCV data fetching
- Kraken Execution (Story 3.1) - Order execution
- Risk Engine (Story 3.2) - ATR-based stop loss calculation
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
from .kraken_execution import (
    KrakenExecutionClient,
    get_kraken_execution_client,
    close_kraken_execution_client,
)
from .execution import (
    execute_buy,
    execute_buy_with_risk,
    execute_sell,
    has_open_position,
    get_open_position,
    get_all_open_positions,
    close_position,
)
from .exceptions import (
    ExecutionError,
    InsufficientFundsError,
    DuplicatePositionError,
    RateLimitError,
    OrderRejectedError,
    InvalidSymbolError,
    PositionNotFoundError,
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
from .risk import (
    calculate_atr,
    calculate_stop_loss,
    calculate_stop_loss_with_config,
    calculate_position_size,
    validate_stop_loss,
)

__all__ = [
    # Kraken client (Story 1.3)
    "KrakenClient",
    "get_kraken_client",
    "close_kraken_client",
    "SYMBOL_MAP",
    # Kraken execution client (Story 3.1)
    "KrakenExecutionClient",
    "get_kraken_execution_client",
    "close_kraken_execution_client",
    # Execution service (Story 3.1, 3.2)
    "execute_buy",
    "execute_buy_with_risk",
    "execute_sell",
    "has_open_position",
    "get_open_position",
    "get_all_open_positions",
    "close_position",
    # Execution exceptions (Story 3.1)
    "ExecutionError",
    "InsufficientFundsError",
    "DuplicatePositionError",
    "RateLimitError",
    "OrderRejectedError",
    "InvalidSymbolError",
    "PositionNotFoundError",
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
    # Risk Engine (Story 3.2)
    "calculate_atr",
    "calculate_stop_loss",
    "calculate_stop_loss_with_config",
    "calculate_position_size",
    "validate_stop_loss",
]
