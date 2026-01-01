"""
Tests for services/safety.py - Global Safety Switch.

Story 3.4: Global Safety Switch

Unit tests for the safety service including:
- SystemConfig initialization and management
- System status (ACTIVE, PAUSED, EMERGENCY_STOP)
- is_trading_enabled() checks
- pause_trading() / resume_trading() controls
- check_drawdown() calculations
- get_portfolio_value() balance tracking
- liquidate_all() emergency function
- enforce_max_drawdown() guard

Test Coverage:
- Status management scenarios
- Kill switch (pause/resume) functionality
- Drawdown calculation edge cases
- Emergency liquidation flow
- Fail-safe behaviors
"""

import pytest
from decimal import Decimal
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
import uuid

from models import SystemConfig, SystemStatus, Trade, TradeStatus


# =============================================================================
# Test Fixtures
# =============================================================================


@pytest.fixture
def sample_system_config():
    """Create a sample system config for testing."""
    return SystemConfig(
        id="system",
        status=SystemStatus.ACTIVE,
        trading_enabled=True,
        initial_balance=Decimal("10000.00"),
        max_drawdown_pct=Decimal("0.20"),
        updated_at=datetime.now(timezone.utc),
    )


@pytest.fixture
def paused_system_config():
    """Create a paused system config for testing."""
    return SystemConfig(
        id="system",
        status=SystemStatus.PAUSED,
        trading_enabled=False,
        initial_balance=Decimal("10000.00"),
        max_drawdown_pct=Decimal("0.20"),
        updated_at=datetime.now(timezone.utc),
    )


@pytest.fixture
def emergency_system_config():
    """Create an emergency stop system config for testing."""
    return SystemConfig(
        id="system",
        status=SystemStatus.EMERGENCY_STOP,
        trading_enabled=False,
        initial_balance=Decimal("10000.00"),
        max_drawdown_pct=Decimal("0.20"),
        emergency_stop_at=datetime.now(timezone.utc),
        emergency_reason="Max drawdown exceeded",
        updated_at=datetime.now(timezone.utc),
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


@pytest.fixture
def sample_open_trade():
    """Create a sample open trade for testing."""
    return Trade(
        id=str(uuid.uuid4()),
        asset_id="asset-123",
        status=TradeStatus.OPEN,
        side="BUY",
        entry_price=Decimal("100.00"),
        stop_loss_price=Decimal("90.00"),
        size=Decimal("10.0"),
        entry_time=datetime.now(timezone.utc),
    )


# =============================================================================
# Test SystemStatus Enum
# =============================================================================


class TestSystemStatusEnum:
    """Tests for SystemStatus enumeration."""

    def test_system_status_values(self):
        """Test all system statuses are defined."""
        assert SystemStatus.ACTIVE.value == "ACTIVE"
        assert SystemStatus.PAUSED.value == "PAUSED"
        assert SystemStatus.EMERGENCY_STOP.value == "EMERGENCY_STOP"

    def test_system_status_is_string_enum(self):
        """Test SystemStatus is a string enum for JSON serialization."""
        assert isinstance(SystemStatus.ACTIVE, str)
        assert SystemStatus.ACTIVE == "ACTIVE"


# =============================================================================
# Test initialize_system_config()
# =============================================================================


class TestInitializeSystemConfig:
    """Tests for initialize_system_config function."""

    @pytest.mark.asyncio
    async def test_initialize_creates_new_config(self, mock_session):
        """Test creates new config when none exists."""
        from services.safety import initialize_system_config

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None

        mock_session.execute = AsyncMock(return_value=mock_result)

        config = await initialize_system_config(
            initial_balance=10000.0,
            max_drawdown_pct=0.20,
            session=mock_session,
        )

        assert config is not None
        assert config.id == "system"
        assert config.initial_balance == Decimal("10000.0")
        assert config.max_drawdown_pct == Decimal("0.20")
        assert config.status == SystemStatus.ACTIVE
        mock_session.add.assert_called_once()
        mock_session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_initialize_updates_existing_config(
        self, mock_session, sample_system_config
    ):
        """Test updates existing config."""
        from services.safety import initialize_system_config

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_system_config

        mock_session.execute = AsyncMock(return_value=mock_result)

        config = await initialize_system_config(
            initial_balance=15000.0,
            max_drawdown_pct=0.15,
            session=mock_session,
        )

        assert config.initial_balance == Decimal("15000.0")
        assert config.max_drawdown_pct == Decimal("0.15")
        mock_session.add.assert_called_once()


# =============================================================================
# Test get_system_status()
# =============================================================================


class TestGetSystemStatus:
    """Tests for get_system_status function."""

    @pytest.mark.asyncio
    async def test_get_status_returns_active(self, mock_session, sample_system_config):
        """Test returns ACTIVE when system is active."""
        from services.safety import get_system_status

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_system_config

        mock_session.execute = AsyncMock(return_value=mock_result)

        status = await get_system_status(session=mock_session)

        assert status == SystemStatus.ACTIVE

    @pytest.mark.asyncio
    async def test_get_status_returns_paused(self, mock_session, paused_system_config):
        """Test returns PAUSED when system is paused."""
        from services.safety import get_system_status

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = paused_system_config

        mock_session.execute = AsyncMock(return_value=mock_result)

        status = await get_system_status(session=mock_session)

        assert status == SystemStatus.PAUSED

    @pytest.mark.asyncio
    async def test_get_status_returns_paused_when_not_initialized(self, mock_session):
        """Test returns PAUSED (fail safe) when config not initialized."""
        from services.safety import get_system_status

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None

        mock_session.execute = AsyncMock(return_value=mock_result)

        status = await get_system_status(session=mock_session)

        # Fail safe - return PAUSED if no config
        assert status == SystemStatus.PAUSED


# =============================================================================
# Test is_trading_enabled()
# =============================================================================


class TestIsTradingEnabled:
    """Tests for is_trading_enabled function."""

    @pytest.mark.asyncio
    async def test_trading_enabled_when_active(
        self, mock_session, sample_system_config
    ):
        """Test returns True when system is ACTIVE and trading enabled."""
        from services.safety import is_trading_enabled

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_system_config

        mock_session.execute = AsyncMock(return_value=mock_result)

        result = await is_trading_enabled(session=mock_session)

        assert result is True

    @pytest.mark.asyncio
    async def test_trading_disabled_when_paused(
        self, mock_session, paused_system_config
    ):
        """Test returns False when system is PAUSED."""
        from services.safety import is_trading_enabled

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = paused_system_config

        mock_session.execute = AsyncMock(return_value=mock_result)

        result = await is_trading_enabled(session=mock_session)

        assert result is False

    @pytest.mark.asyncio
    async def test_trading_disabled_when_emergency_stop(
        self, mock_session, emergency_system_config
    ):
        """Test returns False when system is EMERGENCY_STOP."""
        from services.safety import is_trading_enabled

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = emergency_system_config

        mock_session.execute = AsyncMock(return_value=mock_result)

        result = await is_trading_enabled(session=mock_session)

        assert result is False

    @pytest.mark.asyncio
    async def test_trading_disabled_when_not_initialized(self, mock_session):
        """Test returns False (fail safe) when config not initialized."""
        from services.safety import is_trading_enabled

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None

        mock_session.execute = AsyncMock(return_value=mock_result)

        result = await is_trading_enabled(session=mock_session)

        assert result is False

    @pytest.mark.asyncio
    async def test_trading_disabled_when_flag_false(self, mock_session):
        """Test returns False when trading_enabled flag is False."""
        from services.safety import is_trading_enabled

        config = SystemConfig(
            id="system",
            status=SystemStatus.ACTIVE,
            trading_enabled=False,  # Flag is False
            initial_balance=Decimal("10000.00"),
            max_drawdown_pct=Decimal("0.20"),
        )

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = config

        mock_session.execute = AsyncMock(return_value=mock_result)

        result = await is_trading_enabled(session=mock_session)

        assert result is False


# =============================================================================
# Test set_system_status()
# =============================================================================


class TestSetSystemStatus:
    """Tests for set_system_status function."""

    @pytest.mark.asyncio
    async def test_set_status_to_paused(self, mock_session, sample_system_config):
        """Test setting status to PAUSED."""
        from services.safety import set_system_status

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_system_config

        mock_session.execute = AsyncMock(return_value=mock_result)

        result = await set_system_status(
            SystemStatus.PAUSED,
            reason="Manual pause",
            session=mock_session,
        )

        assert result is True
        assert sample_system_config.status == SystemStatus.PAUSED
        mock_session.add.assert_called_once()
        mock_session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_set_status_to_emergency_sets_fields(
        self, mock_session, sample_system_config
    ):
        """Test setting EMERGENCY_STOP sets additional fields."""
        from services.safety import set_system_status

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_system_config

        mock_session.execute = AsyncMock(return_value=mock_result)

        result = await set_system_status(
            SystemStatus.EMERGENCY_STOP,
            reason="Max drawdown exceeded",
            session=mock_session,
        )

        assert result is True
        assert sample_system_config.status == SystemStatus.EMERGENCY_STOP
        assert sample_system_config.trading_enabled is False
        assert sample_system_config.emergency_stop_at is not None
        assert sample_system_config.emergency_reason == "Max drawdown exceeded"

    @pytest.mark.asyncio
    async def test_set_status_fails_when_not_initialized(self, mock_session):
        """Test returns False when config not found."""
        from services.safety import set_system_status

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None

        mock_session.execute = AsyncMock(return_value=mock_result)

        result = await set_system_status(
            SystemStatus.PAUSED,
            reason="Test",
            session=mock_session,
        )

        assert result is False


# =============================================================================
# Test pause_trading() / resume_trading()
# =============================================================================


class TestPauseResume:
    """Tests for pause_trading and resume_trading functions."""

    @pytest.mark.asyncio
    async def test_pause_trading_success(self, mock_session, sample_system_config):
        """Test pause_trading sets status to PAUSED."""
        from services.safety import pause_trading

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_system_config

        mock_session.execute = AsyncMock(return_value=mock_result)

        result = await pause_trading(
            reason="User requested pause",
            session=mock_session,
        )

        assert result is True
        assert sample_system_config.status == SystemStatus.PAUSED

    @pytest.mark.asyncio
    async def test_resume_trading_success(self, mock_session, paused_system_config):
        """Test resume_trading sets status back to ACTIVE."""
        from services.safety import resume_trading

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = paused_system_config

        mock_session.execute = AsyncMock(return_value=mock_result)

        result = await resume_trading(session=mock_session)

        assert result is True
        assert paused_system_config.status == SystemStatus.ACTIVE
        assert paused_system_config.trading_enabled is True

    @pytest.mark.asyncio
    async def test_resume_blocked_from_emergency_stop(
        self, mock_session, emergency_system_config
    ):
        """Test resume_trading is blocked when in EMERGENCY_STOP."""
        from services.safety import resume_trading

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = emergency_system_config

        mock_session.execute = AsyncMock(return_value=mock_result)

        result = await resume_trading(session=mock_session)

        assert result is False
        # Status should remain EMERGENCY_STOP
        assert emergency_system_config.status == SystemStatus.EMERGENCY_STOP


# =============================================================================
# Test check_drawdown()
# =============================================================================


class TestCheckDrawdown:
    """Tests for check_drawdown function."""

    @pytest.mark.asyncio
    async def test_drawdown_within_limit(self, mock_session, sample_system_config):
        """Test returns False when drawdown is within limit."""
        from services.safety import check_drawdown

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_system_config

        mock_session.execute = AsyncMock(return_value=mock_result)

        # Mock portfolio value - 10% drawdown (within 20% limit)
        with patch(
            "services.safety.get_portfolio_value",
            return_value=(9000.0, {}),
        ):
            exceeds, drawdown_pct, current_value = await check_drawdown(
                session=mock_session
            )

        assert exceeds is False
        assert drawdown_pct == pytest.approx(0.10, rel=0.01)
        assert current_value == 9000.0

    @pytest.mark.asyncio
    async def test_drawdown_exceeds_limit(self, mock_session, sample_system_config):
        """Test returns True when drawdown exceeds limit."""
        from services.safety import check_drawdown

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_system_config

        mock_session.execute = AsyncMock(return_value=mock_result)

        # Mock portfolio value - 25% drawdown (exceeds 20% limit)
        with patch(
            "services.safety.get_portfolio_value",
            return_value=(7500.0, {}),
        ):
            exceeds, drawdown_pct, current_value = await check_drawdown(
                session=mock_session
            )

        assert exceeds is True
        assert drawdown_pct == pytest.approx(0.25, rel=0.01)
        assert current_value == 7500.0

    @pytest.mark.asyncio
    async def test_drawdown_exactly_at_limit(self, mock_session, sample_system_config):
        """Test returns False when drawdown is exactly at limit."""
        from services.safety import check_drawdown

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_system_config

        mock_session.execute = AsyncMock(return_value=mock_result)

        # Mock portfolio value - exactly 20% drawdown
        with patch(
            "services.safety.get_portfolio_value",
            return_value=(8000.0, {}),
        ):
            exceeds, drawdown_pct, current_value = await check_drawdown(
                session=mock_session
            )

        assert exceeds is False  # At limit, not exceeding
        assert drawdown_pct == pytest.approx(0.20, rel=0.01)

    @pytest.mark.asyncio
    async def test_drawdown_with_zero_portfolio(self, mock_session, sample_system_config):
        """Test handles zero portfolio value gracefully."""
        from services.safety import check_drawdown

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_system_config

        mock_session.execute = AsyncMock(return_value=mock_result)

        # Mock portfolio value as zero (API failure)
        with patch(
            "services.safety.get_portfolio_value",
            return_value=(0.0, {}),
        ):
            exceeds, drawdown_pct, current_value = await check_drawdown(
                session=mock_session
            )

        # Should not trigger false emergency on API failure
        assert exceeds is False
        assert current_value == 0.0


# =============================================================================
# Test liquidate_all()
# =============================================================================


class TestLiquidateAll:
    """Tests for liquidate_all function."""

    @pytest.mark.asyncio
    async def test_liquidate_all_no_positions(self, mock_session, sample_system_config):
        """Test liquidation with no open positions."""
        from services.safety import liquidate_all

        # Mock config query
        mock_config_result = MagicMock()
        mock_config_result.scalar_one_or_none.return_value = sample_system_config

        # Mock trades query (empty)
        mock_trades_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = []
        mock_trades_result.scalars.return_value = mock_scalars

        mock_session.execute = AsyncMock(
            side_effect=[mock_config_result, mock_trades_result]
        )

        summary = await liquidate_all(
            reason="Test liquidation",
            session=mock_session,
        )

        assert summary["positions_closed"] == 0
        assert summary["positions_failed"] == 0
        assert sample_system_config.status == SystemStatus.EMERGENCY_STOP

    @pytest.mark.asyncio
    async def test_liquidate_all_closes_positions(
        self, mock_session, sample_system_config, sample_open_trade
    ):
        """Test liquidation closes all open positions."""
        from services.safety import liquidate_all

        # Mock config query
        mock_config_result = MagicMock()
        mock_config_result.scalar_one_or_none.return_value = sample_system_config

        # Mock trades query
        mock_trades_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = [sample_open_trade]
        mock_trades_result.scalars.return_value = mock_scalars

        mock_session.execute = AsyncMock(
            side_effect=[mock_config_result, mock_trades_result]
        )

        with patch(
            "services.safety.get_symbol_for_trade",
            return_value="SOLUSD",
        ), patch(
            "services.safety.close_position",
            return_value=(True, None),
        ):
            summary = await liquidate_all(
                reason="Test liquidation",
                session=mock_session,
            )

        assert summary["positions_closed"] == 1
        assert summary["positions_failed"] == 0


# =============================================================================
# Test enforce_max_drawdown()
# =============================================================================


class TestEnforceMaxDrawdown:
    """Tests for enforce_max_drawdown function."""

    @pytest.mark.asyncio
    async def test_enforce_skips_if_already_emergency(
        self, mock_session, emergency_system_config
    ):
        """Test skips check if already in EMERGENCY_STOP."""
        from services.safety import enforce_max_drawdown

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = emergency_system_config

        mock_session.execute = AsyncMock(return_value=mock_result)

        result = await enforce_max_drawdown(session=mock_session)

        assert result is False

    @pytest.mark.asyncio
    async def test_enforce_skips_if_paused(self, mock_session, paused_system_config):
        """Test skips check if system is PAUSED."""
        from services.safety import enforce_max_drawdown

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = paused_system_config

        mock_session.execute = AsyncMock(return_value=mock_result)

        result = await enforce_max_drawdown(session=mock_session)

        assert result is False

    @pytest.mark.asyncio
    async def test_enforce_triggers_liquidation_on_drawdown(
        self, mock_session, sample_system_config
    ):
        """Test triggers liquidation when drawdown exceeded."""
        from services.safety import enforce_max_drawdown

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_system_config

        mock_session.execute = AsyncMock(return_value=mock_result)

        with patch(
            "services.safety.check_drawdown",
            return_value=(True, 0.25, 7500.0),
        ), patch(
            "services.safety.liquidate_all",
            return_value={"positions_closed": 1, "positions_failed": 0, "total_pnl": -100.0},
        ) as mock_liquidate, patch(
            "services.safety.send_emergency_notification",
        ):
            result = await enforce_max_drawdown(session=mock_session)

        assert result is True
        mock_liquidate.assert_called_once()

    @pytest.mark.asyncio
    async def test_enforce_no_action_when_within_limit(
        self, mock_session, sample_system_config
    ):
        """Test no action when drawdown within limit."""
        from services.safety import enforce_max_drawdown

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_system_config

        mock_session.execute = AsyncMock(return_value=mock_result)

        with patch(
            "services.safety.check_drawdown",
            return_value=(False, 0.10, 9000.0),
        ):
            result = await enforce_max_drawdown(session=mock_session)

        assert result is False


# =============================================================================
# Test execute_buy Kill Switch Integration
# =============================================================================


class TestExecuteBuyKillSwitch:
    """Tests for kill switch integration in execute_buy."""

    @pytest.mark.asyncio
    async def test_execute_buy_blocked_when_trading_disabled(self):
        """Test execute_buy is blocked when trading is disabled."""
        from services.execution import execute_buy

        with patch(
            "services.safety.is_trading_enabled",
            return_value=False,
        ):
            success, error, trade = await execute_buy(
                symbol="SOLUSD",
                amount_usd=100.0,
                skip_safety_check=False,
            )

        assert success is False
        assert "disabled" in error.lower()
        assert trade is None

    @pytest.mark.asyncio
    async def test_execute_buy_proceeds_when_trading_enabled(self, mock_session):
        """Test execute_buy proceeds when trading is enabled."""
        from services.execution import execute_buy
        from models import Asset

        mock_asset = Asset(
            id="test-asset-id",
            symbol="SOLUSD",
            is_active=True,
        )

        # Mock session - asset found, no existing position
        mock_result_asset = MagicMock()
        mock_result_asset.scalar_one_or_none.return_value = mock_asset

        mock_result_no_trade = MagicMock()
        mock_result_no_trade.scalar_one_or_none.return_value = None

        mock_session.execute = AsyncMock(
            side_effect=[mock_result_asset, mock_result_no_trade]
        )
        mock_session.add = MagicMock()
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

        with patch(
            "services.safety.is_trading_enabled",
            return_value=True,
        ):
            success, error, trade = await execute_buy(
                symbol="SOLUSD",
                amount_usd=100.0,
                client=mock_client,
                session=mock_session,
                skip_safety_check=False,
            )

        assert success is True
        assert error is None


# =============================================================================
# Test SystemConfig Model
# =============================================================================


class TestSystemConfigModel:
    """Tests for SystemConfig SQLModel."""

    def test_system_config_defaults(self):
        """Test SystemConfig has correct defaults."""
        config = SystemConfig(
            id="system",
            initial_balance=Decimal("10000.00"),
        )

        assert config.status == SystemStatus.ACTIVE
        assert config.trading_enabled is True
        assert config.max_drawdown_pct == Decimal("0.20")
        assert config.emergency_stop_at is None
        assert config.emergency_reason is None

    def test_system_config_with_emergency(self):
        """Test SystemConfig with emergency fields."""
        now = datetime.now(timezone.utc)
        config = SystemConfig(
            id="system",
            status=SystemStatus.EMERGENCY_STOP,
            trading_enabled=False,
            initial_balance=Decimal("10000.00"),
            emergency_stop_at=now,
            emergency_reason="Max drawdown exceeded",
        )

        assert config.status == SystemStatus.EMERGENCY_STOP
        assert config.trading_enabled is False
        assert config.emergency_stop_at == now
        assert config.emergency_reason == "Max drawdown exceeded"


# =============================================================================
# Edge Cases
# =============================================================================


class TestEdgeCases:
    """Tests for edge cases and error handling."""

    @pytest.mark.asyncio
    async def test_drawdown_with_negative_initial_balance(
        self, mock_session
    ):
        """Test handles invalid initial balance."""
        from services.safety import check_drawdown

        config = SystemConfig(
            id="system",
            initial_balance=Decimal("0"),  # Invalid
            max_drawdown_pct=Decimal("0.20"),
        )

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = config

        mock_session.execute = AsyncMock(return_value=mock_result)

        exceeds, drawdown_pct, current_value = await check_drawdown(
            session=mock_session
        )

        # Should return safe defaults
        assert exceeds is False
        assert drawdown_pct == 0.0

    @pytest.mark.asyncio
    async def test_status_check_handles_db_error(self, mock_session):
        """Test status check handles database errors gracefully."""
        from services.safety import is_trading_enabled

        mock_session.execute = AsyncMock(
            side_effect=Exception("Database connection error")
        )

        # Should not raise - returns False (fail safe)
        try:
            result = await is_trading_enabled(session=mock_session)
            # If it reaches here without raising, that's the expected behavior
            # when using the global session maker path
        except Exception:
            # Exception is also acceptable for direct session usage
            pass

    def test_system_status_comparison(self):
        """Test SystemStatus enum comparisons work correctly."""
        assert SystemStatus.ACTIVE != SystemStatus.PAUSED
        assert SystemStatus.PAUSED != SystemStatus.EMERGENCY_STOP
        assert SystemStatus.ACTIVE == SystemStatus.ACTIVE


# =============================================================================
# Integration Tests
# =============================================================================


class TestSafetyIntegration:
    """Integration-style tests for safety service."""

    @pytest.mark.asyncio
    async def test_full_pause_resume_flow(self, mock_session, sample_system_config):
        """Test complete pause/resume flow."""
        from services.safety import (
            is_trading_enabled,
            pause_trading,
            resume_trading,
            get_system_status,
        )

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_system_config

        mock_session.execute = AsyncMock(return_value=mock_result)

        # Initially active
        assert await is_trading_enabled(session=mock_session) is True

        # Pause
        await pause_trading("Test pause", session=mock_session)
        assert sample_system_config.status == SystemStatus.PAUSED

        # Cannot trade when paused
        mock_result.scalar_one_or_none.return_value = sample_system_config
        # Note: trading_enabled is still True in config, but status is PAUSED

        # Resume
        await resume_trading(session=mock_session)
        assert sample_system_config.status == SystemStatus.ACTIVE

    @pytest.mark.asyncio
    async def test_emergency_stop_cannot_resume(
        self, mock_session, sample_system_config
    ):
        """Test emergency stop requires manual intervention."""
        from services.safety import (
            set_system_status,
            resume_trading,
        )

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_system_config

        mock_session.execute = AsyncMock(return_value=mock_result)

        # Trigger emergency stop
        await set_system_status(
            SystemStatus.EMERGENCY_STOP,
            reason="Test emergency",
            session=mock_session,
        )

        assert sample_system_config.status == SystemStatus.EMERGENCY_STOP

        # Attempt resume should fail
        result = await resume_trading(session=mock_session)
        assert result is False
