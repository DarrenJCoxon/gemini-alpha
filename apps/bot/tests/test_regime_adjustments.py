"""
Tests for services/regime_adjustments.py

Story 5.1: Market Regime Filter

Comprehensive tests for regime-based threshold adjustments including:
- Threshold adjustments per regime
- Position size calculations
- Buy condition validation with regime
"""

import pytest
from typing import Dict, Any

from services.market_regime import MarketRegime, RegimeAnalysis
from services.regime_adjustments import (
    get_regime_adjusted_thresholds,
    should_skip_trading,
    get_position_size_for_regime,
    validate_buy_conditions_with_regime,
    get_regime_summary,
    BASE_FEAR_THRESHOLD_BUY,
    BASE_POSITION_SIZE,
    BASE_TECHNICAL_STRENGTH,
)


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def bull_regime_analysis() -> RegimeAnalysis:
    """Create a BULL regime analysis."""
    return RegimeAnalysis(
        regime=MarketRegime.BULL,
        price_vs_200dma=10.5,
        sma_50=150.0,
        sma_200=135.0,
        golden_cross=True,
        death_cross=False,
        trend_strength=75,
        confidence=85,
        reasoning="BULL: Price above 200 DMA, Golden Cross active"
    )


@pytest.fixture
def bear_regime_analysis() -> RegimeAnalysis:
    """Create a BEAR regime analysis."""
    return RegimeAnalysis(
        regime=MarketRegime.BEAR,
        price_vs_200dma=-15.2,
        sma_50=125.0,
        sma_200=145.0,
        golden_cross=False,
        death_cross=True,
        trend_strength=70,
        confidence=85,
        reasoning="BEAR: Price below 200 DMA, Death Cross active"
    )


@pytest.fixture
def chop_regime_analysis() -> RegimeAnalysis:
    """Create a CHOP regime analysis."""
    return RegimeAnalysis(
        regime=MarketRegime.CHOP,
        price_vs_200dma=2.0,
        sma_50=138.0,
        sma_200=142.0,
        golden_cross=False,
        death_cross=True,
        trend_strength=30,
        confidence=60,
        reasoning="CHOP: Price above 200 DMA but Death Cross present"
    )


@pytest.fixture
def bullish_conditions() -> Dict[str, Any]:
    """Create conditions that should pass in BULL regime."""
    return {
        "fear_score": 15,  # Very low fear
        "technical_signal": "BULLISH",
        "technical_strength": 70,
        "vision_valid": True,
        "vision_confidence": 60,
    }


# =============================================================================
# Test Base Constants
# =============================================================================


class TestBaseConstants:
    """Tests for base threshold constants."""

    def test_base_fear_threshold(self):
        """Test base fear threshold is set correctly."""
        assert BASE_FEAR_THRESHOLD_BUY == 30

    def test_base_position_size(self):
        """Test base position size is 1.0 (100%)."""
        assert BASE_POSITION_SIZE == 1.0

    def test_base_technical_strength(self):
        """Test base technical strength threshold."""
        assert BASE_TECHNICAL_STRENGTH == 50


# =============================================================================
# Test get_regime_adjusted_thresholds
# =============================================================================


class TestGetRegimeAdjustedThresholds:
    """Tests for the get_regime_adjusted_thresholds function."""

    def test_bull_thresholds(self):
        """Test BULL regime has normal thresholds."""
        thresholds = get_regime_adjusted_thresholds(MarketRegime.BULL)

        assert thresholds["fear_threshold_buy"] == 30
        assert thresholds["position_size_multiplier"] == 1.0
        assert thresholds["min_technical_strength"] == 50
        assert thresholds["allow_trading"] is True
        assert "BULL" in thresholds["reasoning"]

    def test_bear_thresholds(self):
        """Test BEAR regime has stricter thresholds."""
        thresholds = get_regime_adjusted_thresholds(MarketRegime.BEAR)

        assert thresholds["fear_threshold_buy"] == 20
        assert thresholds["position_size_multiplier"] == 0.5
        assert thresholds["min_technical_strength"] == 65
        assert thresholds["allow_trading"] is True
        assert "BEAR" in thresholds["reasoning"]

    def test_chop_thresholds(self):
        """Test CHOP regime has most conservative thresholds."""
        thresholds = get_regime_adjusted_thresholds(MarketRegime.CHOP)

        assert thresholds["fear_threshold_buy"] == 15
        assert thresholds["position_size_multiplier"] == 0.25
        assert thresholds["min_technical_strength"] == 75
        assert thresholds["allow_trading"] is True
        assert "CHOP" in thresholds["reasoning"]

    def test_bear_stricter_than_bull(self):
        """Test BEAR has stricter thresholds than BULL."""
        bull = get_regime_adjusted_thresholds(MarketRegime.BULL)
        bear = get_regime_adjusted_thresholds(MarketRegime.BEAR)

        # BEAR requires lower fear score
        assert bear["fear_threshold_buy"] < bull["fear_threshold_buy"]
        # BEAR has smaller position size
        assert bear["position_size_multiplier"] < bull["position_size_multiplier"]
        # BEAR requires stronger technicals
        assert bear["min_technical_strength"] > bull["min_technical_strength"]

    def test_chop_stricter_than_bear(self):
        """Test CHOP has stricter thresholds than BEAR."""
        bear = get_regime_adjusted_thresholds(MarketRegime.BEAR)
        chop = get_regime_adjusted_thresholds(MarketRegime.CHOP)

        # CHOP requires lower fear score
        assert chop["fear_threshold_buy"] < bear["fear_threshold_buy"]
        # CHOP has smaller position size
        assert chop["position_size_multiplier"] < bear["position_size_multiplier"]
        # CHOP requires stronger technicals
        assert chop["min_technical_strength"] > bear["min_technical_strength"]

    def test_custom_config_override(self):
        """Test that custom config can override defaults."""
        custom_config = {
            "bull_fear_threshold": 35,
            "bull_position_multiplier": 0.9,
        }

        thresholds = get_regime_adjusted_thresholds(
            MarketRegime.BULL,
            config=custom_config
        )

        assert thresholds["fear_threshold_buy"] == 35
        assert thresholds["position_size_multiplier"] == 0.9


# =============================================================================
# Test should_skip_trading
# =============================================================================


class TestShouldSkipTrading:
    """Tests for the should_skip_trading function."""

    def test_bull_allows_trading(self):
        """Test BULL regime allows trading."""
        result = should_skip_trading(MarketRegime.BULL)
        assert result is False

    def test_bear_allows_trading(self):
        """Test BEAR regime allows trading (with adjustments)."""
        result = should_skip_trading(MarketRegime.BEAR)
        assert result is False

    def test_chop_allows_trading(self):
        """Test CHOP regime allows trading (with adjustments)."""
        result = should_skip_trading(MarketRegime.CHOP)
        assert result is False


# =============================================================================
# Test get_position_size_for_regime
# =============================================================================


class TestGetPositionSizeForRegime:
    """Tests for the get_position_size_for_regime function."""

    def test_bull_full_position(self):
        """Test BULL regime uses full position size."""
        result = get_position_size_for_regime(MarketRegime.BULL, base_size=1000.0)

        assert result == 1000.0  # 100% of base

    def test_bear_half_position(self):
        """Test BEAR regime uses 50% position size."""
        result = get_position_size_for_regime(MarketRegime.BEAR, base_size=1000.0)

        assert result == 500.0  # 50% of base

    def test_chop_quarter_position(self):
        """Test CHOP regime uses 25% position size."""
        result = get_position_size_for_regime(MarketRegime.CHOP, base_size=1000.0)

        assert result == 250.0  # 25% of base

    def test_position_size_with_custom_config(self):
        """Test position size with custom config."""
        config = {"bear_position_multiplier": 0.3}
        result = get_position_size_for_regime(
            MarketRegime.BEAR,
            base_size=1000.0,
            config=config
        )

        assert result == 300.0  # 30% of base


# =============================================================================
# Test validate_buy_conditions_with_regime
# =============================================================================


class TestValidateBuyConditionsWithRegime:
    """Tests for the validate_buy_conditions_with_regime function."""

    def test_bull_conditions_pass(self, bull_regime_analysis, bullish_conditions):
        """Test conditions pass in BULL regime."""
        result = validate_buy_conditions_with_regime(
            fear_score=bullish_conditions["fear_score"],
            technical_signal=bullish_conditions["technical_signal"],
            technical_strength=bullish_conditions["technical_strength"],
            vision_valid=bullish_conditions["vision_valid"],
            regime_analysis=bull_regime_analysis,
        )

        assert result["is_valid"] is True
        assert "PASS" in result["reasons"][1]  # First pass reason
        assert result["adjustments"]["fear_threshold_buy"] == 30

    def test_bull_conditions_fail_high_fear(self, bull_regime_analysis):
        """Test conditions fail when fear too high even in BULL."""
        result = validate_buy_conditions_with_regime(
            fear_score=50,  # Too high
            technical_signal="BULLISH",
            technical_strength=70,
            vision_valid=True,
            regime_analysis=bull_regime_analysis,
        )

        assert result["is_valid"] is False
        assert any("FAIL" in r and "Fear" in r for r in result["reasons"])

    def test_bear_conditions_require_lower_fear(self, bear_regime_analysis):
        """Test BEAR requires lower fear than BULL."""
        # This would pass in BULL but fail in BEAR
        result = validate_buy_conditions_with_regime(
            fear_score=25,  # Passes BULL (< 30) but fails BEAR (< 20)
            technical_signal="BULLISH",
            technical_strength=70,
            vision_valid=True,
            regime_analysis=bear_regime_analysis,
        )

        assert result["is_valid"] is False
        assert result["adjustments"]["fear_threshold_buy"] == 20

    def test_bear_conditions_require_stronger_technicals(self, bear_regime_analysis):
        """Test BEAR requires stronger technicals."""
        # Strength 60 passes BULL (>= 50) but fails BEAR (>= 65)
        result = validate_buy_conditions_with_regime(
            fear_score=10,  # Very low fear
            technical_signal="BULLISH",
            technical_strength=60,  # Passes BULL, fails BEAR
            vision_valid=True,
            regime_analysis=bear_regime_analysis,
        )

        assert result["is_valid"] is False
        assert result["adjustments"]["min_technical_strength"] == 65

    def test_chop_most_conservative(self, chop_regime_analysis):
        """Test CHOP has most conservative requirements."""
        result = validate_buy_conditions_with_regime(
            fear_score=10,  # Low fear, but >= 15 fails CHOP
            technical_signal="BULLISH",
            technical_strength=70,  # Fails CHOP (>= 75)
            vision_valid=True,
            regime_analysis=chop_regime_analysis,
        )

        assert result["is_valid"] is False
        assert result["adjustments"]["min_technical_strength"] == 75
        assert result["adjustments"]["fear_threshold_buy"] == 15

    def test_chop_extreme_conditions_pass(self, chop_regime_analysis):
        """Test extremely favorable conditions pass even in CHOP."""
        result = validate_buy_conditions_with_regime(
            fear_score=5,  # Extreme fear (< 15)
            technical_signal="BULLISH",
            technical_strength=85,  # Very strong (>= 75)
            vision_valid=True,
            regime_analysis=chop_regime_analysis,
        )

        assert result["is_valid"] is True

    def test_vision_still_required(self, bull_regime_analysis):
        """Test vision validation is still required regardless of regime."""
        result = validate_buy_conditions_with_regime(
            fear_score=10,
            technical_signal="BULLISH",
            technical_strength=70,
            vision_valid=False,  # Invalid vision
            regime_analysis=bull_regime_analysis,
        )

        assert result["is_valid"] is False
        assert any("FAIL" in r and "Vision" in r for r in result["reasons"])

    def test_reasons_include_regime_context(self, bull_regime_analysis):
        """Test that reasons include regime context."""
        result = validate_buy_conditions_with_regime(
            fear_score=10,
            technical_signal="BULLISH",
            technical_strength=70,
            vision_valid=True,
            regime_analysis=bull_regime_analysis,
        )

        # First reason should be regime context
        assert "REGIME: BULL" in result["reasons"][0]


# =============================================================================
# Test get_regime_summary
# =============================================================================


class TestGetRegimeSummary:
    """Tests for the get_regime_summary function."""

    def test_bull_summary(self, bull_regime_analysis):
        """Test BULL regime summary format."""
        summary = get_regime_summary(bull_regime_analysis)

        assert "BULL" in summary
        assert "DMA" in summary
        assert "Confidence" in summary

    def test_bear_summary(self, bear_regime_analysis):
        """Test BEAR regime summary format."""
        summary = get_regime_summary(bear_regime_analysis)

        assert "BEAR" in summary
        assert "-" in summary  # Negative DMA percentage

    def test_chop_summary(self, chop_regime_analysis):
        """Test CHOP regime summary format."""
        summary = get_regime_summary(chop_regime_analysis)

        assert "CHOP" in summary


# =============================================================================
# Integration Tests
# =============================================================================


class TestRegimeAdjustmentsIntegration:
    """Integration tests for regime adjustments."""

    def test_adjustments_applied_consistently(self):
        """Test that adjustments are applied consistently."""
        for regime in [MarketRegime.BULL, MarketRegime.BEAR, MarketRegime.CHOP]:
            thresholds = get_regime_adjusted_thresholds(regime)

            # All required keys present
            assert "fear_threshold_buy" in thresholds
            assert "position_size_multiplier" in thresholds
            assert "min_technical_strength" in thresholds
            assert "allow_trading" in thresholds
            assert "reasoning" in thresholds

            # Values are within valid ranges
            assert 0 <= thresholds["fear_threshold_buy"] <= 100
            assert 0 < thresholds["position_size_multiplier"] <= 1.0
            assert 0 <= thresholds["min_technical_strength"] <= 100

    def test_regime_progression(self):
        """Test that thresholds become stricter from BULL -> BEAR -> CHOP."""
        bull = get_regime_adjusted_thresholds(MarketRegime.BULL)
        bear = get_regime_adjusted_thresholds(MarketRegime.BEAR)
        chop = get_regime_adjusted_thresholds(MarketRegime.CHOP)

        # Fear thresholds decrease (stricter)
        assert bull["fear_threshold_buy"] > bear["fear_threshold_buy"] > chop["fear_threshold_buy"]

        # Position multipliers decrease
        assert bull["position_size_multiplier"] > bear["position_size_multiplier"] > chop["position_size_multiplier"]

        # Technical strength requirements increase
        assert bull["min_technical_strength"] < bear["min_technical_strength"] < chop["min_technical_strength"]

    def test_validate_with_dict_regime(self):
        """Test validation works with dict regime analysis (from state)."""
        regime_dict = {
            "regime": "BEAR",
            "price_vs_200dma": -10.0,
            "confidence": 85,
        }

        # Create a mock analysis from dict
        from services.market_regime import RegimeAnalysis, MarketRegime
        analysis = RegimeAnalysis(
            regime=MarketRegime.BEAR,
            price_vs_200dma=-10.0,
            sma_50=0.0,
            sma_200=0.0,
            golden_cross=False,
            death_cross=True,
            trend_strength=70,
            confidence=85,
            reasoning="Test"
        )

        result = validate_buy_conditions_with_regime(
            fear_score=15,
            technical_signal="BULLISH",
            technical_strength=70,
            vision_valid=True,
            regime_analysis=analysis,
        )

        # BEAR regime adjustments should be applied
        assert result["adjustments"]["fear_threshold_buy"] == 20
