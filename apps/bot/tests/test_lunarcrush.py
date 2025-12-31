"""
Tests for services/lunarcrush.py - LunarCrush API client.

Story 1.4: Sentiment Ingestor - Unit tests for symbol conversion,
mock client, rate limiting, and API response parsing.
"""

import pytest
from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch
import httpx


class TestSymbolConversion:
    """Tests for symbol conversion functions."""

    def test_convert_to_lunarcrush_solusd(self):
        """Test SOLUSD converts to sol."""
        from services.lunarcrush import convert_to_lunarcrush_symbol

        result = convert_to_lunarcrush_symbol("SOLUSD")
        assert result == "sol"

    def test_convert_to_lunarcrush_btcusd(self):
        """Test BTCUSD converts to btc."""
        from services.lunarcrush import convert_to_lunarcrush_symbol

        result = convert_to_lunarcrush_symbol("BTCUSD")
        assert result == "btc"

    def test_convert_to_lunarcrush_ethusd(self):
        """Test ETHUSD converts to eth."""
        from services.lunarcrush import convert_to_lunarcrush_symbol

        result = convert_to_lunarcrush_symbol("ETHUSD")
        assert result == "eth"

    def test_convert_to_lunarcrush_lowercase(self):
        """Test output is always lowercase."""
        from services.lunarcrush import convert_to_lunarcrush_symbol

        result = convert_to_lunarcrush_symbol("AVAXUSD")
        assert result == "avax"
        assert result.islower()

    def test_convert_to_lunarcrush_empty_raises(self):
        """Test empty symbol raises ValueError."""
        from services.lunarcrush import convert_to_lunarcrush_symbol

        with pytest.raises(ValueError, match="Empty symbol"):
            convert_to_lunarcrush_symbol("")

    def test_convert_from_lunarcrush(self):
        """Test converting back from LunarCrush format."""
        from services.lunarcrush import convert_from_lunarcrush_symbol

        result = convert_from_lunarcrush_symbol("sol")
        assert result == "SOLUSD"

    def test_convert_from_lunarcrush_uppercase(self):
        """Test output is uppercase with USD suffix."""
        from services.lunarcrush import convert_from_lunarcrush_symbol

        result = convert_from_lunarcrush_symbol("btc")
        assert result == "BTCUSD"
        assert result.isupper()

    def test_convert_from_lunarcrush_empty_raises(self):
        """Test empty symbol raises ValueError."""
        from services.lunarcrush import convert_from_lunarcrush_symbol

        with pytest.raises(ValueError, match="Empty symbol"):
            convert_from_lunarcrush_symbol("")


class TestLunarCrushMetrics:
    """Tests for LunarCrushMetrics dataclass."""

    def test_metrics_to_dict(self):
        """Test converting metrics to dictionary."""
        from services.lunarcrush import LunarCrushMetrics

        metrics = LunarCrushMetrics(
            galaxy_score=65,
            alt_rank=12,
            social_volume=15000,
            social_score=72,
            bullish_sentiment=0.65,
            bearish_sentiment=0.35,
            symbol="sol",
        )

        result = metrics.to_dict()

        assert result["galaxy_score"] == 65
        assert result["alt_rank"] == 12
        assert result["social_volume"] == 15000
        assert result["social_score"] == 72
        assert result["bullish_sentiment"] == 0.65
        assert result["bearish_sentiment"] == 0.35
        assert result["symbol"] == "sol"


class TestRateLimitTracker:
    """Tests for RateLimitTracker."""

    def test_initial_state(self):
        """Test tracker starts with zero calls."""
        from services.lunarcrush import RateLimitTracker

        tracker = RateLimitTracker(daily_limit=300)

        assert tracker.calls_today == 0
        assert tracker.can_make_request() is True
        assert tracker.get_remaining() == 300

    def test_record_call_decrements_remaining(self):
        """Test recording calls decrements remaining quota."""
        from services.lunarcrush import RateLimitTracker

        tracker = RateLimitTracker(daily_limit=300)

        tracker.record_call()
        assert tracker.calls_today == 1
        assert tracker.get_remaining() == 299

    def test_quota_exhausted_blocks_requests(self):
        """Test can_make_request returns False when quota exhausted."""
        from services.lunarcrush import RateLimitTracker

        tracker = RateLimitTracker(daily_limit=5)

        for _ in range(5):
            tracker.record_call()

        assert tracker.can_make_request() is False
        assert tracker.get_remaining() == 0

    def test_day_rollover_resets_quota(self):
        """Test quota resets on new day."""
        from services.lunarcrush import RateLimitTracker
        from datetime import date, timedelta

        tracker = RateLimitTracker(daily_limit=300)
        tracker.calls_today = 300
        tracker.last_reset_date = date.today() - timedelta(days=1)

        # Should reset on check
        assert tracker.can_make_request() is True
        assert tracker.calls_today == 0


class TestMockLunarCrushClient:
    """Tests for MockLunarCrushClient."""

    @pytest.mark.asyncio
    async def test_mock_returns_metrics(self):
        """Test mock client returns valid metrics."""
        from services.lunarcrush import MockLunarCrushClient

        client = MockLunarCrushClient(seed=42)
        metrics = await client.get_coin_metrics("SOLUSD")

        assert metrics.galaxy_score >= 30
        assert metrics.galaxy_score <= 75
        assert metrics.alt_rank >= 1
        assert metrics.alt_rank <= 100
        assert metrics.social_volume >= 1000
        assert metrics.social_volume <= 50000
        assert metrics.symbol == "sol"

    @pytest.mark.asyncio
    async def test_mock_converts_symbol(self):
        """Test mock client converts symbol format."""
        from services.lunarcrush import MockLunarCrushClient

        client = MockLunarCrushClient()
        metrics = await client.get_coin_metrics("BTCUSD")

        assert metrics.symbol == "btc"

    @pytest.mark.asyncio
    async def test_mock_handles_lowercase_symbol(self):
        """Test mock client handles already-lowercase symbol."""
        from services.lunarcrush import MockLunarCrushClient

        client = MockLunarCrushClient()
        metrics = await client.get_coin_metrics("eth")

        assert metrics.symbol == "eth"

    @pytest.mark.asyncio
    async def test_mock_sentiment_sums_to_one(self):
        """Test bullish + bearish sentiment approximately equals 1."""
        from services.lunarcrush import MockLunarCrushClient

        client = MockLunarCrushClient()
        metrics = await client.get_coin_metrics("SOLUSD")

        total = metrics.bullish_sentiment + metrics.bearish_sentiment
        assert abs(total - 1.0) < 0.01

    def test_mock_can_always_make_request(self):
        """Test mock client always allows requests."""
        from services.lunarcrush import MockLunarCrushClient

        client = MockLunarCrushClient()

        assert client.can_make_request() is True
        assert client.get_remaining_quota() == 999999

    @pytest.mark.asyncio
    async def test_mock_close(self):
        """Test mock client close method."""
        from services.lunarcrush import MockLunarCrushClient

        client = MockLunarCrushClient()
        await client.close()

        assert client._closed is True

    @pytest.mark.asyncio
    async def test_mock_generates_valid_metrics(self):
        """Test mock client generates valid metrics structure."""
        from services.lunarcrush import MockLunarCrushClient

        client = MockLunarCrushClient()
        metrics = await client.get_coin_metrics("SOLUSD")

        # Verify valid structure
        assert 0 <= metrics.galaxy_score <= 100
        assert 1 <= metrics.alt_rank <= 1000
        assert metrics.social_volume >= 0
        assert 0 <= metrics.bullish_sentiment <= 1
        assert 0 <= metrics.bearish_sentiment <= 1


class TestLunarCrushClient:
    """Tests for real LunarCrushClient."""

    def test_client_initialization(self):
        """Test client initializes with API key."""
        from services.lunarcrush import LunarCrushClient

        client = LunarCrushClient(api_key="test_key")

        assert client.api_key == "test_key"
        assert client.rate_tracker.daily_limit == 300

    def test_client_custom_daily_limit(self):
        """Test client accepts custom daily limit."""
        from services.lunarcrush import LunarCrushClient

        client = LunarCrushClient(api_key="test", daily_limit=10000)

        assert client.rate_tracker.daily_limit == 10000

    def test_can_make_request_respects_limit(self):
        """Test can_make_request checks rate tracker."""
        from services.lunarcrush import LunarCrushClient

        client = LunarCrushClient(api_key="test", daily_limit=1)
        client.rate_tracker.calls_today = 1

        assert client.can_make_request() is False

    def test_get_remaining_quota(self):
        """Test get_remaining_quota returns correct value."""
        from services.lunarcrush import LunarCrushClient

        client = LunarCrushClient(api_key="test", daily_limit=100)
        client.rate_tracker.calls_today = 30

        assert client.get_remaining_quota() == 70

    @pytest.mark.asyncio
    async def test_close_client(self):
        """Test closing the client."""
        from services.lunarcrush import LunarCrushClient

        client = LunarCrushClient(api_key="test")
        # Force client creation
        await client._get_client()

        await client.close()

        assert client._initialized is False

    @pytest.mark.asyncio
    async def test_get_coin_metrics_rate_limit_exceeded(self):
        """Test get_coin_metrics raises when rate limit exceeded."""
        from services.lunarcrush import LunarCrushClient

        client = LunarCrushClient(api_key="test", daily_limit=0)

        with pytest.raises(RuntimeError, match="rate limit exceeded"):
            await client.get_coin_metrics("SOLUSD")

    @pytest.mark.asyncio
    async def test_get_coin_metrics_success(self):
        """Test successful API call."""
        from services.lunarcrush import LunarCrushClient

        mock_response = {
            "data": {
                "galaxy_score": 67,
                "alt_rank": 12,
                "social_volume": 15234,
                "social_score": 72,
                "sentiment": {
                    "bullish": 0.65,
                    "bearish": 0.35,
                },
            }
        }

        with patch.object(
            LunarCrushClient,
            "_get_client",
            return_value=AsyncMock(
                get=AsyncMock(
                    return_value=MagicMock(
                        raise_for_status=MagicMock(),
                        json=MagicMock(return_value=mock_response),
                    )
                )
            ),
        ):
            client = LunarCrushClient(api_key="test_key")
            metrics = await client.get_coin_metrics("SOLUSD")

            assert metrics.galaxy_score == 67
            assert metrics.alt_rank == 12
            assert metrics.social_volume == 15234
            assert metrics.bullish_sentiment == 0.65

    @pytest.mark.asyncio
    async def test_get_coin_metrics_404_returns_defaults(self):
        """Test 404 response returns default metrics."""
        from services.lunarcrush import LunarCrushClient

        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Not Found", request=MagicMock(), response=mock_response
        )

        with patch.object(
            LunarCrushClient,
            "_get_client",
            return_value=AsyncMock(get=AsyncMock(return_value=mock_response)),
        ):
            client = LunarCrushClient(api_key="test_key")
            metrics = await client.get_coin_metrics("UNKNOWNCOIN")

            # Should return defaults for unknown coins
            assert metrics.galaxy_score == 50
            assert metrics.alt_rank == 1000


class TestGetLunarCrushClient:
    """Tests for factory function."""

    def test_returns_mock_when_no_api_key(self):
        """Test returns MockLunarCrushClient when no API key."""
        from services.lunarcrush import get_lunarcrush_client, MockLunarCrushClient

        with patch.dict("os.environ", {"LUNARCRUSH_API_KEY": ""}, clear=False):
            client = get_lunarcrush_client()
            assert isinstance(client, MockLunarCrushClient)

    def test_returns_real_when_api_key_set(self):
        """Test returns LunarCrushClient when API key is set."""
        from services.lunarcrush import get_lunarcrush_client, LunarCrushClient

        with patch.dict("os.environ", {"LUNARCRUSH_API_KEY": "real_key"}, clear=False):
            client = get_lunarcrush_client()
            assert isinstance(client, LunarCrushClient)


class TestGlobalClientManagement:
    """Tests for global client instance management."""

    @pytest.mark.asyncio
    async def test_close_global_client(self):
        """Test closing global client."""
        from services import lunarcrush as lc_module
        from services.lunarcrush import (
            close_lunarcrush_client,
            get_or_create_lunarcrush_client,
            MockLunarCrushClient,
        )

        # Reset global state
        lc_module._lunarcrush_client = None

        with patch.dict("os.environ", {"LUNARCRUSH_API_KEY": ""}, clear=False):
            client = get_or_create_lunarcrush_client()
            assert isinstance(client, MockLunarCrushClient)

            await close_lunarcrush_client()
            assert lc_module._lunarcrush_client is None

    def test_get_or_create_returns_same_instance(self):
        """Test singleton pattern."""
        from services import lunarcrush as lc_module
        from services.lunarcrush import get_or_create_lunarcrush_client

        # Reset global state
        lc_module._lunarcrush_client = None

        with patch.dict("os.environ", {"LUNARCRUSH_API_KEY": ""}, clear=False):
            client1 = get_or_create_lunarcrush_client()
            client2 = get_or_create_lunarcrush_client()

            assert client1 is client2
