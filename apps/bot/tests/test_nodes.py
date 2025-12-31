"""
Tests for nodes/ - Placeholder agent nodes.

Story 2.1: LangGraph State Machine Setup

Tests the stub implementations of all agent nodes.
"""

from datetime import datetime, timezone
from typing import Any, Dict

import pytest

from core.state import GraphState, create_initial_state
from nodes.master import master_node
from nodes.sentiment import sentiment_node
from nodes.technical import technical_node
from nodes.vision import vision_node


class TestTechnicalNode:
    """Tests for technical_node function."""

    def test_technical_node_returns_dict(self):
        """Test technical_node returns a dict with technical_analysis key."""
        state = create_initial_state(asset_symbol="SOLUSD")
        result = technical_node(state)

        assert isinstance(result, dict)
        assert "technical_analysis" in result

    def test_technical_node_analysis_structure(self):
        """Test technical_node returns properly structured analysis."""
        state = create_initial_state(
            asset_symbol="SOLUSD",
            candles_data=[
                {
                    "timestamp": datetime.now(timezone.utc),
                    "open": 100.0,
                    "high": 105.0,
                    "low": 98.0,
                    "close": 103.0,
                    "volume": 10000.0
                }
            ]
        )
        result = technical_node(state)
        analysis = result["technical_analysis"]

        # Check all required fields are present
        assert "signal" in analysis
        assert "strength" in analysis
        assert "rsi" in analysis
        assert "sma_50" in analysis
        assert "sma_200" in analysis
        assert "volume_delta" in analysis
        assert "reasoning" in analysis

    def test_technical_node_stub_values(self):
        """Test technical_node stub returns expected NEUTRAL values."""
        state = create_initial_state(asset_symbol="SOLUSD")
        result = technical_node(state)
        analysis = result["technical_analysis"]

        # Stub implementation returns neutral values
        assert analysis["signal"] == "NEUTRAL"
        assert analysis["strength"] == 50
        assert analysis["rsi"] == 50.0

    def test_technical_node_valid_signal_values(self):
        """Test technical_node signal is one of valid options."""
        state = create_initial_state(asset_symbol="SOLUSD")
        result = technical_node(state)

        valid_signals = ["BULLISH", "BEARISH", "NEUTRAL"]
        assert result["technical_analysis"]["signal"] in valid_signals

    def test_technical_node_strength_in_range(self):
        """Test technical_node strength is in valid 0-100 range."""
        state = create_initial_state(asset_symbol="BTCUSD")
        result = technical_node(state)

        strength = result["technical_analysis"]["strength"]
        assert 0 <= strength <= 100


class TestSentimentNode:
    """Tests for sentiment_node function."""

    def test_sentiment_node_returns_dict(self):
        """Test sentiment_node returns a dict with sentiment_analysis key."""
        state = create_initial_state(asset_symbol="SOLUSD")
        result = sentiment_node(state)

        assert isinstance(result, dict)
        assert "sentiment_analysis" in result

    def test_sentiment_node_analysis_structure(self):
        """Test sentiment_node returns properly structured analysis."""
        state = create_initial_state(
            asset_symbol="SOLUSD",
            sentiment_data=[
                {"text": "SOL is great!", "source": "twitter"}
            ]
        )
        result = sentiment_node(state)
        analysis = result["sentiment_analysis"]

        # Check all required fields are present
        assert "fear_score" in analysis
        assert "summary" in analysis
        assert "source_count" in analysis

    def test_sentiment_node_stub_values(self):
        """Test sentiment_node stub returns expected neutral values."""
        state = create_initial_state(asset_symbol="SOLUSD")
        result = sentiment_node(state)
        analysis = result["sentiment_analysis"]

        # Stub implementation returns neutral values
        assert analysis["fear_score"] == 50

    def test_sentiment_node_source_count(self):
        """Test sentiment_node counts sentiment sources correctly."""
        sentiment_entries = [
            {"text": "Entry 1", "source": "twitter"},
            {"text": "Entry 2", "source": "telegram"},
            {"text": "Entry 3", "source": "bluesky"},
        ]
        state = create_initial_state(
            asset_symbol="SOLUSD",
            sentiment_data=sentiment_entries
        )
        result = sentiment_node(state)

        assert result["sentiment_analysis"]["source_count"] == 3

    def test_sentiment_node_fear_score_in_range(self):
        """Test sentiment_node fear_score is in valid 0-100 range."""
        state = create_initial_state(asset_symbol="ETHUSD")
        result = sentiment_node(state)

        fear_score = result["sentiment_analysis"]["fear_score"]
        assert 0 <= fear_score <= 100


class TestVisionNode:
    """Tests for vision_node function."""

    def test_vision_node_returns_dict(self):
        """Test vision_node returns a dict with vision_analysis key."""
        state = create_initial_state(asset_symbol="SOLUSD")
        result = vision_node(state)

        assert isinstance(result, dict)
        assert "vision_analysis" in result

    def test_vision_node_analysis_structure(self):
        """Test vision_node returns properly structured analysis."""
        state = create_initial_state(
            asset_symbol="SOLUSD",
            candles_data=[
                {
                    "timestamp": datetime.now(timezone.utc),
                    "open": 100.0,
                    "high": 105.0,
                    "low": 98.0,
                    "close": 103.0,
                    "volume": 10000.0
                }
            ]
        )
        result = vision_node(state)
        analysis = result["vision_analysis"]

        # Check all required fields are present
        assert "patterns_detected" in analysis
        assert "confidence_score" in analysis
        assert "description" in analysis
        assert "is_valid" in analysis

    def test_vision_node_stub_values(self):
        """Test vision_node stub returns expected default values."""
        state = create_initial_state(asset_symbol="SOLUSD")
        result = vision_node(state)
        analysis = result["vision_analysis"]

        # Stub implementation returns default values
        assert analysis["patterns_detected"] == []
        assert analysis["is_valid"] is True
        assert analysis["confidence_score"] == 50

    def test_vision_node_patterns_is_list(self):
        """Test vision_node patterns_detected is a list."""
        state = create_initial_state(asset_symbol="SOLUSD")
        result = vision_node(state)

        assert isinstance(result["vision_analysis"]["patterns_detected"], list)

    def test_vision_node_confidence_in_range(self):
        """Test vision_node confidence_score is in valid 0-100 range."""
        state = create_initial_state(asset_symbol="BTCUSD")
        result = vision_node(state)

        confidence = result["vision_analysis"]["confidence_score"]
        assert 0 <= confidence <= 100


class TestMasterNode:
    """Tests for master_node function."""

    def test_master_node_returns_dict(self):
        """Test master_node returns a dict with final_decision key."""
        state = create_initial_state(asset_symbol="SOLUSD")
        result = master_node(state)

        assert isinstance(result, dict)
        assert "final_decision" in result

    def test_master_node_decision_structure(self):
        """Test master_node returns properly structured decision."""
        # Create state with all analyses populated
        state: GraphState = {
            "asset_symbol": "SOLUSD",
            "candles_data": [],
            "sentiment_data": [],
            "technical_analysis": {
                "signal": "BULLISH",
                "strength": 75,
                "rsi": 60.0,
                "sma_50": 100.0,
                "sma_200": 95.0,
                "volume_delta": 10.0,
                "reasoning": "Bullish momentum"
            },
            "sentiment_analysis": {
                "fear_score": 25,
                "summary": "Fear in market",
                "source_count": 50
            },
            "vision_analysis": {
                "patterns_detected": [],
                "confidence_score": 70,
                "description": "Clean chart",
                "is_valid": True
            },
            "final_decision": None,
            "error": None
        }
        result = master_node(state)
        decision = result["final_decision"]

        # Check all required fields are present
        assert "action" in decision
        assert "confidence" in decision
        assert "reasoning" in decision
        assert "timestamp" in decision

    def test_master_node_stub_values(self):
        """Test master_node stub returns HOLD decision."""
        state = create_initial_state(asset_symbol="SOLUSD")
        result = master_node(state)
        decision = result["final_decision"]

        # Stub implementation returns HOLD
        assert decision["action"] == "HOLD"
        assert decision["confidence"] == 50

    def test_master_node_valid_action_values(self):
        """Test master_node action is one of valid options."""
        state = create_initial_state(asset_symbol="SOLUSD")
        result = master_node(state)

        valid_actions = ["BUY", "SELL", "HOLD"]
        assert result["final_decision"]["action"] in valid_actions

    def test_master_node_confidence_in_range(self):
        """Test master_node confidence is in valid 0-100 range."""
        state = create_initial_state(asset_symbol="ETHUSD")
        result = master_node(state)

        confidence = result["final_decision"]["confidence"]
        assert 0 <= confidence <= 100

    def test_master_node_includes_timestamp(self):
        """Test master_node includes timestamp in decision."""
        state = create_initial_state(asset_symbol="SOLUSD")
        result = master_node(state)

        timestamp = result["final_decision"]["timestamp"]
        assert timestamp is not None
        assert isinstance(timestamp, datetime)

    def test_master_node_includes_reasoning(self):
        """Test master_node reasoning mentions stub implementation."""
        state = create_initial_state(asset_symbol="SOLUSD")
        result = master_node(state)

        reasoning = result["final_decision"]["reasoning"]
        assert "Stub" in reasoning or "stub" in reasoning.lower()


class TestNodeIntegration:
    """Integration tests for node flow."""

    def test_all_nodes_return_dict(self):
        """Test all nodes return dict (for LangGraph merge pattern)."""
        state = create_initial_state(asset_symbol="SOLUSD")

        results = [
            technical_node(state),
            sentiment_node(state),
            vision_node(state),
            master_node(state),
        ]

        for result in results:
            assert isinstance(result, dict)

    def test_nodes_dont_modify_input_state(self):
        """Test nodes don't modify the input state directly."""
        original_state = create_initial_state(asset_symbol="SOLUSD")

        # Store original values
        original_tech = original_state["technical_analysis"]
        original_sent = original_state["sentiment_analysis"]

        # Run nodes
        technical_node(original_state)
        sentiment_node(original_state)

        # Original state should be unchanged (nodes return updates, not mutate)
        # Note: This is the expected LangGraph pattern
        assert original_state["technical_analysis"] == original_tech
        assert original_state["sentiment_analysis"] == original_sent

    def test_sequential_node_execution(self):
        """Test nodes can be called sequentially with state updates."""
        state = create_initial_state(asset_symbol="SOLUSD")

        # Simulate LangGraph merge pattern
        state = {**state, **sentiment_node(state)}
        assert state["sentiment_analysis"] is not None

        state = {**state, **technical_node(state)}
        assert state["technical_analysis"] is not None

        state = {**state, **vision_node(state)}
        assert state["vision_analysis"] is not None

        state = {**state, **master_node(state)}
        assert state["final_decision"] is not None

        # All fields should now be populated
        assert state["sentiment_analysis"]["fear_score"] == 50
        assert state["technical_analysis"]["signal"] == "NEUTRAL"
        assert state["vision_analysis"]["is_valid"] is True
        assert state["final_decision"]["action"] == "HOLD"
