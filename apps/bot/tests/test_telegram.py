"""
Tests for services/socials/telegram.py - Telegram fetcher.

Story 1.4: Sentiment Ingestor - Unit tests for Telegram message fetching
and mock implementation.
"""

import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import patch


class TestTelegramMessage:
    """Tests for TelegramMessage dataclass."""

    def test_message_to_dict(self):
        """Test converting message to dictionary."""
        from services.socials.telegram import TelegramMessage

        now = datetime.now(timezone.utc)
        msg = TelegramMessage(
            text="BTC breaking out!",
            channel="@CryptoNews",
            timestamp=now,
            views=5000,
            forwards=100,
            message_id=12345,
        )

        result = msg.to_dict()

        assert result["text"] == "BTC breaking out!"
        assert result["channel"] == "@CryptoNews"
        assert result["views"] == 5000
        assert result["forwards"] == 100
        assert result["message_id"] == 12345
        assert "timestamp" in result


class TestTelegramFetcher:
    """Tests for real TelegramFetcher (stub implementation)."""

    @pytest.mark.asyncio
    async def test_fetch_channel_returns_empty(self):
        """Test stub implementation returns empty list."""
        from services.socials.telegram import TelegramFetcher

        fetcher = TelegramFetcher()
        messages = await fetcher.fetch_channel_messages("@CryptoNews", "BTC")

        assert messages == []

    @pytest.mark.asyncio
    async def test_fetch_all_channels_returns_empty(self):
        """Test stub fetch_all_channels returns empty list."""
        from services.socials.telegram import TelegramFetcher

        fetcher = TelegramFetcher()
        messages = await fetcher.fetch_all_channels("BTC")

        assert messages == []

    @pytest.mark.asyncio
    async def test_close_fetcher(self):
        """Test closing the fetcher."""
        from services.socials.telegram import TelegramFetcher

        fetcher = TelegramFetcher()
        await fetcher.close()

        assert fetcher._authenticated is False


class TestMockTelegramFetcher:
    """Tests for MockTelegramFetcher."""

    @pytest.mark.asyncio
    async def test_fetch_channel_returns_messages(self):
        """Test mock fetcher returns messages."""
        from services.socials.telegram import MockTelegramFetcher

        fetcher = MockTelegramFetcher(seed=42)
        messages = await fetcher.fetch_channel_messages("@CryptoNews", "BTC", limit=5)

        assert len(messages) == 5
        for msg in messages:
            assert "BTC" in msg.text
            assert msg.channel == "@CryptoNews"
            assert msg.views >= 0
            assert msg.timestamp is not None
            assert msg.message_id > 0

    @pytest.mark.asyncio
    async def test_fetch_normalizes_symbol(self):
        """Test mock fetcher normalizes symbol format."""
        from services.socials.telegram import MockTelegramFetcher

        fetcher = MockTelegramFetcher(seed=42)
        messages = await fetcher.fetch_channel_messages("@Test", "SOLUSD", limit=3)

        # Should use SOL, not SOLUSD
        for msg in messages:
            assert "SOL" in msg.text
            assert "SOLUSD" not in msg.text

    @pytest.mark.asyncio
    async def test_fetch_handles_lowercase(self):
        """Test mock fetcher handles lowercase input."""
        from services.socials.telegram import MockTelegramFetcher

        fetcher = MockTelegramFetcher()
        messages = await fetcher.fetch_channel_messages("@Test", "eth", limit=3)

        for msg in messages:
            assert "ETH" in msg.text

    @pytest.mark.asyncio
    async def test_fetch_limits_results(self):
        """Test mock fetcher respects limit parameter."""
        from services.socials.telegram import MockTelegramFetcher

        fetcher = MockTelegramFetcher()

        msgs_3 = await fetcher.fetch_channel_messages("@Test", "SOL", limit=3)
        msgs_5 = await fetcher.fetch_channel_messages("@Test", "SOL", limit=5)
        msgs_10 = await fetcher.fetch_channel_messages("@Test", "SOL", limit=10)

        assert len(msgs_3) == 3
        assert len(msgs_5) == 5
        assert len(msgs_10) == 5  # Max per channel is 5

    @pytest.mark.asyncio
    async def test_fetch_all_channels(self):
        """Test fetching from all target channels."""
        from services.socials.telegram import MockTelegramFetcher

        fetcher = MockTelegramFetcher()
        messages = await fetcher.fetch_all_channels("SOL", limit_per_channel=3)

        # Should have messages from multiple channels
        channels_seen = set(msg.channel for msg in messages)
        assert len(channels_seen) > 1

        # All should contain the symbol
        for msg in messages:
            assert "SOL" in msg.text

    @pytest.mark.asyncio
    async def test_fetch_all_channels_sorted_by_time(self):
        """Test messages are sorted by timestamp (most recent first)."""
        from services.socials.telegram import MockTelegramFetcher

        fetcher = MockTelegramFetcher()
        messages = await fetcher.fetch_all_channels("BTC")

        # Check sorted descending
        for i in range(len(messages) - 1):
            assert messages[i].timestamp >= messages[i + 1].timestamp

    @pytest.mark.asyncio
    async def test_messages_have_valid_timestamps(self):
        """Test mock messages have recent timestamps."""
        from services.socials.telegram import MockTelegramFetcher

        fetcher = MockTelegramFetcher()
        messages = await fetcher.fetch_channel_messages("@Test", "SOL")

        now = datetime.now(timezone.utc)
        for msg in messages:
            # All timestamps should be within the last 2 hours
            age = now - msg.timestamp
            assert age < timedelta(hours=2)

    @pytest.mark.asyncio
    async def test_messages_contain_price_info(self):
        """Test some messages contain price information."""
        from services.socials.telegram import MockTelegramFetcher

        fetcher = MockTelegramFetcher()
        # Fetch many messages to ensure we get some with prices
        messages = await fetcher.fetch_all_channels("BTC", limit_per_channel=5)

        # At least some messages should contain price info
        has_price = any("$" in msg.text for msg in messages)
        assert has_price

    @pytest.mark.asyncio
    async def test_mock_close(self):
        """Test closing mock fetcher."""
        from services.socials.telegram import MockTelegramFetcher

        fetcher = MockTelegramFetcher()
        await fetcher.close()

        assert fetcher._closed is True

    @pytest.mark.asyncio
    async def test_mock_generates_valid_messages(self):
        """Test mock generates messages with valid structure."""
        from services.socials.telegram import MockTelegramFetcher

        fetcher = MockTelegramFetcher()
        msgs = await fetcher.fetch_channel_messages("@Test", "SOL", limit=3)

        # All messages should have valid structure
        for msg in msgs:
            assert len(msg.text) > 0
            assert msg.channel.startswith("@")
            assert msg.views >= 0
            assert msg.forwards >= 0
            assert msg.message_id > 0


class TestGetTelegramFetcher:
    """Tests for factory function."""

    def test_returns_mock_fetcher(self):
        """Test factory returns MockTelegramFetcher for MVP."""
        from services.socials.telegram import get_telegram_fetcher, MockTelegramFetcher

        fetcher = get_telegram_fetcher()
        assert isinstance(fetcher, MockTelegramFetcher)

    def test_returns_mock_even_with_credentials(self):
        """Test factory returns mock even when credentials are set (MVP)."""
        from services.socials.telegram import get_telegram_fetcher, MockTelegramFetcher

        with patch.dict(
            "os.environ",
            {
                "TELEGRAM_API_ID": "12345",
                "TELEGRAM_API_HASH": "abc123",
            },
            clear=False,
        ):
            fetcher = get_telegram_fetcher()
            # For MVP, always use mock
            assert isinstance(fetcher, MockTelegramFetcher)


class TestGlobalFetcherManagement:
    """Tests for global fetcher instance management."""

    @pytest.mark.asyncio
    async def test_close_global_fetcher(self):
        """Test closing global fetcher."""
        from services.socials import telegram as tg_module
        from services.socials.telegram import (
            close_telegram_fetcher,
            get_or_create_telegram_fetcher,
            MockTelegramFetcher,
        )

        # Reset global state
        tg_module._telegram_fetcher = None

        fetcher = get_or_create_telegram_fetcher()
        assert isinstance(fetcher, MockTelegramFetcher)

        await close_telegram_fetcher()
        assert tg_module._telegram_fetcher is None

    def test_get_or_create_returns_same_instance(self):
        """Test singleton pattern."""
        from services.socials import telegram as tg_module
        from services.socials.telegram import get_or_create_telegram_fetcher

        # Reset global state
        tg_module._telegram_fetcher = None

        fetcher1 = get_or_create_telegram_fetcher()
        fetcher2 = get_or_create_telegram_fetcher()

        assert fetcher1 is fetcher2


class TestTargetConfiguration:
    """Tests for target channels configuration."""

    def test_target_channels_defined(self):
        """Test target channels are defined."""
        from services.socials.telegram import MockTelegramFetcher

        assert len(MockTelegramFetcher.TARGET_CHANNELS) > 0
        for channel in MockTelegramFetcher.TARGET_CHANNELS:
            assert channel.startswith("@")

    def test_specific_channels_included(self):
        """Test expected channels are included."""
        from services.socials.telegram import MockTelegramFetcher

        assert "@CryptoNews" in MockTelegramFetcher.TARGET_CHANNELS
        assert "@WhaleTrades" in MockTelegramFetcher.TARGET_CHANNELS


class TestPriceGeneration:
    """Tests for price generation in mock."""

    def test_price_ranges_realistic(self):
        """Test generated prices are in realistic ranges."""
        from services.socials.telegram import MockTelegramFetcher

        fetcher = MockTelegramFetcher()

        # BTC should be in reasonable range
        btc_price = fetcher._generate_price("BTC")
        assert 30000 <= btc_price <= 80000

        # ETH should be in reasonable range
        eth_price = fetcher._generate_price("ETH")
        assert 1500 <= eth_price <= 5000

        # SOL should be in reasonable range
        sol_price = fetcher._generate_price("SOL")
        assert 30 <= sol_price <= 250
