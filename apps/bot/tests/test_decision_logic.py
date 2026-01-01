"""
Tests for services/decision_logic.py

Story 2.4: Master Node & Signal Logging

Comprehensive tests for the decision validation logic including:
- BUY condition validation
- SELL condition validation
- Pre-validation decision making
- Confidence calculation
"""

import pytest

from services.decision_logic import (
    validate_buy_conditions,
    validate_sell_conditions,
    pre_validate_decision,
    calculate_decision_confidence,
    FEAR_THRESHOLD_BUY,
    FEAR_THRESHOLD_SELL,
    TECHNICAL_STRENGTH_MIN,
    VISION_CONFIDENCE_MIN,
    BEARISH_STRENGTH_SELL,
)


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def bullish_setup():
    """Setup that should trigger BUY - all conditions met."""
    return {
        "sentiment": {
            "fear_score": 15,
            "summary": "Extreme fear",
            "source_count": 50
        },
        "technical": {
            "signal": "BULLISH",
            "strength": 75,
            "rsi": 28,
            "sma_50": 110,
            "sma_200": 100,
            "volume_delta": 40,
            "reasoning": "Oversold bounce"
        },
        "vision": {
            "patterns_detected": ["Double Bottom"],
            "confidence_score": 70,
            "description": "Clear reversal pattern",
            "is_valid": True
        }
    }


@pytest.fixture
def bearish_setup():
    """Setup that should trigger SELL - extreme greed."""
    return {
        "sentiment": {
            "fear_score": 85,
            "summary": "Extreme greed",
            "source_count": 50
        },
        "technical": {
            "signal": "BEARISH",
            "strength": 80,
            "rsi": 75,
            "sma_50": 90,
            "sma_200": 100,
            "volume_delta": -20,
            "reasoning": "Overbought conditions"
        },
        "vision": {
            "patterns_detected": ["Head and Shoulders"],
            "confidence_score": 65,
            "description": "Bearish reversal pattern",
            "is_valid": False
        }
    }


@pytest.fixture
def neutral_setup():
    """Setup that should trigger HOLD - neutral conditions."""
    return {
        "sentiment": {
            "fear_score": 50,
            "summary": "Neutral sentiment",
            "source_count": 20
        },
        "technical": {
            "signal": "NEUTRAL",
            "strength": 50,
            "rsi": 50,
            "sma_50": 100,
            "sma_200": 100,
            "volume_delta": 0,
            "reasoning": "No clear signal"
        },
        "vision": {
            "patterns_detected": [],
            "confidence_score": 40,
            "description": "No patterns detected",
            "is_valid": True
        }
    }


# =============================================================================
# Test Thresholds
# =============================================================================


class TestThresholds:
    """Test that thresholds are set correctly."""

    def test_fear_threshold_buy_is_20(self):
        """Fear score must be below 20 to buy."""
        assert FEAR_THRESHOLD_BUY == 20

    def test_fear_threshold_sell_is_80(self):
        """Fear score must be above 80 to sell on greed."""
        assert FEAR_THRESHOLD_SELL == 80

    def test_technical_strength_min_is_50(self):
        """Technical strength must be at least 50."""
        assert TECHNICAL_STRENGTH_MIN == 50

    def test_vision_confidence_min_is_30(self):
        """Vision confidence must be at least 30."""
        assert VISION_CONFIDENCE_MIN == 30

    def test_bearish_strength_sell_is_70(self):
        """Bearish strength must be at least 70 to sell."""
        assert BEARISH_STRENGTH_SELL == 70


# =============================================================================
# Test validate_buy_conditions
# =============================================================================


class TestValidateBuyConditions:
    """Tests for validate_buy_conditions function."""

    def test_all_conditions_met(self, bullish_setup):
        """Test BUY when all conditions are met."""
        is_valid, reasons = validate_buy_conditions(
            bullish_setup["sentiment"],
            bullish_setup["technical"],
            bullish_setup["vision"]
        )
        assert is_valid is True
        assert all("PASS" in r for r in reasons)

    def test_fear_score_too_high(self, bullish_setup):
        """Test BUY fails when fear score is too high."""
        bullish_setup["sentiment"]["fear_score"] = 50
        is_valid, reasons = validate_buy_conditions(
            bullish_setup["sentiment"],
            bullish_setup["technical"],
            bullish_setup["vision"]
        )
        assert is_valid is False
        assert any("FAIL" in r and "Fear" in r for r in reasons)

    def test_fear_score_at_threshold(self, bullish_setup):
        """Test BUY fails when fear score equals threshold."""
        bullish_setup["sentiment"]["fear_score"] = 20  # Exactly at threshold
        is_valid, reasons = validate_buy_conditions(
            bullish_setup["sentiment"],
            bullish_setup["technical"],
            bullish_setup["vision"]
        )
        assert is_valid is False

    def test_fear_score_just_below_threshold(self, bullish_setup):
        """Test BUY passes when fear score is just below threshold."""
        bullish_setup["sentiment"]["fear_score"] = 19
        is_valid, reasons = validate_buy_conditions(
            bullish_setup["sentiment"],
            bullish_setup["technical"],
            bullish_setup["vision"]
        )
        assert is_valid is True

    def test_technical_signal_bearish(self, bullish_setup):
        """Test BUY fails when technical signal is BEARISH."""
        bullish_setup["technical"]["signal"] = "BEARISH"
        is_valid, reasons = validate_buy_conditions(
            bullish_setup["sentiment"],
            bullish_setup["technical"],
            bullish_setup["vision"]
        )
        assert is_valid is False
        assert any("FAIL" in r and "Technical" in r for r in reasons)

    def test_technical_signal_neutral(self, bullish_setup):
        """Test BUY fails when technical signal is NEUTRAL."""
        bullish_setup["technical"]["signal"] = "NEUTRAL"
        is_valid, reasons = validate_buy_conditions(
            bullish_setup["sentiment"],
            bullish_setup["technical"],
            bullish_setup["vision"]
        )
        assert is_valid is False

    def test_technical_strength_too_low(self, bullish_setup):
        """Test BUY fails when technical strength is too low."""
        bullish_setup["technical"]["strength"] = 40
        is_valid, reasons = validate_buy_conditions(
            bullish_setup["sentiment"],
            bullish_setup["technical"],
            bullish_setup["vision"]
        )
        assert is_valid is False

    def test_vision_not_valid(self, bullish_setup):
        """Test BUY fails when vision is not valid."""
        bullish_setup["vision"]["is_valid"] = False
        is_valid, reasons = validate_buy_conditions(
            bullish_setup["sentiment"],
            bullish_setup["technical"],
            bullish_setup["vision"]
        )
        assert is_valid is False
        assert any("FAIL" in r and "Vision" in r for r in reasons)

    def test_vision_confidence_too_low(self, bullish_setup):
        """Test BUY fails when vision confidence is too low."""
        bullish_setup["vision"]["confidence_score"] = 20
        is_valid, reasons = validate_buy_conditions(
            bullish_setup["sentiment"],
            bullish_setup["technical"],
            bullish_setup["vision"]
        )
        assert is_valid is False

    def test_empty_inputs(self):
        """Test BUY fails with empty inputs (safe defaults)."""
        is_valid, reasons = validate_buy_conditions({}, {}, {})
        assert is_valid is False

    def test_partial_inputs(self):
        """Test BUY fails with partial inputs."""
        is_valid, reasons = validate_buy_conditions(
            {"fear_score": 10},
            {"signal": "BULLISH"},
            {}
        )
        assert is_valid is False


# =============================================================================
# Test validate_sell_conditions
# =============================================================================


class TestValidateSellConditions:
    """Tests for validate_sell_conditions function."""

    def test_extreme_greed_triggers_sell(self, bearish_setup):
        """Test SELL triggers on extreme greed."""
        is_valid, reasons = validate_sell_conditions(
            bearish_setup["sentiment"],
            bearish_setup["technical"],
            bearish_setup["vision"]
        )
        assert is_valid is True
        assert any("greed" in r.lower() for r in reasons)

    def test_fear_score_at_sell_threshold(self, neutral_setup):
        """Test SELL does not trigger when fear score equals threshold."""
        neutral_setup["sentiment"]["fear_score"] = 80  # Exactly at threshold
        is_valid, reasons = validate_sell_conditions(
            neutral_setup["sentiment"],
            neutral_setup["technical"],
            neutral_setup["vision"]
        )
        assert is_valid is False

    def test_fear_score_above_sell_threshold(self, neutral_setup):
        """Test SELL triggers when fear score is above threshold."""
        neutral_setup["sentiment"]["fear_score"] = 81
        is_valid, reasons = validate_sell_conditions(
            neutral_setup["sentiment"],
            neutral_setup["technical"],
            neutral_setup["vision"]
        )
        assert is_valid is True

    def test_strong_bearish_triggers_sell(self, neutral_setup):
        """Test SELL triggers on strong bearish signal."""
        neutral_setup["technical"]["signal"] = "BEARISH"
        neutral_setup["technical"]["strength"] = 75
        is_valid, reasons = validate_sell_conditions(
            neutral_setup["sentiment"],
            neutral_setup["technical"],
            neutral_setup["vision"]
        )
        assert is_valid is True
        assert any("bearish" in r.lower() for r in reasons)

    def test_weak_bearish_does_not_trigger(self, neutral_setup):
        """Test SELL does not trigger on weak bearish signal."""
        neutral_setup["technical"]["signal"] = "BEARISH"
        neutral_setup["technical"]["strength"] = 60
        is_valid, reasons = validate_sell_conditions(
            neutral_setup["sentiment"],
            neutral_setup["technical"],
            neutral_setup["vision"]
        )
        assert is_valid is False

    def test_no_sell_conditions_neutral(self, neutral_setup):
        """Test no SELL on neutral conditions."""
        is_valid, reasons = validate_sell_conditions(
            neutral_setup["sentiment"],
            neutral_setup["technical"],
            neutral_setup["vision"]
        )
        assert is_valid is False
        assert any("No SELL" in r for r in reasons)

    def test_empty_inputs(self):
        """Test SELL fails with empty inputs (safe defaults)."""
        is_valid, reasons = validate_sell_conditions({}, {}, {})
        assert is_valid is False


# =============================================================================
# Test pre_validate_decision
# =============================================================================


class TestPreValidateDecision:
    """Tests for pre_validate_decision function."""

    def test_returns_buy_when_conditions_met(self, bullish_setup):
        """Test returns BUY when all buy conditions are met."""
        action, reasons = pre_validate_decision(
            bullish_setup["sentiment"],
            bullish_setup["technical"],
            bullish_setup["vision"]
        )
        assert action == "BUY"

    def test_returns_sell_on_extreme_greed(self, bearish_setup):
        """Test returns SELL on extreme greed."""
        action, reasons = pre_validate_decision(
            bearish_setup["sentiment"],
            bearish_setup["technical"],
            bearish_setup["vision"]
        )
        assert action == "SELL"

    def test_returns_hold_on_neutral(self, neutral_setup):
        """Test returns HOLD on neutral conditions."""
        action, reasons = pre_validate_decision(
            neutral_setup["sentiment"],
            neutral_setup["technical"],
            neutral_setup["vision"]
        )
        assert action == "HOLD"

    def test_buy_takes_priority_over_sell(self, bullish_setup):
        """Test BUY is checked before SELL (buy takes priority)."""
        # Even if sell conditions might be partially met,
        # if buy conditions are fully met, return BUY
        action, reasons = pre_validate_decision(
            bullish_setup["sentiment"],
            bullish_setup["technical"],
            bullish_setup["vision"]
        )
        assert action == "BUY"

    def test_sell_when_buy_fails(self, bearish_setup):
        """Test SELL is returned when BUY fails but SELL conditions met."""
        action, reasons = pre_validate_decision(
            bearish_setup["sentiment"],
            bearish_setup["technical"],
            bearish_setup["vision"]
        )
        assert action == "SELL"

    def test_hold_is_default(self):
        """Test HOLD is returned when no conditions met."""
        action, reasons = pre_validate_decision({}, {}, {})
        assert action == "HOLD"

    def test_reasons_are_returned(self, bullish_setup):
        """Test reasons list is returned with decision."""
        action, reasons = pre_validate_decision(
            bullish_setup["sentiment"],
            bullish_setup["technical"],
            bullish_setup["vision"]
        )
        assert isinstance(reasons, list)
        assert len(reasons) > 0


# =============================================================================
# Test calculate_decision_confidence
# =============================================================================


class TestCalculateDecisionConfidence:
    """Tests for calculate_decision_confidence function."""

    def test_buy_confidence_extreme_fear(self, bullish_setup):
        """Test high confidence for BUY with extreme fear."""
        confidence = calculate_decision_confidence(
            "BUY",
            bullish_setup["sentiment"],
            bullish_setup["technical"],
            bullish_setup["vision"]
        )
        assert confidence > 50
        assert confidence <= 100

    def test_buy_confidence_increases_with_lower_fear(self, bullish_setup):
        """Test BUY confidence increases with lower fear score."""
        # Higher fear (higher score) = lower confidence for contrarian BUY
        bullish_setup["sentiment"]["fear_score"] = 5
        confidence_low_fear = calculate_decision_confidence(
            "BUY",
            bullish_setup["sentiment"],
            bullish_setup["technical"],
            bullish_setup["vision"]
        )

        bullish_setup["sentiment"]["fear_score"] = 15
        confidence_mid_fear = calculate_decision_confidence(
            "BUY",
            bullish_setup["sentiment"],
            bullish_setup["technical"],
            bullish_setup["vision"]
        )

        assert confidence_low_fear >= confidence_mid_fear

    def test_sell_confidence_extreme_greed(self, bearish_setup):
        """Test high confidence for SELL with extreme greed."""
        confidence = calculate_decision_confidence(
            "SELL",
            bearish_setup["sentiment"],
            bearish_setup["technical"],
            bearish_setup["vision"]
        )
        assert confidence > 50
        assert confidence <= 100

    def test_hold_confidence_is_medium(self, neutral_setup):
        """Test HOLD confidence is medium (50)."""
        confidence = calculate_decision_confidence(
            "HOLD",
            neutral_setup["sentiment"],
            neutral_setup["technical"],
            neutral_setup["vision"]
        )
        assert confidence == 50

    def test_confidence_never_exceeds_100(self, bullish_setup):
        """Test confidence is capped at 100."""
        bullish_setup["sentiment"]["fear_score"] = 0
        bullish_setup["technical"]["strength"] = 100
        bullish_setup["vision"]["confidence_score"] = 100
        confidence = calculate_decision_confidence(
            "BUY",
            bullish_setup["sentiment"],
            bullish_setup["technical"],
            bullish_setup["vision"]
        )
        assert confidence <= 100

    def test_confidence_with_empty_inputs(self):
        """Test confidence with empty inputs."""
        confidence = calculate_decision_confidence("HOLD", {}, {}, {})
        assert confidence == 50


# =============================================================================
# Integration Tests
# =============================================================================


class TestDecisionLogicIntegration:
    """Integration tests for the decision logic."""

    def test_full_buy_scenario(self, bullish_setup):
        """Test complete BUY scenario with validation and confidence."""
        # Pre-validate
        action, reasons = pre_validate_decision(
            bullish_setup["sentiment"],
            bullish_setup["technical"],
            bullish_setup["vision"]
        )
        assert action == "BUY"

        # Calculate confidence
        confidence = calculate_decision_confidence(
            action,
            bullish_setup["sentiment"],
            bullish_setup["technical"],
            bullish_setup["vision"]
        )
        assert confidence > 50

    def test_full_sell_scenario(self, bearish_setup):
        """Test complete SELL scenario with validation and confidence."""
        action, reasons = pre_validate_decision(
            bearish_setup["sentiment"],
            bearish_setup["technical"],
            bearish_setup["vision"]
        )
        assert action == "SELL"

        confidence = calculate_decision_confidence(
            action,
            bearish_setup["sentiment"],
            bearish_setup["technical"],
            bearish_setup["vision"]
        )
        assert confidence > 50

    def test_full_hold_scenario(self, neutral_setup):
        """Test complete HOLD scenario with validation and confidence."""
        action, reasons = pre_validate_decision(
            neutral_setup["sentiment"],
            neutral_setup["technical"],
            neutral_setup["vision"]
        )
        assert action == "HOLD"

        confidence = calculate_decision_confidence(
            action,
            neutral_setup["sentiment"],
            neutral_setup["technical"],
            neutral_setup["vision"]
        )
        assert confidence == 50

    def test_edge_case_all_zeros(self):
        """Test edge case with all zero values."""
        sentiment = {"fear_score": 0, "summary": "", "source_count": 0}
        technical = {"signal": "NEUTRAL", "strength": 0, "rsi": 0}
        vision = {"patterns_detected": [], "confidence_score": 0, "is_valid": False}

        action, reasons = pre_validate_decision(sentiment, technical, vision)
        # fear_score 0 meets buy condition 1, but other conditions fail
        assert action == "HOLD"
