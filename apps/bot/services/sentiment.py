"""
Sentiment aggregation service.

This module provides functionality to:
- Aggregate sentiment data from multiple sources (LunarCrush, Bluesky, Telegram, Reddit)
- Calculate aggregated sentiment scores
- Store sentiment data in the SentimentLog table
- Implement rotation strategy for API rate limiting

Based on Story 1.4: Sentiment Ingestor requirements.
"""

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy.dialects.postgresql import insert
from sqlmodel.ext.asyncio.session import AsyncSession

from models import Asset, SentimentLog
from .lunarcrush import (
    BaseLunarCrushClient,
    LunarCrushMetrics,
    get_or_create_lunarcrush_client,
    convert_to_lunarcrush_symbol,
)
from .socials.bluesky import (
    BaseBlueskyFetcher,
    BlueskyPost,
    get_or_create_bluesky_fetcher,
)
from .socials.telegram import (
    BaseTelegramFetcher,
    TelegramMessage,
    get_or_create_telegram_fetcher,
)
from .cryptopanic import (
    BaseCryptoPanicClient,
    CryptoPanicNews,
    get_or_create_cryptopanic_client,
)
from .fear_greed import (
    FearGreedData,
    fetch_fear_greed_index,
    fear_greed_to_contrarian_score,
)

# Configure logging
logger = logging.getLogger("sentiment_ingestor")


@dataclass
class AggregatedSentiment:
    """Aggregated sentiment data from all sources."""

    symbol: str
    lunarcrush: Optional[LunarCrushMetrics] = None
    fear_greed: Optional[FearGreedData] = None
    bluesky_posts: list[BlueskyPost] = field(default_factory=list)
    telegram_messages: list[TelegramMessage] = field(default_factory=list)
    cryptopanic_news: list[CryptoPanicNews] = field(default_factory=list)
    aggregated_score: int = 50
    galaxy_score: Optional[int] = None
    alt_rank: Optional[int] = None
    social_volume: Optional[int] = None
    raw_text: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for storage."""
        return {
            "symbol": self.symbol,
            "lunarcrush": self.lunarcrush.to_dict() if self.lunarcrush else None,
            "fear_greed": self.fear_greed.to_dict() if self.fear_greed else None,
            "bluesky_posts": [p.to_dict() for p in self.bluesky_posts],
            "telegram_messages": [m.to_dict() for m in self.telegram_messages],
            "cryptopanic_news": [n.to_dict() for n in self.cryptopanic_news],
            "aggregated_score": self.aggregated_score,
            "galaxy_score": self.galaxy_score,
            "alt_rank": self.alt_rank,
            "social_volume": self.social_volume,
        }


def calculate_aggregated_score(
    galaxy_score: Optional[int],
    social_volume: int,
    fear_greed_value: Optional[int] = None,
    avg_social_volume: int = 10000,
) -> int:
    """
    Calculate aggregated sentiment score.

    Priority:
    1. If Galaxy Score available: 60% Galaxy + 40% Social Volume
    2. If only Fear & Greed available: Use F&G directly (market-wide sentiment)
    3. If neither: Return neutral (50)

    Args:
        galaxy_score: LunarCrush Galaxy Score (0-100)
        social_volume: Current social volume
        fear_greed_value: Alternative.me Fear & Greed Index (0-100)
        avg_social_volume: Average social volume for normalization

    Returns:
        Aggregated score (0-100)
    """
    # If we have Galaxy Score, use the weighted formula
    if galaxy_score is not None:
        # Normalize social volume to 0-100 scale
        if avg_social_volume <= 0:
            avg_social_volume = 10000
        volume_normalized = min(100, (social_volume / avg_social_volume) * 50)

        # Weighted aggregation
        aggregated = (galaxy_score * 0.6) + (volume_normalized * 0.4)
        return int(min(100, max(0, aggregated)))

    # If we have Fear & Greed but no Galaxy Score, use F&G directly
    if fear_greed_value is not None:
        return fear_greed_value

    # No data available - return neutral
    return 50


def concatenate_social_text(
    bluesky_posts: list[BlueskyPost],
    telegram_messages: list[TelegramMessage],
    cryptopanic_news: list[CryptoPanicNews] = None,
    max_length: int = 10000,
) -> str:
    """
    Concatenate social media text for storage.

    Args:
        bluesky_posts: List of Bluesky posts
        telegram_messages: List of Telegram messages
        cryptopanic_news: List of CryptoPanic news items
        max_length: Maximum length of concatenated text

    Returns:
        Concatenated text from all sources
    """
    texts = []
    cryptopanic_news = cryptopanic_news or []

    # Add Bluesky posts
    for post in bluesky_posts:
        texts.append(f"[Bluesky @{post.author}] {post.text}")

    # Add Telegram messages
    for msg in telegram_messages:
        texts.append(f"[Telegram {msg.channel}] {msg.text}")

    # Add CryptoPanic news
    for news in cryptopanic_news:
        sentiment_tag = f" [{news.sentiment}]" if news.sentiment else ""
        texts.append(f"[CryptoPanic {news.source}{sentiment_tag}] {news.title}")

    result = "\n---\n".join(texts)

    # Truncate if too long
    if len(result) > max_length:
        result = result[:max_length] + "\n[TRUNCATED]"

    return result


class SentimentService:
    """
    Service for aggregating sentiment from multiple sources.

    Coordinates fetching from LunarCrush, Bluesky, Telegram, and CryptoPanic,
    calculates aggregated scores, and stores in database.
    """

    def __init__(
        self,
        lunarcrush: Optional[BaseLunarCrushClient] = None,
        bluesky: Optional[BaseBlueskyFetcher] = None,
        telegram: Optional[BaseTelegramFetcher] = None,
        cryptopanic: Optional[BaseCryptoPanicClient] = None,
    ) -> None:
        """
        Initialize sentiment service.

        Args:
            lunarcrush: LunarCrush client (uses global if None)
            bluesky: Bluesky fetcher (uses global if None)
            telegram: Telegram fetcher (uses global if None)
            cryptopanic: CryptoPanic client (uses global if None)
        """
        self._lunarcrush = lunarcrush
        self._bluesky = bluesky
        self._telegram = telegram
        self._cryptopanic = cryptopanic

    @property
    def lunarcrush(self) -> BaseLunarCrushClient:
        """Get LunarCrush client."""
        if self._lunarcrush is None:
            self._lunarcrush = get_or_create_lunarcrush_client()
        return self._lunarcrush

    @property
    def bluesky(self) -> BaseBlueskyFetcher:
        """Get Bluesky fetcher."""
        if self._bluesky is None:
            self._bluesky = get_or_create_bluesky_fetcher()
        return self._bluesky

    @property
    def telegram(self) -> BaseTelegramFetcher:
        """Get Telegram fetcher."""
        if self._telegram is None:
            self._telegram = get_or_create_telegram_fetcher()
        return self._telegram

    @property
    def cryptopanic(self) -> BaseCryptoPanicClient:
        """Get CryptoPanic client."""
        if self._cryptopanic is None:
            self._cryptopanic = get_or_create_cryptopanic_client()
        return self._cryptopanic

    async def fetch_lunarcrush_data(
        self,
        symbol: str,
    ) -> Optional[LunarCrushMetrics]:
        """
        Fetch LunarCrush data for a symbol.

        Args:
            symbol: Database symbol (e.g., "SOLUSD")

        Returns:
            LunarCrushMetrics or None if failed
        """
        try:
            if not self.lunarcrush.can_make_request():
                logger.warning(
                    f"LunarCrush quota exhausted, skipping {symbol}"
                )
                return None

            metrics = await self.lunarcrush.get_coin_metrics(symbol)
            logger.debug(
                f"LunarCrush data for {symbol}: "
                f"GS={metrics.galaxy_score}, AR={metrics.alt_rank}"
            )
            return metrics

        except Exception as e:
            logger.error(f"Error fetching LunarCrush data for {symbol}: {e}")
            return None

    async def fetch_bluesky_data(
        self,
        symbol: str,
        limit: int = 10,
    ) -> list[BlueskyPost]:
        """
        Fetch Bluesky posts for a symbol.

        Args:
            symbol: Database symbol
            limit: Max posts to fetch

        Returns:
            List of BlueskyPost objects
        """
        try:
            posts = await self.bluesky.fetch_recent_posts(symbol, limit)
            logger.debug(f"Fetched {len(posts)} Bluesky posts for {symbol}")
            return posts

        except Exception as e:
            logger.error(f"Error fetching Bluesky data for {symbol}: {e}")
            return []

    async def fetch_telegram_data(
        self,
        symbol: str,
        limit_per_channel: int = 5,
    ) -> list[TelegramMessage]:
        """
        Fetch Telegram messages for a symbol.

        Args:
            symbol: Database symbol
            limit_per_channel: Max messages per channel

        Returns:
            List of TelegramMessage objects
        """
        try:
            messages = await self.telegram.fetch_all_channels(
                symbol, limit_per_channel
            )
            logger.debug(f"Fetched {len(messages)} Telegram messages for {symbol}")
            return messages

        except Exception as e:
            logger.error(f"Error fetching Telegram data for {symbol}: {e}")
            return []

    async def fetch_cryptopanic_data(
        self,
        symbol: str,
        limit: int = 10,
    ) -> list[CryptoPanicNews]:
        """
        Fetch CryptoPanic news for a symbol.

        Args:
            symbol: Database symbol
            limit: Max news items to fetch

        Returns:
            List of CryptoPanicNews objects
        """
        try:
            news = await self.cryptopanic.fetch_news(symbol, limit=limit)
            logger.debug(f"Fetched {len(news)} CryptoPanic news for {symbol}")
            return news

        except Exception as e:
            logger.error(f"Error fetching CryptoPanic data for {symbol}: {e}")
            return []

    async def fetch_fear_greed_data(self) -> Optional[FearGreedData]:
        """
        Fetch the global Fear & Greed Index.

        This is a market-wide indicator (not per-symbol), so we only
        need to fetch it once per ingestion cycle.

        Returns:
            FearGreedData or None if fetch failed
        """
        try:
            fg_data = await fetch_fear_greed_index()
            if fg_data:
                logger.info(
                    f"Fear & Greed Index: {fg_data.value} ({fg_data.classification})"
                )
            return fg_data
        except Exception as e:
            logger.error(f"Error fetching Fear & Greed data: {e}")
            return None

    async def fetch_all_sentiment(
        self,
        symbol: str,
        fetch_lunarcrush: bool = True,
        fetch_socials: bool = True,
        fear_greed_data: Optional[FearGreedData] = None,
    ) -> AggregatedSentiment:
        """
        Fetch sentiment from all sources for a symbol.

        Args:
            symbol: Database symbol (e.g., "SOLUSD")
            fetch_lunarcrush: Whether to fetch LunarCrush data
            fetch_socials: Whether to fetch social media data
            fear_greed_data: Pre-fetched Fear & Greed data (shared across assets)

        Returns:
            AggregatedSentiment with data from all sources
        """
        result = AggregatedSentiment(symbol=symbol)

        # Store Fear & Greed data if provided
        if fear_greed_data:
            result.fear_greed = fear_greed_data

        # Fetch data from all sources in parallel
        tasks = []

        async def return_none():
            return None

        async def return_empty_list():
            return []

        if fetch_lunarcrush:
            tasks.append(self.fetch_lunarcrush_data(symbol))
        else:
            tasks.append(return_none())

        if fetch_socials:
            tasks.append(self.fetch_bluesky_data(symbol))
            tasks.append(self.fetch_telegram_data(symbol))
            tasks.append(self.fetch_cryptopanic_data(symbol))
        else:
            tasks.append(return_empty_list())
            tasks.append(return_empty_list())
            tasks.append(return_empty_list())

        # Execute concurrently
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Process LunarCrush result
        if not isinstance(results[0], Exception) and results[0] is not None:
            result.lunarcrush = results[0]
            result.galaxy_score = results[0].galaxy_score
            result.alt_rank = results[0].alt_rank
            result.social_volume = results[0].social_volume

        # Process Bluesky result
        if not isinstance(results[1], Exception) and results[1]:
            result.bluesky_posts = results[1]

        # Process Telegram result
        if not isinstance(results[2], Exception) and results[2]:
            result.telegram_messages = results[2]

        # Process CryptoPanic result
        if not isinstance(results[3], Exception) and results[3]:
            result.cryptopanic_news = results[3]

        # Concatenate social text
        result.raw_text = concatenate_social_text(
            result.bluesky_posts,
            result.telegram_messages,
            result.cryptopanic_news,
        )

        # Calculate aggregated score (with Fear & Greed fallback)
        fg_value = fear_greed_data.value if fear_greed_data else None
        result.aggregated_score = calculate_aggregated_score(
            result.galaxy_score,
            result.social_volume or 0,
            fear_greed_value=fg_value,
        )

        # Log with Fear & Greed info
        fg_info = f"F&G={fg_value}" if fg_value else "F&G=N/A"
        logger.info(
            f"Sentiment for {symbol}: "
            f"Score={result.aggregated_score}, "
            f"GS={result.galaxy_score}, "
            f"{fg_info}, "
            f"Posts={len(result.bluesky_posts)}, "
            f"Msgs={len(result.telegram_messages)}, "
            f"News={len(result.cryptopanic_news)}"
        )

        return result


async def save_sentiment_log(
    session: AsyncSession,
    asset_id: str,
    source: str,
    sentiment: AggregatedSentiment,
) -> SentimentLog:
    """
    Create a SentimentLog record in the database.

    Args:
        session: Database session
        asset_id: Foreign key to Asset
        source: Source identifier (e.g., "aggregated", "lunarcrush")
        sentiment: Aggregated sentiment data

    Returns:
        Created SentimentLog record
    """
    # Use naive datetime for Prisma compatibility (data is always UTC)
    now = datetime.now(timezone.utc).replace(tzinfo=None)

    log = SentimentLog(
        asset_id=asset_id,
        timestamp=now,
        source=source,
        galaxy_score=sentiment.galaxy_score,
        alt_rank=sentiment.alt_rank,
        social_volume=sentiment.social_volume,
        raw_text=sentiment.raw_text,
        sentiment_score=sentiment.aggregated_score,
    )

    session.add(log)

    logger.debug(
        f"Created SentimentLog for asset {asset_id}: "
        f"score={sentiment.aggregated_score}"
    )

    return log


async def upsert_sentiment_log(
    session: AsyncSession,
    asset_id: str,
    source: str,
    sentiment: AggregatedSentiment,
) -> bool:
    """
    Upsert a SentimentLog record in the database.

    Uses PostgreSQL ON CONFLICT to handle duplicates based on
    asset_id and timestamp.

    Args:
        session: Database session
        asset_id: Foreign key to Asset
        source: Source identifier
        sentiment: Aggregated sentiment data

    Returns:
        True if upsert was successful
    """
    # Use naive datetime for Prisma compatibility (data is always UTC)
    now = datetime.now(timezone.utc).replace(tzinfo=None)

    try:
        # Note: We use sa_column names (camelCase) for the values dict
        # to match the actual database column names
        stmt = insert(SentimentLog).values(
            asset_id=asset_id,
            timestamp=now,
            source=source,
            galaxy_score=sentiment.galaxy_score,
            alt_rank=sentiment.alt_rank,
            social_volume=sentiment.social_volume,
            raw_text=sentiment.raw_text,
            sentiment_score=sentiment.aggregated_score,
        )

        # On conflict, update sentiment fields using database column names
        stmt = stmt.on_conflict_do_update(
            index_elements=["assetId", "timestamp"],
            set_={
                "source": source,
                "galaxyScore": sentiment.galaxy_score,
                "altRank": sentiment.alt_rank,
                "socialVolume": sentiment.social_volume,
                "rawText": sentiment.raw_text,
                "sentimentScore": sentiment.aggregated_score,
            }
        )

        await session.execute(stmt)
        return True

    except Exception as e:
        logger.error(f"Failed to upsert sentiment log for asset {asset_id}: {e}")
        return False


class AssetRotator:
    """
    Implements rotation strategy for API rate limiting.

    Divides assets into groups and rotates which group is fetched
    each cycle to stay within LunarCrush API limits.

    Problem: LunarCrush free tier (300 calls/day) vs
             30 assets * 96 cycles/day = 2,880 calls/day

    Solution: Rotate 3 groups of 10 assets, each updated every 45 minutes.
    """

    def __init__(
        self,
        assets: list[Asset],
        num_groups: int = 3,
    ) -> None:
        """
        Initialize rotator.

        Args:
            assets: List of all active assets
            num_groups: Number of groups to divide into
        """
        self.assets = assets
        self.num_groups = num_groups
        self._current_group = 0

    def get_current_group(self) -> list[Asset]:
        """
        Get the current group of assets to process.

        Returns:
            List of assets for current rotation
        """
        if not self.assets:
            return []

        # Calculate group size
        group_size = len(self.assets) // self.num_groups
        if group_size == 0:
            return self.assets

        start_idx = self._current_group * group_size
        end_idx = start_idx + group_size

        # Handle remainder in last group
        if self._current_group == self.num_groups - 1:
            end_idx = len(self.assets)

        return self.assets[start_idx:end_idx]

    def advance(self) -> int:
        """
        Advance to the next group.

        Returns:
            New current group index
        """
        self._current_group = (self._current_group + 1) % self.num_groups
        return self._current_group

    @property
    def current_group_index(self) -> int:
        """Get current group index."""
        return self._current_group


# Global service instance
_sentiment_service: Optional[SentimentService] = None


def get_sentiment_service() -> SentimentService:
    """Get or create the global sentiment service instance."""
    global _sentiment_service
    if _sentiment_service is None:
        _sentiment_service = SentimentService()
    return _sentiment_service


async def close_sentiment_service() -> None:
    """Close the sentiment service and its clients."""
    global _sentiment_service
    if _sentiment_service is not None:
        # Close clients if they were created
        if _sentiment_service._lunarcrush:
            await _sentiment_service._lunarcrush.close()
        if _sentiment_service._bluesky:
            await _sentiment_service._bluesky.close()
        if _sentiment_service._telegram:
            await _sentiment_service._telegram.close()
        if _sentiment_service._cryptopanic:
            await _sentiment_service._cryptopanic.close()
        _sentiment_service = None
