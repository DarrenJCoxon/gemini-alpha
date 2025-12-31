"""
Tests for core/graph.py - LangGraph State Machine.

Story 2.1: LangGraph State Machine Setup

Tests the StateGraph construction, compilation, and execution.
"""

from datetime import datetime, timezone
from typing import Any, Dict

import pytest

from core.graph import build_council_graph, get_council_graph
from core.state import create_initial_state


class TestBuildCouncilGraph:
    """Tests for build_council_graph function."""

    def test_build_council_graph_compiles(self):
        """Test build_council_graph compiles without errors."""
        graph = build_council_graph()
        assert graph is not None

    def test_build_council_graph_is_invokable(self):
        """Test compiled graph has invoke method."""
        graph = build_council_graph()
        assert hasattr(graph, "invoke")
        assert callable(graph.invoke)

    def test_build_council_graph_returns_same_type(self):
        """Test multiple builds return same graph type."""
        graph1 = build_council_graph()
        graph2 = build_council_graph()

        assert type(graph1) == type(graph2)


class TestGetCouncilGraph:
    """Tests for get_council_graph caching function."""

    def test_get_council_graph_returns_graph(self):
        """Test get_council_graph returns a compiled graph."""
        graph = get_council_graph()
        assert graph is not None
        assert hasattr(graph, "invoke")

    def test_get_council_graph_caches(self):
        """Test get_council_graph returns same instance (cached)."""
        graph1 = get_council_graph()
        graph2 = get_council_graph()

        # Should be the exact same object (cached)
        assert graph1 is graph2


class TestGraphInvocation:
    """Tests for graph invocation with test data."""

    def test_graph_invoke_minimal_state(self):
        """Test graph invocation with minimal state."""
        graph = build_council_graph()
        state = create_initial_state(asset_symbol="SOLUSD")

        result = graph.invoke(state)

        assert result is not None
        assert result["asset_symbol"] == "SOLUSD"

    def test_graph_invoke_with_candles(self):
        """Test graph invocation with candle data."""
        graph = build_council_graph()
        state = create_initial_state(
            asset_symbol="BTCUSD",
            candles_data=[
                {
                    "timestamp": datetime.now(timezone.utc),
                    "open": 50000.0,
                    "high": 51000.0,
                    "low": 49000.0,
                    "close": 50500.0,
                    "volume": 1000.0
                }
            ]
        )

        result = graph.invoke(state)

        assert result["asset_symbol"] == "BTCUSD"
        assert len(result["candles_data"]) == 1

    def test_graph_invoke_with_sentiment(self):
        """Test graph invocation with sentiment data."""
        graph = build_council_graph()
        state = create_initial_state(
            asset_symbol="ETHUSD",
            sentiment_data=[
                {"text": "ETH looking strong", "source": "twitter"},
                {"text": "Bearish on ETH", "source": "telegram"},
            ]
        )

        result = graph.invoke(state)

        assert result["asset_symbol"] == "ETHUSD"
        assert len(result["sentiment_data"]) == 2


class TestGraphOutputs:
    """Tests for graph output field population."""

    def test_graph_populates_technical_analysis(self):
        """Test graph populates technical_analysis field."""
        graph = build_council_graph()
        state = create_initial_state(asset_symbol="SOLUSD")

        result = graph.invoke(state)

        assert result["technical_analysis"] is not None
        assert "signal" in result["technical_analysis"]
        assert "strength" in result["technical_analysis"]

    def test_graph_populates_sentiment_analysis(self):
        """Test graph populates sentiment_analysis field."""
        graph = build_council_graph()
        state = create_initial_state(asset_symbol="SOLUSD")

        result = graph.invoke(state)

        assert result["sentiment_analysis"] is not None
        assert "fear_score" in result["sentiment_analysis"]
        assert "summary" in result["sentiment_analysis"]

    def test_graph_populates_vision_analysis(self):
        """Test graph populates vision_analysis field."""
        graph = build_council_graph()
        state = create_initial_state(asset_symbol="SOLUSD")

        result = graph.invoke(state)

        assert result["vision_analysis"] is not None
        assert "patterns_detected" in result["vision_analysis"]
        assert "is_valid" in result["vision_analysis"]

    def test_graph_populates_final_decision(self):
        """Test graph populates final_decision field."""
        graph = build_council_graph()
        state = create_initial_state(asset_symbol="SOLUSD")

        result = graph.invoke(state)

        assert result["final_decision"] is not None
        assert "action" in result["final_decision"]
        assert "confidence" in result["final_decision"]
        assert "reasoning" in result["final_decision"]
        assert "timestamp" in result["final_decision"]

    def test_graph_no_error_on_success(self):
        """Test graph does not set error field on successful execution."""
        graph = build_council_graph()
        state = create_initial_state(asset_symbol="SOLUSD")

        result = graph.invoke(state)

        assert result["error"] is None


class TestGraphStubBehavior:
    """Tests verifying behavior with insufficient/no data."""

    def test_graph_insufficient_data_returns_neutral_technical(self):
        """Test returns NEUTRAL technical signal when no data provided."""
        graph = build_council_graph()
        state = create_initial_state(asset_symbol="SOLUSD")

        result = graph.invoke(state)

        # With no candle data, technical analysis returns NEUTRAL with 0 strength
        assert result["technical_analysis"]["signal"] == "NEUTRAL"
        assert result["technical_analysis"]["strength"] == 0  # No confidence without data

    def test_graph_stub_returns_neutral_sentiment(self):
        """Test stub returns neutral fear score (50)."""
        graph = build_council_graph()
        state = create_initial_state(asset_symbol="SOLUSD")

        result = graph.invoke(state)

        assert result["sentiment_analysis"]["fear_score"] == 50

    def test_graph_stub_returns_valid_chart(self):
        """Test stub returns is_valid=True (no manipulation detected)."""
        graph = build_council_graph()
        state = create_initial_state(asset_symbol="SOLUSD")

        result = graph.invoke(state)

        assert result["vision_analysis"]["is_valid"] is True
        assert result["vision_analysis"]["patterns_detected"] == []

    def test_graph_stub_returns_hold_decision(self):
        """Test stub returns HOLD decision."""
        graph = build_council_graph()
        state = create_initial_state(asset_symbol="SOLUSD")

        result = graph.invoke(state)

        assert result["final_decision"]["action"] == "HOLD"
        assert result["final_decision"]["confidence"] == 50


class TestGraphEdgeCases:
    """Tests for edge cases and error handling."""

    def test_graph_handles_empty_candles(self):
        """Test graph handles empty candles_data gracefully."""
        graph = build_council_graph()
        state = create_initial_state(
            asset_symbol="SOLUSD",
            candles_data=[]
        )

        result = graph.invoke(state)

        # Should complete without error
        assert result["final_decision"] is not None
        assert result["error"] is None

    def test_graph_handles_empty_sentiment(self):
        """Test graph handles empty sentiment_data gracefully."""
        graph = build_council_graph()
        state = create_initial_state(
            asset_symbol="SOLUSD",
            sentiment_data=[]
        )

        result = graph.invoke(state)

        # Should complete without error
        assert result["final_decision"] is not None
        assert result["sentiment_analysis"]["source_count"] == 0

    def test_graph_handles_both_empty(self):
        """Test graph handles both empty data sources gracefully."""
        graph = build_council_graph()
        state = create_initial_state(
            asset_symbol="SOLUSD",
            candles_data=[],
            sentiment_data=[]
        )

        result = graph.invoke(state)

        # Should complete and return HOLD
        assert result["final_decision"]["action"] == "HOLD"

    def test_graph_preserves_asset_symbol(self):
        """Test graph preserves original asset_symbol through flow."""
        graph = build_council_graph()

        for symbol in ["SOLUSD", "BTCUSD", "ETHUSD", "XRPUSD"]:
            state = create_initial_state(asset_symbol=symbol)
            result = graph.invoke(state)
            assert result["asset_symbol"] == symbol

    def test_graph_preserves_input_data(self):
        """Test graph preserves input candles and sentiment data."""
        graph = build_council_graph()
        candles = [
            {
                "timestamp": datetime.now(timezone.utc),
                "open": 100.0,
                "high": 105.0,
                "low": 98.0,
                "close": 103.0,
                "volume": 10000.0
            }
        ]
        sentiment = [{"text": "Test", "source": "test"}]

        state = create_initial_state(
            asset_symbol="SOLUSD",
            candles_data=candles,
            sentiment_data=sentiment
        )

        result = graph.invoke(state)

        # Input data should be preserved
        assert len(result["candles_data"]) == 1
        assert result["candles_data"][0]["open"] == 100.0
        assert len(result["sentiment_data"]) == 1


class TestGraphAcceptanceCriteria:
    """Tests verifying Story 2.1 Acceptance Criteria."""

    def test_ac1_graph_state_has_required_keys(self):
        """AC1: GraphState TypedDict has 7+ required keys."""
        graph = build_council_graph()
        state = create_initial_state(asset_symbol="SOLUSD")
        result = graph.invoke(state)

        required_keys = [
            "asset_symbol",
            "candles_data",
            "sentiment_data",
            "technical_analysis",
            "sentiment_analysis",
            "vision_analysis",
            "final_decision",
        ]
        for key in required_keys:
            assert key in result, f"Missing required key: {key}"

    def test_ac2_graph_has_four_nodes(self):
        """AC2: Graph has 4 nodes - all analyses populated."""
        graph = build_council_graph()
        state = create_initial_state(asset_symbol="SOLUSD")
        result = graph.invoke(state)

        # All 4 nodes should have executed and populated their fields
        assert result["sentiment_analysis"] is not None, "SentimentAgent did not run"
        assert result["technical_analysis"] is not None, "TechnicalAgent did not run"
        assert result["vision_analysis"] is not None, "VisionAgent did not run"
        assert result["final_decision"] is not None, "MasterNode did not run"

    def test_ac3_edges_connected_sequentially(self):
        """AC3: Edges connect nodes - all outputs have reasoning."""
        graph = build_council_graph()
        state = create_initial_state(asset_symbol="SOLUSD")
        result = graph.invoke(state)

        # Each node should have produced reasoning/summary
        assert "reasoning" in result["technical_analysis"]
        assert "summary" in result["sentiment_analysis"]
        assert "description" in result["vision_analysis"]
        assert "reasoning" in result["final_decision"]

    def test_ac4_graph_runs_without_errors(self):
        """AC4: Graph runs through flow without errors."""
        graph = build_council_graph()
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
            ],
            sentiment_data=[
                {"text": "Test sentiment", "source": "test"}
            ]
        )

        # Should not raise any exceptions
        result = graph.invoke(state)

        # All fields should be populated
        assert result["technical_analysis"] is not None
        assert result["sentiment_analysis"] is not None
        assert result["vision_analysis"] is not None
        assert result["final_decision"] is not None
        assert result["error"] is None
