"""
Tests for services/kraken.py - Kraken API client.

Story 1.3: Kraken Data Ingestor - Unit tests for symbol conversion,
retry logic, and circuit breaker pattern.
"""

import pytest
from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import ccxt


class TestSymbolConversion:
    """Tests for symbol conversion functions."""

    def test_convert_symbol_btc_to_xbt(self):
        """Test BTC is converted to XBT for Kraken."""
        from services.kraken import KrakenClient

        result = KrakenClient.convert_symbol_to_kraken("BTCUSD")
        assert result == "XBT/USD"

    def test_convert_symbol_standard_pairs(self):
        """Test standard trading pairs are converted correctly."""
        from services.kraken import KrakenClient

        test_cases = [
            ("ETHUSD", "ETH/USD"),
            ("SOLUSD", "SOL/USD"),
            ("ADAUSD", "ADA/USD"),
            ("DOTUSD", "DOT/USD"),
            ("AVAXUSD", "AVAX/USD"),
            ("LINKUSD", "LINK/USD"),
        ]

        for db_symbol, expected in test_cases:
            result = KrakenClient.convert_symbol_to_kraken(db_symbol)
            assert result == expected, f"Failed for {db_symbol}"

    def test_convert_symbol_from_kraken(self):
        """Test conversion from Kraken format back to database format."""
        from services.kraken import KrakenClient

        test_cases = [
            ("XBT/USD", "BTCUSD"),
            ("ETH/USD", "ETHUSD"),
            ("SOL/USD", "SOLUSD"),
        ]

        for kraken_symbol, expected in test_cases:
            result = KrakenClient.convert_symbol_from_kraken(kraken_symbol)
            assert result == expected, f"Failed for {kraken_symbol}"

    def test_convert_symbol_unknown_raises_error(self):
        """Test unknown symbol format raises ValueError."""
        from services.kraken import KrakenClient

        with pytest.raises(ValueError, match="Unknown symbol format"):
            KrakenClient.convert_symbol_to_kraken("INVALID")

    def test_convert_symbol_from_kraken_invalid_raises_error(self):
        """Test invalid Kraken format raises ValueError."""
        from services.kraken import KrakenClient

        with pytest.raises(ValueError, match="Invalid Kraken symbol format"):
            KrakenClient.convert_symbol_from_kraken("INVALID_FORMAT")


class TestCircuitBreaker:
    """Tests for CircuitBreaker class."""

    def test_circuit_breaker_initial_state(self):
        """Test circuit breaker starts in closed state."""
        from services.kraken import CircuitBreaker

        cb = CircuitBreaker(failure_threshold=5, cooldown_seconds=300)
        assert cb.is_open is False
        assert cb.consecutive_failures == 0
        assert cb.can_proceed() is True

    def test_circuit_breaker_opens_after_threshold(self):
        """Test circuit breaker opens after reaching failure threshold."""
        from services.kraken import CircuitBreaker

        cb = CircuitBreaker(failure_threshold=3, cooldown_seconds=300)

        # Record failures up to threshold
        cb.record_failure()
        assert cb.is_open is False

        cb.record_failure()
        assert cb.is_open is False

        cb.record_failure()  # This should open the circuit
        assert cb.is_open is True
        assert cb.can_proceed() is False

    def test_circuit_breaker_success_resets_failures(self):
        """Test successful call resets failure count."""
        from services.kraken import CircuitBreaker

        cb = CircuitBreaker(failure_threshold=5)

        cb.record_failure()
        cb.record_failure()
        assert cb.consecutive_failures == 2

        cb.record_success()
        assert cb.consecutive_failures == 0
        assert cb.is_open is False

    def test_circuit_breaker_recovers_after_cooldown(self):
        """Test circuit breaker recovers after cooldown period."""
        from services.kraken import CircuitBreaker

        # Use a very short cooldown for testing
        cb = CircuitBreaker(failure_threshold=1, cooldown_seconds=0)

        cb.record_failure()  # Opens the circuit
        assert cb.is_open is True

        # With 0 cooldown, should immediately allow proceed
        assert cb.can_proceed() is True
        assert cb.is_open is False


class TestKrakenClient:
    """Tests for KrakenClient class."""

    @pytest.mark.asyncio
    async def test_initialize_creates_exchange(self):
        """Test initialize creates ccxt exchange instance."""
        from services.kraken import KrakenClient

        with patch("services.kraken.ccxt.kraken") as mock_kraken:
            mock_exchange = MagicMock()
            mock_kraken.return_value = mock_exchange

            client = KrakenClient()
            await client.initialize()

            assert client._initialized is True
            mock_kraken.assert_called_once()

    @pytest.mark.asyncio
    async def test_test_connection_success(self):
        """Test successful connection check."""
        from services.kraken import KrakenClient

        with patch("services.kraken.ccxt.kraken") as mock_kraken:
            mock_exchange = AsyncMock()
            mock_exchange.fetch_status = AsyncMock(return_value={"status": "ok"})
            mock_kraken.return_value = mock_exchange

            client = KrakenClient()
            result = await client.test_connection()

            assert result is True
            mock_exchange.fetch_status.assert_called_once()

    @pytest.mark.asyncio
    async def test_test_connection_failure(self):
        """Test failed connection check."""
        from services.kraken import KrakenClient

        with patch("services.kraken.ccxt.kraken") as mock_kraken:
            mock_exchange = AsyncMock()
            mock_exchange.fetch_status = AsyncMock(
                side_effect=Exception("Connection failed")
            )
            mock_kraken.return_value = mock_exchange

            client = KrakenClient()
            result = await client.test_connection()

            assert result is False

    @pytest.mark.asyncio
    async def test_fetch_ohlcv_returns_correct_format(self):
        """Test fetch_ohlcv returns correctly formatted data."""
        from services.kraken import KrakenClient

        # Mock OHLCV data from ccxt
        mock_ohlcv = [
            [1704067200000, 42000.0, 42500.0, 41500.0, 42100.0, 100.5],
        ]

        with patch("services.kraken.ccxt.kraken") as mock_kraken:
            mock_exchange = AsyncMock()
            mock_exchange.fetch_ohlcv = AsyncMock(return_value=mock_ohlcv)
            mock_kraken.return_value = mock_exchange

            client = KrakenClient()
            client.circuit_breaker.can_proceed = MagicMock(return_value=True)

            result = await client.fetch_ohlcv("XBT/USD", timeframe="15m", limit=1)

            assert len(result) == 1
            candle = result[0]
            assert "timestamp" in candle
            assert "open" in candle
            assert "high" in candle
            assert "low" in candle
            assert "close" in candle
            assert "volume" in candle
            assert "timeframe" in candle

            assert isinstance(candle["timestamp"], datetime)
            assert isinstance(candle["open"], Decimal)
            assert candle["open"] == Decimal("42000.0")
            assert candle["timeframe"] == "15m"

    @pytest.mark.asyncio
    async def test_fetch_ohlcv_circuit_breaker_blocks(self):
        """Test fetch_ohlcv respects circuit breaker."""
        from services.kraken import KrakenClient

        with patch("services.kraken.ccxt.kraken") as mock_kraken:
            mock_exchange = AsyncMock()
            mock_kraken.return_value = mock_exchange

            client = KrakenClient()
            await client.initialize()
            client.circuit_breaker.is_open = True
            client.circuit_breaker.last_failure_time = datetime.now(timezone.utc)
            client.circuit_breaker.cooldown_seconds = 300  # Long cooldown

            with pytest.raises(RuntimeError, match="Circuit breaker is open"):
                await client.fetch_ohlcv("XBT/USD")

    @pytest.mark.asyncio
    async def test_fetch_ohlcv_for_asset_converts_symbol(self):
        """Test fetch_ohlcv_for_asset converts database symbol."""
        from services.kraken import KrakenClient

        mock_ohlcv = [
            [1704067200000, 42000.0, 42500.0, 41500.0, 42100.0, 100.5],
        ]

        with patch("services.kraken.ccxt.kraken") as mock_kraken:
            mock_exchange = AsyncMock()
            mock_exchange.fetch_ohlcv = AsyncMock(return_value=mock_ohlcv)
            mock_kraken.return_value = mock_exchange

            client = KrakenClient()
            client.circuit_breaker.can_proceed = MagicMock(return_value=True)

            # Use database format (BTCUSD)
            result = await client.fetch_ohlcv_for_asset("BTCUSD")

            # Verify it was converted to Kraken format (XBT/USD)
            mock_exchange.fetch_ohlcv.assert_called_once_with(
                "XBT/USD", timeframe="15m", limit=1
            )

    @pytest.mark.asyncio
    async def test_close_cleans_up(self):
        """Test close method cleans up resources."""
        from services.kraken import KrakenClient

        with patch("services.kraken.ccxt.kraken") as mock_kraken:
            mock_exchange = AsyncMock()
            mock_exchange.close = AsyncMock()
            mock_kraken.return_value = mock_exchange

            client = KrakenClient()
            await client.initialize()
            assert client._initialized is True

            await client.close()
            assert client._initialized is False
            mock_exchange.close.assert_called_once()


class TestRetryLogic:
    """Tests for retry decorator and error handling."""

    @pytest.mark.asyncio
    async def test_retry_on_network_error(self):
        """Test that network errors trigger retry."""
        from services.kraken import KrakenClient

        call_count = 0

        async def mock_fetch(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ccxt.NetworkError("Network error")
            return [[1704067200000, 42000.0, 42500.0, 41500.0, 42100.0, 100.5]]

        with patch("services.kraken.ccxt.kraken") as mock_kraken:
            mock_exchange = AsyncMock()
            mock_exchange.fetch_ohlcv = mock_fetch
            mock_kraken.return_value = mock_exchange

            client = KrakenClient()
            client.circuit_breaker.can_proceed = MagicMock(return_value=True)

            result = await client.fetch_ohlcv("XBT/USD")

            # Should have retried and eventually succeeded
            assert call_count == 3
            assert len(result) == 1

    @pytest.mark.asyncio
    async def test_bad_symbol_does_not_retry(self):
        """Test that BadSymbol errors are not retried."""
        from services.kraken import KrakenClient

        call_count = 0

        async def mock_fetch(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            raise ccxt.BadSymbol("Invalid symbol")

        with patch("services.kraken.ccxt.kraken") as mock_kraken:
            mock_exchange = AsyncMock()
            mock_exchange.fetch_ohlcv = mock_fetch
            mock_kraken.return_value = mock_exchange

            client = KrakenClient()
            client.circuit_breaker.can_proceed = MagicMock(return_value=True)

            with pytest.raises(ccxt.BadSymbol):
                await client.fetch_ohlcv("INVALID/USD")

            # Should only be called once (no retry)
            assert call_count == 1


class TestSymbolMap:
    """Tests for SYMBOL_MAP coverage."""

    def test_symbol_map_contains_expected_assets(self):
        """Test SYMBOL_MAP contains all expected trading pairs."""
        from services.kraken import SYMBOL_MAP

        # Core assets that must be present
        expected_symbols = [
            "BTCUSD",
            "ETHUSD",
            "SOLUSD",
            "ADAUSD",
            "DOTUSD",
            "AVAXUSD",
            "MATICUSD",
            "LINKUSD",
        ]

        for symbol in expected_symbols:
            assert symbol in SYMBOL_MAP, f"Missing {symbol} in SYMBOL_MAP"

    def test_symbol_map_has_thirty_assets(self):
        """Test SYMBOL_MAP contains 30 assets as per requirements."""
        from services.kraken import SYMBOL_MAP

        assert len(SYMBOL_MAP) == 30, f"Expected 30 symbols, got {len(SYMBOL_MAP)}"

    def test_symbol_map_all_usd_pairs(self):
        """Test all symbols in SYMBOL_MAP are USD pairs."""
        from services.kraken import SYMBOL_MAP

        for db_symbol, kraken_symbol in SYMBOL_MAP.items():
            assert db_symbol.endswith("USD"), f"{db_symbol} is not a USD pair"
            assert kraken_symbol.endswith("/USD"), f"{kraken_symbol} is not a /USD pair"
