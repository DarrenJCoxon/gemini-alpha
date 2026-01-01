"""
Tests for Story 5.4: Scale In/Out Position Management.

This test module covers:
- ScaleConfig configuration validation
- Average price calculations (weighted average)
- Realized P&L calculations
- Scale-in trigger detection
- Scale-out profit target detection
- ScaledPosition and ScaleOrder model behavior
"""

import os
import pytest
from decimal import Decimal
from datetime import datetime, timezone, timedelta
from unittest.mock import patch, MagicMock, AsyncMock


# =============================================================================
# ScaleConfig Tests
# =============================================================================

class TestScaleConfig:
    """Tests for ScaleConfig class."""

    def test_scale_config_defaults(self):
        """Test ScaleConfig with default values."""
        with patch.dict(os.environ, {}, clear=True):
            import importlib
            import config as config_module
            importlib.reload(config_module)

            scale_config = config_module.ScaleConfig()

            # Check default percentages
            assert scale_config.scale_in_pct_1 == 33.33
            assert scale_config.scale_in_pct_2 == 33.33
            assert scale_config.scale_in_pct_3 == 33.34

            # Check default triggers
            assert scale_config.scale_in_drop_2 == 5.0
            assert scale_config.scale_in_drop_3 == 10.0
            assert scale_config.scale_out_profit_1 == 10.0
            assert scale_config.scale_out_profit_2 == 20.0

            # Check timeout
            assert scale_config.scale_timeout_hours == 168  # 7 days

    def test_scale_config_from_env(self):
        """Test ScaleConfig reads from environment variables."""
        env_vars = {
            "NUM_SCALE_IN_LEVELS": "3",
            "SCALE_IN_PCT_1": "40.0",
            "SCALE_IN_PCT_2": "30.0",
            "SCALE_IN_PCT_3": "30.0",
            "SCALE_IN_DROP_2": "7.5",
            "SCALE_IN_DROP_3": "15.0",
            "SCALE_OUT_PROFIT_1": "15.0",
            "SCALE_OUT_PROFIT_2": "25.0",
            "SCALE_TIMEOUT_HOURS": "72",
        }
        with patch.dict(os.environ, env_vars, clear=True):
            import importlib
            import config as config_module
            importlib.reload(config_module)

            scale_config = config_module.ScaleConfig()

            assert scale_config.scale_in_pct_1 == 40.0
            assert scale_config.scale_in_pct_2 == 30.0
            assert scale_config.scale_in_pct_3 == 30.0
            assert scale_config.scale_in_drop_2 == 7.5
            assert scale_config.scale_in_drop_3 == 15.0
            assert scale_config.scale_out_profit_1 == 15.0
            assert scale_config.scale_out_profit_2 == 25.0
            assert scale_config.scale_timeout_hours == 72

    def test_get_scale_in_percentages(self):
        """Test get_scale_in_percentages returns list of percentages."""
        import config as config_module

        scale_config = config_module.ScaleConfig()
        percentages = scale_config.get_scale_in_percentages()

        assert isinstance(percentages, list)
        assert len(percentages) == 3
        assert percentages[0] == scale_config.scale_in_pct_1
        assert percentages[1] == scale_config.scale_in_pct_2
        assert percentages[2] == scale_config.scale_in_pct_3

    def test_get_scale_out_percentages(self):
        """Test get_scale_out_percentages returns list of percentages."""
        import config as config_module

        scale_config = config_module.ScaleConfig()
        percentages = scale_config.get_scale_out_percentages()

        assert isinstance(percentages, list)
        assert len(percentages) == 3
        assert abs(sum(percentages) - 100.0) < 0.1

    def test_scale_percentages_sum_to_100(self):
        """Test that scale percentages sum to 100%."""
        import config as config_module

        # Reload to get fresh config
        config = config_module.get_config()

        scale_in = config.scale.get_scale_in_percentages()
        scale_out = config.scale.get_scale_out_percentages()

        # Allow small floating point tolerance
        assert abs(sum(scale_in) - 100.0) < 0.1
        assert abs(sum(scale_out) - 100.0) < 0.1

    def test_scale_config_validate_success(self):
        """Test ScaleConfig validate() passes with valid config."""
        import config as config_module

        scale_config = config_module.ScaleConfig()
        # Should not raise
        scale_config.validate()

    def test_scale_config_validate_invalid_sum(self):
        """Test ScaleConfig validate() fails when percentages don't sum to 100."""
        import config as config_module

        scale_config = config_module.ScaleConfig()
        scale_config.scale_in_pct_1 = 50.0
        scale_config.scale_in_pct_2 = 50.0
        scale_config.scale_in_pct_3 = 50.0  # Sum = 150

        with pytest.raises(ValueError, match="must sum to 100"):
            scale_config.validate()

    def test_scale_config_validate_invalid_triggers(self):
        """Test ScaleConfig validate() fails with invalid trigger order."""
        import config as config_module

        scale_config = config_module.ScaleConfig()
        scale_config.scale_in_drop_2 = 15.0
        scale_config.scale_in_drop_3 = 10.0  # Should be greater than drop_2

        with pytest.raises(ValueError, match="must be greater than"):
            scale_config.validate()


# =============================================================================
# Average Price Tests
# =============================================================================

class TestAveragePriceCalculations:
    """Tests for average price calculation utilities."""

    def test_calculate_average_entry_single_entry(self):
        """Test average with single entry."""
        from services.average_price import calculate_average_entry

        entries = [
            {"size": Decimal("1.0"), "price": Decimal("100.0")},
        ]
        result = calculate_average_entry(entries)

        assert result.total_size == Decimal("1.0")
        assert result.total_cost == Decimal("100.0")
        assert result.average_price == Decimal("100.0")
        assert result.num_entries == 1

    def test_calculate_average_entry_multiple_entries(self):
        """Test weighted average with multiple entries."""
        from services.average_price import calculate_average_entry

        entries = [
            {"size": Decimal("1.0"), "price": Decimal("100.0")},
            {"size": Decimal("1.0"), "price": Decimal("90.0")},
            {"size": Decimal("1.0"), "price": Decimal("80.0")},
        ]
        result = calculate_average_entry(entries)

        assert result.total_size == Decimal("3.0")
        assert result.total_cost == Decimal("270.0")  # 100 + 90 + 80
        assert result.average_price == Decimal("90.0")  # 270/3 = 90
        assert result.num_entries == 3

    def test_calculate_average_entry_weighted(self):
        """Test weighted average gives more weight to larger positions."""
        from services.average_price import calculate_average_entry

        entries = [
            {"size": Decimal("2.0"), "price": Decimal("100.0")},  # Cost: 200
            {"size": Decimal("1.0"), "price": Decimal("80.0")},   # Cost: 80
        ]
        result = calculate_average_entry(entries)

        # Total: 3 units, 280 cost
        # Average: 280/3 = 93.333...
        assert result.total_size == Decimal("3.0")
        assert result.total_cost == Decimal("280.0")
        expected_avg = Decimal("280") / Decimal("3")
        assert abs(result.average_price - expected_avg) < Decimal("0.001")

    def test_calculate_average_entry_empty(self):
        """Test average with no entries."""
        from services.average_price import calculate_average_entry

        entries = []
        result = calculate_average_entry(entries)

        assert result.total_size == Decimal("0")
        assert result.average_price == Decimal("0")
        assert result.num_entries == 0

    def test_calculate_realized_pnl_profit(self):
        """Test realized P&L calculation with profit."""
        from services.average_price import calculate_realized_pnl

        entries = [
            {"size": Decimal("1.0"), "price": Decimal("100.0")},
            {"size": Decimal("1.0"), "price": Decimal("90.0")},
        ]
        exits = [
            {"size": Decimal("1.0"), "price": Decimal("110.0")},
        ]
        result = calculate_realized_pnl(entries, exits)

        # Average entry: (100 + 90) / 2 = 95
        # Sold 1 @ 110, cost basis 95 = +15 profit
        assert result.average_entry == Decimal("95.0")
        assert result.realized_pnl == Decimal("15.0")
        assert result.exited_size == Decimal("1.0")
        assert result.remaining_size == Decimal("1.0")

    def test_calculate_realized_pnl_loss(self):
        """Test realized P&L calculation with loss."""
        from services.average_price import calculate_realized_pnl

        entries = [
            {"size": Decimal("1.0"), "price": Decimal("100.0")},
        ]
        exits = [
            {"size": Decimal("1.0"), "price": Decimal("80.0")},
        ]
        result = calculate_realized_pnl(entries, exits)

        # Sold 1 @ 80, cost basis 100 = -20 loss
        assert result.realized_pnl == Decimal("-20.0")
        assert result.realized_pnl_pct == Decimal("-20.0")  # -20%

    def test_calculate_realized_pnl_multiple_exits(self):
        """Test P&L with multiple partial exits."""
        from services.average_price import calculate_realized_pnl

        entries = [
            {"size": Decimal("3.0"), "price": Decimal("100.0")},  # Total: 3 @ 100
        ]
        exits = [
            {"size": Decimal("1.0"), "price": Decimal("110.0")},  # +10
            {"size": Decimal("1.0"), "price": Decimal("120.0")},  # +20
        ]
        result = calculate_realized_pnl(entries, exits)

        # Sold 2 total, value = 110 + 120 = 230
        # Cost basis = 2 * 100 = 200
        # P&L = 230 - 200 = 30
        assert result.exited_size == Decimal("2.0")
        assert result.remaining_size == Decimal("1.0")
        assert result.realized_pnl == Decimal("30.0")

    def test_calculate_unrealized_pnl(self):
        """Test unrealized P&L calculation."""
        from services.average_price import calculate_unrealized_pnl

        entries = [
            {"size": Decimal("2.0"), "price": Decimal("100.0")},
        ]
        result = calculate_unrealized_pnl(entries, current_price=110.0)

        # 2 units * (110 - 100) = 20 unrealized profit
        assert result["unrealized_pnl"] == Decimal("20.0")
        assert result["remaining_size"] == Decimal("2.0")

    def test_calculate_total_pnl(self):
        """Test total P&L (realized + unrealized)."""
        from services.average_price import calculate_total_pnl

        entries = [
            {"size": Decimal("3.0"), "price": Decimal("100.0")},
        ]
        exits = [
            {"size": Decimal("1.0"), "price": Decimal("110.0")},  # +10 realized
        ]
        # Remaining 2 @ 115 = +30 unrealized
        result = calculate_total_pnl(entries, exits, current_price=115.0)

        assert result["realized_pnl"] == Decimal("10.0")
        # Unrealized: 2 * (115 - 100) = 30
        assert result["unrealized_pnl"] == Decimal("30.0")
        assert result["total_pnl"] == Decimal("40.0")


# =============================================================================
# ScaledPosition Model Tests
# =============================================================================

class TestScaledPositionModel:
    """Tests for ScaledPosition and ScaleOrder models."""

    def test_scaled_position_creation(self):
        """Test ScaledPosition model creation."""
        from models import ScaledPosition, ScaleDirection

        position = ScaledPosition(
            asset_id="test_asset",
            direction=ScaleDirection.SCALE_IN.value,
            target_size=Decimal("10.0"),
            remaining_size=Decimal("10.0"),
        )

        assert position.asset_id == "test_asset"
        assert position.direction == "SCALE_IN"
        assert position.is_active is True
        assert position.filled_size == Decimal("0")
        assert position.num_scales == 3
        assert position.scales_executed == 0

    def test_scaled_position_calculate_average(self):
        """Test average price calculation method."""
        from models import ScaledPosition, ScaleDirection

        position = ScaledPosition(
            asset_id="test_asset",
            direction=ScaleDirection.SCALE_IN.value,
            target_size=Decimal("10.0"),
            remaining_size=Decimal("5.0"),
            filled_size=Decimal("5.0"),
            total_cost=Decimal("500.0"),
        )

        avg = position.calculate_average_price()
        assert avg == Decimal("100.0")  # 500/5 = 100

    def test_scaled_position_is_complete(self):
        """Test is_complete method."""
        from models import ScaledPosition, ScaleDirection

        position = ScaledPosition(
            asset_id="test_asset",
            direction=ScaleDirection.SCALE_IN.value,
            target_size=Decimal("10.0"),
            remaining_size=Decimal("0"),
            num_scales=3,
            scales_executed=3,
        )

        assert position.is_complete() is True

        position.scales_executed = 2
        assert position.is_complete() is False

    def test_scaled_position_fill_percentage(self):
        """Test get_fill_percentage method."""
        from models import ScaledPosition, ScaleDirection

        position = ScaledPosition(
            asset_id="test_asset",
            direction=ScaleDirection.SCALE_IN.value,
            target_size=Decimal("10.0"),
            filled_size=Decimal("5.0"),
            remaining_size=Decimal("5.0"),
        )

        assert position.get_fill_percentage() == 50.0

    def test_scale_order_creation(self):
        """Test ScaleOrder model creation."""
        from models import ScaleOrder, ScaleStatus, ScaleTriggerType

        order = ScaleOrder(
            scaled_position_id="pos_123",
            scale_number=1,
            trigger_type=ScaleTriggerType.IMMEDIATE.value,
            target_size=Decimal("3.33"),
        )

        assert order.scale_number == 1
        assert order.status == ScaleStatus.PENDING.value
        assert order.trigger_type == "IMMEDIATE"
        assert order.executed_size is None

    def test_scale_order_is_triggered_immediate(self):
        """Test is_triggered for IMMEDIATE orders."""
        from models import ScaleOrder, ScaleStatus, ScaleTriggerType, ScaleDirection

        order = ScaleOrder(
            scaled_position_id="pos_123",
            scale_number=1,
            status=ScaleStatus.PENDING.value,
            trigger_type=ScaleTriggerType.IMMEDIATE.value,
            target_size=Decimal("3.33"),
        )

        # Immediate orders should always trigger
        assert order.is_triggered(100.0, ScaleDirection.SCALE_IN.value) is True

    def test_scale_order_is_triggered_price_drop(self):
        """Test is_triggered for PRICE_DROP orders (scale-in)."""
        from models import ScaleOrder, ScaleStatus, ScaleTriggerType, ScaleDirection

        order = ScaleOrder(
            scaled_position_id="pos_123",
            scale_number=2,
            status=ScaleStatus.PENDING.value,
            trigger_type=ScaleTriggerType.PRICE_DROP.value,
            trigger_price=Decimal("95.0"),  # Triggers at $95 or below
            target_size=Decimal("3.33"),
        )

        # Price above trigger - should NOT trigger
        assert order.is_triggered(100.0, ScaleDirection.SCALE_IN.value) is False

        # Price at trigger - should trigger
        assert order.is_triggered(95.0, ScaleDirection.SCALE_IN.value) is True

        # Price below trigger - should trigger
        assert order.is_triggered(90.0, ScaleDirection.SCALE_IN.value) is True

    def test_scale_order_is_triggered_profit_target(self):
        """Test is_triggered for PROFIT_TARGET orders (scale-out)."""
        from models import ScaleOrder, ScaleStatus, ScaleTriggerType, ScaleDirection

        order = ScaleOrder(
            scaled_position_id="pos_123",
            scale_number=1,
            status=ScaleStatus.PENDING.value,
            trigger_type=ScaleTriggerType.PROFIT_TARGET.value,
            trigger_price=Decimal("110.0"),  # Triggers at $110 or above
            target_size=Decimal("3.33"),
        )

        # Price below target - should NOT trigger
        assert order.is_triggered(100.0, ScaleDirection.SCALE_OUT.value) is False

        # Price at target - should trigger
        assert order.is_triggered(110.0, ScaleDirection.SCALE_OUT.value) is True

        # Price above target - should trigger
        assert order.is_triggered(120.0, ScaleDirection.SCALE_OUT.value) is True

    def test_scale_order_not_triggered_when_executed(self):
        """Test that already executed orders don't trigger."""
        from models import ScaleOrder, ScaleStatus, ScaleTriggerType, ScaleDirection

        order = ScaleOrder(
            scaled_position_id="pos_123",
            scale_number=1,
            status=ScaleStatus.EXECUTED.value,  # Already executed
            trigger_type=ScaleTriggerType.IMMEDIATE.value,
            target_size=Decimal("3.33"),
        )

        assert order.is_triggered(100.0, ScaleDirection.SCALE_IN.value) is False

    def test_scale_order_execution_value(self):
        """Test get_execution_value method."""
        from models import ScaleOrder, ScaleStatus, ScaleTriggerType

        order = ScaleOrder(
            scaled_position_id="pos_123",
            scale_number=1,
            status=ScaleStatus.EXECUTED.value,
            trigger_type=ScaleTriggerType.IMMEDIATE.value,
            target_size=Decimal("3.33"),
            executed_size=Decimal("3.33"),
            executed_price=Decimal("100.0"),
        )

        value = order.get_execution_value()
        assert value == Decimal("333.0")


# =============================================================================
# Scale Direction Enum Tests
# =============================================================================

class TestScaleEnums:
    """Tests for scale-related enums."""

    def test_scale_direction_values(self):
        """Test ScaleDirection enum values."""
        from models import ScaleDirection

        assert ScaleDirection.SCALE_IN.value == "SCALE_IN"
        assert ScaleDirection.SCALE_OUT.value == "SCALE_OUT"

    def test_scale_status_values(self):
        """Test ScaleStatus enum values."""
        from models import ScaleStatus

        assert ScaleStatus.PENDING.value == "PENDING"
        assert ScaleStatus.EXECUTED.value == "EXECUTED"
        assert ScaleStatus.CANCELLED.value == "CANCELLED"
        assert ScaleStatus.EXPIRED.value == "EXPIRED"

    def test_scale_trigger_type_values(self):
        """Test ScaleTriggerType enum values."""
        from models import ScaleTriggerType

        assert ScaleTriggerType.IMMEDIATE.value == "IMMEDIATE"
        assert ScaleTriggerType.PRICE_DROP.value == "PRICE_DROP"
        assert ScaleTriggerType.CAPITULATION.value == "CAPITULATION"
        assert ScaleTriggerType.PROFIT_TARGET.value == "PROFIT_TARGET"
        assert ScaleTriggerType.TRAILING_STOP.value == "TRAILING_STOP"


# =============================================================================
# Integration Tests (with mocks)
# =============================================================================

class TestScaleInTriggerDetection:
    """Tests for scale-in trigger detection logic."""

    def test_scale_in_trigger_calculation(self):
        """Test that scale-in trigger prices are calculated correctly."""
        import config as config_module

        scale_config = config_module.ScaleConfig()
        first_entry_price = 100.0

        # Scale 2 triggers at -5%
        scale_2_trigger = first_entry_price * (1 - scale_config.scale_in_drop_2 / 100)
        assert scale_2_trigger == 95.0

        # Scale 3 triggers at -10%
        scale_3_trigger = first_entry_price * (1 - scale_config.scale_in_drop_3 / 100)
        assert scale_3_trigger == 90.0

    def test_scale_out_profit_target_calculation(self):
        """Test that scale-out profit targets are calculated correctly."""
        import config as config_module

        scale_config = config_module.ScaleConfig()
        average_entry = 100.0

        # Scale 1 exits at +10%
        scale_1_target = average_entry * (1 + scale_config.scale_out_profit_1 / 100)
        assert abs(scale_1_target - 110.0) < 0.001

        # Scale 2 exits at +20%
        scale_2_target = average_entry * (1 + scale_config.scale_out_profit_2 / 100)
        assert abs(scale_2_target - 120.0) < 0.001


class TestPartialExitCalculations:
    """Tests for partial exit position size calculations."""

    def test_partial_exit_reduces_position(self):
        """Test that partial exits correctly reduce position size."""
        from decimal import Decimal

        original_size = Decimal("3.0")

        # Use the actual percentages from config (33.33, 33.33, 33.34 = 100)
        scale_pcts = [Decimal("33.33"), Decimal("33.33"), Decimal("33.34")]

        remaining = original_size

        # After all 3 exits
        for pct in scale_pcts:
            exit_size = original_size * pct / Decimal("100")
            remaining -= exit_size
            assert remaining < original_size  # Always reducing

        # Should be approximately zero (allow for rounding)
        # With 33.33 + 33.33 + 33.34 = 100, we get exactly 0
        assert abs(remaining) < Decimal("0.01")


# =============================================================================
# Config Integration with Main Config
# =============================================================================

class TestConfigIntegration:
    """Tests for ScaleConfig integration with main Config."""

    def test_config_has_scale_attribute(self):
        """Test that main Config includes scale configuration."""
        import config as config_module

        cfg = config_module.Config()
        assert hasattr(cfg, "scale")
        assert isinstance(cfg.scale, config_module.ScaleConfig)

    def test_get_config_includes_scale(self):
        """Test that get_config returns config with scale settings."""
        import config as config_module

        cfg = config_module.get_config()
        assert hasattr(cfg, "scale")

        # Check default values are accessible
        assert cfg.scale.num_scale_in_levels == 3
        assert cfg.scale.num_scale_out_levels == 3
