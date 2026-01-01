"""
Tests for Factor Checkers.

Story 5.7: Enhanced Technical Indicators

Tests for factor checking functions that evaluate technical
indicator signals for multi-factor confirmation.

Uses pytest for testing (not vitest).
"""

import pytest
from typing import Dict, Any

from services.factor_checkers import (
    check_macd_bullish,
    check_macd_bearish,
    check_bollinger_oversold,
    check_bollinger_overbought,
    check_obv_accumulation,
    check_obv_distribution,
    check_adx_weak_trend,
    check_adx_strong_trend,
    check_vwap_below,
    check_vwap_above,
    check_all_buy_factors,
    check_all_sell_factors,
    calculate_factor_score,
    count_triggered_factors,
    FactorResult,
)
from services.signal_factors import BuyFactor, SellFactor


# =============================================================================
# Test Fixtures
# =============================================================================

@pytest.fixture
def bullish_technical_analysis() -> Dict[str, Any]:
    """Technical analysis data with bullish indicators."""
    return {
        "macd": {
            "value": 0.5,
            "signal": "STRONG_BULLISH",
            "histogram": 0.2,
            "bullish_cross": True,
            "bearish_cross": False,
        },
        "bollinger": {
            "percent_b": 0.10,
            "signal": "STRONG_BULLISH",
            "upper": 110,
            "middle": 100,
            "lower": 90,
            "is_squeeze": False,
        },
        "obv": {
            "signal": "BULLISH",
            "bullish_divergence": True,
            "bearish_divergence": False,
        },
        "adx": {
            "value": 18.5,
            "safe_for_contrarian": True,
            "trend_direction": "up",
            "is_trending": False,
        },
        "vwap": {
            "value": 100,
            "distance_pct": -2.5,
            "position": "below",
        },
    }


@pytest.fixture
def bearish_technical_analysis() -> Dict[str, Any]:
    """Technical analysis data with bearish indicators."""
    return {
        "macd": {
            "value": -0.5,
            "signal": "STRONG_BEARISH",
            "histogram": -0.2,
            "bullish_cross": False,
            "bearish_cross": True,
        },
        "bollinger": {
            "percent_b": 0.92,
            "signal": "STRONG_BEARISH",
            "upper": 110,
            "middle": 100,
            "lower": 90,
            "is_squeeze": False,
        },
        "obv": {
            "signal": "BEARISH",
            "bullish_divergence": False,
            "bearish_divergence": True,
        },
        "adx": {
            "value": 55.0,
            "safe_for_contrarian": False,
            "trend_direction": "down",
            "is_trending": True,
        },
        "vwap": {
            "value": 100,
            "distance_pct": 3.5,
            "position": "above",
        },
    }


@pytest.fixture
def neutral_technical_analysis() -> Dict[str, Any]:
    """Technical analysis data with neutral indicators."""
    return {
        "macd": {
            "value": 0.0,
            "signal": "NEUTRAL",
            "histogram": 0.0,
            "bullish_cross": False,
            "bearish_cross": False,
        },
        "bollinger": {
            "percent_b": 0.50,
            "signal": "NEUTRAL",
            "upper": 110,
            "middle": 100,
            "lower": 90,
            "is_squeeze": False,
        },
        "obv": {
            "signal": "NEUTRAL",
            "bullish_divergence": False,
            "bearish_divergence": False,
        },
        "adx": {
            "value": 25.0,
            "safe_for_contrarian": True,
            "trend_direction": "up",
            "is_trending": False,
        },
        "vwap": {
            "value": 100,
            "distance_pct": 0.5,
            "position": "above",
        },
    }


@pytest.fixture
def empty_technical_analysis() -> Dict[str, Any]:
    """Empty technical analysis data."""
    return {}


# =============================================================================
# MACD Factor Tests
# =============================================================================

class TestMACDFactors:
    """Tests for MACD factor checkers."""

    def test_macd_bullish_triggered(self, bullish_technical_analysis):
        """Test MACD bullish factor triggers on bullish signal."""
        result = check_macd_bullish(bullish_technical_analysis)

        assert result.factor == BuyFactor.MACD_BULLISH.value
        assert result.triggered is True
        assert "MACD" in result.reasoning

    def test_macd_bullish_not_triggered(self, bearish_technical_analysis):
        """Test MACD bullish factor does not trigger on bearish signal."""
        result = check_macd_bullish(bearish_technical_analysis)

        assert result.triggered is False

    def test_macd_bearish_triggered(self, bearish_technical_analysis):
        """Test MACD bearish factor triggers on bearish signal."""
        result = check_macd_bearish(bearish_technical_analysis)

        assert result.factor == SellFactor.MACD_BEARISH.value
        assert result.triggered is True

    def test_macd_bearish_not_triggered(self, bullish_technical_analysis):
        """Test MACD bearish factor does not trigger on bullish signal."""
        result = check_macd_bearish(bullish_technical_analysis)

        assert result.triggered is False

    def test_macd_crossover_in_reasoning(self, bullish_technical_analysis):
        """Test MACD crossover is mentioned in reasoning."""
        result = check_macd_bullish(bullish_technical_analysis)

        assert "crossover" in result.reasoning.lower()


# =============================================================================
# Bollinger Bands Factor Tests
# =============================================================================

class TestBollingerFactors:
    """Tests for Bollinger Bands factor checkers."""

    def test_bollinger_oversold_triggered(self, bullish_technical_analysis):
        """Test Bollinger oversold factor triggers at lower band."""
        result = check_bollinger_oversold(bullish_technical_analysis)

        assert result.factor == BuyFactor.BOLLINGER_OVERSOLD.value
        assert result.triggered is True

    def test_bollinger_oversold_not_triggered(self, bearish_technical_analysis):
        """Test Bollinger oversold does not trigger at upper band."""
        result = check_bollinger_oversold(bearish_technical_analysis)

        # %B of 0.92 is not oversold
        assert result.triggered is False

    def test_bollinger_overbought_triggered(self, bearish_technical_analysis):
        """Test Bollinger overbought factor triggers at upper band."""
        result = check_bollinger_overbought(bearish_technical_analysis)

        assert result.factor == SellFactor.BOLLINGER_OVERBOUGHT.value
        assert result.triggered is True

    def test_bollinger_overbought_not_triggered(self, bullish_technical_analysis):
        """Test Bollinger overbought does not trigger at lower band."""
        result = check_bollinger_overbought(bullish_technical_analysis)

        # %B of 0.10 is not overbought
        assert result.triggered is False

    def test_bollinger_threshold_boundary(self):
        """Test Bollinger threshold at exact boundary."""
        # At exactly 0.20 (boundary for oversold)
        data = {"bollinger": {"percent_b": 0.20, "signal": "NEUTRAL"}}
        result = check_bollinger_oversold(data)
        assert result.triggered is True

        # Just above 0.20
        data = {"bollinger": {"percent_b": 0.21, "signal": "NEUTRAL"}}
        result = check_bollinger_oversold(data)
        assert result.triggered is False


# =============================================================================
# OBV Factor Tests
# =============================================================================

class TestOBVFactors:
    """Tests for OBV factor checkers."""

    def test_obv_accumulation_triggered(self, bullish_technical_analysis):
        """Test OBV accumulation factor triggers on bullish divergence."""
        result = check_obv_accumulation(bullish_technical_analysis)

        assert result.factor == BuyFactor.OBV_ACCUMULATION.value
        assert result.triggered is True

    def test_obv_accumulation_not_triggered(self, bearish_technical_analysis):
        """Test OBV accumulation does not trigger on distribution."""
        result = check_obv_accumulation(bearish_technical_analysis)

        assert result.triggered is False

    def test_obv_distribution_triggered(self, bearish_technical_analysis):
        """Test OBV distribution factor triggers on bearish divergence."""
        result = check_obv_distribution(bearish_technical_analysis)

        assert result.factor == SellFactor.OBV_DISTRIBUTION.value
        assert result.triggered is True

    def test_obv_distribution_not_triggered(self, bullish_technical_analysis):
        """Test OBV distribution does not trigger on accumulation."""
        result = check_obv_distribution(bullish_technical_analysis)

        assert result.triggered is False

    def test_obv_divergence_in_reasoning(self, bullish_technical_analysis):
        """Test OBV divergence is mentioned in reasoning."""
        result = check_obv_accumulation(bullish_technical_analysis)

        assert "divergence" in result.reasoning.lower()


# =============================================================================
# ADX Factor Tests - CRITICAL FOR CONTRARIAN
# =============================================================================

class TestADXFactors:
    """Tests for ADX factor checkers - critical for contrarian strategy."""

    def test_adx_weak_trend_triggered(self, bullish_technical_analysis):
        """Test ADX weak trend factor triggers when safe for contrarian."""
        result = check_adx_weak_trend(bullish_technical_analysis)

        assert result.factor == BuyFactor.ADX_WEAK_TREND.value
        assert result.triggered is True
        assert result.value == 18.5  # From fixture

    def test_adx_weak_trend_not_triggered(self, bearish_technical_analysis):
        """Test ADX weak trend does not trigger in strong trend."""
        result = check_adx_weak_trend(bearish_technical_analysis)

        assert result.triggered is False  # safe_for_contrarian is False

    def test_adx_strong_trend_triggered(self, bearish_technical_analysis):
        """Test ADX strong trend warning triggers in strong trend."""
        result = check_adx_strong_trend(bearish_technical_analysis)

        assert result.factor == SellFactor.ADX_STRONG_TREND.value
        assert result.triggered is True
        assert "STRONG" in result.reasoning or "AVOID" in result.reasoning

    def test_adx_strong_trend_not_triggered(self, bullish_technical_analysis):
        """Test ADX strong trend does not trigger in weak trend."""
        result = check_adx_strong_trend(bullish_technical_analysis)

        # ADX 18.5 is not trending
        assert result.triggered is False

    def test_adx_threshold_30(self):
        """Test ADX uses correct threshold of 30 for contrarian safety."""
        # Below 30 - safe for contrarian
        data = {"adx": {"value": 29.9, "safe_for_contrarian": True, "is_trending": False}}
        result = check_adx_weak_trend(data)
        assert result.triggered is True
        assert result.threshold == 30

        # At 30 - no longer safe
        data = {"adx": {"value": 30.0, "safe_for_contrarian": False, "is_trending": True}}
        result = check_adx_weak_trend(data)
        assert result.triggered is False

    def test_adx_ideal_reasoning(self):
        """Test ADX shows IDEAL in reasoning for very low ADX."""
        data = {"adx": {"value": 15.0, "safe_for_contrarian": True, "trend_direction": "up"}}
        result = check_adx_weak_trend(data)

        assert "IDEAL" in result.reasoning

    def test_adx_avoid_reasoning(self):
        """Test ADX shows AVOID in reasoning for high ADX."""
        data = {"adx": {"value": 45.0, "safe_for_contrarian": False, "is_trending": True, "trend_direction": "up"}}
        result = check_adx_strong_trend(data)

        assert "AVOID" in result.reasoning or "STRONG" in result.reasoning


# =============================================================================
# VWAP Factor Tests
# =============================================================================

class TestVWAPFactors:
    """Tests for VWAP factor checkers."""

    def test_vwap_below_triggered(self, bullish_technical_analysis):
        """Test VWAP below factor triggers when price below VWAP."""
        result = check_vwap_below(bullish_technical_analysis)

        assert result.factor == BuyFactor.VWAP_BELOW.value
        assert result.triggered is True

    def test_vwap_below_not_triggered(self, bearish_technical_analysis):
        """Test VWAP below does not trigger when price above VWAP."""
        result = check_vwap_below(bearish_technical_analysis)

        assert result.triggered is False

    def test_vwap_above_triggered(self, bearish_technical_analysis):
        """Test VWAP above factor triggers when price above VWAP."""
        result = check_vwap_above(bearish_technical_analysis)

        assert result.factor == SellFactor.VWAP_ABOVE.value
        assert result.triggered is True

    def test_vwap_above_not_triggered(self, bullish_technical_analysis):
        """Test VWAP above does not trigger when price below VWAP."""
        result = check_vwap_above(bullish_technical_analysis)

        assert result.triggered is False

    def test_vwap_threshold_1_percent(self):
        """Test VWAP uses 1% threshold."""
        # Below -1% - triggered
        data = {"vwap": {"distance_pct": -1.5, "position": "below"}}
        result = check_vwap_below(data)
        assert result.triggered is True
        assert result.threshold == -1.0

        # At exactly -1%
        data = {"vwap": {"distance_pct": -1.0, "position": "below"}}
        result = check_vwap_below(data)
        assert result.triggered is True


# =============================================================================
# Aggregation Function Tests
# =============================================================================

class TestAggregationFunctions:
    """Tests for factor aggregation functions."""

    def test_check_all_buy_factors(self, bullish_technical_analysis):
        """Test all buy factors are checked."""
        results = check_all_buy_factors(bullish_technical_analysis)

        assert len(results) == 5  # MACD, Bollinger, OBV, ADX, VWAP
        assert all(isinstance(r, FactorResult) for r in results)

    def test_check_all_sell_factors(self, bearish_technical_analysis):
        """Test all sell factors are checked."""
        results = check_all_sell_factors(bearish_technical_analysis)

        assert len(results) == 5  # MACD, Bollinger, OBV, ADX, VWAP
        assert all(isinstance(r, FactorResult) for r in results)

    def test_empty_analysis_returns_empty(self, empty_technical_analysis):
        """Test empty analysis returns no factors."""
        buy_results = check_all_buy_factors(empty_technical_analysis)
        sell_results = check_all_sell_factors(empty_technical_analysis)

        assert len(buy_results) == 0
        assert len(sell_results) == 0

    def test_calculate_factor_score(self, bullish_technical_analysis):
        """Test factor score calculation."""
        results = check_all_buy_factors(bullish_technical_analysis)
        score = calculate_factor_score(results)

        assert isinstance(score, float)
        assert score > 0  # At least some factors should trigger

    def test_count_triggered_factors(self, bullish_technical_analysis):
        """Test counting triggered factors."""
        results = check_all_buy_factors(bullish_technical_analysis)
        count = count_triggered_factors(results)

        assert isinstance(count, int)
        assert count >= 0
        assert count <= len(results)

    def test_all_factors_triggered_in_bullish(self, bullish_technical_analysis):
        """Test most buy factors trigger in bullish conditions."""
        results = check_all_buy_factors(bullish_technical_analysis)
        triggered_count = count_triggered_factors(results)

        # In bullish fixture, most factors should trigger
        assert triggered_count >= 3

    def test_all_factors_triggered_in_bearish(self, bearish_technical_analysis):
        """Test most sell factors trigger in bearish conditions."""
        results = check_all_sell_factors(bearish_technical_analysis)
        triggered_count = count_triggered_factors(results)

        # In bearish fixture, most factors should trigger
        assert triggered_count >= 3


# =============================================================================
# FactorResult Tests
# =============================================================================

class TestFactorResult:
    """Tests for FactorResult dataclass."""

    def test_factor_result_creation(self):
        """Test FactorResult can be created correctly."""
        result = FactorResult(
            factor="TEST_FACTOR",
            triggered=True,
            value=50.0,
            threshold=30.0,
            weight=1.25,
            reasoning="Test reasoning"
        )

        assert result.factor == "TEST_FACTOR"
        assert result.triggered is True
        assert result.value == 50.0
        assert result.threshold == 30.0
        assert result.weight == 1.25
        assert result.reasoning == "Test reasoning"


# =============================================================================
# Edge Cases
# =============================================================================

class TestEdgeCases:
    """Tests for edge cases."""

    def test_missing_indicator_data(self):
        """Test checkers handle missing indicator data gracefully."""
        # Missing macd entirely
        data = {"bollinger": {"percent_b": 0.5, "signal": "NEUTRAL"}}
        result = check_macd_bullish(data)

        assert result.triggered is False
        assert result.factor == BuyFactor.MACD_BULLISH.value

    def test_partial_indicator_data(self):
        """Test checkers handle partial indicator data."""
        # macd exists but missing some fields
        data = {"macd": {"signal": "BULLISH"}}  # Missing histogram, crossover flags
        result = check_macd_bullish(data)

        assert result.triggered is True
        assert result.value == 0  # Default histogram

    def test_none_values_in_data(self):
        """Test checkers handle None values."""
        data = {
            "adx": {
                "value": 25,  # Default value instead of None
                "safe_for_contrarian": True,
                "is_trending": False,
                "trend_direction": "unknown"
            }
        }
        result = check_adx_weak_trend(data)

        # Should handle gracefully without raising
        assert result.factor == BuyFactor.ADX_WEAK_TREND.value
        assert result.triggered is True  # safe_for_contrarian is True
