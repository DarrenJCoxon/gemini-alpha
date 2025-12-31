"""
Tests for services/sentiment.py - Sentiment aggregation service.

Story 1.4: Sentiment Ingestor - Unit tests for sentiment aggregation,
score calculation, and database storage.
"""

import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch


class TestCalculateAggregatedScore:
    """Tests for aggregated score calculation."""

    def test_balanced_score(self):
        """Test balanced galaxy score and volume."""
        from services.sentiment import calculate_aggregated_score

        # Galaxy Score 50 = 30 points (50 * 0.6)
        # Volume 10000/10000 * 50 = 50 = 20 points (50 * 0.4)
        score = calculate_aggregated_score(
            galaxy_score=50,
            social_volume=10000,
            avg_social_volume=10000,
        )

        assert score == 50

    def test_high_galaxy_score(self):
        """Test high galaxy score dominates."""
        from services.sentiment import calculate_aggregated_score

        # Galaxy Score 80 = 48 points
        # Volume 10000/10000 * 50 = 50 = 20 points
        score = calculate_aggregated_score(
            galaxy_score=80,
            social_volume=10000,
            avg_social_volume=10000,
        )

        assert score == 68

    def test_low_galaxy_score(self):
        """Test low galaxy score results in low aggregated score."""
        from services.sentiment import calculate_aggregated_score

        # Galaxy Score 20 = 12 points
        # Volume 10000/10000 * 50 = 50 = 20 points
        score = calculate_aggregated_score(
            galaxy_score=20,
            social_volume=10000,
            avg_social_volume=10000,
        )

        assert score == 32

    def test_none_galaxy_score_defaults_to_50(self):
        """Test None galaxy score defaults to 50."""
        from services.sentiment import calculate_aggregated_score

        score = calculate_aggregated_score(
            galaxy_score=None,
            social_volume=10000,
            avg_social_volume=10000,
        )

        assert score == 50

    def test_high_volume_bonus(self):
        """Test high social volume adds to score."""
        from services.sentiment import calculate_aggregated_score

        # Galaxy Score 50 = 30 points
        # Volume 20000/10000 * 50 = 100 = 40 points (capped at 100 normalized)
        score = calculate_aggregated_score(
            galaxy_score=50,
            social_volume=20000,
            avg_social_volume=10000,
        )

        assert score == 70

    def test_low_volume_penalty(self):
        """Test low social volume reduces score."""
        from services.sentiment import calculate_aggregated_score

        # Galaxy Score 50 = 30 points
        # Volume 1000/10000 * 50 = 5 = 2 points
        score = calculate_aggregated_score(
            galaxy_score=50,
            social_volume=1000,
            avg_social_volume=10000,
        )

        assert score == 32

    def test_zero_volume(self):
        """Test zero volume."""
        from services.sentiment import calculate_aggregated_score

        score = calculate_aggregated_score(
            galaxy_score=50,
            social_volume=0,
            avg_social_volume=10000,
        )

        assert score == 30

    def test_score_clamped_to_max_100(self):
        """Test score is clamped to maximum 100."""
        from services.sentiment import calculate_aggregated_score

        score = calculate_aggregated_score(
            galaxy_score=100,
            social_volume=100000,
            avg_social_volume=10000,
        )

        assert score == 100

    def test_score_clamped_to_min_0(self):
        """Test score is clamped to minimum 0."""
        from services.sentiment import calculate_aggregated_score

        score = calculate_aggregated_score(
            galaxy_score=0,
            social_volume=0,
            avg_social_volume=10000,
        )

        assert score == 0

    def test_zero_avg_volume_uses_default(self):
        """Test zero avg volume uses default 10000."""
        from services.sentiment import calculate_aggregated_score

        score = calculate_aggregated_score(
            galaxy_score=50,
            social_volume=10000,
            avg_social_volume=0,
        )

        # Should use default avg of 10000
        assert score == 50


class TestConcatenateSocialText:
    """Tests for social text concatenation."""

    def test_concatenate_bluesky_posts(self):
        """Test concatenating Bluesky posts."""
        from services.sentiment import concatenate_social_text
        from services.socials.bluesky import BlueskyPost

        posts = [
            BlueskyPost(
                text="SOL looking bullish!",
                author="trader1.bsky.social",
                timestamp=datetime.now(timezone.utc),
                likes=100,
                reposts=10,
                uri="at://test/1",
            ),
        ]

        result = concatenate_social_text(posts, [])

        assert "[Bluesky @trader1.bsky.social]" in result
        assert "SOL looking bullish!" in result

    def test_concatenate_telegram_messages(self):
        """Test concatenating Telegram messages."""
        from services.sentiment import concatenate_social_text
        from services.socials.telegram import TelegramMessage

        messages = [
            TelegramMessage(
                text="BTC breaking out!",
                channel="@CryptoNews",
                timestamp=datetime.now(timezone.utc),
                views=5000,
                forwards=100,
                message_id=12345,
            ),
        ]

        result = concatenate_social_text([], messages)

        assert "[Telegram @CryptoNews]" in result
        assert "BTC breaking out!" in result

    def test_concatenate_mixed_sources(self):
        """Test concatenating from both sources."""
        from services.sentiment import concatenate_social_text
        from services.socials.bluesky import BlueskyPost
        from services.socials.telegram import TelegramMessage

        posts = [
            BlueskyPost(
                text="Post 1",
                author="user.bsky.social",
                timestamp=datetime.now(timezone.utc),
                likes=10,
                reposts=1,
                uri="at://test/1",
            ),
        ]
        messages = [
            TelegramMessage(
                text="Message 1",
                channel="@Channel",
                timestamp=datetime.now(timezone.utc),
                views=1000,
                forwards=50,
                message_id=1,
            ),
        ]

        result = concatenate_social_text(posts, messages)

        assert "[Bluesky" in result
        assert "[Telegram" in result
        assert "---" in result  # Separator

    def test_truncate_long_text(self):
        """Test text is truncated when too long."""
        from services.sentiment import concatenate_social_text
        from services.socials.bluesky import BlueskyPost

        # Create a very long post
        long_text = "x" * 20000
        posts = [
            BlueskyPost(
                text=long_text,
                author="user.bsky.social",
                timestamp=datetime.now(timezone.utc),
                likes=10,
                reposts=1,
                uri="at://test/1",
            ),
        ]

        result = concatenate_social_text(posts, [], max_length=1000)

        assert len(result) <= 1000 + len("\n[TRUNCATED]")
        assert "[TRUNCATED]" in result

    def test_empty_inputs(self):
        """Test empty inputs return empty string."""
        from services.sentiment import concatenate_social_text

        result = concatenate_social_text([], [])

        assert result == ""


class TestAggregatedSentiment:
    """Tests for AggregatedSentiment dataclass."""

    def test_to_dict(self):
        """Test converting to dictionary."""
        from services.sentiment import AggregatedSentiment
        from services.lunarcrush import LunarCrushMetrics

        sentiment = AggregatedSentiment(
            symbol="SOL",
            lunarcrush=LunarCrushMetrics(
                galaxy_score=65,
                alt_rank=12,
                social_volume=15000,
                social_score=72,
                bullish_sentiment=0.65,
                bearish_sentiment=0.35,
                symbol="sol",
            ),
            aggregated_score=68,
            galaxy_score=65,
            alt_rank=12,
            social_volume=15000,
        )

        result = sentiment.to_dict()

        assert result["symbol"] == "SOL"
        assert result["aggregated_score"] == 68
        assert result["galaxy_score"] == 65
        assert result["lunarcrush"]["galaxy_score"] == 65

    def test_to_dict_without_lunarcrush(self):
        """Test to_dict when lunarcrush is None."""
        from services.sentiment import AggregatedSentiment

        sentiment = AggregatedSentiment(symbol="BTC")

        result = sentiment.to_dict()

        assert result["lunarcrush"] is None
        assert result["aggregated_score"] == 50


class TestSentimentService:
    """Tests for SentimentService class."""

    @pytest.mark.asyncio
    async def test_fetch_lunarcrush_data(self):
        """Test fetching LunarCrush data."""
        from services.sentiment import SentimentService
        from services.lunarcrush import MockLunarCrushClient

        mock_client = MockLunarCrushClient(seed=42)
        service = SentimentService(lunarcrush=mock_client)

        result = await service.fetch_lunarcrush_data("SOLUSD")

        assert result is not None
        assert result.galaxy_score >= 30
        assert result.symbol == "sol"

    @pytest.mark.asyncio
    async def test_fetch_lunarcrush_data_quota_exhausted(self):
        """Test fetching when quota exhausted."""
        from services.sentiment import SentimentService
        from services.lunarcrush import MockLunarCrushClient

        mock_client = MockLunarCrushClient()
        mock_client.can_make_request = MagicMock(return_value=False)

        service = SentimentService(lunarcrush=mock_client)

        result = await service.fetch_lunarcrush_data("SOLUSD")

        assert result is None

    @pytest.mark.asyncio
    async def test_fetch_bluesky_data(self):
        """Test fetching Bluesky data."""
        from services.sentiment import SentimentService
        from services.socials.bluesky import MockBlueskyFetcher

        mock_fetcher = MockBlueskyFetcher(seed=42)
        service = SentimentService(bluesky=mock_fetcher)

        result = await service.fetch_bluesky_data("SOLUSD", limit=5)

        assert len(result) == 5
        assert all("SOL" in post.text for post in result)

    @pytest.mark.asyncio
    async def test_fetch_telegram_data(self):
        """Test fetching Telegram data."""
        from services.sentiment import SentimentService
        from services.socials.telegram import MockTelegramFetcher

        mock_fetcher = MockTelegramFetcher(seed=42)
        service = SentimentService(telegram=mock_fetcher)

        result = await service.fetch_telegram_data("SOLUSD")

        assert len(result) > 0
        assert all("SOL" in msg.text for msg in result)

    @pytest.mark.asyncio
    async def test_fetch_all_sentiment(self):
        """Test fetching from all sources."""
        from services.sentiment import SentimentService
        from services.lunarcrush import MockLunarCrushClient
        from services.socials.bluesky import MockBlueskyFetcher
        from services.socials.telegram import MockTelegramFetcher

        service = SentimentService(
            lunarcrush=MockLunarCrushClient(seed=42),
            bluesky=MockBlueskyFetcher(seed=42),
            telegram=MockTelegramFetcher(seed=42),
        )

        result = await service.fetch_all_sentiment("SOLUSD")

        assert result.symbol == "SOLUSD"
        assert result.lunarcrush is not None
        assert result.galaxy_score is not None
        assert len(result.bluesky_posts) > 0
        assert len(result.telegram_messages) > 0
        assert result.aggregated_score >= 0
        assert result.aggregated_score <= 100
        assert result.raw_text is not None

    @pytest.mark.asyncio
    async def test_fetch_all_sentiment_without_lunarcrush(self):
        """Test fetching without LunarCrush."""
        from services.sentiment import SentimentService
        from services.socials.bluesky import MockBlueskyFetcher
        from services.socials.telegram import MockTelegramFetcher

        mock_lc = MagicMock()
        mock_lc.can_make_request.return_value = False

        service = SentimentService(
            lunarcrush=mock_lc,
            bluesky=MockBlueskyFetcher(),
            telegram=MockTelegramFetcher(),
        )

        result = await service.fetch_all_sentiment("SOLUSD")

        assert result.lunarcrush is None
        assert result.galaxy_score is None
        # Should still have social data
        assert len(result.bluesky_posts) > 0


class TestAssetRotator:
    """Tests for AssetRotator class."""

    def test_get_current_group(self):
        """Test getting current group of assets."""
        from services.sentiment import AssetRotator

        # Create mock assets
        assets = [MagicMock(symbol=f"ASSET{i}USD") for i in range(9)]

        rotator = AssetRotator(assets, num_groups=3)

        group = rotator.get_current_group()

        # First group should have 3 assets (9 / 3)
        assert len(group) == 3

    def test_advance_rotates_groups(self):
        """Test advancing to next group."""
        from services.sentiment import AssetRotator

        assets = [MagicMock(symbol=f"ASSET{i}USD") for i in range(9)]
        rotator = AssetRotator(assets, num_groups=3)

        assert rotator.current_group_index == 0

        rotator.advance()
        assert rotator.current_group_index == 1

        rotator.advance()
        assert rotator.current_group_index == 2

        rotator.advance()
        assert rotator.current_group_index == 0  # Wraps around

    def test_all_assets_covered(self):
        """Test all assets are covered across groups."""
        from services.sentiment import AssetRotator

        assets = [MagicMock(symbol=f"ASSET{i}USD") for i in range(10)]
        rotator = AssetRotator(assets, num_groups=3)

        all_processed = []

        for _ in range(3):
            group = rotator.get_current_group()
            all_processed.extend(group)
            rotator.advance()

        # All assets should be covered
        assert len(all_processed) == 10

    def test_empty_assets(self):
        """Test empty asset list."""
        from services.sentiment import AssetRotator

        rotator = AssetRotator([], num_groups=3)

        group = rotator.get_current_group()

        assert group == []

    def test_fewer_assets_than_groups(self):
        """Test when fewer assets than groups."""
        from services.sentiment import AssetRotator

        assets = [MagicMock(symbol="ASSET1USD")]
        rotator = AssetRotator(assets, num_groups=3)

        group = rotator.get_current_group()

        # Should return all assets
        assert len(group) == 1


class TestSaveSentimentLog:
    """Tests for save_sentiment_log function."""

    @pytest.mark.asyncio
    async def test_save_sentiment_log(self):
        """Test saving sentiment log to database."""
        from services.sentiment import save_sentiment_log, AggregatedSentiment

        sentiment = AggregatedSentiment(
            symbol="SOLUSD",
            aggregated_score=65,
            galaxy_score=60,
            alt_rank=12,
            social_volume=15000,
            raw_text="Sample text",
        )

        mock_session = AsyncMock()

        log = await save_sentiment_log(
            mock_session,
            asset_id="asset-123",
            source="aggregated",
            sentiment=sentiment,
        )

        mock_session.add.assert_called_once()
        assert log.asset_id == "asset-123"
        assert log.source == "aggregated"
        assert log.sentiment_score == 65
        assert log.galaxy_score == 60


class TestUpsertSentimentLog:
    """Tests for upsert_sentiment_log function."""

    @pytest.mark.asyncio
    async def test_upsert_success(self):
        """Test successful upsert."""
        from services.sentiment import upsert_sentiment_log, AggregatedSentiment

        sentiment = AggregatedSentiment(
            symbol="SOLUSD",
            aggregated_score=65,
        )

        mock_session = AsyncMock()

        result = await upsert_sentiment_log(
            mock_session,
            asset_id="asset-123",
            source="aggregated",
            sentiment=sentiment,
        )

        assert result is True
        mock_session.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_upsert_failure(self):
        """Test upsert handles errors."""
        from services.sentiment import upsert_sentiment_log, AggregatedSentiment

        sentiment = AggregatedSentiment(symbol="SOLUSD")

        mock_session = AsyncMock()
        mock_session.execute.side_effect = Exception("DB Error")

        result = await upsert_sentiment_log(
            mock_session,
            asset_id="asset-123",
            source="aggregated",
            sentiment=sentiment,
        )

        assert result is False


class TestGlobalServiceManagement:
    """Tests for global service instance management."""

    def test_get_sentiment_service_singleton(self):
        """Test singleton pattern."""
        from services import sentiment as sentiment_module
        from services.sentiment import get_sentiment_service

        # Reset global state
        sentiment_module._sentiment_service = None

        service1 = get_sentiment_service()
        service2 = get_sentiment_service()

        assert service1 is service2

    @pytest.mark.asyncio
    async def test_close_sentiment_service(self):
        """Test closing sentiment service."""
        from services import sentiment as sentiment_module
        from services.sentiment import close_sentiment_service, get_sentiment_service

        # Reset and create
        sentiment_module._sentiment_service = None
        get_sentiment_service()

        await close_sentiment_service()

        assert sentiment_module._sentiment_service is None
