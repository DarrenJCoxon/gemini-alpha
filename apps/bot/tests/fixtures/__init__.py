"""
Test fixtures for the trading bot tests.

This module contains fixture data for testing:
- Sentiment data (Story 1.4)
- Other test data
"""

from .sentiment_data import (
    SAMPLE_LUNARCRUSH_RESPONSE,
    SAMPLE_BLUESKY_POSTS,
    SAMPLE_TELEGRAM_MESSAGES,
    SAMPLE_AGGREGATED_SENTIMENT,
    generate_mock_lunarcrush_metrics,
    generate_mock_bluesky_posts,
    generate_mock_telegram_messages,
)

__all__ = [
    "SAMPLE_LUNARCRUSH_RESPONSE",
    "SAMPLE_BLUESKY_POSTS",
    "SAMPLE_TELEGRAM_MESSAGES",
    "SAMPLE_AGGREGATED_SENTIMENT",
    "generate_mock_lunarcrush_metrics",
    "generate_mock_bluesky_posts",
    "generate_mock_telegram_messages",
]
