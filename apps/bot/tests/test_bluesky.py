"""
Tests for services/socials/bluesky.py - Bluesky fetcher.

Story 1.4: Sentiment Ingestor - Unit tests for Bluesky post fetching
and mock implementation.
"""

import pytest
from datetime import datetime, timezone
from unittest.mock import patch


class TestBlueskyPost:
    """Tests for BlueskyPost dataclass."""

    def test_post_to_dict(self):
        """Test converting post to dictionary."""
        from services.socials.bluesky import BlueskyPost

        now = datetime.now(timezone.utc)
        post = BlueskyPost(
            text="SOL is looking bullish!",
            author="trader.bsky.social",
            timestamp=now,
            likes=100,
            reposts=25,
            uri="at://test/app.bsky.feed.post/123",
        )

        result = post.to_dict()

        assert result["text"] == "SOL is looking bullish!"
        assert result["author"] == "trader.bsky.social"
        assert result["likes"] == 100
        assert result["reposts"] == 25
        assert result["uri"] == "at://test/app.bsky.feed.post/123"
        assert "timestamp" in result


class TestBlueskyFetcher:
    """Tests for real BlueskyFetcher (stub implementation)."""

    @pytest.mark.asyncio
    async def test_fetch_returns_empty_list(self):
        """Test stub implementation returns empty list."""
        from services.socials.bluesky import BlueskyFetcher

        fetcher = BlueskyFetcher()
        posts = await fetcher.fetch_recent_posts("SOL")

        assert posts == []

    @pytest.mark.asyncio
    async def test_close_fetcher(self):
        """Test closing the fetcher."""
        from services.socials.bluesky import BlueskyFetcher

        fetcher = BlueskyFetcher()
        await fetcher.close()

        assert fetcher._authenticated is False


class TestMockBlueskyFetcher:
    """Tests for MockBlueskyFetcher."""

    @pytest.mark.asyncio
    async def test_fetch_returns_posts(self):
        """Test mock fetcher returns posts."""
        from services.socials.bluesky import MockBlueskyFetcher

        fetcher = MockBlueskyFetcher(seed=42)
        posts = await fetcher.fetch_recent_posts("SOL", limit=5)

        assert len(posts) == 5
        for post in posts:
            assert "SOL" in post.text
            assert post.author.endswith(".bsky.social")
            assert post.likes >= 0
            assert post.timestamp is not None

    @pytest.mark.asyncio
    async def test_fetch_normalizes_symbol(self):
        """Test mock fetcher normalizes symbol format."""
        from services.socials.bluesky import MockBlueskyFetcher

        fetcher = MockBlueskyFetcher(seed=42)
        posts = await fetcher.fetch_recent_posts("SOLUSD", limit=3)

        # Should use SOL, not SOLUSD
        for post in posts:
            assert "SOL" in post.text
            assert "SOLUSD" not in post.text

    @pytest.mark.asyncio
    async def test_fetch_handles_lowercase(self):
        """Test mock fetcher handles lowercase input."""
        from services.socials.bluesky import MockBlueskyFetcher

        fetcher = MockBlueskyFetcher()
        posts = await fetcher.fetch_recent_posts("btc", limit=3)

        for post in posts:
            assert "BTC" in post.text

    @pytest.mark.asyncio
    async def test_fetch_limits_results(self):
        """Test mock fetcher respects limit parameter."""
        from services.socials.bluesky import MockBlueskyFetcher

        fetcher = MockBlueskyFetcher()

        posts_5 = await fetcher.fetch_recent_posts("SOL", limit=5)
        posts_10 = await fetcher.fetch_recent_posts("SOL", limit=10)
        posts_15 = await fetcher.fetch_recent_posts("SOL", limit=15)

        assert len(posts_5) == 5
        assert len(posts_10) == 10
        assert len(posts_15) == 10  # Max is 10

    @pytest.mark.asyncio
    async def test_posts_have_valid_timestamps(self):
        """Test mock posts have recent timestamps."""
        from services.socials.bluesky import MockBlueskyFetcher
        from datetime import timedelta

        fetcher = MockBlueskyFetcher()
        posts = await fetcher.fetch_recent_posts("SOL")

        now = datetime.now(timezone.utc)
        for post in posts:
            # All timestamps should be within the last hour
            age = now - post.timestamp
            assert age < timedelta(hours=1)

    @pytest.mark.asyncio
    async def test_posts_have_uri(self):
        """Test mock posts have URI field."""
        from services.socials.bluesky import MockBlueskyFetcher

        fetcher = MockBlueskyFetcher()
        posts = await fetcher.fetch_recent_posts("SOL")

        for post in posts:
            assert post.uri.startswith("at://")
            assert "sol" in post.uri.lower()

    @pytest.mark.asyncio
    async def test_mock_close(self):
        """Test closing mock fetcher."""
        from services.socials.bluesky import MockBlueskyFetcher

        fetcher = MockBlueskyFetcher()
        await fetcher.close()

        assert fetcher._closed is True

    @pytest.mark.asyncio
    async def test_mock_generates_valid_posts(self):
        """Test mock generates posts with valid structure."""
        from services.socials.bluesky import MockBlueskyFetcher

        fetcher = MockBlueskyFetcher()
        posts = await fetcher.fetch_recent_posts("SOL", limit=3)

        # All posts should have valid structure
        for post in posts:
            assert len(post.text) > 0
            assert post.author.endswith(".bsky.social")
            assert post.likes >= 0
            assert post.reposts >= 0


class TestGetBlueskyFetcher:
    """Tests for factory function."""

    def test_returns_mock_fetcher(self):
        """Test factory returns MockBlueskyFetcher for MVP."""
        from services.socials.bluesky import get_bluesky_fetcher, MockBlueskyFetcher

        fetcher = get_bluesky_fetcher()
        assert isinstance(fetcher, MockBlueskyFetcher)

    def test_returns_mock_even_with_credentials(self):
        """Test factory returns mock even when credentials are set (MVP)."""
        from services.socials.bluesky import get_bluesky_fetcher, MockBlueskyFetcher

        with patch.dict(
            "os.environ",
            {
                "BLUESKY_HANDLE": "test.bsky.social",
                "BLUESKY_PASSWORD": "password123",
            },
            clear=False,
        ):
            fetcher = get_bluesky_fetcher()
            # For MVP, always use mock
            assert isinstance(fetcher, MockBlueskyFetcher)


class TestGlobalFetcherManagement:
    """Tests for global fetcher instance management."""

    @pytest.mark.asyncio
    async def test_close_global_fetcher(self):
        """Test closing global fetcher."""
        from services.socials import bluesky as bsky_module
        from services.socials.bluesky import (
            close_bluesky_fetcher,
            get_or_create_bluesky_fetcher,
            MockBlueskyFetcher,
        )

        # Reset global state
        bsky_module._bluesky_fetcher = None

        fetcher = get_or_create_bluesky_fetcher()
        assert isinstance(fetcher, MockBlueskyFetcher)

        await close_bluesky_fetcher()
        assert bsky_module._bluesky_fetcher is None

    def test_get_or_create_returns_same_instance(self):
        """Test singleton pattern."""
        from services.socials import bluesky as bsky_module
        from services.socials.bluesky import get_or_create_bluesky_fetcher

        # Reset global state
        bsky_module._bluesky_fetcher = None

        fetcher1 = get_or_create_bluesky_fetcher()
        fetcher2 = get_or_create_bluesky_fetcher()

        assert fetcher1 is fetcher2


class TestTargetConfiguration:
    """Tests for target hashtags and accounts."""

    def test_target_hashtags_defined(self):
        """Test target hashtags are defined."""
        from services.socials.bluesky import MockBlueskyFetcher

        assert len(MockBlueskyFetcher.TARGET_HASHTAGS) > 0
        assert "#crypto" in MockBlueskyFetcher.TARGET_HASHTAGS

    def test_target_accounts_defined(self):
        """Test target accounts are defined."""
        from services.socials.bluesky import MockBlueskyFetcher

        assert len(MockBlueskyFetcher.TARGET_ACCOUNTS) > 0
        for account in MockBlueskyFetcher.TARGET_ACCOUNTS:
            assert account.endswith(".bsky.social")

    def test_sample_authors_defined(self):
        """Test sample authors for mock are defined."""
        from services.socials.bluesky import MockBlueskyFetcher

        assert len(MockBlueskyFetcher.SAMPLE_AUTHORS) > 0
        for author in MockBlueskyFetcher.SAMPLE_AUTHORS:
            assert author.endswith(".bsky.social")
