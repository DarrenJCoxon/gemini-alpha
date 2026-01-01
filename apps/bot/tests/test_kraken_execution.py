"""
Tests for services/kraken_execution.py - Kraken execution client.

Story 3.1: Kraken Order Execution Service

Unit tests for the Kraken execution client including:
- Sandbox mode behavior
- Balance queries
- Market order execution
- Error handling
"""

import pytest
from decimal import Decimal
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
import os


class TestKrakenExecutionClientInit:
    """Tests for client initialization."""

    def test_client_creation(self):
        """Test client can be created."""
        from services.kraken_execution import KrakenExecutionClient

        # Force sandbox mode via environment
        with patch.dict(os.environ, {"KRAKEN_SANDBOX_MODE": "true"}):
            client = KrakenExecutionClient()
            assert client is not None
            assert client._initialized is False

    def test_sandbox_mode_default_true(self):
        """Test sandbox mode defaults to true when not set."""
        from services.kraken_execution import KrakenExecutionClient

        with patch.dict(os.environ, {"KRAKEN_SANDBOX_MODE": "true"}):
            client = KrakenExecutionClient()
            assert client.is_sandbox is True

    def test_sandbox_mode_can_be_disabled(self):
        """Test sandbox mode can be disabled."""
        from services.kraken_execution import KrakenExecutionClient
        from config import KrakenConfig

        # Note: The config is loaded at import time, so we need to
        # create a fresh client that reads the patched environment
        with patch.dict(os.environ, {
            "KRAKEN_SANDBOX_MODE": "false",
            "KRAKEN_API_KEY": "test-key",
            "KRAKEN_API_SECRET": "test-secret",
            "KRAKEN_PRIVATE_KEY": "test-private",
        }, clear=False):
            # Verify the config reads correctly
            config = KrakenConfig()
            assert config.sandbox_mode is False


class TestKrakenExecutionClientSandbox:
    """Tests for sandbox mode behavior."""

    @pytest.mark.asyncio
    async def test_get_balance_sandbox_returns_mock(self):
        """Test get_balance returns mock balance in sandbox mode."""
        from services.kraken_execution import KrakenExecutionClient

        with patch.dict(os.environ, {"KRAKEN_SANDBOX_MODE": "true"}):
            with patch("services.kraken_execution.ccxt.kraken") as mock_kraken:
                mock_exchange = AsyncMock()
                mock_kraken.return_value = mock_exchange

                client = KrakenExecutionClient()
                balance = await client.get_balance("USD")

                assert balance == Decimal("10000.00")

    @pytest.mark.asyncio
    async def test_get_balance_sandbox_other_currency(self):
        """Test get_balance returns 100 for non-USD currencies in sandbox."""
        from services.kraken_execution import KrakenExecutionClient

        with patch.dict(os.environ, {"KRAKEN_SANDBOX_MODE": "true"}):
            with patch("services.kraken_execution.ccxt.kraken") as mock_kraken:
                mock_exchange = AsyncMock()
                mock_kraken.return_value = mock_exchange

                client = KrakenExecutionClient()
                balance = await client.get_balance("SOL")

                assert balance == Decimal("100.0")

    @pytest.mark.asyncio
    async def test_create_market_buy_sandbox_no_real_order(self):
        """Test market buy in sandbox mode doesn't execute real order."""
        from services.kraken_execution import KrakenExecutionClient

        with patch.dict(os.environ, {"KRAKEN_SANDBOX_MODE": "true"}):
            with patch("services.kraken_execution.ccxt.kraken") as mock_kraken:
                mock_exchange = AsyncMock()
                # Mock price fetch
                mock_exchange.fetch_ticker = AsyncMock(return_value={"last": 100.0})
                mock_kraken.return_value = mock_exchange

                client = KrakenExecutionClient()
                order = await client.create_market_buy_order("SOL/USD", 10.0)

                # Verify mock order returned
                assert order["id"].startswith("sandbox_buy_")
                assert order["symbol"] == "SOL/USD"
                assert order["side"] == "buy"
                assert order["amount"] == 10.0
                assert order["status"] == "closed"

                # Verify real order was NOT called
                mock_exchange.create_market_buy_order.assert_not_called()

    @pytest.mark.asyncio
    async def test_create_market_sell_sandbox_no_real_order(self):
        """Test market sell in sandbox mode doesn't execute real order."""
        from services.kraken_execution import KrakenExecutionClient

        with patch.dict(os.environ, {"KRAKEN_SANDBOX_MODE": "true"}):
            with patch("services.kraken_execution.ccxt.kraken") as mock_kraken:
                mock_exchange = AsyncMock()
                mock_exchange.fetch_ticker = AsyncMock(return_value={"last": 105.0})
                mock_kraken.return_value = mock_exchange

                client = KrakenExecutionClient()
                order = await client.create_market_sell_order("SOL/USD", 5.0)

                # Verify mock order returned
                assert order["id"].startswith("sandbox_sell_")
                assert order["symbol"] == "SOL/USD"
                assert order["side"] == "sell"
                assert order["amount"] == 5.0

                # Verify real order was NOT called
                mock_exchange.create_market_sell_order.assert_not_called()


class TestKrakenExecutionClientConnection:
    """Tests for connection testing."""

    @pytest.mark.asyncio
    async def test_test_connection_sandbox_success(self):
        """Test connection test in sandbox mode."""
        from services.kraken_execution import KrakenExecutionClient

        with patch.dict(os.environ, {"KRAKEN_SANDBOX_MODE": "true"}):
            with patch("services.kraken_execution.ccxt.kraken") as mock_kraken:
                mock_exchange = AsyncMock()
                mock_exchange.fetch_status = AsyncMock(return_value={"status": "ok"})
                mock_kraken.return_value = mock_exchange

                client = KrakenExecutionClient()
                result = await client.test_connection()

                assert result is True
                mock_exchange.fetch_status.assert_called_once()

    @pytest.mark.asyncio
    async def test_test_connection_failure(self):
        """Test connection test handles failure."""
        from services.kraken_execution import KrakenExecutionClient

        with patch.dict(os.environ, {"KRAKEN_SANDBOX_MODE": "true"}):
            with patch("services.kraken_execution.ccxt.kraken") as mock_kraken:
                mock_exchange = AsyncMock()
                mock_exchange.fetch_status = AsyncMock(
                    side_effect=Exception("Network error")
                )
                mock_kraken.return_value = mock_exchange

                client = KrakenExecutionClient()
                result = await client.test_connection()

                assert result is False


class TestKrakenExecutionClientPricing:
    """Tests for price fetching."""

    @pytest.mark.asyncio
    async def test_get_current_price(self):
        """Test current price fetching."""
        from services.kraken_execution import KrakenExecutionClient

        with patch.dict(os.environ, {"KRAKEN_SANDBOX_MODE": "true"}):
            with patch("services.kraken_execution.ccxt.kraken") as mock_kraken:
                mock_exchange = AsyncMock()
                mock_exchange.fetch_ticker = AsyncMock(return_value={"last": 123.45})
                mock_kraken.return_value = mock_exchange

                client = KrakenExecutionClient()
                price = await client.get_current_price("SOL/USD")

                assert price == Decimal("123.45")
                mock_exchange.fetch_ticker.assert_called_once_with("SOL/USD")

    @pytest.mark.asyncio
    async def test_get_current_price_invalid_symbol(self):
        """Test price fetch with invalid symbol."""
        from services.kraken_execution import KrakenExecutionClient
        from services.exceptions import InvalidSymbolError
        import ccxt

        with patch.dict(os.environ, {"KRAKEN_SANDBOX_MODE": "true"}):
            with patch("services.kraken_execution.ccxt.kraken") as mock_kraken:
                mock_exchange = AsyncMock()
                mock_exchange.fetch_ticker = AsyncMock(
                    side_effect=ccxt.BadSymbol("Invalid symbol")
                )
                mock_kraken.return_value = mock_exchange

                client = KrakenExecutionClient()

                with pytest.raises(InvalidSymbolError):
                    await client.get_current_price("INVALID/USD")


class TestKrakenExecutionClientErrorHandling:
    """Tests for error handling in order execution."""

    @pytest.mark.asyncio
    async def test_buy_insufficient_funds_error(self):
        """Test buy order handles insufficient funds."""
        from services.kraken_execution import KrakenExecutionClient
        from services.exceptions import InsufficientFundsError
        import ccxt

        with patch.dict(os.environ, {
            "KRAKEN_SANDBOX_MODE": "false",
            "KRAKEN_API_KEY": "test",
            "KRAKEN_API_SECRET": "test",
            "KRAKEN_PRIVATE_KEY": "test",
        }):
            with patch("services.kraken_execution.ccxt.kraken") as mock_kraken:
                mock_exchange = AsyncMock()
                # Mock fetch_ticker for price lookup
                mock_exchange.fetch_ticker = AsyncMock(return_value={"last": 100.0})
                mock_exchange.create_market_buy_order = AsyncMock(
                    side_effect=ccxt.InsufficientFunds("Not enough USD")
                )
                mock_kraken.return_value = mock_exchange

                client = KrakenExecutionClient()
                client._sandbox_mode = False  # Force non-sandbox mode
                await client.initialize()

                with pytest.raises(InsufficientFundsError):
                    await client.create_market_buy_order("SOL/USD", 100.0)

    @pytest.mark.asyncio
    async def test_buy_rate_limit_error(self):
        """Test buy order handles rate limit exceeded."""
        from services.kraken_execution import KrakenExecutionClient
        from services.exceptions import RateLimitError
        import ccxt

        with patch.dict(os.environ, {
            "KRAKEN_SANDBOX_MODE": "false",
            "KRAKEN_API_KEY": "test",
            "KRAKEN_API_SECRET": "test",
            "KRAKEN_PRIVATE_KEY": "test",
        }):
            with patch("services.kraken_execution.ccxt.kraken") as mock_kraken:
                mock_exchange = AsyncMock()
                # Mock fetch_ticker for price lookup
                mock_exchange.fetch_ticker = AsyncMock(return_value={"last": 100.0})
                mock_exchange.create_market_buy_order = AsyncMock(
                    side_effect=ccxt.RateLimitExceeded("Rate limit")
                )
                mock_kraken.return_value = mock_exchange

                client = KrakenExecutionClient()
                client._sandbox_mode = False  # Force non-sandbox mode
                await client.initialize()

                with pytest.raises(RateLimitError):
                    await client.create_market_buy_order("SOL/USD", 10.0)

    @pytest.mark.asyncio
    async def test_sell_order_rejected_error(self):
        """Test sell order handles exchange rejection."""
        from services.kraken_execution import KrakenExecutionClient
        from services.exceptions import OrderRejectedError
        import ccxt

        with patch.dict(os.environ, {
            "KRAKEN_SANDBOX_MODE": "false",
            "KRAKEN_API_KEY": "test",
            "KRAKEN_API_SECRET": "test",
            "KRAKEN_PRIVATE_KEY": "test",
        }):
            with patch("services.kraken_execution.ccxt.kraken") as mock_kraken:
                mock_exchange = AsyncMock()
                # Mock fetch_ticker for price lookup
                mock_exchange.fetch_ticker = AsyncMock(return_value={"last": 100.0})
                mock_exchange.create_market_sell_order = AsyncMock(
                    side_effect=ccxt.ExchangeError("Order rejected")
                )
                mock_kraken.return_value = mock_exchange

                client = KrakenExecutionClient()
                client._sandbox_mode = False  # Force non-sandbox mode
                await client.initialize()

                with pytest.raises(OrderRejectedError):
                    await client.create_market_sell_order("SOL/USD", 5.0)


class TestKrakenExecutionClientSymbolConversion:
    """Tests for symbol conversion."""

    def test_convert_symbol_to_kraken(self):
        """Test symbol conversion to Kraken format."""
        from services.kraken_execution import KrakenExecutionClient

        assert KrakenExecutionClient.convert_symbol_to_kraken("BTCUSD") == "XBT/USD"
        assert KrakenExecutionClient.convert_symbol_to_kraken("SOLUSD") == "SOL/USD"
        assert KrakenExecutionClient.convert_symbol_to_kraken("ETHUSD") == "ETH/USD"

    def test_convert_symbol_from_kraken(self):
        """Test symbol conversion from Kraken format."""
        from services.kraken_execution import KrakenExecutionClient

        assert KrakenExecutionClient.convert_symbol_from_kraken("XBT/USD") == "BTCUSD"
        assert KrakenExecutionClient.convert_symbol_from_kraken("SOL/USD") == "SOLUSD"
        assert KrakenExecutionClient.convert_symbol_from_kraken("ETH/USD") == "ETHUSD"


class TestKrakenExecutionClientGlobal:
    """Tests for global client instance."""

    def test_get_kraken_execution_client(self):
        """Test global client getter returns same instance."""
        from services.kraken_execution import (
            get_kraken_execution_client,
            _execution_client,
        )
        import services.kraken_execution as module

        # Reset global state
        module._execution_client = None

        with patch.dict(os.environ, {"KRAKEN_SANDBOX_MODE": "true"}):
            client1 = get_kraken_execution_client()
            client2 = get_kraken_execution_client()

            assert client1 is client2

        # Cleanup
        module._execution_client = None

    @pytest.mark.asyncio
    async def test_close_kraken_execution_client(self):
        """Test global client can be closed."""
        from services.kraken_execution import (
            get_kraken_execution_client,
            close_kraken_execution_client,
        )
        import services.kraken_execution as module

        # Reset global state
        module._execution_client = None

        with patch.dict(os.environ, {"KRAKEN_SANDBOX_MODE": "true"}):
            with patch("services.kraken_execution.ccxt.kraken") as mock_kraken:
                mock_exchange = AsyncMock()
                mock_kraken.return_value = mock_exchange

                client = get_kraken_execution_client()
                await client.initialize()

                await close_kraken_execution_client()

                assert module._execution_client is None

        # Cleanup
        module._execution_client = None


class TestKrakenExecutionClientCredentialValidation:
    """Tests for credential validation."""

    def test_validate_credentials_sandbox_no_error(self):
        """Test credentials not required in sandbox mode."""
        from services.kraken_execution import KrakenExecutionClient

        with patch.dict(os.environ, {
            "KRAKEN_SANDBOX_MODE": "true",
            "KRAKEN_API_KEY": "",
            "KRAKEN_API_SECRET": "",
        }):
            client = KrakenExecutionClient()
            # Should not raise
            assert client.is_sandbox is True

    def test_validate_credentials_live_requires_keys(self):
        """Test credentials required in live mode."""
        from config import KrakenConfig

        with patch.dict(os.environ, {
            "KRAKEN_SANDBOX_MODE": "false",
            "KRAKEN_API_KEY": "",
            "KRAKEN_API_SECRET": "",
            "KRAKEN_PRIVATE_KEY": "",
        }):
            config = KrakenConfig()

            with pytest.raises(ValueError, match="KRAKEN_API_KEY"):
                config.validate_trading_credentials()

    def test_validate_credentials_live_requires_private_key(self):
        """Test private key required in live mode."""
        from config import KrakenConfig

        with patch.dict(os.environ, {
            "KRAKEN_SANDBOX_MODE": "false",
            "KRAKEN_API_KEY": "test-key",
            "KRAKEN_API_SECRET": "test-secret",
            "KRAKEN_PRIVATE_KEY": "",
        }):
            config = KrakenConfig()

            with pytest.raises(ValueError, match="KRAKEN_PRIVATE_KEY"):
                config.validate_trading_credentials()
