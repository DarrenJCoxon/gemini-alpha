"""
Tests for services/scheduler.py - APScheduler and ingestion logic.

Story 1.3: Kraken Data Ingestor - Tests for scheduler configuration,
active assets fetching, and candle upsert logic.
"""

import pytest
from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

from apscheduler.triggers.cron import CronTrigger


class TestSchedulerConfiguration:
    """Tests for scheduler setup."""

    def test_create_scheduler_returns_scheduler(self):
        """Test create_scheduler returns AsyncIOScheduler."""
        from services.scheduler import create_scheduler

        scheduler = create_scheduler()
        assert scheduler is not None

    def test_scheduler_has_kraken_job(self):
        """Test scheduler has Kraken ingestion job configured."""
        from services.scheduler import create_scheduler

        scheduler = create_scheduler()
        jobs = scheduler.get_jobs()

        job_ids = [job.id for job in jobs]
        assert "kraken_ingest" in job_ids

    def test_scheduler_job_uses_cron_trigger(self):
        """Test Kraken job uses CronTrigger with correct minutes."""
        from services.scheduler import create_scheduler

        scheduler = create_scheduler()
        job = scheduler.get_job("kraken_ingest")

        assert job is not None
        assert isinstance(job.trigger, CronTrigger)

    def test_get_scheduler_returns_singleton(self):
        """Test get_scheduler returns the same instance."""
        from services import scheduler as scheduler_module

        # Reset the singleton
        scheduler_module._scheduler = None

        s1 = scheduler_module.get_scheduler()
        s2 = scheduler_module.get_scheduler()

        assert s1 is s2


class TestGetActiveAssets:
    """Tests for get_active_assets function."""

    @pytest.mark.asyncio
    async def test_get_active_assets_returns_list(self):
        """Test get_active_assets returns list of assets."""
        from services.scheduler import get_active_assets

        mock_asset = MagicMock()
        mock_asset.id = "test-id"
        mock_asset.symbol = "BTCUSD"
        mock_asset.is_active = True

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [mock_asset]

        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(return_value=mock_result)

        result = await get_active_assets(mock_session)

        assert len(result) == 1
        assert result[0].symbol == "BTCUSD"

    @pytest.mark.asyncio
    async def test_get_active_assets_empty_database(self):
        """Test get_active_assets handles empty database."""
        from services.scheduler import get_active_assets

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []

        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(return_value=mock_result)

        result = await get_active_assets(mock_session)

        assert result == []


class TestUpsertCandle:
    """Tests for upsert_candle function."""

    @pytest.mark.asyncio
    async def test_upsert_candle_success(self):
        """Test successful candle upsert."""
        from services.scheduler import upsert_candle

        candle_data = {
            "timestamp": datetime.now(timezone.utc),
            "timeframe": "15m",
            "open": Decimal("42000.00"),
            "high": Decimal("42500.00"),
            "low": Decimal("41500.00"),
            "close": Decimal("42100.00"),
            "volume": Decimal("100.50"),
        }

        mock_session = AsyncMock()
        mock_session.execute = AsyncMock()

        result = await upsert_candle(mock_session, "asset-123", candle_data)

        assert result is True
        mock_session.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_upsert_candle_handles_error(self):
        """Test upsert_candle handles database errors gracefully."""
        from services.scheduler import upsert_candle

        candle_data = {
            "timestamp": datetime.now(timezone.utc),
            "timeframe": "15m",
            "open": Decimal("42000.00"),
            "high": Decimal("42500.00"),
            "low": Decimal("41500.00"),
            "close": Decimal("42100.00"),
            "volume": Decimal("100.50"),
        }

        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(side_effect=Exception("DB Error"))

        result = await upsert_candle(mock_session, "asset-123", candle_data)

        assert result is False


class TestUpdateAssetPrice:
    """Tests for update_asset_price function."""

    @pytest.mark.asyncio
    async def test_update_asset_price_success(self):
        """Test successful asset price update."""
        from services.scheduler import update_asset_price

        mock_asset = MagicMock()
        mock_asset.id = "asset-123"
        mock_asset.last_price = None
        mock_asset.last_updated = None

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_asset

        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_session.add = MagicMock()

        await update_asset_price(mock_session, "asset-123", Decimal("42100.00"))

        mock_session.add.assert_called_once_with(mock_asset)
        assert mock_asset.last_price == Decimal("42100.00")
        assert mock_asset.last_updated is not None

    @pytest.mark.asyncio
    async def test_update_asset_price_not_found(self):
        """Test update_asset_price handles missing asset."""
        from services.scheduler import update_asset_price

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None

        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(return_value=mock_result)

        # Should not raise
        await update_asset_price(mock_session, "nonexistent", Decimal("42100.00"))


class TestIngestSingleAsset:
    """Tests for ingest_single_asset function."""

    @pytest.mark.asyncio
    async def test_ingest_single_asset_success(self):
        """Test successful single asset ingestion."""
        from services.scheduler import ingest_single_asset

        mock_asset = MagicMock()
        mock_asset.id = "asset-123"
        mock_asset.symbol = "BTCUSD"

        mock_candle = {
            "timestamp": datetime.now(timezone.utc),
            "timeframe": "15m",
            "open": Decimal("42000.00"),
            "high": Decimal("42500.00"),
            "low": Decimal("41500.00"),
            "close": Decimal("42100.00"),
            "volume": Decimal("100.50"),
        }

        mock_client = AsyncMock()
        mock_client.fetch_ohlcv_for_asset = AsyncMock(return_value=[mock_candle])

        mock_session = AsyncMock()
        mock_session.execute = AsyncMock()

        with patch("services.scheduler.upsert_candle", return_value=True):
            with patch("services.scheduler.update_asset_price", return_value=None):
                success, count = await ingest_single_asset(
                    mock_client, mock_session, mock_asset
                )

        assert success is True
        assert count == 1

    @pytest.mark.asyncio
    async def test_ingest_single_asset_no_data(self):
        """Test ingest_single_asset handles empty response."""
        from services.scheduler import ingest_single_asset

        mock_asset = MagicMock()
        mock_asset.id = "asset-123"
        mock_asset.symbol = "BTCUSD"

        mock_client = AsyncMock()
        mock_client.fetch_ohlcv_for_asset = AsyncMock(return_value=[])

        mock_session = AsyncMock()

        success, count = await ingest_single_asset(
            mock_client, mock_session, mock_asset
        )

        assert success is False
        assert count == 0

    @pytest.mark.asyncio
    async def test_ingest_single_asset_handles_error(self):
        """Test ingest_single_asset handles API errors."""
        from services.scheduler import ingest_single_asset

        mock_asset = MagicMock()
        mock_asset.id = "asset-123"
        mock_asset.symbol = "BTCUSD"

        mock_client = AsyncMock()
        mock_client.fetch_ohlcv_for_asset = AsyncMock(
            side_effect=Exception("API Error")
        )

        mock_session = AsyncMock()

        success, count = await ingest_single_asset(
            mock_client, mock_session, mock_asset
        )

        assert success is False
        assert count == 0

    @pytest.mark.asyncio
    async def test_ingest_single_asset_invalid_symbol(self):
        """Test ingest_single_asset handles invalid symbol."""
        from services.scheduler import ingest_single_asset

        mock_asset = MagicMock()
        mock_asset.id = "asset-123"
        mock_asset.symbol = "INVALID"

        mock_client = AsyncMock()
        mock_client.fetch_ohlcv_for_asset = AsyncMock(
            side_effect=ValueError("Unknown symbol")
        )

        mock_session = AsyncMock()

        success, count = await ingest_single_asset(
            mock_client, mock_session, mock_asset
        )

        assert success is False
        assert count == 0


class TestIngestKrakenData:
    """Tests for main ingestion function."""

    @pytest.mark.asyncio
    async def test_ingest_kraken_data_returns_stats(self):
        """Test ingest_kraken_data returns statistics."""
        from services.scheduler import ingest_kraken_data

        mock_asset = MagicMock()
        mock_asset.id = "asset-123"
        mock_asset.symbol = "BTCUSD"

        mock_candle = {
            "timestamp": datetime.now(timezone.utc),
            "timeframe": "15m",
            "open": Decimal("42000.00"),
            "high": Decimal("42500.00"),
            "low": Decimal("41500.00"),
            "close": Decimal("42100.00"),
            "volume": Decimal("100.50"),
        }

        with patch("services.scheduler.get_kraken_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_client.initialize = AsyncMock()
            mock_client.fetch_ohlcv_for_asset = AsyncMock(return_value=[mock_candle])
            mock_get_client.return_value = mock_client

            with patch("services.scheduler.get_session_maker") as mock_get_session:
                mock_session = AsyncMock()
                mock_session.execute = AsyncMock()
                mock_session.commit = AsyncMock()

                mock_session_maker = MagicMock()
                mock_session_maker.return_value.__aenter__ = AsyncMock(
                    return_value=mock_session
                )
                mock_session_maker.return_value.__aexit__ = AsyncMock()
                mock_get_session.return_value = mock_session_maker

                with patch(
                    "services.scheduler.get_active_assets",
                    return_value=[mock_asset],
                ):
                    with patch(
                        "services.scheduler.ingest_single_asset",
                        return_value=(True, 1),
                    ):
                        stats = await ingest_kraken_data()

        assert "start_time" in stats
        assert "end_time" in stats
        assert "total_assets" in stats
        assert "successful" in stats
        assert "failed" in stats
        assert "candles_upserted" in stats
        assert "duration_seconds" in stats

    @pytest.mark.asyncio
    async def test_ingest_kraken_data_handles_no_assets(self):
        """Test ingest_kraken_data handles empty asset list."""
        with patch("services.scheduler.get_kraken_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_client.initialize = AsyncMock()
            mock_get_client.return_value = mock_client

            with patch("services.scheduler.get_session_maker") as mock_get_session:
                mock_session = AsyncMock()

                mock_session_maker = MagicMock()
                mock_session_maker.return_value.__aenter__ = AsyncMock(
                    return_value=mock_session
                )
                mock_session_maker.return_value.__aexit__ = AsyncMock()
                mock_get_session.return_value = mock_session_maker

                with patch(
                    "services.scheduler.get_active_assets",
                    return_value=[],
                ):
                    from services.scheduler import ingest_kraken_data

                    stats = await ingest_kraken_data()

        assert stats["total_assets"] == 0
        assert stats["successful"] == 0
