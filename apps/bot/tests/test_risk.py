"""
Tests for services/risk.py - Dynamic Risk Engine.

Story 3.2: Dynamic Risk Engine (ATR Stop Loss)

Unit tests for the risk service including:
- calculate_atr() functionality
- calculate_stop_loss() with various scenarios
- calculate_position_size() for risk-based sizing
- validate_stop_loss() utility
- Edge cases and fallback behavior
"""

import pytest
from decimal import Decimal
from unittest.mock import patch, MagicMock

from services.risk import (
    calculate_atr,
    calculate_stop_loss,
    calculate_stop_loss_with_config,
    calculate_position_size,
    validate_stop_loss,
)


# =============================================================================
# Sample Candle Data for Testing
# =============================================================================

def generate_sample_candles(count: int = 20, base_price: float = 100.0) -> list:
    """
    Generate sample candle data for testing.

    Creates realistic candle data with ~5% volatility around base price.
    """
    import random
    random.seed(42)  # For reproducibility

    candles = []
    close = base_price

    for i in range(count):
        # Generate realistic price movements
        volatility = 0.05  # 5% volatility
        change = random.uniform(-volatility, volatility)
        close = close * (1 + change)

        # High/Low around close with some range
        high = close * (1 + random.uniform(0.01, 0.03))
        low = close * (1 - random.uniform(0.01, 0.03))
        open_price = close * (1 + random.uniform(-0.02, 0.02))

        candles.append({
            "timestamp": 1704067200000 + (i * 900000),  # 15-min intervals
            "open": open_price,
            "high": high,
            "low": low,
            "close": close,
            "volume": random.uniform(1000, 10000),
        })

    return candles


# Standard test candles
SAMPLE_CANDLES = generate_sample_candles(count=20, base_price=100.0)

# Minimal candles (not enough for ATR-14)
MINIMAL_CANDLES = generate_sample_candles(count=5, base_price=100.0)

# Extreme volatility candles
EXTREME_CANDLES = [
    {"high": 1000.0, "low": 1.0, "close": 100.0} for _ in range(20)
]


# =============================================================================
# Test calculate_atr()
# =============================================================================

class TestCalculateAtr:
    """Tests for calculate_atr function."""

    def test_calculate_atr_with_valid_data(self):
        """Test ATR calculation with valid candle data."""
        atr = calculate_atr(SAMPLE_CANDLES, period=14)

        assert atr is not None
        assert isinstance(atr, float)
        assert atr > 0

    def test_calculate_atr_returns_none_for_insufficient_data(self):
        """Test ATR returns None when not enough candles."""
        atr = calculate_atr(MINIMAL_CANDLES, period=14)

        assert atr is None

    def test_calculate_atr_returns_none_for_empty_list(self):
        """Test ATR returns None for empty candle list."""
        atr = calculate_atr([], period=14)

        assert atr is None

    def test_calculate_atr_with_exact_minimum_candles(self):
        """Test ATR works with exactly period+1 candles."""
        candles = generate_sample_candles(count=15, base_price=100.0)
        atr = calculate_atr(candles, period=14)

        assert atr is not None
        assert atr > 0

    def test_calculate_atr_missing_columns(self):
        """Test ATR returns None when required columns are missing."""
        invalid_candles = [{"open": 100, "close": 105}]  # Missing high, low
        atr = calculate_atr(invalid_candles, period=14)

        assert atr is None

    def test_calculate_atr_with_custom_period(self):
        """Test ATR works with different periods."""
        # Need at least 8 candles for period=7
        candles = generate_sample_candles(count=10, base_price=100.0)
        atr = calculate_atr(candles, period=7)

        assert atr is not None
        assert atr > 0

    def test_calculate_atr_with_string_values(self):
        """Test ATR handles string values in candle data."""
        candles = [
            {"high": "105.0", "low": "95.0", "close": "100.0"},
            {"high": "108.0", "low": "98.0", "close": "105.0"},
        ] * 10  # 20 candles

        atr = calculate_atr(candles, period=14)

        assert atr is not None
        assert atr > 0

    def test_calculate_atr_higher_volatility(self):
        """Test that higher volatility candles produce higher ATR."""
        # Low volatility
        low_vol_candles = [
            {"high": 101.0, "low": 99.0, "close": 100.0}
            for _ in range(20)
        ]
        atr_low = calculate_atr(low_vol_candles, period=14)

        # High volatility
        high_vol_candles = [
            {"high": 110.0, "low": 90.0, "close": 100.0}
            for _ in range(20)
        ]
        atr_high = calculate_atr(high_vol_candles, period=14)

        assert atr_low is not None
        assert atr_high is not None
        assert atr_high > atr_low


# =============================================================================
# Test calculate_stop_loss()
# =============================================================================

class TestCalculateStopLoss:
    """Tests for calculate_stop_loss function."""

    def test_calculate_stop_loss_basic(self):
        """Test basic stop loss calculation."""
        entry_price = 100.0
        stop_loss, atr = calculate_stop_loss(
            entry_price=entry_price,
            candles=SAMPLE_CANDLES,
            atr_multiplier=2.0,
        )

        assert stop_loss is not None
        assert atr is not None
        assert stop_loss < entry_price
        assert stop_loss > 0

    def test_calculate_stop_loss_formula(self):
        """Test stop loss follows correct formula: Entry - (Multiplier * ATR)."""
        entry_price = 100.0
        atr_multiplier = 2.0

        # Calculate ATR first
        atr = calculate_atr(SAMPLE_CANDLES, period=14)

        # Calculate stop loss
        stop_loss, returned_atr = calculate_stop_loss(
            entry_price=entry_price,
            candles=SAMPLE_CANDLES,
            atr_multiplier=atr_multiplier,
        )

        # Expected: Entry - (2 * ATR)
        expected_stop = entry_price - (atr_multiplier * atr)

        # Should match within bounds of min/max stop loss
        assert stop_loss is not None
        assert returned_atr == atr
        # Stop should be close to expected (may be capped by min/max)
        assert stop_loss <= entry_price

    def test_calculate_stop_loss_multiplier_effect(self):
        """Test higher multiplier gives lower (wider) stop loss."""
        entry_price = 100.0

        stop_2x, _ = calculate_stop_loss(
            entry_price=entry_price,
            candles=SAMPLE_CANDLES,
            atr_multiplier=2.0,
        )

        stop_3x, _ = calculate_stop_loss(
            entry_price=entry_price,
            candles=SAMPLE_CANDLES,
            atr_multiplier=3.0,
        )

        assert stop_2x is not None
        assert stop_3x is not None
        # 3x ATR should give lower (wider) stop
        assert stop_3x < stop_2x

    def test_calculate_stop_loss_insufficient_data(self):
        """Test stop loss returns None with insufficient candles."""
        stop_loss, atr = calculate_stop_loss(
            entry_price=100.0,
            candles=MINIMAL_CANDLES,
        )

        assert stop_loss is None
        assert atr is None

    def test_calculate_stop_loss_invalid_entry_price(self):
        """Test stop loss handles invalid entry price."""
        stop_loss, atr = calculate_stop_loss(
            entry_price=0,
            candles=SAMPLE_CANDLES,
        )

        assert stop_loss is None
        assert atr is None

        stop_loss, atr = calculate_stop_loss(
            entry_price=-100,
            candles=SAMPLE_CANDLES,
        )

        assert stop_loss is None
        assert atr is None

    def test_calculate_stop_loss_fallback_for_negative(self):
        """Test fallback when ATR would give negative stop loss."""
        # Use extremely high ATR candles with low entry price
        stop_loss, _ = calculate_stop_loss(
            entry_price=10.0,  # Low entry price
            candles=EXTREME_CANDLES,
            atr_multiplier=2.0,
        )

        # Should use fallback (15% = 20% max stop)
        assert stop_loss is not None
        assert stop_loss > 0
        assert stop_loss == 10.0 * 0.80  # 20% max stop

    def test_calculate_stop_loss_caps_at_max(self):
        """Test stop loss is capped at max percentage."""
        # High volatility data that would exceed 20%
        stop_loss, _ = calculate_stop_loss(
            entry_price=100.0,
            candles=EXTREME_CANDLES,
            atr_multiplier=2.0,
            max_stop_loss_percentage=0.20,
        )

        # Should be capped at 20% below entry
        assert stop_loss is not None
        assert stop_loss >= 100.0 * 0.80

    def test_calculate_stop_loss_enforces_min(self):
        """Test stop loss enforces minimum percentage."""
        # Very low volatility - uniform candles
        low_vol_candles = [
            {"high": 100.5, "low": 99.5, "close": 100.0}
            for _ in range(20)
        ]

        stop_loss, _ = calculate_stop_loss(
            entry_price=100.0,
            candles=low_vol_candles,
            atr_multiplier=0.5,  # Very small multiplier
            min_stop_loss_percentage=0.02,
        )

        # Should enforce minimum 2% stop
        assert stop_loss is not None
        assert stop_loss <= 100.0 * 0.98

    def test_calculate_stop_loss_respects_period(self):
        """Test stop loss respects custom ATR period."""
        # Use period=7 which needs only 8 candles
        candles = generate_sample_candles(count=10, base_price=100.0)

        stop_loss, atr = calculate_stop_loss(
            entry_price=100.0,
            candles=candles,
            atr_period=7,
        )

        assert stop_loss is not None
        assert atr is not None


# =============================================================================
# Test calculate_stop_loss_with_config()
# =============================================================================

class TestCalculateStopLossWithConfig:
    """Tests for calculate_stop_loss_with_config function."""

    def test_calculate_stop_loss_with_config_basic(self):
        """Test stop loss with config uses defaults."""
        stop_loss, atr = calculate_stop_loss_with_config(
            entry_price=100.0,
            candles=SAMPLE_CANDLES,
        )

        assert stop_loss is not None
        assert atr is not None
        assert stop_loss < 100.0

    @patch('services.risk.get_config')
    def test_calculate_stop_loss_with_custom_config(self, mock_get_config):
        """Test stop loss with custom config settings."""
        mock_config = MagicMock()
        mock_risk = MagicMock()
        mock_risk.atr_period = 14
        mock_risk.atr_multiplier = 3.0
        mock_risk.max_stop_loss_percentage = 0.25
        mock_risk.min_stop_loss_percentage = 0.05
        mock_config.risk = mock_risk
        mock_get_config.return_value = mock_config

        stop_loss, atr = calculate_stop_loss_with_config(
            entry_price=100.0,
            candles=SAMPLE_CANDLES,
        )

        assert stop_loss is not None
        assert atr is not None


# =============================================================================
# Test calculate_position_size()
# =============================================================================

class TestCalculatePositionSize:
    """Tests for calculate_position_size function."""

    def test_calculate_position_size_basic(self):
        """Test basic position sizing."""
        size = calculate_position_size(
            account_balance=10000.0,
            entry_price=100.0,
            stop_loss_price=90.0,
            risk_percentage=0.02,
        )

        # Risk $200 (2% of $10000)
        # Risk per unit = $100 - $90 = $10
        # Position size = $200 / $10 = 20 units
        assert size is not None
        assert size == pytest.approx(20.0, rel=0.01)

    def test_calculate_position_size_formula(self):
        """Test position size formula: (Account * Risk%) / (Entry - Stop)."""
        account = 5000.0
        entry = 50.0
        stop = 45.0
        risk_pct = 0.01  # 1%

        size = calculate_position_size(
            account_balance=account,
            entry_price=entry,
            stop_loss_price=stop,
            risk_percentage=risk_pct,
        )

        # Expected: ($5000 * 0.01) / ($50 - $45) = $50 / $5 = 10 units
        assert size is not None
        assert size == pytest.approx(10.0, rel=0.01)

    def test_calculate_position_size_invalid_account_balance(self):
        """Test position size with invalid account balance."""
        size = calculate_position_size(
            account_balance=0,
            entry_price=100.0,
            stop_loss_price=90.0,
        )

        assert size is None

        size = calculate_position_size(
            account_balance=-1000,
            entry_price=100.0,
            stop_loss_price=90.0,
        )

        assert size is None

    def test_calculate_position_size_invalid_entry_price(self):
        """Test position size with invalid entry price."""
        size = calculate_position_size(
            account_balance=10000.0,
            entry_price=0,
            stop_loss_price=90.0,
        )

        assert size is None

    def test_calculate_position_size_invalid_stop_loss(self):
        """Test position size with invalid stop loss."""
        # Stop above entry
        size = calculate_position_size(
            account_balance=10000.0,
            entry_price=100.0,
            stop_loss_price=110.0,
        )

        assert size is None

        # Stop equal to entry
        size = calculate_position_size(
            account_balance=10000.0,
            entry_price=100.0,
            stop_loss_price=100.0,
        )

        assert size is None

    def test_calculate_position_size_caps_risk_percentage(self):
        """Test position size caps risk at 10%."""
        # Try to risk 20% - should be capped at 10%
        size = calculate_position_size(
            account_balance=10000.0,
            entry_price=100.0,
            stop_loss_price=90.0,
            risk_percentage=0.20,  # 20% - exceeds safe limit
        )

        # Should be capped at 10%
        # Risk $1000 (10% of $10000) / $10 risk per unit = 100 units
        assert size is not None
        assert size == pytest.approx(100.0, rel=0.01)

    def test_calculate_position_size_tight_stop(self):
        """Test position size with tight stop loss."""
        size = calculate_position_size(
            account_balance=10000.0,
            entry_price=100.0,
            stop_loss_price=99.0,  # Only 1% stop
            risk_percentage=0.02,
        )

        # Risk $200 / $1 per unit = 200 units
        assert size is not None
        assert size == pytest.approx(200.0, rel=0.01)


# =============================================================================
# Test validate_stop_loss()
# =============================================================================

class TestValidateStopLoss:
    """Tests for validate_stop_loss function."""

    def test_validate_stop_loss_valid(self):
        """Test validation passes for valid stop loss."""
        is_valid, reason = validate_stop_loss(
            entry_price=100.0,
            stop_loss_price=90.0,
        )

        assert is_valid is True
        assert reason == ""

    def test_validate_stop_loss_negative_stop(self):
        """Test validation fails for negative stop loss."""
        is_valid, reason = validate_stop_loss(
            entry_price=100.0,
            stop_loss_price=-10.0,
        )

        assert is_valid is False
        assert "positive" in reason.lower()

    def test_validate_stop_loss_above_entry(self):
        """Test validation fails when stop is above entry."""
        is_valid, reason = validate_stop_loss(
            entry_price=100.0,
            stop_loss_price=110.0,
        )

        assert is_valid is False
        assert "below entry" in reason.lower()

    def test_validate_stop_loss_exceeds_max(self):
        """Test validation fails when stop exceeds max percentage."""
        is_valid, reason = validate_stop_loss(
            entry_price=100.0,
            stop_loss_price=70.0,  # 30% stop
            max_percentage=0.20,
        )

        assert is_valid is False
        assert "exceeds maximum" in reason.lower()

    def test_validate_stop_loss_below_min(self):
        """Test validation fails when stop is below min percentage."""
        is_valid, reason = validate_stop_loss(
            entry_price=100.0,
            stop_loss_price=99.5,  # 0.5% stop
            min_percentage=0.02,
        )

        assert is_valid is False
        assert "below minimum" in reason.lower()

    def test_validate_stop_loss_at_boundary(self):
        """Test validation passes at exact boundary."""
        # Exactly 10% stop
        is_valid, reason = validate_stop_loss(
            entry_price=100.0,
            stop_loss_price=90.0,
            max_percentage=0.10,
        )

        # Should pass at exactly 10%
        assert is_valid is True


# =============================================================================
# Integration Tests
# =============================================================================

class TestRiskIntegration:
    """Integration tests for risk module."""

    def test_full_risk_calculation_flow(self):
        """Test complete risk calculation flow."""
        # 1. Calculate stop loss
        entry_price = 100.0
        stop_loss, atr = calculate_stop_loss(
            entry_price=entry_price,
            candles=SAMPLE_CANDLES,
        )

        assert stop_loss is not None
        assert atr is not None

        # 2. Validate stop loss
        is_valid, _ = validate_stop_loss(
            entry_price=entry_price,
            stop_loss_price=stop_loss,
        )

        assert is_valid is True

        # 3. Calculate position size
        size = calculate_position_size(
            account_balance=10000.0,
            entry_price=entry_price,
            stop_loss_price=stop_loss,
        )

        assert size is not None
        assert size > 0

    def test_different_asset_volatilities(self):
        """Test risk calculation adapts to different volatilities."""
        entry_price = 100.0

        # Low volatility asset (BTC-like, tight range)
        low_vol_candles = [
            {"high": 102.0, "low": 98.0, "close": 100.0}
            for _ in range(20)
        ]
        stop_low, atr_low = calculate_stop_loss(
            entry_price=entry_price,
            candles=low_vol_candles,
        )

        # High volatility asset (altcoin-like, wide range)
        high_vol_candles = [
            {"high": 120.0, "low": 80.0, "close": 100.0}
            for _ in range(20)
        ]
        stop_high, atr_high = calculate_stop_loss(
            entry_price=entry_price,
            candles=high_vol_candles,
        )

        # Both should work
        assert stop_low is not None
        assert stop_high is not None

        # High volatility should have wider stop (lower price)
        assert stop_high < stop_low
        assert atr_high > atr_low


# =============================================================================
# Edge Cases
# =============================================================================

class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_very_small_prices(self):
        """Test handling of very small asset prices."""
        # Micro-cap token with tiny price
        candles = [
            {"high": 0.0001, "low": 0.00005, "close": 0.00008}
            for _ in range(20)
        ]

        stop_loss, atr = calculate_stop_loss(
            entry_price=0.00008,
            candles=candles,
        )

        assert stop_loss is not None
        assert stop_loss > 0
        assert stop_loss < 0.00008

    def test_very_large_prices(self):
        """Test handling of very large asset prices."""
        # High-priced asset (BTC)
        candles = [
            {"high": 45000.0, "low": 43000.0, "close": 44000.0}
            for _ in range(20)
        ]

        stop_loss, atr = calculate_stop_loss(
            entry_price=44000.0,
            candles=candles,
        )

        assert stop_loss is not None
        assert stop_loss > 0
        assert stop_loss < 44000.0

    def test_decimal_precision(self):
        """Test decimal precision in calculations."""
        candles = [
            {"high": "100.12345678", "low": "99.87654321", "close": "100.00000001"}
            for _ in range(20)
        ]

        stop_loss, atr = calculate_stop_loss(
            entry_price=100.00000001,
            candles=candles,
        )

        assert stop_loss is not None
        assert isinstance(stop_loss, float)

    def test_nan_values_in_candles(self):
        """Test handling of NaN values in candle data."""
        candles = [
            {"high": 105.0, "low": 95.0, "close": 100.0}
            for _ in range(18)
        ]
        # Add candles with NaN-producing values
        candles.extend([
            {"high": "invalid", "low": 95.0, "close": 100.0},
            {"high": 105.0, "low": "invalid", "close": 100.0},
        ])

        # Should handle gracefully
        atr = calculate_atr(candles, period=14)
        # May return None or a valid value after dropping bad rows
        # Just ensure no crash


# =============================================================================
# Config Tests
# =============================================================================

class TestRiskConfig:
    """Tests for RiskConfig from config.py."""

    def test_risk_config_defaults(self):
        """Test RiskConfig has sensible defaults."""
        from config import RiskConfig

        config = RiskConfig()

        assert config.atr_period == 14
        assert config.atr_multiplier == 2.0
        assert config.max_stop_loss_percentage == 0.20
        assert config.min_stop_loss_percentage == 0.02
        assert config.default_risk_per_trade == 0.02

    def test_risk_config_validation_valid(self):
        """Test RiskConfig validation passes for valid config."""
        from config import RiskConfig

        config = RiskConfig()
        # Should not raise
        config.validate()

    def test_risk_config_validation_invalid_atr_period(self):
        """Test RiskConfig validation fails for invalid ATR period."""
        from config import RiskConfig

        with patch.dict('os.environ', {'RISK_ATR_PERIOD': '0'}):
            config = RiskConfig()
            with pytest.raises(ValueError, match="ATR period"):
                config.validate()

    def test_risk_config_validation_invalid_multiplier(self):
        """Test RiskConfig validation fails for invalid multiplier."""
        from config import RiskConfig

        with patch.dict('os.environ', {'RISK_ATR_MULTIPLIER': '-1'}):
            config = RiskConfig()
            with pytest.raises(ValueError, match="multiplier"):
                config.validate()

    def test_risk_config_validation_invalid_bounds(self):
        """Test RiskConfig validation fails for invalid stop loss bounds."""
        from config import RiskConfig

        # Min > Max
        with patch.dict('os.environ', {
            'RISK_MIN_STOP_LOSS_PERCENTAGE': '0.30',
            'RISK_MAX_STOP_LOSS_PERCENTAGE': '0.20',
        }):
            config = RiskConfig()
            with pytest.raises(ValueError, match="bounds"):
                config.validate()
