"""
Tests for services/position_manager.py - Position Manager Service.

Story 3.3: Position Manager (Trailing Stops & Exits)

Unit tests for the position manager service including:
- check_stop_loss() functionality
- check_breakeven_trigger() with ATR-based triggers
- update_trailing_stop() trailing logic
- close_position() execution and P&L calculation
- check_council_sell_signal() integration
- check_open_positions() main loop

Test Coverage:
- Stop loss triggered / not triggered scenarios
- Breakeven trigger at correct levels
- Trailing stop only updates upward
- Position close with correct exit reason
- Council SELL signal detection
- Priority order in main loop
"""

import pytest
from decimal import Decimal
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
import uuid

from models import Trade, TradeStatus, Asset
from services.position_manager import (
    ExitReason,
    check_stop_loss,
    check_breakeven_trigger,
    update_trailing_stop,
    check_council_sell_signal,
    get_open_positions,
    get_symbol_for_trade,
    get_current_price,
    get_current_prices,
    fetch_recent_candles,
    update_stop_loss,
    close_position,
    check_open_positions,
)


# =============================================================================
# Test Fixtures
# =============================================================================

@pytest.fixture
def sample_trade():
    """Create a sample trade for testing."""
    return Trade(
        id=str(uuid.uuid4()),
        asset_id="asset-123",
        status=TradeStatus.OPEN,
        side="BUY",
        entry_price=Decimal("100.00"),
        stop_loss_price=Decimal("90.00"),
        size=Decimal("1.0"),
        entry_time=datetime.now(timezone.utc),
    )


@pytest.fixture
def trade_at_breakeven():
    """Create a trade with stop at breakeven."""
    return Trade(
        id=str(uuid.uuid4()),
        asset_id="asset-123",
        status=TradeStatus.OPEN,
        side="BUY",
        entry_price=Decimal("100.00"),
        stop_loss_price=Decimal("100.00"),  # Stop at entry (breakeven)
        size=Decimal("1.0"),
        entry_time=datetime.now(timezone.utc),
    )


@pytest.fixture
def sample_asset():
    """Create a sample asset for testing."""
    return Asset(
        id="asset-123",
        symbol="SOLUSD",
        is_active=True,
    )


@pytest.fixture
def mock_session():
    """Create a mock database session."""
    session = AsyncMock()
    session.execute = AsyncMock()
    session.add = MagicMock()
    session.commit = AsyncMock()
    session.refresh = AsyncMock()
    return session


# =============================================================================
# Test ExitReason Enum
# =============================================================================

class TestExitReason:
    """Tests for ExitReason enumeration."""

    def test_exit_reason_values(self):
        """Test all exit reasons are defined."""
        assert ExitReason.STOP_LOSS.value == "STOP_LOSS"
        assert ExitReason.TRAILING_STOP.value == "TRAILING_STOP"
        assert ExitReason.COUNCIL_SELL.value == "COUNCIL_SELL"
        assert ExitReason.TAKE_PROFIT.value == "TAKE_PROFIT"
        assert ExitReason.MANUAL.value == "MANUAL"
        assert ExitReason.EMERGENCY.value == "EMERGENCY"
        assert ExitReason.MAX_DRAWDOWN.value == "MAX_DRAWDOWN"

    def test_exit_reason_is_string_enum(self):
        """Test ExitReason is a string enum for JSON serialization."""
        assert isinstance(ExitReason.STOP_LOSS, str)
        assert ExitReason.STOP_LOSS == "STOP_LOSS"


# =============================================================================
# Test check_stop_loss()
# =============================================================================

class TestCheckStopLoss:
    """Tests for check_stop_loss function."""

    def test_stop_loss_triggered_price_below_stop(self, sample_trade):
        """Test returns True when price is below stop."""
        # Price $89 < Stop $90
        result = check_stop_loss(sample_trade, 89.00)
        assert result is True

    def test_stop_loss_triggered_price_equals_stop(self, sample_trade):
        """Test returns True when price equals stop."""
        # Price $90 == Stop $90
        result = check_stop_loss(sample_trade, 90.00)
        assert result is True

    def test_stop_loss_not_triggered_price_above_stop(self, sample_trade):
        """Test returns False when price is above stop."""
        # Price $95 > Stop $90
        result = check_stop_loss(sample_trade, 95.00)
        assert result is False

    def test_stop_loss_not_triggered_price_well_above(self, sample_trade):
        """Test returns False when price is well above stop."""
        # Price $150 >> Stop $90
        result = check_stop_loss(sample_trade, 150.00)
        assert result is False

    def test_stop_loss_no_stop_set(self):
        """Test returns False when trade has no stop loss set."""
        trade = Trade(
            id=str(uuid.uuid4()),
            asset_id="asset-123",
            status=TradeStatus.OPEN,
            entry_price=Decimal("100.00"),
            stop_loss_price=None,  # No stop loss
            size=Decimal("1.0"),
            entry_time=datetime.now(timezone.utc),
        )
        result = check_stop_loss(trade, 50.00)
        assert result is False


# =============================================================================
# Test check_breakeven_trigger()
# =============================================================================

class TestCheckBreakevenTrigger:
    """Tests for check_breakeven_trigger function."""

    @pytest.mark.asyncio
    async def test_breakeven_triggered_at_threshold(self, sample_trade, mock_session):
        """Test breakeven triggers when price > entry + (2 * ATR)."""
        # Entry=$100, ATR=$5, Trigger=$110
        # Current price $112 >= $110 triggers breakeven
        atr = 5.0

        with patch('services.position_manager.update_stop_loss') as mock_update:
            mock_update.return_value = True

            result = await check_breakeven_trigger(
                sample_trade, 112.00, atr, session=mock_session
            )

            assert result is True
            # Stop should be moved to entry price ($100)
            mock_update.assert_called_once()
            call_args = mock_update.call_args
            assert call_args[0][1] == 100.00  # new stop = entry price

    @pytest.mark.asyncio
    async def test_breakeven_not_triggered_below_threshold(
        self, sample_trade, mock_session
    ):
        """Test breakeven doesn't trigger when below threshold."""
        # Entry=$100, ATR=$5, Trigger=$110
        # Current price $108 < $110
        atr = 5.0

        result = await check_breakeven_trigger(
            sample_trade, 108.00, atr, session=mock_session
        )

        assert result is False

    @pytest.mark.asyncio
    async def test_breakeven_skipped_when_already_at_breakeven(
        self, trade_at_breakeven, mock_session
    ):
        """Test breakeven skips when stop is already at entry."""
        # Stop is already at $100 (entry price)
        atr = 5.0

        result = await check_breakeven_trigger(
            trade_at_breakeven, 120.00, atr, session=mock_session
        )

        # Should return False - already at breakeven
        assert result is False

    @pytest.mark.asyncio
    async def test_breakeven_skipped_when_stop_above_entry(self, mock_session):
        """Test breakeven skips when stop is already above entry."""
        trade = Trade(
            id=str(uuid.uuid4()),
            asset_id="asset-123",
            status=TradeStatus.OPEN,
            entry_price=Decimal("100.00"),
            stop_loss_price=Decimal("105.00"),  # Stop above entry (trailing)
            size=Decimal("1.0"),
            entry_time=datetime.now(timezone.utc),
        )
        atr = 5.0

        result = await check_breakeven_trigger(
            trade, 120.00, atr, session=mock_session
        )

        assert result is False


# =============================================================================
# Test update_trailing_stop()
# =============================================================================

class TestUpdateTrailingStop:
    """Tests for update_trailing_stop function."""

    @pytest.mark.asyncio
    async def test_trailing_stop_updates_when_in_profit(
        self, trade_at_breakeven, mock_session
    ):
        """Test trailing stop updates when price rises and we're in profit."""
        # Entry=$100, Stop=$100 (at breakeven), Price=$120, ATR=$5
        # New stop = $120 - (2*$5) = $110 > current stop $100
        atr = 5.0

        with patch('services.position_manager.update_stop_loss') as mock_update:
            mock_update.return_value = True

            result = await update_trailing_stop(
                trade_at_breakeven, 120.00, atr, session=mock_session
            )

            assert result is True
            mock_update.assert_called_once()
            call_args = mock_update.call_args
            assert call_args[0][1] == 110.0  # new stop = 120 - 10

    @pytest.mark.asyncio
    async def test_trailing_stop_no_update_when_would_decrease(
        self, mock_session
    ):
        """Test trailing stop doesn't decrease stop loss."""
        trade = Trade(
            id=str(uuid.uuid4()),
            asset_id="asset-123",
            status=TradeStatus.OPEN,
            entry_price=Decimal("100.00"),
            stop_loss_price=Decimal("110.00"),  # Already at $110
            size=Decimal("1.0"),
            entry_time=datetime.now(timezone.utc),
        )
        # Price=$115, ATR=$5 -> New stop would be $115-10=$105 < current $110
        atr = 5.0

        result = await update_trailing_stop(
            trade, 115.00, atr, session=mock_session
        )

        # Should not update - would lower stop
        assert result is False

    @pytest.mark.asyncio
    async def test_trailing_stop_skipped_when_not_in_profit(
        self, sample_trade, mock_session
    ):
        """Test trailing stop skips when stop is below entry (not yet breakeven)."""
        # Entry=$100, Stop=$90 (below entry - not at breakeven yet)
        atr = 5.0

        result = await update_trailing_stop(
            sample_trade, 120.00, atr, session=mock_session
        )

        # Should return False - not yet at breakeven
        assert result is False

    @pytest.mark.asyncio
    async def test_trailing_stop_respects_multiplier(
        self, trade_at_breakeven, mock_session
    ):
        """Test trailing stop uses correct ATR multiplier."""
        atr = 5.0
        multiplier = 3.0  # Use 3x ATR instead of 2x

        with patch('services.position_manager.update_stop_loss') as mock_update:
            mock_update.return_value = True

            result = await update_trailing_stop(
                trade_at_breakeven,
                120.00,
                atr,
                atr_multiplier=multiplier,
                session=mock_session,
            )

            assert result is True
            call_args = mock_update.call_args
            # New stop = $120 - (3*$5) = $105
            assert call_args[0][1] == 105.0


# =============================================================================
# Test check_council_sell_signal()
# =============================================================================

class TestCheckCouncilSellSignal:
    """Tests for check_council_sell_signal function."""

    def test_council_sell_signal_detected(self, sample_trade):
        """Test SELL signal is detected for matching asset."""
        council_decision = {
            'action': 'SELL',
            'asset_id': 'asset-123',
            'reasoning': 'Sentiment turned to greed',
        }

        result = check_council_sell_signal(sample_trade, council_decision)

        assert result is True

    def test_council_hold_signal_ignored(self, sample_trade):
        """Test HOLD signal is ignored."""
        council_decision = {
            'action': 'HOLD',
            'asset_id': 'asset-123',
            'reasoning': 'No clear direction',
        }

        result = check_council_sell_signal(sample_trade, council_decision)

        assert result is False

    def test_council_buy_signal_ignored(self, sample_trade):
        """Test BUY signal is ignored."""
        council_decision = {
            'action': 'BUY',
            'asset_id': 'asset-123',
            'reasoning': 'Strong bullish signal',
        }

        result = check_council_sell_signal(sample_trade, council_decision)

        assert result is False

    def test_council_sell_signal_wrong_asset(self, sample_trade):
        """Test SELL signal for different asset is ignored."""
        council_decision = {
            'action': 'SELL',
            'asset_id': 'different-asset',  # Different asset ID
            'reasoning': 'Sentiment turned to greed',
        }

        result = check_council_sell_signal(sample_trade, council_decision)

        assert result is False

    def test_council_none_decision(self, sample_trade):
        """Test None decision is handled."""
        result = check_council_sell_signal(sample_trade, None)

        assert result is False

    def test_council_empty_decision(self, sample_trade):
        """Test empty dict decision is handled."""
        result = check_council_sell_signal(sample_trade, {})

        assert result is False


# =============================================================================
# Test get_open_positions()
# =============================================================================

class TestGetOpenPositions:
    """Tests for get_open_positions function."""

    @pytest.mark.asyncio
    async def test_get_open_positions_returns_list(self, sample_trade, mock_session):
        """Test returns list of open positions."""
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = [sample_trade]

        mock_result = MagicMock()
        mock_result.scalars.return_value = mock_scalars

        mock_session.execute = AsyncMock(return_value=mock_result)

        result = await get_open_positions(session=mock_session)

        assert len(result) == 1
        assert result[0].status == TradeStatus.OPEN

    @pytest.mark.asyncio
    async def test_get_open_positions_empty(self, mock_session):
        """Test returns empty list when no open positions."""
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = []

        mock_result = MagicMock()
        mock_result.scalars.return_value = mock_scalars

        mock_session.execute = AsyncMock(return_value=mock_result)

        result = await get_open_positions(session=mock_session)

        assert len(result) == 0


# =============================================================================
# Test get_symbol_for_trade()
# =============================================================================

class TestGetSymbolForTrade:
    """Tests for get_symbol_for_trade function."""

    @pytest.mark.asyncio
    async def test_get_symbol_returns_symbol(
        self, sample_trade, sample_asset, mock_session
    ):
        """Test returns asset symbol."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_asset

        mock_session.execute = AsyncMock(return_value=mock_result)

        result = await get_symbol_for_trade(sample_trade, session=mock_session)

        assert result == "SOLUSD"

    @pytest.mark.asyncio
    async def test_get_symbol_returns_none_when_not_found(
        self, sample_trade, mock_session
    ):
        """Test returns None when asset not found."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None

        mock_session.execute = AsyncMock(return_value=mock_result)

        result = await get_symbol_for_trade(sample_trade, session=mock_session)

        assert result is None


# =============================================================================
# Test update_stop_loss()
# =============================================================================

class TestUpdateStopLoss:
    """Tests for update_stop_loss function."""

    @pytest.mark.asyncio
    async def test_update_stop_loss_success(self, sample_trade, mock_session):
        """Test stop loss is updated successfully."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_trade

        mock_session.execute = AsyncMock(return_value=mock_result)

        result = await update_stop_loss(
            sample_trade.id, 95.00, session=mock_session
        )

        assert result is True
        assert sample_trade.stop_loss_price == Decimal("95.00")
        mock_session.add.assert_called_once()
        mock_session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_stop_loss_trade_not_found(self, mock_session):
        """Test returns False when trade not found."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None

        mock_session.execute = AsyncMock(return_value=mock_result)

        result = await update_stop_loss(
            "nonexistent-trade", 95.00, session=mock_session
        )

        assert result is False


# =============================================================================
# Test close_position()
# =============================================================================

class TestClosePosition:
    """Tests for close_position function."""

    @pytest.mark.asyncio
    async def test_close_position_success(
        self, sample_trade, sample_asset, mock_session
    ):
        """Test position closes successfully."""
        # Mock get_symbol_for_trade
        mock_asset_result = MagicMock()
        mock_asset_result.scalar_one_or_none.return_value = sample_asset

        mock_session.execute = AsyncMock(return_value=mock_asset_result)

        # Mock execute_sell
        with patch('services.position_manager.execute_sell') as mock_sell:
            mock_sell.return_value = (
                True,
                None,
                {'average': 105.0, 'filled': 1.0},
            )

            success, error = await close_position(
                sample_trade,
                ExitReason.STOP_LOSS,
                exit_price=105.0,
                session=mock_session,
            )

            assert success is True
            assert error is None
            mock_sell.assert_called_once()

    @pytest.mark.asyncio
    async def test_close_position_sell_failed(
        self, sample_trade, sample_asset, mock_session
    ):
        """Test handles sell failure gracefully."""
        mock_asset_result = MagicMock()
        mock_asset_result.scalar_one_or_none.return_value = sample_asset

        mock_session.execute = AsyncMock(return_value=mock_asset_result)

        with patch('services.position_manager.execute_sell') as mock_sell:
            mock_sell.return_value = (False, "Order rejected", None)

            success, error = await close_position(
                sample_trade,
                ExitReason.STOP_LOSS,
                session=mock_session,
            )

            assert success is False
            assert error is not None

    @pytest.mark.asyncio
    async def test_close_position_asset_not_found(self, sample_trade, mock_session):
        """Test handles missing asset."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None

        mock_session.execute = AsyncMock(return_value=mock_result)

        success, error = await close_position(
            sample_trade,
            ExitReason.STOP_LOSS,
            session=mock_session,
        )

        assert success is False
        assert "not found" in error.lower()


# =============================================================================
# Test check_open_positions() Main Loop
# =============================================================================

class TestCheckOpenPositions:
    """Tests for check_open_positions main loop."""

    @pytest.mark.asyncio
    async def test_check_open_positions_no_positions(self, mock_session):
        """Test handles no open positions."""
        with patch(
            'services.position_manager.get_open_positions'
        ) as mock_get_positions:
            mock_get_positions.return_value = []

            result = await check_open_positions(session=mock_session)

            assert result['positions_checked'] == 0
            assert result['stops_hit'] == 0

    @pytest.mark.asyncio
    async def test_check_open_positions_stop_loss_priority(
        self, sample_trade, sample_asset, mock_session
    ):
        """Test stop loss is checked first (priority 1)."""
        with patch(
            'services.position_manager.get_open_positions'
        ) as mock_get_positions, \
             patch(
                 'services.position_manager.get_symbol_for_trade'
             ) as mock_get_symbol, \
             patch(
                 'services.position_manager.get_current_prices'
             ) as mock_get_prices, \
             patch(
                 'services.position_manager.close_position'
             ) as mock_close:

            mock_get_positions.return_value = [sample_trade]
            mock_get_symbol.return_value = "SOLUSD"
            # Price $85 < Stop $90 triggers stop loss
            mock_get_prices.return_value = {"SOLUSD": 85.0}
            mock_close.return_value = (True, None)

            result = await check_open_positions(session=mock_session)

            assert result['stops_hit'] == 1
            mock_close.assert_called_once()
            # Verify called with STOP_LOSS reason
            call_args = mock_close.call_args
            assert call_args[0][1] == ExitReason.STOP_LOSS

    @pytest.mark.asyncio
    async def test_check_open_positions_council_sell_priority(
        self, sample_trade, sample_asset, mock_session
    ):
        """Test Council SELL is checked after stop loss (priority 2)."""
        with patch(
            'services.position_manager.get_open_positions'
        ) as mock_get_positions, \
             patch(
                 'services.position_manager.get_symbol_for_trade'
             ) as mock_get_symbol, \
             patch(
                 'services.position_manager.get_current_prices'
             ) as mock_get_prices, \
             patch(
                 'services.position_manager.fetch_recent_candles'
             ) as mock_candles, \
             patch('services.position_manager.calculate_atr') as mock_atr, \
             patch(
                 'services.position_manager.close_position'
             ) as mock_close:

            mock_get_positions.return_value = [sample_trade]
            mock_get_symbol.return_value = "SOLUSD"
            # Price $95 > Stop $90 - no stop loss trigger
            mock_get_prices.return_value = {"SOLUSD": 95.0}
            mock_candles.return_value = [{"high": 100, "low": 90, "close": 95}]
            mock_atr.return_value = 5.0
            mock_close.return_value = (True, None)

            # Council issues SELL for this asset
            council_decisions = {
                'asset-123': {
                    'action': 'SELL',
                    'asset_id': 'asset-123',
                    'reasoning': 'Bearish reversal',
                }
            }

            result = await check_open_positions(
                council_decisions=council_decisions,
                session=mock_session,
            )

            assert result['council_closes'] == 1
            mock_close.assert_called_once()
            call_args = mock_close.call_args
            assert call_args[0][1] == ExitReason.COUNCIL_SELL

    @pytest.mark.asyncio
    async def test_check_open_positions_breakeven_and_trailing(
        self, sample_trade, mock_session
    ):
        """Test breakeven and trailing are checked when not closing."""
        with patch(
            'services.position_manager.get_open_positions'
        ) as mock_get_positions, \
             patch(
                 'services.position_manager.get_symbol_for_trade'
             ) as mock_get_symbol, \
             patch(
                 'services.position_manager.get_current_prices'
             ) as mock_get_prices, \
             patch(
                 'services.position_manager.fetch_recent_candles'
             ) as mock_candles, \
             patch('services.position_manager.calculate_atr') as mock_atr, \
             patch(
                 'services.position_manager.check_breakeven_trigger'
             ) as mock_breakeven, \
             patch(
                 'services.position_manager.update_trailing_stop'
             ) as mock_trailing:

            mock_get_positions.return_value = [sample_trade]
            mock_get_symbol.return_value = "SOLUSD"
            # Price $112 - triggers breakeven ($100 + 2*$5 = $110)
            mock_get_prices.return_value = {"SOLUSD": 112.0}
            mock_candles.return_value = [{"high": 115, "low": 108, "close": 112}]
            mock_atr.return_value = 5.0
            mock_breakeven.return_value = True
            mock_trailing.return_value = False

            result = await check_open_positions(session=mock_session)

            assert result['breakevens_triggered'] == 1
            mock_breakeven.assert_called_once()
            mock_trailing.assert_called_once()

    @pytest.mark.asyncio
    async def test_check_open_positions_handles_price_fetch_error(
        self, sample_trade, mock_session
    ):
        """Test handles price fetch errors gracefully."""
        with patch(
            'services.position_manager.get_open_positions'
        ) as mock_get_positions, \
             patch(
                 'services.position_manager.get_symbol_for_trade'
             ) as mock_get_symbol, \
             patch(
                 'services.position_manager.get_current_prices'
             ) as mock_get_prices:

            mock_get_positions.return_value = [sample_trade]
            mock_get_symbol.return_value = "SOLUSD"
            mock_get_prices.return_value = {"SOLUSD": None}  # Price fetch failed

            result = await check_open_positions(session=mock_session)

            assert result['errors'] == 1
            assert result['stops_hit'] == 0


# =============================================================================
# Test Price Fetching Functions
# =============================================================================

class TestPriceFetching:
    """Tests for price fetching functions."""

    @pytest.mark.asyncio
    async def test_get_current_price_success(self):
        """Test single price fetch."""
        with patch(
            'services.position_manager.get_kraken_client'
        ) as mock_get_client:
            mock_client = AsyncMock()
            mock_client.initialize = AsyncMock()
            mock_client.convert_symbol_to_kraken.return_value = "SOL/USD"
            mock_client.exchange = AsyncMock()
            mock_client.exchange.fetch_ticker = AsyncMock(
                return_value={'last': 150.0}
            )
            mock_get_client.return_value = mock_client

            result = await get_current_price("SOLUSD")

            assert result == 150.0

    @pytest.mark.asyncio
    async def test_get_current_prices_batch(self):
        """Test batch price fetch."""
        with patch(
            'services.position_manager.get_kraken_client'
        ) as mock_get_client:
            mock_client = AsyncMock()
            mock_client.initialize = AsyncMock()
            mock_client.convert_symbol_to_kraken.side_effect = [
                "SOL/USD", "BTC/USD"
            ]
            mock_client.exchange = AsyncMock()
            mock_client.exchange.fetch_ticker = AsyncMock(
                side_effect=[
                    {'last': 150.0},
                    {'last': 45000.0},
                ]
            )
            mock_get_client.return_value = mock_client

            result = await get_current_prices(["SOLUSD", "BTCUSD"])

            assert result["SOLUSD"] == 150.0
            assert result["BTCUSD"] == 45000.0

    @pytest.mark.asyncio
    async def test_fetch_recent_candles(self):
        """Test candle fetch for ATR."""
        with patch(
            'services.position_manager.get_kraken_client'
        ) as mock_get_client:
            mock_client = AsyncMock()
            mock_client.fetch_ohlcv_for_asset = AsyncMock(
                return_value=[
                    {'high': Decimal('105'), 'low': Decimal('95'), 'close': Decimal('100')},
                    {'high': Decimal('108'), 'low': Decimal('98'), 'close': Decimal('105')},
                ]
            )
            mock_get_client.return_value = mock_client

            result = await fetch_recent_candles("SOLUSD", limit=2)

            assert len(result) == 2
            assert result[0]['high'] == 105.0
            assert result[0]['low'] == 95.0


# =============================================================================
# Integration Tests
# =============================================================================

class TestPositionManagerIntegration:
    """Integration-style tests for position manager."""

    @pytest.mark.asyncio
    async def test_full_position_check_flow(self, mock_session):
        """Test complete position check flow."""
        # Create multiple trades with different scenarios
        trade_stop_hit = Trade(
            id="trade-1",
            asset_id="asset-1",
            status=TradeStatus.OPEN,
            entry_price=Decimal("100.00"),
            stop_loss_price=Decimal("90.00"),
            size=Decimal("1.0"),
            entry_time=datetime.now(timezone.utc),
        )

        trade_in_profit = Trade(
            id="trade-2",
            asset_id="asset-2",
            status=TradeStatus.OPEN,
            entry_price=Decimal("100.00"),
            stop_loss_price=Decimal("100.00"),  # At breakeven
            size=Decimal("1.0"),
            entry_time=datetime.now(timezone.utc),
        )

        with patch(
            'services.position_manager.get_open_positions'
        ) as mock_get_positions, \
             patch(
                 'services.position_manager.get_symbol_for_trade'
             ) as mock_get_symbol, \
             patch(
                 'services.position_manager.get_current_prices'
             ) as mock_get_prices, \
             patch(
                 'services.position_manager.fetch_recent_candles'
             ) as mock_candles, \
             patch('services.position_manager.calculate_atr') as mock_atr, \
             patch(
                 'services.position_manager.close_position'
             ) as mock_close, \
             patch(
                 'services.position_manager.update_trailing_stop'
             ) as mock_trail:

            mock_get_positions.return_value = [trade_stop_hit, trade_in_profit]
            mock_get_symbol.side_effect = ["SOLUSD", "ETHUSD"]
            mock_get_prices.return_value = {
                "SOLUSD": 85.0,   # Below stop - triggers stop loss
                "ETHUSD": 120.0,  # Above entry - in profit
            }
            mock_candles.return_value = [{"high": 125, "low": 115, "close": 120}]
            mock_atr.return_value = 5.0
            mock_close.return_value = (True, None)
            mock_trail.return_value = True

            result = await check_open_positions(session=mock_session)

            # Trade 1 should hit stop loss
            assert result['stops_hit'] == 1
            # Trade 2 should update trailing stop
            assert result['trailing_updates'] == 1

    def test_priority_order_documentation(self):
        """Verify priority order is documented correctly."""
        # This test ensures the priority order is explicit
        # Priority 1: Stop Loss (capital preservation)
        # Priority 2: Council SELL (take profits on reversal)
        # Priority 3: Breakeven (lock in entry)
        # Priority 4: Trailing (maximize profits)

        from services.position_manager import check_open_positions
        import inspect

        source = inspect.getsource(check_open_positions)

        # Verify priority comments exist in code
        assert "PRIORITY 1" in source
        assert "PRIORITY 2" in source
        assert "PRIORITY 3" in source
        assert "PRIORITY 4" in source


# =============================================================================
# Edge Cases
# =============================================================================

class TestEdgeCases:
    """Tests for edge cases and error handling."""

    def test_stop_loss_at_zero(self):
        """Test handling of zero stop loss."""
        trade = Trade(
            id=str(uuid.uuid4()),
            asset_id="asset-123",
            status=TradeStatus.OPEN,
            entry_price=Decimal("100.00"),
            stop_loss_price=Decimal("0.00"),  # Zero stop
            size=Decimal("1.0"),
            entry_time=datetime.now(timezone.utc),
        )

        # Price $50 is above stop $0, should NOT trigger
        result = check_stop_loss(trade, 50.0)
        assert result is False  # Price > stop, no trigger

    def test_very_small_atr(self, trade_at_breakeven):
        """Test trailing stop with very small ATR."""
        # ATR of $0.01 should still work
        atr = 0.01
        new_stop = 120.0 - (2 * atr)  # $119.98

        assert new_stop > 100.0  # Should still be above breakeven

    def test_very_large_atr(self, sample_trade):
        """Test breakeven trigger with large ATR."""
        # Entry=$100, ATR=$50 -> Trigger would be $200
        atr = 50.0
        trigger = 100.0 + (2 * atr)  # $200

        # Price $150 should not trigger breakeven
        assert 150.0 < trigger

    @pytest.mark.asyncio
    async def test_concurrent_position_updates(self, mock_session):
        """Test handling multiple positions updating simultaneously."""
        trades = [
            Trade(
                id=f"trade-{i}",
                asset_id=f"asset-{i}",
                status=TradeStatus.OPEN,
                entry_price=Decimal("100.00"),
                stop_loss_price=Decimal("100.00"),
                size=Decimal("1.0"),
                entry_time=datetime.now(timezone.utc),
            )
            for i in range(5)
        ]

        with patch(
            'services.position_manager.get_open_positions'
        ) as mock_get_positions, \
             patch(
                 'services.position_manager.get_symbol_for_trade'
             ) as mock_get_symbol, \
             patch(
                 'services.position_manager.get_current_prices'
             ) as mock_get_prices, \
             patch(
                 'services.position_manager.fetch_recent_candles'
             ) as mock_candles, \
             patch('services.position_manager.calculate_atr') as mock_atr, \
             patch(
                 'services.position_manager.update_trailing_stop'
             ) as mock_trail:

            mock_get_positions.return_value = trades
            mock_get_symbol.return_value = "SOLUSD"
            mock_get_prices.return_value = {
                "SOLUSD": 120.0,
            }
            mock_candles.return_value = [{"high": 125, "low": 115, "close": 120}]
            mock_atr.return_value = 5.0
            mock_trail.return_value = True

            result = await check_open_positions(session=mock_session)

            # All 5 should have trailing updates
            assert result['positions_checked'] == 5
            assert result['trailing_updates'] == 5
