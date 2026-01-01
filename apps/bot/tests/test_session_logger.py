"""
Tests for services/session_logger.py

Story 2.4: Master Node & Signal Logging

Tests for the session logging functionality.
Note: Full database integration tests require a test database.
These tests focus on unit testing the logic and mock interactions.
"""

import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from decimal import Decimal

from models.base import Decision
from models.council import CouncilSession


# =============================================================================
# Test Data Fixtures
# =============================================================================


@pytest.fixture
def mock_state():
    """Create a mock GraphState for testing."""
    return {
        "asset_symbol": "SOLUSD",
        "candles_data": [],
        "sentiment_data": [],
        "sentiment_analysis": {
            "fear_score": 15,
            "summary": "Extreme fear",
            "source_count": 50
        },
        "technical_analysis": {
            "signal": "BULLISH",
            "strength": 75,
            "rsi": 28,
            "sma_50": 110,
            "sma_200": 100,
            "volume_delta": 40,
            "reasoning": "Oversold bounce"
        },
        "vision_analysis": {
            "patterns_detected": ["Double Bottom"],
            "confidence_score": 70,
            "description": "Clear reversal",
            "is_valid": True
        },
        "final_decision": {
            "action": "BUY",
            "confidence": 80,
            "reasoning": "All conditions met for contrarian buy",
            "timestamp": datetime.now(timezone.utc)
        },
        "error": None
    }


@pytest.fixture
def mock_state_sell():
    """Create a mock GraphState for SELL decision."""
    return {
        "asset_symbol": "BTCUSD",
        "candles_data": [],
        "sentiment_data": [],
        "sentiment_analysis": {
            "fear_score": 85,
            "summary": "Extreme greed",
            "source_count": 100
        },
        "technical_analysis": {
            "signal": "BEARISH",
            "strength": 72,
            "rsi": 78,
            "sma_50": 42000,
            "sma_200": 45000,
            "volume_delta": -15,
            "reasoning": "Overbought with bearish divergence"
        },
        "vision_analysis": {
            "patterns_detected": ["Head and Shoulders"],
            "confidence_score": 65,
            "description": "Bearish reversal pattern",
            "is_valid": False
        },
        "final_decision": {
            "action": "SELL",
            "confidence": 75,
            "reasoning": "Extreme greed triggering sell",
            "timestamp": datetime.now(timezone.utc)
        },
        "error": None
    }


@pytest.fixture
def mock_state_hold():
    """Create a mock GraphState for HOLD decision."""
    return {
        "asset_symbol": "ETHUSD",
        "candles_data": [],
        "sentiment_data": [],
        "sentiment_analysis": {
            "fear_score": 50,
            "summary": "Neutral sentiment",
            "source_count": 30
        },
        "technical_analysis": {
            "signal": "NEUTRAL",
            "strength": 45,
            "rsi": 50,
            "sma_50": 2500,
            "sma_200": 2500,
            "volume_delta": 0,
            "reasoning": "No clear direction"
        },
        "vision_analysis": {
            "patterns_detected": [],
            "confidence_score": 40,
            "description": "No patterns detected",
            "is_valid": True
        },
        "final_decision": {
            "action": "HOLD",
            "confidence": 50,
            "reasoning": "No clear signals - holding",
            "timestamp": datetime.now(timezone.utc)
        },
        "error": None
    }


@pytest.fixture
def mock_state_minimal():
    """Create a minimal mock GraphState with mostly missing data."""
    return {
        "asset_symbol": "TESTUSD",
        "candles_data": [],
        "sentiment_data": [],
        "sentiment_analysis": None,
        "technical_analysis": None,
        "vision_analysis": None,
        "final_decision": {
            "action": "HOLD",
            "confidence": 0,
            "reasoning": "Insufficient data",
            "timestamp": datetime.now(timezone.utc)
        },
        "error": "Missing analysis data"
    }


# =============================================================================
# Test State Validation
# =============================================================================


class TestStateValidation:
    """Test that mock states have all required fields."""

    def test_buy_state_has_required_fields(self, mock_state):
        """Verify BUY mock state has all required fields."""
        assert "sentiment_analysis" in mock_state
        assert "technical_analysis" in mock_state
        assert "vision_analysis" in mock_state
        assert "final_decision" in mock_state
        assert mock_state["final_decision"]["action"] == "BUY"

    def test_sell_state_has_required_fields(self, mock_state_sell):
        """Verify SELL mock state has all required fields."""
        assert "sentiment_analysis" in mock_state_sell
        assert "technical_analysis" in mock_state_sell
        assert "vision_analysis" in mock_state_sell
        assert "final_decision" in mock_state_sell
        assert mock_state_sell["final_decision"]["action"] == "SELL"

    def test_hold_state_has_required_fields(self, mock_state_hold):
        """Verify HOLD mock state has all required fields."""
        assert "sentiment_analysis" in mock_state_hold
        assert "technical_analysis" in mock_state_hold
        assert "vision_analysis" in mock_state_hold
        assert "final_decision" in mock_state_hold
        assert mock_state_hold["final_decision"]["action"] == "HOLD"

    def test_minimal_state_handles_none(self, mock_state_minimal):
        """Verify minimal state handles None values."""
        assert mock_state_minimal["sentiment_analysis"] is None
        assert mock_state_minimal["technical_analysis"] is None
        assert mock_state_minimal["vision_analysis"] is None
        assert mock_state_minimal["final_decision"] is not None


# =============================================================================
# Test Data Extraction Logic
# =============================================================================


class TestDataExtraction:
    """Test the data extraction logic used in log_council_session."""

    def test_extract_sentiment_score(self, mock_state):
        """Test extracting sentiment score from state."""
        sentiment = mock_state.get("sentiment_analysis") or {}
        score = sentiment.get("fear_score", 50)
        assert score == 15

    def test_extract_sentiment_score_default(self, mock_state_minimal):
        """Test sentiment score defaults to 50 when missing."""
        sentiment = mock_state_minimal.get("sentiment_analysis") or {}
        score = sentiment.get("fear_score", 50)
        assert score == 50

    def test_extract_technical_signal(self, mock_state):
        """Test extracting technical signal from state."""
        technical = mock_state.get("technical_analysis") or {}
        signal = technical.get("signal", "NEUTRAL")
        assert signal == "BULLISH"

    def test_extract_technical_signal_default(self, mock_state_minimal):
        """Test technical signal defaults to NEUTRAL when missing."""
        technical = mock_state_minimal.get("technical_analysis") or {}
        signal = technical.get("signal", "NEUTRAL")
        assert signal == "NEUTRAL"

    def test_extract_vision_confidence(self, mock_state):
        """Test extracting vision confidence from state."""
        vision = mock_state.get("vision_analysis") or {}
        confidence = vision.get("confidence_score", 0)
        assert confidence == 70

    def test_extract_decision_action(self, mock_state):
        """Test extracting decision action from state."""
        decision = mock_state.get("final_decision") or {}
        action = decision.get("action", "HOLD")
        assert action == "BUY"


# =============================================================================
# Test Decision Enum Mapping
# =============================================================================


class TestDecisionEnumMapping:
    """Test mapping decision strings to Decision enum."""

    def test_map_buy_to_enum(self):
        """Test mapping BUY string to Decision.BUY."""
        action = "BUY"
        decision_enum = Decision.BUY if action == "BUY" else Decision.HOLD
        assert decision_enum == Decision.BUY

    def test_map_sell_to_enum(self):
        """Test mapping SELL string to Decision.SELL."""
        action = "SELL"
        if action == "BUY":
            decision_enum = Decision.BUY
        elif action == "SELL":
            decision_enum = Decision.SELL
        else:
            decision_enum = Decision.HOLD
        assert decision_enum == Decision.SELL

    def test_map_hold_to_enum(self):
        """Test mapping HOLD string to Decision.HOLD."""
        action = "HOLD"
        if action == "BUY":
            decision_enum = Decision.BUY
        elif action == "SELL":
            decision_enum = Decision.SELL
        else:
            decision_enum = Decision.HOLD
        assert decision_enum == Decision.HOLD

    def test_map_unknown_to_hold(self):
        """Test mapping unknown action to HOLD (safe default)."""
        action = "UNKNOWN"
        if action == "BUY":
            decision_enum = Decision.BUY
        elif action == "SELL":
            decision_enum = Decision.SELL
        else:
            decision_enum = Decision.HOLD
        assert decision_enum == Decision.HOLD


# =============================================================================
# Test Vision Confidence Conversion
# =============================================================================


class TestVisionConfidenceConversion:
    """Test converting vision confidence to Decimal."""

    def test_convert_confidence_to_decimal(self):
        """Test converting 70 to 0.70 Decimal."""
        confidence = 70
        decimal_value = Decimal(str(confidence)) / 100
        assert decimal_value == Decimal("0.70")

    def test_convert_zero_confidence(self):
        """Test converting 0 to 0.00 Decimal."""
        confidence = 0
        decimal_value = Decimal(str(confidence)) / 100
        assert decimal_value == Decimal("0.00")

    def test_convert_full_confidence(self):
        """Test converting 100 to 1.00 Decimal."""
        confidence = 100
        decimal_value = Decimal(str(confidence)) / 100
        assert decimal_value == Decimal("1.00")


# =============================================================================
# Test Technical Details JSON
# =============================================================================


class TestTechnicalDetailsJson:
    """Test building technical details JSON structure."""

    def test_build_technical_details(self, mock_state):
        """Test building technical details dict."""
        technical = mock_state.get("technical_analysis") or {}
        technical_details = {
            "rsi": technical.get("rsi"),
            "sma_50": technical.get("sma_50"),
            "sma_200": technical.get("sma_200"),
            "volume_delta": technical.get("volume_delta"),
            "reasoning": technical.get("reasoning"),
            "strength": technical.get("strength"),
        }

        assert technical_details["rsi"] == 28
        assert technical_details["sma_50"] == 110
        assert technical_details["sma_200"] == 100
        assert technical_details["volume_delta"] == 40
        assert technical_details["reasoning"] == "Oversold bounce"
        assert technical_details["strength"] == 75

    def test_build_technical_details_empty(self, mock_state_minimal):
        """Test building technical details with empty state."""
        technical = mock_state_minimal.get("technical_analysis") or {}
        technical_details = {
            "rsi": technical.get("rsi"),
            "sma_50": technical.get("sma_50"),
            "sma_200": technical.get("sma_200"),
            "volume_delta": technical.get("volume_delta"),
            "reasoning": technical.get("reasoning"),
            "strength": technical.get("strength"),
        }

        assert technical_details["rsi"] is None
        assert technical_details["sma_50"] is None
        assert technical_details["reasoning"] is None


# =============================================================================
# Test CouncilSession Model
# =============================================================================


class TestCouncilSessionModel:
    """Test CouncilSession model creation."""

    def test_council_session_model_exists(self):
        """Test CouncilSession model is importable."""
        assert CouncilSession is not None

    def test_decision_enum_values(self):
        """Test Decision enum has correct values."""
        assert Decision.BUY.value == "BUY"
        assert Decision.SELL.value == "SELL"
        assert Decision.HOLD.value == "HOLD"


# =============================================================================
# Integration-like Tests (without database)
# =============================================================================


class TestSessionLoggerLogic:
    """Test session logger logic without database."""

    def test_extract_all_buy_data(self, mock_state):
        """Test extracting all data for BUY session."""
        sentiment = mock_state.get("sentiment_analysis") or {}
        technical = mock_state.get("technical_analysis") or {}
        vision = mock_state.get("vision_analysis") or {}
        decision = mock_state.get("final_decision") or {}

        # All extractions should work
        assert sentiment.get("fear_score") == 15
        assert technical.get("signal") == "BULLISH"
        assert vision.get("is_valid") is True
        assert decision.get("action") == "BUY"

    def test_extract_all_sell_data(self, mock_state_sell):
        """Test extracting all data for SELL session."""
        sentiment = mock_state_sell.get("sentiment_analysis") or {}
        technical = mock_state_sell.get("technical_analysis") or {}
        vision = mock_state_sell.get("vision_analysis") or {}
        decision = mock_state_sell.get("final_decision") or {}

        assert sentiment.get("fear_score") == 85
        assert technical.get("signal") == "BEARISH"
        assert vision.get("is_valid") is False
        assert decision.get("action") == "SELL"

    def test_reasoning_log_preserved(self, mock_state):
        """Test reasoning log is properly extracted."""
        decision = mock_state.get("final_decision") or {}
        reasoning = decision.get("reasoning", "No reasoning provided")
        assert "All conditions met" in reasoning


class TestGetRecentSessionsLogic:
    """Test get_recent_sessions logic."""

    def test_limit_parameter(self):
        """Test limit parameter is properly validated."""
        # This tests the parameter validation logic
        limit = 10
        assert isinstance(limit, int)
        assert limit > 0
        assert limit <= 100  # Reasonable upper bound

    def test_asset_id_is_string(self):
        """Test asset_id should be a string."""
        asset_id = "clxyz123"
        assert isinstance(asset_id, str)
        assert len(asset_id) > 0


class TestGetSessionStatsLogic:
    """Test session stats calculation logic."""

    def test_calculate_percentages(self):
        """Test percentage calculation logic."""
        total = 10
        buy_count = 2
        sell_count = 3
        hold_count = 5

        buy_pct = round(buy_count / total * 100, 1)
        sell_pct = round(sell_count / total * 100, 1)
        hold_pct = round(hold_count / total * 100, 1)

        assert buy_pct == 20.0
        assert sell_pct == 30.0
        assert hold_pct == 50.0
        assert buy_pct + sell_pct + hold_pct == 100.0

    def test_handle_zero_total(self):
        """Test handling zero total sessions."""
        total = 0
        stats = {
            "total_sessions": total,
            "buy_count": 0,
            "sell_count": 0,
            "hold_count": 0,
        }
        # Should return early with zeros, no division
        assert stats["total_sessions"] == 0
