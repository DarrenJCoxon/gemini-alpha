"""
Tests for services/execution.py - Execution service.

Story 3.1: Kraken Order Execution Service

Unit tests for the execution service including:
- execute_buy() functionality
- execute_sell() functionality
- has_open_position() duplicate prevention
- Trade record creation and updates
"""

import pytest
from decimal import Decimal
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
import uuid
import os


class TestHasOpenPosition:
    """Tests for has_open_position function."""

    @pytest.mark.asyncio
    async def test_has_open_position_returns_true_when_exists(self):
        """Test returns True when open position exists."""
        from services.execution import has_open_position
        from models import Trade, TradeStatus

        mock_trade = Trade(
            id=str(uuid.uuid4()),
            asset_id="test-asset-id",
            status=TradeStatus.OPEN,
            entry_price=Decimal("100.0"),
            size=Decimal("10.0"),
            entry_time=datetime.now(timezone.utc),
            stop_loss_price=Decimal("95.0"),
        )

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_trade

        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(return_value=mock_result)

        result = await has_open_position("test-asset-id", session=mock_session)

        assert result is True

    @pytest.mark.asyncio
    async def test_has_open_position_returns_false_when_none(self):
        """Test returns False when no open position exists."""
        from services.execution import has_open_position

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None

        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(return_value=mock_result)

        result = await has_open_position("test-asset-id", session=mock_session)

        assert result is False


class TestGetOpenPosition:
    """Tests for get_open_position function."""

    @pytest.mark.asyncio
    async def test_get_open_position_returns_trade(self):
        """Test returns Trade object when exists."""
        from services.execution import get_open_position
        from models import Trade, TradeStatus

        mock_trade = Trade(
            id=str(uuid.uuid4()),
            asset_id="test-asset-id",
            status=TradeStatus.OPEN,
            entry_price=Decimal("100.0"),
            size=Decimal("10.0"),
            entry_time=datetime.now(timezone.utc),
            stop_loss_price=Decimal("95.0"),
        )

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_trade

        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(return_value=mock_result)

        result = await get_open_position("test-asset-id", session=mock_session)

        assert result is not None
        assert result.id == mock_trade.id
        assert result.status == TradeStatus.OPEN

    @pytest.mark.asyncio
    async def test_get_open_position_returns_none(self):
        """Test returns None when no position exists."""
        from services.execution import get_open_position

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None

        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(return_value=mock_result)

        result = await get_open_position("test-asset-id", session=mock_session)

        assert result is None


class TestExecuteBuy:
    """Tests for execute_buy function."""

    @pytest.mark.asyncio
    async def test_execute_buy_prevents_duplicate_position(self):
        """Test execute_buy prevents opening duplicate position."""
        from services.execution import execute_buy
        from services.exceptions import DuplicatePositionError
        from models import Trade, TradeStatus, Asset

        # Create mock asset
        mock_asset = Asset(
            id="test-asset-id",
            symbol="SOLUSD",
            is_active=True,
        )

        # Create existing open trade
        mock_trade = Trade(
            id=str(uuid.uuid4()),
            asset_id="test-asset-id",
            status=TradeStatus.OPEN,
            entry_price=Decimal("100.0"),
            size=Decimal("10.0"),
            entry_time=datetime.now(timezone.utc),
            stop_loss_price=Decimal("95.0"),
        )

        # Mock session to return asset and existing trade
        mock_result_asset = MagicMock()
        mock_result_asset.scalar_one_or_none.return_value = mock_asset

        mock_result_trade = MagicMock()
        mock_result_trade.scalar_one_or_none.return_value = mock_trade

        mock_session = AsyncMock()
        # First call returns asset, second returns existing trade
        mock_session.execute = AsyncMock(
            side_effect=[mock_result_asset, mock_result_trade]
        )

        # Mock client
        mock_client = MagicMock()
        mock_client.is_sandbox = True

        success, error, trade = await execute_buy(
            symbol="SOLUSD",
            amount_usd=100.0,
            client=mock_client,
            session=mock_session,
        )

        assert success is False
        assert "open position already exists" in error.lower()
        assert trade is None

    @pytest.mark.asyncio
    async def test_execute_buy_creates_trade_record(self):
        """Test execute_buy creates Trade record on success."""
        from services.execution import execute_buy
        from models import Asset

        # Mock asset
        mock_asset = Asset(
            id="test-asset-id",
            symbol="SOLUSD",
            is_active=True,
        )

        # Mock session - no existing position
        mock_result_asset = MagicMock()
        mock_result_asset.scalar_one_or_none.return_value = mock_asset

        mock_result_no_trade = MagicMock()
        mock_result_no_trade.scalar_one_or_none.return_value = None

        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(
            side_effect=[mock_result_asset, mock_result_no_trade]
        )
        mock_session.add = MagicMock()
        mock_session.commit = AsyncMock()
        mock_session.refresh = AsyncMock()

        # Mock client in sandbox mode
        mock_client = AsyncMock()
        mock_client.is_sandbox = True
        mock_client.convert_symbol_to_kraken = MagicMock(return_value="SOL/USD")
        mock_client.get_current_price = AsyncMock(return_value=Decimal("100.0"))
        mock_client.get_balance = AsyncMock(return_value=Decimal("10000.0"))
        mock_client.create_market_buy_order = AsyncMock(return_value={
            "id": "sandbox_order_123",
            "price": 100.0,
            "average": 100.0,
            "filled": 1.0,
            "amount": 1.0,
        })

        success, error, trade = await execute_buy(
            symbol="SOLUSD",
            amount_usd=100.0,
            stop_loss_price=95.0,
            client=mock_client,
            session=mock_session,
        )

        assert success is True
        assert error is None
        assert trade is not None
        # Verify session.add was called
        mock_session.add.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_buy_returns_error_for_missing_asset(self):
        """Test execute_buy returns error when asset not found."""
        from services.execution import execute_buy

        # Mock session - asset not found
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None

        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(return_value=mock_result)

        mock_client = MagicMock()
        mock_client.is_sandbox = True

        success, error, trade = await execute_buy(
            symbol="INVALID",
            amount_usd=100.0,
            client=mock_client,
            session=mock_session,
        )

        assert success is False
        assert "not found" in error.lower()
        assert trade is None


class TestExecuteSell:
    """Tests for execute_sell function."""

    @pytest.mark.asyncio
    async def test_execute_sell_success(self):
        """Test execute_sell executes successfully."""
        from services.execution import execute_sell

        # Mock client in sandbox mode
        mock_client = AsyncMock()
        mock_client.is_sandbox = True
        mock_client.convert_symbol_to_kraken = MagicMock(return_value="SOL/USD")
        mock_client.create_market_sell_order = AsyncMock(return_value={
            "id": "sandbox_sell_123",
            "price": 110.0,
            "average": 110.0,
            "filled": 10.0,
            "amount": 10.0,
        })

        mock_session = AsyncMock()
        mock_session.commit = AsyncMock()

        success, error, order = await execute_sell(
            symbol="SOLUSD",
            amount_token=10.0,
            client=mock_client,
            session=mock_session,
        )

        assert success is True
        assert error is None
        assert order is not None
        assert order["id"] == "sandbox_sell_123"

    @pytest.mark.asyncio
    async def test_execute_sell_updates_trade_record(self):
        """Test execute_sell updates Trade record when trade_id provided."""
        from services.execution import execute_sell
        from models import Trade, TradeStatus

        # Create mock trade
        mock_trade = Trade(
            id="trade-123",
            asset_id="test-asset-id",
            status=TradeStatus.OPEN,
            entry_price=Decimal("100.0"),
            size=Decimal("10.0"),
            entry_time=datetime.now(timezone.utc),
            stop_loss_price=Decimal("95.0"),
        )

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_trade

        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_session.add = MagicMock()
        mock_session.commit = AsyncMock()

        # Mock client
        mock_client = AsyncMock()
        mock_client.is_sandbox = True
        mock_client.convert_symbol_to_kraken = MagicMock(return_value="SOL/USD")
        mock_client.create_market_sell_order = AsyncMock(return_value={
            "id": "sandbox_sell_123",
            "price": 110.0,
            "average": 110.0,
            "filled": 10.0,
        })

        success, error, order = await execute_sell(
            symbol="SOLUSD",
            amount_token=10.0,
            trade_id="trade-123",
            exit_reason="take_profit",
            client=mock_client,
            session=mock_session,
        )

        assert success is True
        assert mock_trade.status == TradeStatus.CLOSED
        assert mock_trade.exit_reason == "take_profit"
        assert mock_trade.exit_price is not None


class TestClosePosition:
    """Tests for close_position function."""

    @pytest.mark.asyncio
    async def test_close_position_not_found(self):
        """Test close_position handles non-existent trade."""
        from services.execution import close_position

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None

        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(return_value=mock_result)

        success, error, order = await close_position(
            trade_id="nonexistent-trade",
            session=mock_session,
        )

        assert success is False
        assert "not found" in error.lower()


class TestGetAllOpenPositions:
    """Tests for get_all_open_positions function."""

    @pytest.mark.asyncio
    async def test_get_all_open_positions_returns_list(self):
        """Test returns list of open positions."""
        from services.execution import get_all_open_positions
        from models import Trade, TradeStatus

        mock_trades = [
            Trade(
                id=str(uuid.uuid4()),
                asset_id="asset-1",
                status=TradeStatus.OPEN,
                entry_price=Decimal("100.0"),
                size=Decimal("10.0"),
                entry_time=datetime.now(timezone.utc),
                stop_loss_price=Decimal("95.0"),
            ),
            Trade(
                id=str(uuid.uuid4()),
                asset_id="asset-2",
                status=TradeStatus.OPEN,
                entry_price=Decimal("50.0"),
                size=Decimal("20.0"),
                entry_time=datetime.now(timezone.utc),
                stop_loss_price=Decimal("45.0"),
            ),
        ]

        mock_scalars = MagicMock()
        mock_scalars.all.return_value = mock_trades

        mock_result = MagicMock()
        mock_result.scalars.return_value = mock_scalars

        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(return_value=mock_result)

        result = await get_all_open_positions(session=mock_session)

        assert len(result) == 2
        assert all(t.status == TradeStatus.OPEN for t in result)


class TestExecuteBuyIntegration:
    """Integration-style tests for execute_buy."""

    @pytest.mark.asyncio
    async def test_execute_buy_sandbox_mode_full_flow(self):
        """Test complete buy flow in sandbox mode."""
        from services.execution import execute_buy
        from models import Asset, TradeStatus

        # Mock asset
        mock_asset = Asset(
            id="test-asset-id",
            symbol="SOLUSD",
            is_active=True,
        )

        # Mock session
        mock_result_asset = MagicMock()
        mock_result_asset.scalar_one_or_none.return_value = mock_asset

        mock_result_no_trade = MagicMock()
        mock_result_no_trade.scalar_one_or_none.return_value = None

        captured_trade = None

        def capture_add(trade):
            nonlocal captured_trade
            captured_trade = trade

        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(
            side_effect=[mock_result_asset, mock_result_no_trade]
        )
        mock_session.add = MagicMock(side_effect=capture_add)
        mock_session.commit = AsyncMock()
        mock_session.refresh = AsyncMock()

        # Mock client
        mock_client = AsyncMock()
        mock_client.is_sandbox = True
        mock_client.convert_symbol_to_kraken = MagicMock(return_value="SOL/USD")
        mock_client.get_current_price = AsyncMock(return_value=Decimal("100.0"))
        mock_client.get_balance = AsyncMock(return_value=Decimal("10000.0"))
        mock_client.create_market_buy_order = AsyncMock(return_value={
            "id": "sandbox_order_123",
            "price": 100.0,
            "average": 100.0,
            "filled": 1.0,
            "amount": 1.0,
        })

        success, error, trade = await execute_buy(
            symbol="SOLUSD",
            amount_usd=100.0,
            stop_loss_price=95.0,
            client=mock_client,
            session=mock_session,
        )

        # Verify success
        assert success is True
        assert error is None

        # Verify trade was captured
        assert captured_trade is not None
        assert captured_trade.status == TradeStatus.OPEN
        assert captured_trade.asset_id == "test-asset-id"
        assert captured_trade.kraken_order_id == "sandbox_order_123"


class TestExecutionErrorHandling:
    """Tests for error handling in execution functions."""

    @pytest.mark.asyncio
    async def test_execute_buy_handles_price_fetch_error(self):
        """Test execute_buy handles price fetch failure."""
        from services.execution import execute_buy
        from models import Asset

        mock_asset = Asset(
            id="test-asset-id",
            symbol="SOLUSD",
            is_active=True,
        )

        mock_result_asset = MagicMock()
        mock_result_asset.scalar_one_or_none.return_value = mock_asset

        mock_result_no_trade = MagicMock()
        mock_result_no_trade.scalar_one_or_none.return_value = None

        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(
            side_effect=[mock_result_asset, mock_result_no_trade]
        )

        # Mock client that fails on price fetch
        mock_client = AsyncMock()
        mock_client.is_sandbox = True
        mock_client.convert_symbol_to_kraken = MagicMock(return_value="SOL/USD")
        mock_client.get_current_price = AsyncMock(
            side_effect=Exception("Network error")
        )

        success, error, trade = await execute_buy(
            symbol="SOLUSD",
            amount_usd=100.0,
            client=mock_client,
            session=mock_session,
        )

        assert success is False
        assert "price" in error.lower()
        assert trade is None

    @pytest.mark.asyncio
    async def test_execute_sell_handles_invalid_symbol(self):
        """Test execute_sell handles invalid symbol."""
        from services.execution import execute_sell

        # Mock client that fails on symbol conversion
        mock_client = MagicMock()
        mock_client.is_sandbox = True
        mock_client.convert_symbol_to_kraken = MagicMock(
            side_effect=ValueError("Unknown symbol")
        )

        mock_session = AsyncMock()

        success, error, order = await execute_sell(
            symbol="INVALID",
            amount_token=10.0,
            client=mock_client,
            session=mock_session,
        )

        assert success is False
        assert "symbol" in error.lower()
        assert order is None
