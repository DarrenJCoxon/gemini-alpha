"""
Tests for Story 5.5: Risk Parameter Optimization.

Comprehensive tests for the enhanced risk management system including:
- EnhancedRiskConfig validation
- RiskStatus and RiskLevel
- DrawdownTracker
- CorrelationTracker
- RiskValidator

Uses pytest with async support for database operations.
"""

import pytest
from decimal import Decimal
from datetime import datetime, timezone
from unittest.mock import patch, MagicMock, AsyncMock

from config import EnhancedRiskConfig
from services.risk_status import (
    RiskLevel,
    RiskStatus,
    PositionRisk,
    determine_risk_level,
)
from services.correlation_tracker import (
    get_correlation_group,
    get_group_members,
    calculate_correlated_exposure,
    would_exceed_correlation_limit,
    CORRELATION_GROUPS,
)
from services.drawdown_tracker import DrawdownTracker
from services.risk_validator import RiskValidator, TradeRiskCheck


# =============================================================================
# Sample Data Fixtures
# =============================================================================


@pytest.fixture
def sample_positions():
    """Sample positions for testing."""
    return [
        {"symbol": "BTCUSD", "value": 5000},
        {"symbol": "ETHUSD", "value": 3000},
        {"symbol": "SOLUSD", "value": 2000},
    ]


@pytest.fixture
def enhanced_risk_config():
    """Create EnhancedRiskConfig with test values."""
    return EnhancedRiskConfig()


@pytest.fixture
def mock_drawdown_tracker():
    """Create a mock DrawdownTracker."""
    tracker = MagicMock(spec=DrawdownTracker)
    tracker.get_current_drawdown = AsyncMock(return_value=5.0)
    tracker.peak_value = Decimal("100000")
    tracker.current_value = Decimal("95000")
    return tracker


# =============================================================================
# Test EnhancedRiskConfig
# =============================================================================


class TestEnhancedRiskConfig:
    """Tests for EnhancedRiskConfig class."""

    def test_config_default_values(self):
        """Test that config has correct default values."""
        config = EnhancedRiskConfig()

        assert config.max_drawdown_pct == 15.0
        assert config.per_trade_risk_pct == 1.5
        assert config.max_single_position_pct == 10.0
        assert config.max_correlated_exposure_pct == 30.0
        assert config.correlation_threshold == 0.7
        assert config.alert_threshold_pct == 80.0
        assert config.daily_loss_limit_pct == 5.0
        assert config.atr_period == 14
        assert config.atr_multiplier == 2.0
        assert config.max_stop_loss_pct == 15.0
        assert config.min_stop_loss_pct == 2.0

    def test_config_validation_valid(self):
        """Test validation passes for default config."""
        config = EnhancedRiskConfig()
        # Should not raise
        config.validate()

    def test_config_validation_invalid_max_drawdown(self):
        """Test validation fails for invalid max drawdown."""
        with patch.dict('os.environ', {'MAX_DRAWDOWN_PCT': '60.0'}):
            config = EnhancedRiskConfig()
            with pytest.raises(ValueError, match="Max drawdown"):
                config.validate()

    def test_config_validation_invalid_per_trade_risk(self):
        """Test validation fails for invalid per-trade risk."""
        with patch.dict('os.environ', {'PER_TRADE_RISK_PCT': '10.0'}):
            config = EnhancedRiskConfig()
            with pytest.raises(ValueError, match="Per-trade risk"):
                config.validate()

    def test_config_validation_invalid_max_position(self):
        """Test validation fails for invalid max position size."""
        with patch.dict('os.environ', {'MAX_SINGLE_POSITION_PCT': '30.0'}):
            config = EnhancedRiskConfig()
            with pytest.raises(ValueError, match="Max position"):
                config.validate()

    def test_config_validation_invalid_correlated_exposure(self):
        """Test validation fails for invalid correlated exposure."""
        with patch.dict('os.environ', {'MAX_CORRELATED_EXPOSURE_PCT': '5.0'}):
            config = EnhancedRiskConfig()
            with pytest.raises(ValueError, match="Correlated exposure"):
                config.validate()

    def test_config_from_environment(self):
        """Test config reads from environment variables."""
        with patch.dict('os.environ', {
            'MAX_DRAWDOWN_PCT': '20.0',
            'PER_TRADE_RISK_PCT': '2.0',
        }):
            config = EnhancedRiskConfig()
            assert config.max_drawdown_pct == 20.0
            assert config.per_trade_risk_pct == 2.0


# =============================================================================
# Test RiskStatus and RiskLevel
# =============================================================================


class TestRiskLevel:
    """Tests for RiskLevel enum."""

    def test_risk_level_values(self):
        """Test RiskLevel enum has expected values."""
        assert RiskLevel.LOW.value == "LOW"
        assert RiskLevel.MODERATE.value == "MODERATE"
        assert RiskLevel.HIGH.value == "HIGH"
        assert RiskLevel.CRITICAL.value == "CRITICAL"

    def test_determine_risk_level_low(self):
        """Test risk level is LOW for utilization < 50%."""
        assert determine_risk_level(0) == RiskLevel.LOW
        assert determine_risk_level(25) == RiskLevel.LOW
        assert determine_risk_level(49) == RiskLevel.LOW

    def test_determine_risk_level_moderate(self):
        """Test risk level is MODERATE for utilization 50-80%."""
        assert determine_risk_level(50) == RiskLevel.MODERATE
        assert determine_risk_level(65) == RiskLevel.MODERATE
        assert determine_risk_level(79) == RiskLevel.MODERATE

    def test_determine_risk_level_high(self):
        """Test risk level is HIGH for utilization 80-100%."""
        assert determine_risk_level(80) == RiskLevel.HIGH
        assert determine_risk_level(90) == RiskLevel.HIGH
        assert determine_risk_level(99) == RiskLevel.HIGH

    def test_determine_risk_level_critical(self):
        """Test risk level is CRITICAL for utilization >= 100%."""
        assert determine_risk_level(100) == RiskLevel.CRITICAL
        assert determine_risk_level(150) == RiskLevel.CRITICAL


class TestRiskStatus:
    """Tests for RiskStatus dataclass."""

    def test_risk_status_creation(self):
        """Test RiskStatus can be created with all fields."""
        status = RiskStatus(
            current_drawdown_pct=5.0,
            max_drawdown_pct=15.0,
            drawdown_utilization=33.3,
            per_trade_risk_pct=1.5,
            max_per_trade_risk_pct=1.5,
            largest_position_pct=8.0,
            max_single_position_pct=10.0,
            position_concentration_utilization=80.0,
            correlated_exposure_pct=25.0,
            max_correlated_exposure_pct=30.0,
            correlation_utilization=83.3,
            daily_loss_pct=2.0,
            daily_loss_limit_pct=5.0,
            daily_loss_utilization=40.0,
            overall_risk_level=RiskLevel.HIGH,
            can_trade=True,
            alerts=["Test alert"],
            recommendations=["Test recommendation"],
        )

        assert status.current_drawdown_pct == 5.0
        assert status.overall_risk_level == RiskLevel.HIGH
        assert len(status.alerts) == 1

    def test_risk_status_to_dict(self):
        """Test RiskStatus.to_dict() method."""
        status = RiskStatus(
            current_drawdown_pct=5.0,
            max_drawdown_pct=15.0,
            drawdown_utilization=33.3,
            per_trade_risk_pct=1.5,
            max_per_trade_risk_pct=1.5,
            largest_position_pct=8.0,
            max_single_position_pct=10.0,
            position_concentration_utilization=80.0,
            correlated_exposure_pct=25.0,
            max_correlated_exposure_pct=30.0,
            correlation_utilization=83.3,
            daily_loss_pct=2.0,
            daily_loss_limit_pct=5.0,
            daily_loss_utilization=40.0,
            overall_risk_level=RiskLevel.HIGH,
            can_trade=True,
            alerts=[],
            recommendations=[],
        )

        result = status.to_dict()

        assert "drawdown" in result
        assert result["drawdown"]["current"] == 5.0
        assert result["overall"]["risk_level"] == "HIGH"


class TestPositionRisk:
    """Tests for PositionRisk dataclass."""

    def test_position_risk_creation(self):
        """Test PositionRisk can be created."""
        position = PositionRisk(
            symbol="BTCUSD",
            position_value=Decimal("5000"),
            position_pct=5.0,
            correlation_group="BTC_CORRELATED",
            correlated_with=["ETHUSD"],
            risk_contribution=5.0,
        )

        assert position.symbol == "BTCUSD"
        assert position.position_pct == 5.0
        assert position.correlation_group == "BTC_CORRELATED"

    def test_position_risk_to_dict(self):
        """Test PositionRisk.to_dict() method."""
        position = PositionRisk(
            symbol="BTCUSD",
            position_value=Decimal("5000"),
            position_pct=5.0,
            correlation_group="BTC_CORRELATED",
            correlated_with=["ETHUSD"],
            risk_contribution=5.0,
        )

        result = position.to_dict()

        assert result["symbol"] == "BTCUSD"
        assert result["position_value"] == 5000.0


# =============================================================================
# Test CorrelationTracker
# =============================================================================


class TestCorrelationGroups:
    """Tests for correlation group functions."""

    def test_get_correlation_group_btc(self):
        """Test BTC is in BTC_CORRELATED group."""
        assert get_correlation_group("BTCUSD") == "BTC_CORRELATED"

    def test_get_correlation_group_eth(self):
        """Test ETH is in BTC_CORRELATED group."""
        assert get_correlation_group("ETHUSD") == "BTC_CORRELATED"

    def test_get_correlation_group_sol(self):
        """Test SOL is in ALT_LAYER1 group."""
        assert get_correlation_group("SOLUSD") == "ALT_LAYER1"

    def test_get_correlation_group_link(self):
        """Test LINK is in DEFI group."""
        assert get_correlation_group("LINKUSD") == "DEFI"

    def test_get_correlation_group_unknown(self):
        """Test unknown symbol returns UNCORRELATED."""
        assert get_correlation_group("UNKNOWN") == "UNCORRELATED"
        assert get_correlation_group("XYZUSD") == "UNCORRELATED"

    def test_get_group_members(self):
        """Test getting members of a correlation group."""
        btc_members = get_group_members("BTC_CORRELATED")
        assert "BTCUSD" in btc_members
        assert "ETHUSD" in btc_members

    def test_get_group_members_unknown(self):
        """Test getting members of unknown group returns empty list."""
        assert get_group_members("UNKNOWN") == []


class TestCorrelatedExposure:
    """Tests for correlated exposure calculation."""

    @pytest.mark.asyncio
    async def test_calculate_correlated_exposure_empty(self):
        """Test correlated exposure with empty positions."""
        result = await calculate_correlated_exposure([], Decimal("100000"))

        assert result["correlated_exposure_pct"] == 0.0
        assert result["largest_correlated_group_pct"] == 0.0

    @pytest.mark.asyncio
    async def test_calculate_correlated_exposure_single_position(self, sample_positions):
        """Test correlated exposure with positions."""
        result = await calculate_correlated_exposure(
            sample_positions,
            Decimal("100000"),
        )

        # BTC + ETH = 8000 = 8% of 100k (BTC_CORRELATED group)
        # SOL = 2000 = 2% of 100k (ALT_LAYER1 group)
        assert "BTC_CORRELATED" in result["correlation_groups"]
        assert "ALT_LAYER1" in result["correlation_groups"]

    @pytest.mark.asyncio
    async def test_calculate_correlated_exposure_percentages(self, sample_positions):
        """Test correlated exposure percentage calculation."""
        result = await calculate_correlated_exposure(
            sample_positions,
            Decimal("100000"),
        )

        # Total correlated = BTC_CORRELATED (8%) + ALT_LAYER1 (2%) = 10%
        assert result["correlated_exposure_pct"] == pytest.approx(10.0, rel=0.1)

    def test_would_exceed_correlation_limit_false(self):
        """Test when adding position would not exceed limit."""
        positions = [{"symbol": "BTCUSD", "value": 5000}]
        portfolio = Decimal("100000")

        would_exceed, current, projected = would_exceed_correlation_limit(
            new_symbol="LINKUSD",  # Different group (DEFI)
            new_value=Decimal("5000"),
            existing_positions=positions,
            portfolio_value=portfolio,
            max_correlated_exposure_pct=30.0,
        )

        assert would_exceed is False

    def test_would_exceed_correlation_limit_true(self):
        """Test when adding position would exceed limit."""
        # Already at 25% correlated exposure
        positions = [
            {"symbol": "BTCUSD", "value": 15000},
            {"symbol": "ETHUSD", "value": 10000},
        ]
        portfolio = Decimal("100000")

        would_exceed, current, projected = would_exceed_correlation_limit(
            new_symbol="SOLUSD",  # Different group but still correlated
            new_value=Decimal("10000"),
            existing_positions=positions,
            portfolio_value=portfolio,
            max_correlated_exposure_pct=30.0,
        )

        # Projected would be 35% correlated
        assert would_exceed is True
        assert projected > 30.0


# =============================================================================
# Test DrawdownTracker
# =============================================================================


class TestDrawdownTracker:
    """Tests for DrawdownTracker class."""

    def test_drawdown_tracker_initialization(self):
        """Test DrawdownTracker initializes correctly."""
        tracker = DrawdownTracker()

        assert tracker.peak_value is None
        assert tracker.current_value is None
        assert tracker._loaded is False

    @pytest.mark.asyncio
    async def test_get_current_drawdown_no_data(self):
        """Test get_current_drawdown when no data loaded."""
        tracker = DrawdownTracker()

        # Mock the _load_latest to set values
        async def mock_load(session=None):
            tracker.peak_value = Decimal("100000")
            tracker.current_value = Decimal("90000")
            tracker._loaded = True

        tracker._load_latest = mock_load

        drawdown = await tracker.get_current_drawdown()

        # (100000 - 90000) / 100000 * 100 = 10%
        assert drawdown == pytest.approx(10.0, rel=0.01)


# =============================================================================
# Test RiskValidator
# =============================================================================


class TestTradeRiskCheck:
    """Tests for TradeRiskCheck dataclass."""

    def test_trade_risk_check_approved(self):
        """Test TradeRiskCheck for approved trade."""
        check = TradeRiskCheck(
            approved=True,
            max_allowed_size=Decimal("1000"),
            rejection_reasons=[],
            warnings=["Minor warning"],
            risk_adjustments={"max_risk_usd": 150.0},
        )

        assert check.approved is True
        assert float(check.max_allowed_size) == 1000.0
        assert len(check.warnings) == 1

    def test_trade_risk_check_rejected(self):
        """Test TradeRiskCheck for rejected trade."""
        check = TradeRiskCheck(
            approved=False,
            max_allowed_size=Decimal("0"),
            rejection_reasons=["Daily loss limit reached"],
            warnings=[],
            risk_adjustments={},
        )

        assert check.approved is False
        assert len(check.rejection_reasons) == 1

    def test_trade_risk_check_to_dict(self):
        """Test TradeRiskCheck.to_dict() method."""
        check = TradeRiskCheck(
            approved=True,
            max_allowed_size=Decimal("1000"),
            rejection_reasons=[],
            warnings=[],
            risk_adjustments={},
        )

        result = check.to_dict()

        assert result["approved"] is True
        assert result["max_allowed_size"] == 1000.0


class TestRiskValidator:
    """Tests for RiskValidator class."""

    @pytest.mark.asyncio
    async def test_validate_trade_within_limits(self, mock_drawdown_tracker, sample_positions):
        """Test trade validation when within all limits."""
        validator = RiskValidator(drawdown_tracker=mock_drawdown_tracker)

        result = await validator.validate_trade(
            symbol="LINKUSD",
            requested_size_usd=1000,
            portfolio_value=100000,
            current_positions=sample_positions,
            daily_pnl=0.0,
        )

        assert result.approved is True
        assert float(result.max_allowed_size) == 1000

    @pytest.mark.asyncio
    async def test_validate_trade_position_size_reduced(self, mock_drawdown_tracker, sample_positions):
        """Test trade validation reduces position size to limit."""
        validator = RiskValidator(drawdown_tracker=mock_drawdown_tracker)

        # Request 15% position (exceeds 10% limit)
        result = await validator.validate_trade(
            symbol="LINKUSD",
            requested_size_usd=15000,
            portfolio_value=100000,
            current_positions=sample_positions,
            daily_pnl=0.0,
        )

        assert result.approved is True
        # Should be reduced to 10% = $10,000
        assert float(result.max_allowed_size) == 10000
        assert result.risk_adjustments.get("position_size_reduced") is True

    @pytest.mark.asyncio
    async def test_validate_trade_daily_loss_rejection(self, mock_drawdown_tracker, sample_positions):
        """Test trade rejection when daily loss limit reached."""
        validator = RiskValidator(drawdown_tracker=mock_drawdown_tracker)

        # -6% daily loss exceeds 5% limit
        result = await validator.validate_trade(
            symbol="LINKUSD",
            requested_size_usd=1000,
            portfolio_value=100000,
            current_positions=sample_positions,
            daily_pnl=-6000,
        )

        assert result.approved is False
        assert any("Daily loss" in r for r in result.rejection_reasons)

    @pytest.mark.asyncio
    async def test_validate_trade_max_drawdown_rejection(self, sample_positions):
        """Test trade rejection when max drawdown reached."""
        mock_tracker = MagicMock(spec=DrawdownTracker)
        mock_tracker.get_current_drawdown = AsyncMock(return_value=16.0)  # Exceeds 15%

        validator = RiskValidator(drawdown_tracker=mock_tracker)

        result = await validator.validate_trade(
            symbol="LINKUSD",
            requested_size_usd=1000,
            portfolio_value=100000,
            current_positions=sample_positions,
            daily_pnl=0.0,
        )

        assert result.approved is False
        assert any("drawdown" in r.lower() for r in result.rejection_reasons)

    @pytest.mark.asyncio
    async def test_validate_trade_zero_portfolio(self, mock_drawdown_tracker):
        """Test trade rejection with zero portfolio value."""
        validator = RiskValidator(drawdown_tracker=mock_drawdown_tracker)

        result = await validator.validate_trade(
            symbol="LINKUSD",
            requested_size_usd=1000,
            portfolio_value=0,
            current_positions=[],
            daily_pnl=0.0,
        )

        assert result.approved is False

    @pytest.mark.asyncio
    async def test_get_risk_status(self, mock_drawdown_tracker, sample_positions):
        """Test getting comprehensive risk status."""
        validator = RiskValidator(drawdown_tracker=mock_drawdown_tracker)

        status = await validator.get_risk_status(
            portfolio_value=100000,
            current_positions=sample_positions,
            daily_pnl=-1000,  # -1% loss
        )

        assert isinstance(status, RiskStatus)
        assert status.can_trade is True
        assert status.current_drawdown_pct == 5.0  # From mock

    @pytest.mark.asyncio
    async def test_risk_status_alerts_at_threshold(self, sample_positions):
        """Test that alerts are generated at 80% threshold."""
        mock_tracker = MagicMock(spec=DrawdownTracker)
        mock_tracker.get_current_drawdown = AsyncMock(return_value=12.5)  # ~83% of 15% limit

        validator = RiskValidator(drawdown_tracker=mock_tracker)

        status = await validator.get_risk_status(
            portfolio_value=100000,
            current_positions=sample_positions,
            daily_pnl=0.0,
        )

        # Should have drawdown alert since 12.5/15 = 83.3% > 80%
        assert any("drawdown" in alert.lower() for alert in status.alerts)

    @pytest.mark.asyncio
    async def test_risk_status_can_trade_false_at_critical(self, sample_positions):
        """Test can_trade is False at CRITICAL level."""
        mock_tracker = MagicMock(spec=DrawdownTracker)
        mock_tracker.get_current_drawdown = AsyncMock(return_value=16.0)  # > 15% limit

        validator = RiskValidator(drawdown_tracker=mock_tracker)

        status = await validator.get_risk_status(
            portfolio_value=100000,
            current_positions=sample_positions,
            daily_pnl=0.0,
        )

        assert status.overall_risk_level == RiskLevel.CRITICAL
        assert status.can_trade is False


# =============================================================================
# Integration Tests
# =============================================================================


class TestRiskIntegration:
    """Integration tests for risk parameter system."""

    @pytest.mark.asyncio
    async def test_full_risk_validation_flow(self, mock_drawdown_tracker):
        """Test complete risk validation flow."""
        validator = RiskValidator(drawdown_tracker=mock_drawdown_tracker)

        positions = [
            {"symbol": "BTCUSD", "value": 5000},
            {"symbol": "ETHUSD", "value": 3000},
        ]

        # Step 1: Validate a trade
        result = await validator.validate_trade(
            symbol="SOLUSD",
            requested_size_usd=2000,
            portfolio_value=100000,
            current_positions=positions,
            daily_pnl=-500,
        )

        assert result.approved is True

        # Step 2: Get risk status
        status = await validator.get_risk_status(
            portfolio_value=100000,
            current_positions=positions,
            daily_pnl=-500,
        )

        assert status.can_trade is True
        assert status.overall_risk_level in [RiskLevel.LOW, RiskLevel.MODERATE]

    @pytest.mark.asyncio
    async def test_correlation_limit_enforcement(self, mock_drawdown_tracker):
        """Test that correlation limits are enforced."""
        validator = RiskValidator(drawdown_tracker=mock_drawdown_tracker)

        # Positions already at 25% correlated exposure
        positions = [
            {"symbol": "BTCUSD", "value": 15000},
            {"symbol": "ETHUSD", "value": 10000},
        ]

        # Try to add another position in a correlated group
        result = await validator.validate_trade(
            symbol="SOLUSD",  # ALT_LAYER1 group
            requested_size_usd=10000,
            portfolio_value=100000,
            current_positions=positions,
            daily_pnl=0.0,
        )

        # Should be approved but potentially reduced
        assert result.approved is True
        # Max size may be reduced due to correlation limits


class TestEdgeCases:
    """Test edge cases and error handling."""

    @pytest.mark.asyncio
    async def test_empty_positions(self, mock_drawdown_tracker):
        """Test validation with empty positions list."""
        validator = RiskValidator(drawdown_tracker=mock_drawdown_tracker)

        result = await validator.validate_trade(
            symbol="BTCUSD",
            requested_size_usd=5000,
            portfolio_value=100000,
            current_positions=[],
            daily_pnl=0.0,
        )

        assert result.approved is True

    @pytest.mark.asyncio
    async def test_very_small_trade(self, mock_drawdown_tracker):
        """Test validation with very small trade size."""
        validator = RiskValidator(drawdown_tracker=mock_drawdown_tracker)

        result = await validator.validate_trade(
            symbol="BTCUSD",
            requested_size_usd=1,
            portfolio_value=100000,
            current_positions=[],
            daily_pnl=0.0,
        )

        assert result.approved is True
        assert float(result.max_allowed_size) == 1

    @pytest.mark.asyncio
    async def test_positive_daily_pnl(self, mock_drawdown_tracker):
        """Test that positive daily P&L doesn't cause issues."""
        validator = RiskValidator(drawdown_tracker=mock_drawdown_tracker)

        result = await validator.validate_trade(
            symbol="BTCUSD",
            requested_size_usd=5000,
            portfolio_value=100000,
            current_positions=[],
            daily_pnl=5000,  # Positive P&L
        )

        assert result.approved is True

    def test_correlation_group_case_sensitivity(self):
        """Test correlation group lookup is case-sensitive."""
        assert get_correlation_group("BTCUSD") == "BTC_CORRELATED"
        assert get_correlation_group("btcusd") == "UNCORRELATED"  # lowercase

    @pytest.mark.asyncio
    async def test_negative_portfolio_value(self, mock_drawdown_tracker):
        """Test handling of negative portfolio value."""
        validator = RiskValidator(drawdown_tracker=mock_drawdown_tracker)

        result = await validator.validate_trade(
            symbol="BTCUSD",
            requested_size_usd=1000,
            portfolio_value=-100,  # Invalid
            current_positions=[],
            daily_pnl=0.0,
        )

        assert result.approved is False
