"""
Bluesky fetcher for social sentiment data.

This module provides functionality to:
- Fetch recent posts mentioning crypto symbols from Bluesky
- Monitor specific accounts and hashtags
- Extract post content for sentiment analysis

Note: Currently implemented as a mock/stub for MVP.
Real implementation would use AT Protocol (atproto) library.

Based on Story 1.4: Sentiment Ingestor requirements.
"""

import logging
import os
import random
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from typing import Optional

# Configure logging
logger = logging.getLogger("sentiment_ingestor")


@dataclass
class BlueskyPost:
    """Data class for a Bluesky post."""

    text: str
    author: str
    timestamp: datetime
    likes: int
    reposts: int
    uri: str

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "text": self.text,
            "author": self.author,
            "timestamp": self.timestamp.isoformat(),
            "likes": self.likes,
            "reposts": self.reposts,
            "uri": self.uri,
        }


class BaseBlueskyFetcher(ABC):
    """Abstract base class for Bluesky fetchers."""

    # Target hashtags to monitor
    TARGET_HASHTAGS = ["#crypto", "#bitcoin", "#altcoins", "#trading"]

    # Target accounts known for crypto content
    TARGET_ACCOUNTS = [
        "cryptoanalyst.bsky.social",
        "tradingview.bsky.social",
        "coingecko.bsky.social",
    ]

    @abstractmethod
    async def fetch_recent_posts(
        self,
        symbol: str,
        limit: int = 10,
    ) -> list[BlueskyPost]:
        """
        Fetch recent posts mentioning a crypto symbol.

        Args:
            symbol: Crypto symbol to search for (e.g., "SOL", "BTC")
            limit: Maximum number of posts to return

        Returns:
            List of BlueskyPost objects
        """
        pass

    @abstractmethod
    async def close(self) -> None:
        """Close the fetcher connection."""
        pass


class BlueskyFetcher(BaseBlueskyFetcher):
    """
    Real Bluesky fetcher using AT Protocol.

    Note: This is a stub implementation for MVP.
    Full implementation would use the atproto library.
    """

    def __init__(
        self,
        handle: Optional[str] = None,
        password: Optional[str] = None,
    ) -> None:
        """
        Initialize Bluesky fetcher.

        Args:
            handle: Bluesky handle (e.g., "yourhandle.bsky.social")
            password: App password for authentication
        """
        self.handle = handle or os.getenv("BLUESKY_HANDLE", "")
        self.password = password or os.getenv("BLUESKY_PASSWORD", "")
        self._authenticated = False

    async def fetch_recent_posts(
        self,
        symbol: str,
        limit: int = 10,
    ) -> list[BlueskyPost]:
        """
        Fetch recent posts mentioning a crypto symbol.

        Note: Stub implementation - returns empty list.
        Real implementation would search Bluesky feeds.
        """
        logger.warning(
            f"BlueskyFetcher.fetch_recent_posts called for {symbol} - "
            "Real implementation pending. Returning empty list."
        )
        return []

    async def close(self) -> None:
        """Close the fetcher."""
        self._authenticated = False
        logger.debug("BlueskyFetcher closed")


class MockBlueskyFetcher(BaseBlueskyFetcher):
    """
    Mock Bluesky fetcher for development and testing.

    Generates realistic sample posts for sentiment pipeline testing.
    """

    # Sample post templates for different sentiments
    BULLISH_TEMPLATES = [
        "{symbol} is looking extremely bullish right now! Breaking out of resistance.",
        "Just added more {symbol} to my portfolio. This one is going to moon!",
        "Technical analysis shows {symbol} ready for a major move up.",
        "Huge volume spike on {symbol}. Whales are accumulating.",
        "Long term holder of {symbol}. The fundamentals are solid.",
    ]

    BEARISH_TEMPLATES = [
        "{symbol} showing weakness. Might see lower prices soon.",
        "Taking profits on {symbol}. Looks overbought to me.",
        "Warning: {symbol} breaking support levels. Be careful.",
        "Not sure about {symbol} at these prices. Waiting for a pullback.",
        "Sold my {symbol} position. Better opportunities elsewhere.",
    ]

    NEUTRAL_TEMPLATES = [
        "{symbol} consolidating at current levels. Watching for direction.",
        "Interesting development for {symbol} today.",
        "What do you think about {symbol}? Share your thoughts.",
        "{symbol} trading sideways. No clear trend yet.",
        "Keeping an eye on {symbol} this week.",
    ]

    SAMPLE_AUTHORS = [
        "cryptotrader.bsky.social",
        "btc_maxi.bsky.social",
        "defi_degen.bsky.social",
        "hodler4life.bsky.social",
        "whale_alerts.bsky.social",
        "market_watch.bsky.social",
        "trading_guru.bsky.social",
        "crypto_news.bsky.social",
    ]

    def __init__(self, seed: Optional[int] = None) -> None:
        """
        Initialize mock fetcher.

        Args:
            seed: Random seed for reproducible results
        """
        if seed is not None:
            random.seed(seed)
        self._closed = False

    async def fetch_recent_posts(
        self,
        symbol: str,
        limit: int = 10,
    ) -> list[BlueskyPost]:
        """
        Generate mock posts mentioning a crypto symbol.

        Args:
            symbol: Crypto symbol (e.g., "SOL", "BTC")
            limit: Maximum number of posts

        Returns:
            List of mock BlueskyPost objects
        """
        # Normalize symbol
        clean_symbol = symbol.upper()
        if clean_symbol.endswith("USD"):
            clean_symbol = clean_symbol[:-3]

        posts = []
        now = datetime.now(timezone.utc)

        for i in range(min(limit, 10)):
            # Mix of sentiments
            sentiment_type = random.choice(["bullish", "bullish", "bearish", "neutral"])

            if sentiment_type == "bullish":
                template = random.choice(self.BULLISH_TEMPLATES)
            elif sentiment_type == "bearish":
                template = random.choice(self.BEARISH_TEMPLATES)
            else:
                template = random.choice(self.NEUTRAL_TEMPLATES)

            text = template.format(symbol=clean_symbol)

            # Random engagement
            likes = random.randint(5, 500)
            reposts = random.randint(0, likes // 3)

            # Random timestamp within last hour
            minutes_ago = random.randint(1, 60)
            timestamp = now - timedelta(minutes=minutes_ago)

            posts.append(
                BlueskyPost(
                    text=text,
                    author=random.choice(self.SAMPLE_AUTHORS),
                    timestamp=timestamp,
                    likes=likes,
                    reposts=reposts,
                    uri=f"at://mock.bsky.social/app.bsky.feed.post/{i}_{clean_symbol.lower()}",
                )
            )

        logger.debug(f"[MOCK] Generated {len(posts)} Bluesky posts for {clean_symbol}")
        return posts

    async def close(self) -> None:
        """Close mock fetcher."""
        self._closed = True


def get_bluesky_fetcher() -> BaseBlueskyFetcher:
    """
    Factory function to get appropriate Bluesky fetcher.

    Returns MockBlueskyFetcher for MVP since real API integration
    is not yet implemented.

    Returns:
        BaseBlueskyFetcher instance
    """
    handle = os.getenv("BLUESKY_HANDLE", "")
    password = os.getenv("BLUESKY_PASSWORD", "")

    if handle and password:
        logger.info("Bluesky credentials found, but using mock for MVP")
        # For MVP, always use mock
        # Real implementation would return: BlueskyFetcher(handle, password)

    logger.info("Using mock Bluesky fetcher")
    return MockBlueskyFetcher()


# Global fetcher instance
_bluesky_fetcher: Optional[BaseBlueskyFetcher] = None


def get_or_create_bluesky_fetcher() -> BaseBlueskyFetcher:
    """Get or create the global Bluesky fetcher instance."""
    global _bluesky_fetcher
    if _bluesky_fetcher is None:
        _bluesky_fetcher = get_bluesky_fetcher()
    return _bluesky_fetcher


async def close_bluesky_fetcher() -> None:
    """Close the global Bluesky fetcher."""
    global _bluesky_fetcher
    if _bluesky_fetcher is not None:
        await _bluesky_fetcher.close()
        _bluesky_fetcher = None
