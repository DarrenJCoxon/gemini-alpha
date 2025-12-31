"""
Tests for main FastAPI application.

Story 1.3: Added tests for Kraken ingestion endpoints.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch


class TestRootEndpoint:
    """Tests for root endpoint."""

    @pytest.mark.asyncio
    async def test_root_returns_status(self):
        """Test root endpoint returns correct status."""
        from main import root

        result = await root()

        assert result["status"] == "ok"
        assert result["service"] == "contrarian-ai-bot"


class TestHealthEndpoint:
    """Tests for health check endpoint."""

    @pytest.mark.asyncio
    async def test_health_returns_healthy(self):
        """Test health check returns healthy status."""
        with patch("main.get_scheduler") as mock_get_scheduler:
            mock_scheduler = MagicMock()
            mock_scheduler.running = True
            mock_scheduler.get_jobs.return_value = [MagicMock(), MagicMock()]
            mock_get_scheduler.return_value = mock_scheduler

            from main import health_check

            result = await health_check()

            assert result["status"] == "healthy"
            assert result["scheduler_running"] is True
            assert result["scheduled_jobs"] == 2


class TestKrakenIngestionEndpoint:
    """Tests for manual Kraken ingestion endpoint."""

    @pytest.mark.asyncio
    async def test_trigger_ingestion_success(self):
        """Test manual ingestion returns stats on success."""
        mock_stats = {
            "start_time": "2024-01-01T00:00:00+00:00",
            "total_assets": 30,
            "successful": 30,
            "failed": 0,
            "candles_upserted": 30,
        }

        with patch("main.ingest_kraken_data", new_callable=AsyncMock) as mock_ingest:
            mock_ingest.return_value = mock_stats

            from main import trigger_kraken_ingestion

            result = await trigger_kraken_ingestion()

            assert result["status"] == "completed"
            assert result["stats"] == mock_stats

    @pytest.mark.asyncio
    async def test_trigger_ingestion_failure(self):
        """Test manual ingestion raises HTTPException on failure."""
        from fastapi import HTTPException

        with patch("main.ingest_kraken_data", new_callable=AsyncMock) as mock_ingest:
            mock_ingest.side_effect = Exception("API Error")

            from main import trigger_kraken_ingestion

            with pytest.raises(HTTPException) as exc_info:
                await trigger_kraken_ingestion()

            assert exc_info.value.status_code == 500
            assert "Ingestion failed" in str(exc_info.value.detail)


class TestIngestionStatusEndpoint:
    """Tests for ingestion status endpoint."""

    @pytest.mark.asyncio
    async def test_get_status_returns_jobs(self):
        """Test status endpoint returns job information."""
        from datetime import datetime, timezone

        mock_job = MagicMock()
        mock_job.id = "kraken_ingest"
        mock_job.name = "Kraken OHLCV Ingestion"
        mock_job.next_run_time = datetime(2024, 1, 1, 0, 15, tzinfo=timezone.utc)

        with patch("main.get_scheduler") as mock_get_scheduler:
            mock_scheduler = MagicMock()
            mock_scheduler.running = True
            mock_scheduler.get_jobs.return_value = [mock_job]
            mock_get_scheduler.return_value = mock_scheduler

            from main import get_ingestion_status

            result = await get_ingestion_status()

            assert result["scheduler_running"] is True
            assert len(result["jobs"]) == 1
            assert result["jobs"][0]["id"] == "kraken_ingest"
            assert result["jobs"][0]["name"] == "Kraken OHLCV Ingestion"


class TestKrakenConnectionEndpoint:
    """Tests for Kraken connection test endpoint."""

    @pytest.mark.asyncio
    async def test_connection_success(self):
        """Test connection endpoint returns connected on success."""
        with patch("main.get_kraken_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_client.test_connection = AsyncMock(return_value=True)
            mock_get_client.return_value = mock_client

            from main import test_kraken_connection

            result = await test_kraken_connection()

            assert result["status"] == "connected"
            assert result["exchange"] == "kraken"

    @pytest.mark.asyncio
    async def test_connection_failure(self):
        """Test connection endpoint returns disconnected on failure."""
        with patch("main.get_kraken_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_client.test_connection = AsyncMock(return_value=False)
            mock_get_client.return_value = mock_client

            from main import test_kraken_connection

            result = await test_kraken_connection()

            assert result["status"] == "disconnected"

    @pytest.mark.asyncio
    async def test_connection_error(self):
        """Test connection endpoint raises HTTPException on error."""
        from fastapi import HTTPException

        with patch("main.get_kraken_client") as mock_get_client:
            mock_client = MagicMock()
            mock_client.test_connection = AsyncMock(
                side_effect=Exception("Connection error")
            )
            mock_get_client.return_value = mock_client

            from main import test_kraken_connection

            with pytest.raises(HTTPException) as exc_info:
                await test_kraken_connection()

            assert exc_info.value.status_code == 503
