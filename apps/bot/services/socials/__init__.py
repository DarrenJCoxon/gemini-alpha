"""
Social media scrapers for sentiment data.

This package contains fetchers for various social media platforms:
- Bluesky (AT Protocol)
- Telegram

Based on Story 1.4: Sentiment Ingestor requirements.
"""

from .bluesky import BlueskyFetcher, MockBlueskyFetcher, get_bluesky_fetcher
from .telegram import TelegramFetcher, MockTelegramFetcher, get_telegram_fetcher

__all__ = [
    # Bluesky
    "BlueskyFetcher",
    "MockBlueskyFetcher",
    "get_bluesky_fetcher",
    # Telegram
    "TelegramFetcher",
    "MockTelegramFetcher",
    "get_telegram_fetcher",
]
