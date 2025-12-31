"""
Unit tests for Data Loader Utilities.

Story 2.2: Sentiment & Technical Agents

Tests cover:
- Loading candles for assets
- Loading sentiment for assets
- Asset lookup functions
- Error handling
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timedelta
from decimal import Decimal

from services.data_loader import (
    load_candles_for_asset,
    load_sentiment_for_asset,
    load_asset_by_symbol,
    get_active_assets
)


@pytest.fixture
def mock_candles():
    """Create mock Candle objects."""
    candles = []
    base_time = datetime.utcnow() - timedelta(hours=10)

    for i in range(10):
        mock_candle = MagicMock()
        mock_candle.timestamp = base_time + timedelta(hours=i)
        mock_candle.open = Decimal("100.0") + Decimal(i)
        mock_candle.high = Decimal("101.0") + Decimal(i)
        mock_candle.low = Decimal("99.0") + Decimal(i)
        mock_candle.close = Decimal("100.5") + Decimal(i)
        mock_candle.volume = Decimal("10000.0") + Decimal(i * 100)
        candles.append(mock_candle)

    return candles


@pytest.fixture
def mock_sentiment_logs():
    """Create mock SentimentLog objects."""
    logs = []
    base_time = datetime.utcnow() - timedelta(hours=5)

    for i in range(5):
        mock_log = MagicMock()
        mock_log.raw_text = f"Sentiment text {i}"
        mock_log.source = "twitter" if i % 2 == 0 else "reddit"
        mock_log.timestamp = base_time + timedelta(hours=i)
        mock_log.galaxy_score = 50 + i
        mock_log.sentiment_score = 60 + i
        logs.append(mock_log)

    return logs


@pytest.fixture
def mock_asset():
    """Create a mock Asset object."""
    mock = MagicMock()
    mock.id = "test-asset-id"
    mock.symbol = "BTCUSD"
    mock.name = "Bitcoin"
    mock.is_active = True
    return mock


class TestLoadCandlesForAsset:
    """Tests for load_candles_for_asset function."""

    @pytest.mark.asyncio
    async def test_returns_candles_as_dicts(self, mock_candles):
        """Test that candles are returned as dict format."""
        # Create mock session
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = mock_candles
        mock_session.execute.return_value = mock_result

        result = await load_candles_for_asset(
            asset_id="test-asset-id",
            limit=200,
            session=mock_session
        )

        assert len(result) == 10
        assert all(isinstance(c, dict) for c in result)

        # Check dict structure
        first_candle = result[0]
        assert "timestamp" in first_candle
        assert "open" in first_candle
        assert "high" in first_candle
        assert "low" in first_candle
        assert "close" in first_candle
        assert "volume" in first_candle

    @pytest.mark.asyncio
    async def test_converts_decimal_to_float(self, mock_candles):
        """Test that Decimal values are converted to float."""
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = mock_candles
        mock_session.execute.return_value = mock_result

        result = await load_candles_for_asset(
            asset_id="test-asset-id",
            session=mock_session
        )

        first_candle = result[0]
        assert isinstance(first_candle["open"], float)
        assert isinstance(first_candle["close"], float)
        assert isinstance(first_candle["volume"], float)

    @pytest.mark.asyncio
    async def test_returns_empty_list_on_error(self):
        """Test that empty list is returned on database error."""
        mock_session = AsyncMock()
        mock_session.execute.side_effect = Exception("Database error")

        result = await load_candles_for_asset(
            asset_id="test-asset-id",
            session=mock_session
        )

        assert result == []

    @pytest.mark.asyncio
    async def test_respects_limit_parameter(self, mock_candles):
        """Test that limit parameter is used in query."""
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = mock_candles[:5]
        mock_session.execute.return_value = mock_result

        result = await load_candles_for_asset(
            asset_id="test-asset-id",
            limit=5,
            session=mock_session
        )

        assert len(result) == 5

    @pytest.mark.asyncio
    async def test_candles_sorted_oldest_first(self, mock_candles):
        """Test that candles are sorted oldest-first for TA."""
        mock_session = AsyncMock()
        mock_result = MagicMock()
        # Return in descending order (newest first from DB)
        mock_result.scalars.return_value.all.return_value = list(reversed(mock_candles))
        mock_session.execute.return_value = mock_result

        result = await load_candles_for_asset(
            asset_id="test-asset-id",
            session=mock_session
        )

        # Should be oldest-first after reversal
        timestamps = [c["timestamp"] for c in result]
        assert timestamps == sorted(timestamps)


class TestLoadSentimentForAsset:
    """Tests for load_sentiment_for_asset function."""

    @pytest.mark.asyncio
    async def test_returns_sentiment_as_dicts(self, mock_sentiment_logs, mock_asset):
        """Test that sentiment logs are returned as dict format."""
        mock_session = AsyncMock()

        # Mock asset lookup
        asset_result = MagicMock()
        asset_result.scalar_one_or_none.return_value = mock_asset

        # Mock sentiment query
        sentiment_result = MagicMock()
        sentiment_result.scalars.return_value.all.return_value = mock_sentiment_logs

        mock_session.execute.side_effect = [asset_result, sentiment_result]

        result = await load_sentiment_for_asset(
            asset_symbol="BTCUSD",
            hours=24,
            session=mock_session
        )

        assert len(result) == 5
        assert all(isinstance(s, dict) for s in result)

        # Check dict structure
        first_sentiment = result[0]
        assert "text" in first_sentiment
        assert "source" in first_sentiment
        assert "timestamp" in first_sentiment

    @pytest.mark.asyncio
    async def test_returns_empty_list_for_unknown_asset(self):
        """Test returns empty list when asset not found."""
        mock_session = AsyncMock()

        asset_result = MagicMock()
        asset_result.scalar_one_or_none.return_value = None

        mock_session.execute.return_value = asset_result

        result = await load_sentiment_for_asset(
            asset_symbol="UNKNOWNUSD",
            session=mock_session
        )

        assert result == []

    @pytest.mark.asyncio
    async def test_returns_empty_list_on_error(self):
        """Test returns empty list on database error."""
        mock_session = AsyncMock()
        mock_session.execute.side_effect = Exception("Database error")

        result = await load_sentiment_for_asset(
            asset_symbol="BTCUSD",
            session=mock_session
        )

        assert result == []

    @pytest.mark.asyncio
    async def test_filters_empty_text(self, mock_asset):
        """Test that logs without text are filtered out."""
        logs = [
            MagicMock(raw_text="Valid text", source="twitter", timestamp=datetime.utcnow(), galaxy_score=50, sentiment_score=60),
            MagicMock(raw_text="", source="reddit", timestamp=datetime.utcnow(), galaxy_score=50, sentiment_score=60),
            MagicMock(raw_text=None, source="news", timestamp=datetime.utcnow(), galaxy_score=50, sentiment_score=60),
        ]

        mock_session = AsyncMock()

        asset_result = MagicMock()
        asset_result.scalar_one_or_none.return_value = mock_asset

        sentiment_result = MagicMock()
        sentiment_result.scalars.return_value.all.return_value = logs

        mock_session.execute.side_effect = [asset_result, sentiment_result]

        result = await load_sentiment_for_asset(
            asset_symbol="BTCUSD",
            session=mock_session
        )

        # Should only include the one with valid text
        assert len(result) == 1
        assert result[0]["text"] == "Valid text"


class TestLoadAssetBySymbol:
    """Tests for load_asset_by_symbol function."""

    @pytest.mark.asyncio
    async def test_returns_asset_when_found(self, mock_asset):
        """Test returns asset when found."""
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_asset
        mock_session.execute.return_value = mock_result

        result = await load_asset_by_symbol(
            symbol="BTCUSD",
            session=mock_session
        )

        assert result is not None
        assert result.symbol == "BTCUSD"

    @pytest.mark.asyncio
    async def test_returns_none_when_not_found(self):
        """Test returns None when asset not found."""
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        result = await load_asset_by_symbol(
            symbol="UNKNOWNUSD",
            session=mock_session
        )

        assert result is None

    @pytest.mark.asyncio
    async def test_returns_none_on_error(self):
        """Test returns None on database error."""
        mock_session = AsyncMock()
        mock_session.execute.side_effect = Exception("Database error")

        result = await load_asset_by_symbol(
            symbol="BTCUSD",
            session=mock_session
        )

        assert result is None


class TestGetActiveAssets:
    """Tests for get_active_assets function."""

    @pytest.mark.asyncio
    async def test_returns_active_assets(self, mock_asset):
        """Test returns list of active assets."""
        mock_assets = [mock_asset, mock_asset]

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = mock_assets
        mock_session.execute.return_value = mock_result

        result = await get_active_assets(session=mock_session)

        assert len(result) == 2

    @pytest.mark.asyncio
    async def test_returns_empty_list_when_none_active(self):
        """Test returns empty list when no active assets."""
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_session.execute.return_value = mock_result

        result = await get_active_assets(session=mock_session)

        assert result == []

    @pytest.mark.asyncio
    async def test_returns_empty_list_on_error(self):
        """Test returns empty list on database error."""
        mock_session = AsyncMock()
        mock_session.execute.side_effect = Exception("Database error")

        result = await get_active_assets(session=mock_session)

        assert result == []
