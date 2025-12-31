"""
LunarCrush API client for fetching sentiment data.

This module provides functionality to:
- Connect to LunarCrush API v4
- Fetch Galaxy Score, AltRank, and social metrics
- Handle rate limiting (300 calls/day free tier)
- Implement retry logic with exponential backoff
- Use rotation strategy to stay within API limits

Based on Story 1.4: Sentiment Ingestor requirements.
"""

import logging
import os
import random
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone, date
from typing import Any, Optional

import httpx
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    before_sleep_log,
)

# Configure logging
logger = logging.getLogger("sentiment_ingestor")


@dataclass
class LunarCrushMetrics:
    """Data class for LunarCrush sentiment metrics."""

    galaxy_score: int
    alt_rank: int
    social_volume: int
    social_score: int
    bullish_sentiment: float
    bearish_sentiment: float
    symbol: str

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for storage."""
        return {
            "galaxy_score": self.galaxy_score,
            "alt_rank": self.alt_rank,
            "social_volume": self.social_volume,
            "social_score": self.social_score,
            "bullish_sentiment": self.bullish_sentiment,
            "bearish_sentiment": self.bearish_sentiment,
            "symbol": self.symbol,
        }


@dataclass
class RateLimitTracker:
    """
    Tracks API rate limit usage for LunarCrush.

    LunarCrush free tier: ~300 calls/day
    """

    daily_limit: int = 300
    calls_today: int = 0
    last_reset_date: date = field(default_factory=lambda: date.today())

    def check_and_reset(self) -> None:
        """Check if we need to reset the daily counter."""
        today = date.today()
        if today > self.last_reset_date:
            self.calls_today = 0
            self.last_reset_date = today
            logger.info("Rate limit counter reset for new day")

    def can_make_request(self) -> bool:
        """Check if we can make another API call today."""
        self.check_and_reset()
        return self.calls_today < self.daily_limit

    def record_call(self) -> None:
        """Record an API call."""
        self.calls_today += 1
        remaining = self.daily_limit - self.calls_today

        # Log warnings at threshold levels
        if remaining <= 0:
            logger.warning("LunarCrush daily quota EXHAUSTED")
        elif remaining <= 50:
            logger.warning(f"LunarCrush quota low: {remaining} calls remaining")
        elif remaining <= 100:
            logger.info(f"LunarCrush quota: {remaining} calls remaining")

    def get_remaining(self) -> int:
        """Get remaining calls for today."""
        self.check_and_reset()
        return max(0, self.daily_limit - self.calls_today)


def convert_to_lunarcrush_symbol(db_symbol: str) -> str:
    """
    Convert database symbol format to LunarCrush format.

    Args:
        db_symbol: Symbol from database (e.g., "SOLUSD", "BTCUSD")

    Returns:
        LunarCrush symbol (e.g., "sol", "btc") - lowercase, USD suffix removed

    Examples:
        >>> convert_to_lunarcrush_symbol("SOLUSD")
        'sol'
        >>> convert_to_lunarcrush_symbol("BTCUSD")
        'btc'
        >>> convert_to_lunarcrush_symbol("ETHUSD")
        'eth'
    """
    if not db_symbol:
        raise ValueError("Empty symbol provided")

    # Remove USD suffix and convert to lowercase
    if db_symbol.upper().endswith("USD"):
        base = db_symbol[:-3].lower()
    else:
        base = db_symbol.lower()

    return base


def convert_from_lunarcrush_symbol(lc_symbol: str) -> str:
    """
    Convert LunarCrush symbol format to database format.

    Args:
        lc_symbol: LunarCrush symbol (e.g., "sol", "btc")

    Returns:
        Database symbol (e.g., "SOLUSD", "BTCUSD")
    """
    if not lc_symbol:
        raise ValueError("Empty symbol provided")

    return f"{lc_symbol.upper()}USD"


class BaseLunarCrushClient(ABC):
    """Abstract base class for LunarCrush clients."""

    @abstractmethod
    async def get_coin_metrics(self, symbol: str) -> LunarCrushMetrics:
        """Fetch Galaxy Score, AltRank, and social volume for a coin."""
        pass

    @abstractmethod
    async def close(self) -> None:
        """Close the client connection."""
        pass

    @abstractmethod
    def can_make_request(self) -> bool:
        """Check if rate limit allows another request."""
        pass

    @abstractmethod
    def get_remaining_quota(self) -> int:
        """Get remaining API calls for today."""
        pass


class LunarCrushClient(BaseLunarCrushClient):
    """
    Async client for LunarCrush API v4.

    Provides methods to fetch sentiment metrics with proper rate limiting
    and retry logic.
    """

    BASE_URL = "https://lunarcrush.com/api4/public"

    def __init__(self, api_key: Optional[str] = None, daily_limit: int = 300) -> None:
        """
        Initialize the LunarCrush client.

        Args:
            api_key: LunarCrush API key. If None, reads from LUNARCRUSH_API_KEY env var.
            daily_limit: Daily API call limit (default: 300 for free tier)
        """
        self.api_key = api_key or os.getenv("LUNARCRUSH_API_KEY", "")
        self.rate_tracker = RateLimitTracker(daily_limit=daily_limit)
        self._client: Optional[httpx.AsyncClient] = None
        self._initialized = False

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create the HTTP client."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Accept": "application/json",
                },
                timeout=30.0,
            )
            self._initialized = True
        return self._client

    async def close(self) -> None:
        """Close the client connection."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._initialized = False
            logger.info("LunarCrush client closed")

    def can_make_request(self) -> bool:
        """Check if rate limit allows another request."""
        return self.rate_tracker.can_make_request()

    def get_remaining_quota(self) -> int:
        """Get remaining API calls for today."""
        return self.rate_tracker.get_remaining()

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((httpx.TimeoutException, httpx.ConnectError)),
        before_sleep=before_sleep_log(logger, logging.WARNING),
    )
    async def get_coin_metrics(self, symbol: str) -> LunarCrushMetrics:
        """
        Fetch sentiment metrics for a single symbol.

        Args:
            symbol: Database symbol (e.g., "SOLUSD") or LunarCrush symbol (e.g., "sol")

        Returns:
            LunarCrushMetrics with galaxy_score, alt_rank, social_volume, etc.

        Raises:
            ValueError: If symbol is invalid
            httpx.HTTPStatusError: On API errors
            RuntimeError: If rate limit exceeded
        """
        # Check rate limit
        if not self.can_make_request():
            raise RuntimeError("LunarCrush daily rate limit exceeded")

        # Convert symbol if needed
        lc_symbol = symbol
        if symbol.upper().endswith("USD"):
            lc_symbol = convert_to_lunarcrush_symbol(symbol)

        client = await self._get_client()

        try:
            # LunarCrush API v4 endpoint
            url = f"{self.BASE_URL}/coins/{lc_symbol}/v1"

            response = await client.get(url)
            response.raise_for_status()

            # Record successful call
            self.rate_tracker.record_call()

            data = response.json()

            # Parse response
            coin_data = data.get("data", data)

            return LunarCrushMetrics(
                galaxy_score=int(coin_data.get("galaxy_score", 50)),
                alt_rank=int(coin_data.get("alt_rank", 100)),
                social_volume=int(coin_data.get("social_volume", 0)),
                social_score=int(coin_data.get("social_score", 50)),
                bullish_sentiment=float(coin_data.get("sentiment", {}).get("bullish", 0.5)),
                bearish_sentiment=float(coin_data.get("sentiment", {}).get("bearish", 0.5)),
                symbol=lc_symbol,
            )

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 429:
                logger.error("LunarCrush rate limit hit (429)")
                self.rate_tracker.calls_today = self.rate_tracker.daily_limit
            elif e.response.status_code == 404:
                logger.warning(f"Coin not found on LunarCrush: {lc_symbol}")
                # Return default metrics for unknown coins
                return LunarCrushMetrics(
                    galaxy_score=50,
                    alt_rank=1000,
                    social_volume=0,
                    social_score=50,
                    bullish_sentiment=0.5,
                    bearish_sentiment=0.5,
                    symbol=lc_symbol,
                )
            raise


class MockLunarCrushClient(BaseLunarCrushClient):
    """
    Mock LunarCrush client for development and testing.

    Generates realistic random scores when API key is not available.
    """

    def __init__(self, seed: Optional[int] = None) -> None:
        """
        Initialize mock client.

        Args:
            seed: Random seed for reproducible results in tests
        """
        if seed is not None:
            random.seed(seed)
        self._closed = False

    async def get_coin_metrics(self, symbol: str) -> LunarCrushMetrics:
        """
        Generate mock sentiment metrics for a symbol.

        Generates realistic scores in typical ranges:
        - Galaxy Score: 30-75 (typical market conditions)
        - Alt Rank: 1-100 (for top coins)
        - Social Volume: 1000-50000
        - Social Score: 40-80
        """
        # Convert symbol if needed
        lc_symbol = symbol
        if symbol.upper().endswith("USD"):
            lc_symbol = convert_to_lunarcrush_symbol(symbol)

        # Generate realistic random scores
        galaxy_score = random.randint(30, 75)
        alt_rank = random.randint(1, 100)
        social_volume = random.randint(1000, 50000)
        social_score = random.randint(40, 80)

        # Bullish/bearish should sum to ~1.0
        bullish = round(random.uniform(0.3, 0.7), 2)
        bearish = round(1.0 - bullish, 2)

        logger.debug(f"[MOCK] Generated metrics for {lc_symbol}: GS={galaxy_score}")

        return LunarCrushMetrics(
            galaxy_score=galaxy_score,
            alt_rank=alt_rank,
            social_volume=social_volume,
            social_score=social_score,
            bullish_sentiment=bullish,
            bearish_sentiment=bearish,
            symbol=lc_symbol,
        )

    async def close(self) -> None:
        """Close mock client (no-op)."""
        self._closed = True

    def can_make_request(self) -> bool:
        """Mock client has no rate limit."""
        return True

    def get_remaining_quota(self) -> int:
        """Mock client returns unlimited quota."""
        return 999999


def get_lunarcrush_client() -> BaseLunarCrushClient:
    """
    Factory function to get appropriate LunarCrush client.

    Returns LunarCrushClient if API key is set, otherwise MockLunarCrushClient.

    Returns:
        BaseLunarCrushClient instance
    """
    api_key = os.getenv("LUNARCRUSH_API_KEY", "")

    if api_key:
        logger.info("Using real LunarCrush client")
        return LunarCrushClient(api_key=api_key)
    else:
        logger.warning("LUNARCRUSH_API_KEY not set, using mock client")
        return MockLunarCrushClient()


# Global client instance
_lunarcrush_client: Optional[BaseLunarCrushClient] = None


def get_or_create_lunarcrush_client() -> BaseLunarCrushClient:
    """Get or create the global LunarCrush client instance."""
    global _lunarcrush_client
    if _lunarcrush_client is None:
        _lunarcrush_client = get_lunarcrush_client()
    return _lunarcrush_client


async def close_lunarcrush_client() -> None:
    """Close the global LunarCrush client."""
    global _lunarcrush_client
    if _lunarcrush_client is not None:
        await _lunarcrush_client.close()
        _lunarcrush_client = None
