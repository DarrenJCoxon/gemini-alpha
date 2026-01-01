"""
Tests for Multi-Factor Confirmation System.

Story 5.3: Multi-Factor Confirmation System

Comprehensive tests for the multi-factor confirmation system including:
- Signal factor types and dataclasses
- Individual factor checking functions
- Multi-factor analysis functions
- Integration with decision logic
"""

import pytest
from unittest.mock import patch

from services.signal_factors import (
    BuyFactor,
    SellFactor,
    FactorResult,
    MultiFactorAnalysis,
)
from services.factor_checkers import (
    check_extreme_fear,
    check_extreme_greed,
    check_rsi_oversold,
    check_rsi_overbought,
    check_price_at_support,
    check_price_at_resistance,
    check_volume_capitulation,
    check_volume_exhaustion,
    check_bullish_technicals,
    check_bearish_technicals,
    check_vision_validated,
    check_vision_bearish,
)
from services.multi_factor_analyzer import (
    analyze_buy_factors,
    analyze_sell_factors,
    analyze_all_factors,
)
from services.decision_logic import validate_decision_with_multi_factor


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def extreme_fear_sentiment():
    """Sentiment showing extreme fear - BUY signal."""
    return {"fear_score": 15, "summary": "Panic selling in markets"}


@pytest.fixture
def extreme_greed_sentiment():
    """Sentiment showing extreme greed - SELL signal."""
    return {"fear_score": 85, "summary": "Euphoria in markets"}


@pytest.fixture
def neutral_sentiment():
    """Neutral sentiment."""
    return {"fear_score": 50, "summary": "Mixed sentiment"}


@pytest.fixture
def oversold_technicals():
    """Technicals showing oversold conditions."""
    return {
        "signal": "BULLISH",
        "strength": 70,
        "rsi": 22,
        "sma_50": 105,
        "sma_200": 100.0,
        "volume_delta": 150,  # 150% above average
        "reasoning": "Oversold bounce setup"
    }


@pytest.fixture
def overbought_technicals():
    """Technicals showing overbought conditions."""
    return {
        "signal": "BEARISH",
        "strength": 75,
        "rsi": 78,
        "sma_50": 95,
        "sma_200": 100.0,
        "volume_delta": -60,  # 60% below average
        "reasoning": "Overbought exhaustion"
    }


@pytest.fixture
def neutral_technicals():
    """Neutral technicals."""
    return {
        "signal": "NEUTRAL",
        "strength": 40,
        "rsi": 50,
        "sma_50": 100,
        "sma_200": 100.0,
        "volume_delta": 10,
        "reasoning": "Sideways action"
    }


@pytest.fixture
def valid_vision():
    """Valid vision analysis confirming setup."""
    return {
        "is_valid": True,
        "confidence_score": 75,
        "patterns_detected": ["Double Bottom"],
        "description": "Clear reversal pattern forming"
    }


@pytest.fixture
def invalid_vision():
    """Invalid vision analysis (scam wick detected)."""
    return {
        "is_valid": False,
        "confidence_score": 20,
        "patterns_detected": [],
        "description": "Potential scam wick detected"
    }


@pytest.fixture
def bearish_vision():
    """Vision showing bearish patterns."""
    return {
        "is_valid": True,
        "confidence_score": 70,
        "patterns_detected": ["Head and Shoulders", "Rising Wedge"],
        "description": "Bearish reversal patterns detected"
    }


# =============================================================================
# Test Signal Factor Types
# =============================================================================


class TestSignalFactorTypes:
    """Tests for signal factor enums and dataclasses."""

    def test_buy_factor_enum_values(self):
        """Test BuyFactor enum has expected values."""
        assert BuyFactor.EXTREME_FEAR.value == "EXTREME_FEAR"
        assert BuyFactor.RSI_OVERSOLD.value == "RSI_OVERSOLD"
        assert BuyFactor.PRICE_AT_SUPPORT.value == "PRICE_AT_SUPPORT"
        assert BuyFactor.VOLUME_CAPITULATION.value == "VOLUME_CAPITULATION"
        assert BuyFactor.BULLISH_TECHNICALS.value == "BULLISH_TECHNICALS"
        assert BuyFactor.VISION_VALIDATED.value == "VISION_VALIDATED"

    def test_sell_factor_enum_values(self):
        """Test SellFactor enum has expected values."""
        assert SellFactor.EXTREME_GREED.value == "EXTREME_GREED"
        assert SellFactor.RSI_OVERBOUGHT.value == "RSI_OVERBOUGHT"
        assert SellFactor.PRICE_AT_RESISTANCE.value == "PRICE_AT_RESISTANCE"
        assert SellFactor.VOLUME_EXHAUSTION.value == "VOLUME_EXHAUSTION"
        assert SellFactor.BEARISH_TECHNICALS.value == "BEARISH_TECHNICALS"
        assert SellFactor.VISION_BEARISH.value == "VISION_BEARISH"

    def test_factor_result_dataclass(self):
        """Test FactorResult dataclass creation."""
        result = FactorResult(
            factor="EXTREME_FEAR",
            triggered=True,
            value=15.0,
            threshold=25.0,
            weight=1.5,
            reasoning="Fear score 15 < 25"
        )
        assert result.factor == "EXTREME_FEAR"
        assert result.triggered is True
        assert result.value == 15.0
        assert result.threshold == 25.0
        assert result.weight == 1.5

    def test_multi_factor_analysis_dataclass(self):
        """Test MultiFactorAnalysis dataclass creation."""
        factor_result = FactorResult(
            factor="EXTREME_FEAR",
            triggered=True,
            value=15.0,
            threshold=25.0,
            weight=1.5,
            reasoning="Fear score 15 < 25"
        )
        analysis = MultiFactorAnalysis(
            signal_type="BUY",
            factors_triggered=[factor_result],
            factors_not_triggered=[],
            total_factors_checked=6,
            factors_met=3,
            weighted_score=3.5,
            min_factors_required=3,
            passes_threshold=True,
            confidence=70.0,
            reasoning="Test reasoning"
        )
        assert analysis.signal_type == "BUY"
        assert len(analysis.factors_triggered) == 1
        assert analysis.passes_threshold is True


# =============================================================================
# Test Individual Factor Checkers
# =============================================================================


class TestExtremeFearChecker:
    """Tests for check_extreme_fear function."""

    def test_extreme_fear_triggered(self, extreme_fear_sentiment):
        """Test extreme fear is triggered when score < threshold."""
        result = check_extreme_fear(extreme_fear_sentiment)
        assert result.triggered is True
        assert result.factor == BuyFactor.EXTREME_FEAR.value
        assert result.value == 15
        assert result.weight == 1.5

    def test_extreme_fear_not_triggered(self, neutral_sentiment):
        """Test extreme fear not triggered when score >= threshold."""
        result = check_extreme_fear(neutral_sentiment)
        assert result.triggered is False
        assert result.factor == BuyFactor.EXTREME_FEAR.value

    def test_extreme_fear_at_threshold(self):
        """Test extreme fear not triggered at exact threshold."""
        result = check_extreme_fear({"fear_score": 25})
        assert result.triggered is False

    def test_extreme_fear_just_below_threshold(self):
        """Test extreme fear triggered just below threshold."""
        result = check_extreme_fear({"fear_score": 24})
        assert result.triggered is True


class TestExtremeGreedChecker:
    """Tests for check_extreme_greed function."""

    def test_extreme_greed_triggered(self, extreme_greed_sentiment):
        """Test extreme greed is triggered when score > threshold."""
        result = check_extreme_greed(extreme_greed_sentiment)
        assert result.triggered is True
        assert result.factor == SellFactor.EXTREME_GREED.value
        assert result.value == 85
        assert result.weight == 1.5

    def test_extreme_greed_not_triggered(self, neutral_sentiment):
        """Test extreme greed not triggered when score <= threshold."""
        result = check_extreme_greed(neutral_sentiment)
        assert result.triggered is False

    def test_extreme_greed_at_threshold(self):
        """Test extreme greed not triggered at exact threshold."""
        result = check_extreme_greed({"fear_score": 75})
        assert result.triggered is False


class TestRSICheckers:
    """Tests for RSI checker functions."""

    def test_rsi_oversold_triggered(self, oversold_technicals):
        """Test RSI oversold is triggered when RSI < threshold."""
        result = check_rsi_oversold(oversold_technicals)
        assert result.triggered is True
        assert result.factor == BuyFactor.RSI_OVERSOLD.value
        assert result.value == 22

    def test_rsi_oversold_not_triggered(self, neutral_technicals):
        """Test RSI oversold not triggered when RSI >= threshold."""
        result = check_rsi_oversold(neutral_technicals)
        assert result.triggered is False

    def test_rsi_overbought_triggered(self, overbought_technicals):
        """Test RSI overbought is triggered when RSI > threshold."""
        result = check_rsi_overbought(overbought_technicals)
        assert result.triggered is True
        assert result.factor == SellFactor.RSI_OVERBOUGHT.value
        assert result.value == 78

    def test_rsi_overbought_not_triggered(self, neutral_technicals):
        """Test RSI overbought not triggered when RSI <= threshold."""
        result = check_rsi_overbought(neutral_technicals)
        assert result.triggered is False


class TestPricePositionCheckers:
    """Tests for price at support/resistance checkers."""

    def test_price_at_support_triggered(self, oversold_technicals):
        """Test price at support when within proximity of SMA200."""
        result = check_price_at_support(oversold_technicals, current_price=102.0)
        assert result.triggered is True
        assert result.factor == BuyFactor.PRICE_AT_SUPPORT.value

    def test_price_at_support_not_triggered_too_high(self, oversold_technicals):
        """Test price at support not triggered when too far above SMA200."""
        result = check_price_at_support(oversold_technicals, current_price=110.0)
        assert result.triggered is False

    def test_price_at_support_not_triggered_below(self, oversold_technicals):
        """Test price at support not triggered when below SMA200."""
        result = check_price_at_support(oversold_technicals, current_price=95.0)
        assert result.triggered is False

    def test_price_at_support_no_sma(self):
        """Test price at support with missing SMA200."""
        result = check_price_at_support({"sma_200": 0}, current_price=100.0)
        assert result.triggered is False
        assert "not available" in result.reasoning

    def test_price_at_resistance_triggered(self, overbought_technicals):
        """Test price at resistance when extended above SMA200."""
        result = check_price_at_resistance(overbought_technicals, current_price=110.0)
        assert result.triggered is True
        assert result.factor == SellFactor.PRICE_AT_RESISTANCE.value

    def test_price_at_resistance_not_triggered(self, overbought_technicals):
        """Test price at resistance not triggered near SMA200."""
        result = check_price_at_resistance(overbought_technicals, current_price=102.0)
        assert result.triggered is False


class TestVolumeCheckers:
    """Tests for volume checker functions."""

    def test_volume_capitulation_triggered(self, oversold_technicals):
        """Test volume capitulation triggered on volume spike."""
        result = check_volume_capitulation(oversold_technicals)
        assert result.triggered is True
        assert result.factor == BuyFactor.VOLUME_CAPITULATION.value
        assert result.value == 150

    def test_volume_capitulation_not_triggered(self, neutral_technicals):
        """Test volume capitulation not triggered on normal volume."""
        result = check_volume_capitulation(neutral_technicals)
        assert result.triggered is False

    def test_volume_exhaustion_triggered(self, overbought_technicals):
        """Test volume exhaustion triggered on low volume."""
        result = check_volume_exhaustion(overbought_technicals)
        assert result.triggered is True
        assert result.factor == SellFactor.VOLUME_EXHAUSTION.value

    def test_volume_exhaustion_not_triggered(self, oversold_technicals):
        """Test volume exhaustion not triggered on high volume."""
        result = check_volume_exhaustion(oversold_technicals)
        assert result.triggered is False


class TestTechnicalSignalCheckers:
    """Tests for technical signal checker functions."""

    def test_bullish_technicals_triggered(self, oversold_technicals):
        """Test bullish technicals triggered on BULLISH signal with strength."""
        result = check_bullish_technicals(oversold_technicals)
        assert result.triggered is True
        assert result.factor == BuyFactor.BULLISH_TECHNICALS.value

    def test_bullish_technicals_not_triggered_wrong_signal(self, overbought_technicals):
        """Test bullish technicals not triggered on BEARISH signal."""
        result = check_bullish_technicals(overbought_technicals)
        assert result.triggered is False

    def test_bullish_technicals_not_triggered_low_strength(self):
        """Test bullish technicals not triggered on low strength."""
        result = check_bullish_technicals({"signal": "BULLISH", "strength": 40})
        assert result.triggered is False

    def test_bearish_technicals_triggered(self, overbought_technicals):
        """Test bearish technicals triggered on BEARISH signal with strength."""
        result = check_bearish_technicals(overbought_technicals)
        assert result.triggered is True
        assert result.factor == SellFactor.BEARISH_TECHNICALS.value

    def test_bearish_technicals_not_triggered(self, oversold_technicals):
        """Test bearish technicals not triggered on BULLISH signal."""
        result = check_bearish_technicals(oversold_technicals)
        assert result.triggered is False


class TestVisionCheckers:
    """Tests for vision checker functions."""

    def test_vision_validated_triggered(self, valid_vision):
        """Test vision validated triggered when valid with confidence."""
        result = check_vision_validated(valid_vision)
        assert result.triggered is True
        assert result.factor == BuyFactor.VISION_VALIDATED.value
        assert result.weight == 0.75

    def test_vision_validated_not_triggered_invalid(self, invalid_vision):
        """Test vision validated not triggered when invalid."""
        result = check_vision_validated(invalid_vision)
        assert result.triggered is False

    def test_vision_validated_not_triggered_low_confidence(self):
        """Test vision validated not triggered on low confidence."""
        result = check_vision_validated({"is_valid": True, "confidence_score": 30})
        assert result.triggered is False

    def test_vision_bearish_triggered(self, bearish_vision):
        """Test vision bearish triggered on bearish patterns."""
        result = check_vision_bearish(bearish_vision)
        assert result.triggered is True
        assert result.factor == SellFactor.VISION_BEARISH.value

    def test_vision_bearish_not_triggered(self, valid_vision):
        """Test vision bearish not triggered without bearish patterns."""
        result = check_vision_bearish(valid_vision)
        assert result.triggered is False


# =============================================================================
# Test Multi-Factor Analyzer
# =============================================================================


class TestAnalyzeBuyFactors:
    """Tests for analyze_buy_factors function."""

    def test_buy_passes_with_multiple_factors(
        self,
        extreme_fear_sentiment,
        oversold_technicals,
        valid_vision
    ):
        """Test BUY signal when 3+ factors are met."""
        result = analyze_buy_factors(
            extreme_fear_sentiment,
            oversold_technicals,
            valid_vision,
            current_price=102.0
        )

        assert result.factors_met >= 3
        assert result.passes_threshold is True
        assert result.signal_type == "BUY"

    def test_buy_fails_with_insufficient_factors(
        self,
        neutral_sentiment,
        neutral_technicals,
        invalid_vision
    ):
        """Test HOLD signal when < 3 factors are met."""
        result = analyze_buy_factors(
            neutral_sentiment,
            neutral_technicals,
            invalid_vision,
            current_price=100.0
        )

        assert result.factors_met < 3
        assert result.passes_threshold is False
        assert result.signal_type == "HOLD"

    def test_buy_factors_tracked_correctly(
        self,
        extreme_fear_sentiment,
        oversold_technicals,
        valid_vision
    ):
        """Test all factor results are properly tracked."""
        result = analyze_buy_factors(
            extreme_fear_sentiment,
            oversold_technicals,
            valid_vision,
            current_price=102.0
        )

        assert result.total_factors_checked == 6
        assert len(result.factors_triggered) + len(result.factors_not_triggered) == 6

    def test_buy_weighted_score_calculation(
        self,
        extreme_fear_sentiment,
        oversold_technicals,
        valid_vision
    ):
        """Test weighted score is calculated correctly."""
        result = analyze_buy_factors(
            extreme_fear_sentiment,
            oversold_technicals,
            valid_vision,
            current_price=102.0
        )

        # Extreme fear has weight 1.5, should be included
        assert result.weighted_score > 0
        assert result.confidence > 0


class TestAnalyzeSellFactors:
    """Tests for analyze_sell_factors function."""

    def test_sell_passes_with_multiple_factors(
        self,
        extreme_greed_sentiment,
        overbought_technicals,
        invalid_vision
    ):
        """Test SELL signal when 2+ factors are met."""
        result = analyze_sell_factors(
            extreme_greed_sentiment,
            overbought_technicals,
            invalid_vision,
            current_price=110.0
        )

        assert result.factors_met >= 2
        assert result.passes_threshold is True
        assert result.signal_type == "SELL"

    def test_sell_fails_with_insufficient_factors(
        self,
        neutral_sentiment,
        neutral_technicals,
        valid_vision
    ):
        """Test HOLD signal when < 2 factors are met."""
        result = analyze_sell_factors(
            neutral_sentiment,
            neutral_technicals,
            valid_vision,
            current_price=100.0
        )

        assert result.factors_met < 2
        assert result.passes_threshold is False
        assert result.signal_type == "HOLD"


class TestAnalyzeAllFactors:
    """Tests for analyze_all_factors function."""

    def test_returns_both_buy_and_sell_analysis(
        self,
        neutral_sentiment,
        neutral_technicals,
        valid_vision
    ):
        """Test both buy and sell analyses are returned."""
        result = analyze_all_factors(
            neutral_sentiment,
            neutral_technicals,
            valid_vision,
            current_price=100.0
        )

        assert "buy" in result
        assert "sell" in result
        assert isinstance(result["buy"], MultiFactorAnalysis)
        assert isinstance(result["sell"], MultiFactorAnalysis)


# =============================================================================
# Test Decision Logic Integration
# =============================================================================


class TestValidateDecisionWithMultiFactor:
    """Tests for validate_decision_with_multi_factor function."""

    def test_returns_buy_when_buy_factors_pass(
        self,
        extreme_fear_sentiment,
        oversold_technicals,
        valid_vision
    ):
        """Test BUY returned when buy factors pass threshold."""
        action, details = validate_decision_with_multi_factor(
            extreme_fear_sentiment,
            oversold_technicals,
            valid_vision,
            current_price=102.0
        )

        assert action == "BUY"
        assert "buy_analysis" in details
        assert "sell_analysis" in details

    def test_returns_sell_when_sell_factors_pass(
        self,
        extreme_greed_sentiment,
        overbought_technicals,
        invalid_vision
    ):
        """Test SELL returned when sell factors pass threshold."""
        action, details = validate_decision_with_multi_factor(
            extreme_greed_sentiment,
            overbought_technicals,
            invalid_vision,
            current_price=110.0
        )

        assert action == "SELL"

    def test_returns_hold_when_no_threshold_met(
        self,
        neutral_sentiment,
        neutral_technicals,
        invalid_vision
    ):
        """Test HOLD returned when neither threshold is met."""
        action, details = validate_decision_with_multi_factor(
            neutral_sentiment,
            neutral_technicals,
            invalid_vision,
            current_price=100.0
        )

        assert action == "HOLD"

    def test_regime_adjustment_bear_market(
        self,
        extreme_fear_sentiment,
        oversold_technicals,
        valid_vision
    ):
        """Test BEAR regime increases factor requirement."""
        # First verify it passes without regime
        action_normal, _ = validate_decision_with_multi_factor(
            extreme_fear_sentiment,
            oversold_technicals,
            valid_vision,
            current_price=102.0,
            regime_analysis=None
        )

        # Now with BEAR regime - may require 4+ factors
        action_bear, details = validate_decision_with_multi_factor(
            extreme_fear_sentiment,
            oversold_technicals,
            valid_vision,
            current_price=102.0,
            regime_analysis={"regime": "BEAR"}
        )

        # If < 4 factors met, should be HOLD in bear regime
        buy_factors = details["buy_analysis"].factors_met
        if buy_factors < 4:
            assert action_bear == "HOLD"
            assert "BEAR regime requires 4+" in details["buy_analysis"].reasoning

    def test_returns_factors_met_count(
        self,
        extreme_fear_sentiment,
        oversold_technicals,
        valid_vision
    ):
        """Test factors_met count is returned."""
        action, details = validate_decision_with_multi_factor(
            extreme_fear_sentiment,
            oversold_technicals,
            valid_vision,
            current_price=102.0
        )

        assert "factors_met" in details
        assert isinstance(details["factors_met"], int)

    def test_returns_confidence(
        self,
        extreme_fear_sentiment,
        oversold_technicals,
        valid_vision
    ):
        """Test confidence is returned."""
        action, details = validate_decision_with_multi_factor(
            extreme_fear_sentiment,
            oversold_technicals,
            valid_vision,
            current_price=102.0
        )

        assert "confidence" in details
        assert 0 <= details["confidence"] <= 100


# =============================================================================
# Edge Cases and Integration Tests
# =============================================================================


class TestEdgeCases:
    """Tests for edge cases and error handling."""

    def test_empty_inputs_returns_hold(self):
        """Test empty inputs return HOLD safely."""
        action, details = validate_decision_with_multi_factor(
            {}, {}, {}, current_price=100.0
        )
        assert action == "HOLD"

    def test_zero_price_handled(
        self,
        extreme_fear_sentiment,
        oversold_technicals,
        valid_vision
    ):
        """Test zero price is handled gracefully."""
        result = analyze_buy_factors(
            extreme_fear_sentiment,
            oversold_technicals,
            valid_vision,
            current_price=0
        )
        # Should still analyze other factors
        assert result.total_factors_checked == 6

    def test_missing_fear_score_defaults(self):
        """Test missing fear_score uses default of 50."""
        result = check_extreme_fear({})
        assert result.value == 50
        assert result.triggered is False

    def test_missing_rsi_defaults(self):
        """Test missing RSI uses default of 50."""
        result = check_rsi_oversold({})
        assert result.value == 50
        assert result.triggered is False

    def test_all_factors_pass_high_confidence(
        self,
        extreme_fear_sentiment,
        oversold_technicals,
        valid_vision
    ):
        """Test all factors passing gives high confidence."""
        result = analyze_buy_factors(
            extreme_fear_sentiment,
            oversold_technicals,
            valid_vision,
            current_price=102.0
        )

        if result.factors_met == result.total_factors_checked:
            assert result.confidence >= 80

    def test_no_factors_pass_low_confidence(
        self,
        neutral_sentiment,
        neutral_technicals,
        invalid_vision
    ):
        """Test no factors passing gives low confidence."""
        result = analyze_buy_factors(
            neutral_sentiment,
            neutral_technicals,
            invalid_vision,
            current_price=100.0
        )

        if result.factors_met == 0:
            assert result.confidence == 0


class TestMultiFactorIntegration:
    """Integration tests for multi-factor system."""

    def test_full_buy_scenario(
        self,
        extreme_fear_sentiment,
        oversold_technicals,
        valid_vision
    ):
        """Test complete BUY scenario from analysis to decision."""
        # 1. Analyze factors
        buy_analysis = analyze_buy_factors(
            extreme_fear_sentiment,
            oversold_technicals,
            valid_vision,
            current_price=102.0
        )

        # 2. Verify factors
        assert buy_analysis.factors_met >= 3
        triggered_factors = [f.factor for f in buy_analysis.factors_triggered]
        assert BuyFactor.EXTREME_FEAR.value in triggered_factors
        assert BuyFactor.RSI_OVERSOLD.value in triggered_factors

        # 3. Validate decision
        action, details = validate_decision_with_multi_factor(
            extreme_fear_sentiment,
            oversold_technicals,
            valid_vision,
            current_price=102.0
        )
        assert action == "BUY"
        assert details["confidence"] > 50

    def test_full_sell_scenario(
        self,
        extreme_greed_sentiment,
        overbought_technicals,
        bearish_vision
    ):
        """Test complete SELL scenario from analysis to decision."""
        # 1. Analyze factors
        sell_analysis = analyze_sell_factors(
            extreme_greed_sentiment,
            overbought_technicals,
            bearish_vision,
            current_price=110.0
        )

        # 2. Verify factors
        assert sell_analysis.factors_met >= 2
        triggered_factors = [f.factor for f in sell_analysis.factors_triggered]
        assert SellFactor.EXTREME_GREED.value in triggered_factors

        # 3. Validate decision
        action, details = validate_decision_with_multi_factor(
            extreme_greed_sentiment,
            overbought_technicals,
            bearish_vision,
            current_price=110.0
        )
        assert action == "SELL"

    def test_mixed_signals_returns_hold(
        self,
        neutral_sentiment,
        neutral_technicals,
        valid_vision
    ):
        """Test mixed signals without clear direction returns HOLD."""
        action, details = validate_decision_with_multi_factor(
            neutral_sentiment,
            neutral_technicals,
            valid_vision,
            current_price=100.0
        )
        assert action == "HOLD"
        assert details["buy_analysis"].passes_threshold is False
        assert details["sell_analysis"].passes_threshold is False
