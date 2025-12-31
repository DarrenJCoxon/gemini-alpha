"""
Tests for core/state.py - GraphState and related TypedDicts.

Story 2.1: LangGraph State Machine Setup

Tests the GraphState TypedDict validation and factory functions.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List

import pytest

from core.state import (
    CandleData,
    FinalDecision,
    GraphState,
    SentimentAnalysis,
    TechnicalAnalysis,
    VisionAnalysis,
    create_initial_state,
)


class TestCandleData:
    """Tests for CandleData TypedDict."""

    def test_candle_data_valid(self):
        """Test CandleData with valid values."""
        candle: CandleData = {
            "timestamp": datetime.now(timezone.utc),
            "open": 100.0,
            "high": 105.0,
            "low": 98.0,
            "close": 103.0,
            "volume": 10000.0
        }
        assert candle["open"] == 100.0
        assert candle["high"] == 105.0
        assert candle["low"] == 98.0
        assert candle["close"] == 103.0
        assert candle["volume"] == 10000.0

    def test_candle_data_all_fields_present(self):
        """Test that CandleData requires all OHLCV fields."""
        candle: CandleData = {
            "timestamp": datetime.now(timezone.utc),
            "open": 50.0,
            "high": 55.0,
            "low": 48.0,
            "close": 52.0,
            "volume": 5000.0
        }
        required_fields = ["timestamp", "open", "high", "low", "close", "volume"]
        for field in required_fields:
            assert field in candle


class TestTechnicalAnalysis:
    """Tests for TechnicalAnalysis TypedDict."""

    def test_technical_analysis_bullish(self):
        """Test TechnicalAnalysis with BULLISH signal."""
        analysis: TechnicalAnalysis = {
            "signal": "BULLISH",
            "strength": 75,
            "rsi": 65.0,
            "sma_50": 100.0,
            "sma_200": 95.0,
            "volume_delta": 15.0,
            "reasoning": "Price above both SMAs, RSI healthy"
        }
        assert analysis["signal"] == "BULLISH"
        assert analysis["strength"] == 75
        assert 0 <= analysis["strength"] <= 100

    def test_technical_analysis_bearish(self):
        """Test TechnicalAnalysis with BEARISH signal."""
        analysis: TechnicalAnalysis = {
            "signal": "BEARISH",
            "strength": 80,
            "rsi": 25.0,
            "sma_50": 90.0,
            "sma_200": 100.0,
            "volume_delta": -10.0,
            "reasoning": "Price below SMAs, RSI oversold"
        }
        assert analysis["signal"] == "BEARISH"
        assert analysis["strength"] == 80

    def test_technical_analysis_neutral(self):
        """Test TechnicalAnalysis with NEUTRAL signal."""
        analysis: TechnicalAnalysis = {
            "signal": "NEUTRAL",
            "strength": 50,
            "rsi": 50.0,
            "sma_50": 100.0,
            "sma_200": 100.0,
            "volume_delta": 0.0,
            "reasoning": "Mixed signals"
        }
        assert analysis["signal"] == "NEUTRAL"
        assert analysis["strength"] == 50


class TestSentimentAnalysis:
    """Tests for SentimentAnalysis TypedDict."""

    def test_sentiment_analysis_fear(self):
        """Test SentimentAnalysis with low fear score (extreme fear)."""
        analysis: SentimentAnalysis = {
            "fear_score": 15,
            "summary": "Extreme fear in the market",
            "source_count": 50
        }
        assert analysis["fear_score"] == 15
        assert 0 <= analysis["fear_score"] <= 100

    def test_sentiment_analysis_greed(self):
        """Test SentimentAnalysis with high fear score (greed)."""
        analysis: SentimentAnalysis = {
            "fear_score": 85,
            "summary": "Extreme greed in the market",
            "source_count": 100
        }
        assert analysis["fear_score"] == 85

    def test_sentiment_analysis_neutral(self):
        """Test SentimentAnalysis with neutral fear score."""
        analysis: SentimentAnalysis = {
            "fear_score": 50,
            "summary": "Neutral sentiment",
            "source_count": 25
        }
        assert analysis["fear_score"] == 50
        assert analysis["source_count"] == 25


class TestVisionAnalysis:
    """Tests for VisionAnalysis TypedDict."""

    def test_vision_analysis_patterns_detected(self):
        """Test VisionAnalysis with detected patterns."""
        analysis: VisionAnalysis = {
            "patterns_detected": ["head_and_shoulders", "double_top"],
            "confidence_score": 80,
            "description": "Clear reversal patterns visible",
            "is_valid": True
        }
        assert len(analysis["patterns_detected"]) == 2
        assert "head_and_shoulders" in analysis["patterns_detected"]
        assert analysis["is_valid"] is True

    def test_vision_analysis_no_patterns(self):
        """Test VisionAnalysis with no patterns detected."""
        analysis: VisionAnalysis = {
            "patterns_detected": [],
            "confidence_score": 50,
            "description": "No clear patterns",
            "is_valid": True
        }
        assert len(analysis["patterns_detected"]) == 0
        assert analysis["is_valid"] is True

    def test_vision_analysis_scam_wick(self):
        """Test VisionAnalysis detecting manipulation (scam wick)."""
        analysis: VisionAnalysis = {
            "patterns_detected": ["scam_wick"],
            "confidence_score": 90,
            "description": "Potential manipulation detected",
            "is_valid": False
        }
        assert analysis["is_valid"] is False
        assert "scam_wick" in analysis["patterns_detected"]


class TestFinalDecision:
    """Tests for FinalDecision TypedDict."""

    def test_final_decision_buy(self):
        """Test FinalDecision with BUY action."""
        decision: FinalDecision = {
            "action": "BUY",
            "confidence": 85,
            "reasoning": "Fear is high, technicals bullish",
            "timestamp": datetime.now(timezone.utc)
        }
        assert decision["action"] == "BUY"
        assert decision["confidence"] == 85
        assert decision["timestamp"] is not None

    def test_final_decision_sell(self):
        """Test FinalDecision with SELL action."""
        decision: FinalDecision = {
            "action": "SELL",
            "confidence": 70,
            "reasoning": "Greed is high, technicals bearish",
            "timestamp": datetime.now(timezone.utc)
        }
        assert decision["action"] == "SELL"

    def test_final_decision_hold(self):
        """Test FinalDecision with HOLD action."""
        decision: FinalDecision = {
            "action": "HOLD",
            "confidence": 50,
            "reasoning": "Mixed signals, staying neutral",
            "timestamp": datetime.now(timezone.utc)
        }
        assert decision["action"] == "HOLD"


class TestGraphState:
    """Tests for GraphState TypedDict."""

    def test_graph_state_all_fields(self):
        """Test GraphState contains all required fields."""
        state: GraphState = {
            "asset_symbol": "SOLUSD",
            "candles_data": [],
            "sentiment_data": [],
            "technical_analysis": None,
            "sentiment_analysis": None,
            "vision_analysis": None,
            "final_decision": None,
            "error": None
        }
        assert state["asset_symbol"] == "SOLUSD"
        assert state["candles_data"] == []
        assert state["sentiment_data"] == []
        assert state["technical_analysis"] is None
        assert state["sentiment_analysis"] is None
        assert state["vision_analysis"] is None
        assert state["final_decision"] is None
        assert state["error"] is None

    def test_graph_state_with_data(self):
        """Test GraphState with populated data."""
        state: GraphState = {
            "asset_symbol": "BTCUSD",
            "candles_data": [
                {
                    "timestamp": datetime.now(timezone.utc),
                    "open": 50000.0,
                    "high": 51000.0,
                    "low": 49000.0,
                    "close": 50500.0,
                    "volume": 1000.0
                }
            ],
            "sentiment_data": [
                {"text": "BTC to the moon!", "source": "twitter"}
            ],
            "technical_analysis": {
                "signal": "BULLISH",
                "strength": 70,
                "rsi": 60.0,
                "sma_50": 48000.0,
                "sma_200": 45000.0,
                "volume_delta": 5.0,
                "reasoning": "Bullish momentum"
            },
            "sentiment_analysis": {
                "fear_score": 30,
                "summary": "Fear in market",
                "source_count": 100
            },
            "vision_analysis": {
                "patterns_detected": ["cup_and_handle"],
                "confidence_score": 75,
                "description": "Bullish continuation pattern",
                "is_valid": True
            },
            "final_decision": {
                "action": "BUY",
                "confidence": 80,
                "reasoning": "Contrarian buy signal",
                "timestamp": datetime.now(timezone.utc)
            },
            "error": None
        }
        assert state["asset_symbol"] == "BTCUSD"
        assert len(state["candles_data"]) == 1
        assert state["technical_analysis"]["signal"] == "BULLISH"
        assert state["final_decision"]["action"] == "BUY"

    def test_graph_state_with_error(self):
        """Test GraphState with error field populated."""
        state: GraphState = {
            "asset_symbol": "ETHUSD",
            "candles_data": [],
            "sentiment_data": [],
            "technical_analysis": None,
            "sentiment_analysis": None,
            "vision_analysis": None,
            "final_decision": None,
            "error": "Failed to fetch data from Kraken"
        }
        assert state["error"] is not None
        assert "Kraken" in state["error"]


class TestCreateInitialState:
    """Tests for create_initial_state factory function."""

    def test_create_initial_state_minimal(self):
        """Test create_initial_state with minimal parameters."""
        state = create_initial_state(asset_symbol="SOLUSD")

        assert state["asset_symbol"] == "SOLUSD"
        assert state["candles_data"] == []
        assert state["sentiment_data"] == []
        assert state["technical_analysis"] is None
        assert state["sentiment_analysis"] is None
        assert state["vision_analysis"] is None
        assert state["final_decision"] is None
        assert state["error"] is None

    def test_create_initial_state_with_candles(self):
        """Test create_initial_state with candles data."""
        candles: List[CandleData] = [
            {
                "timestamp": datetime.now(timezone.utc),
                "open": 100.0,
                "high": 105.0,
                "low": 98.0,
                "close": 103.0,
                "volume": 10000.0
            }
        ]
        state = create_initial_state(
            asset_symbol="SOLUSD",
            candles_data=candles
        )

        assert len(state["candles_data"]) == 1
        assert state["candles_data"][0]["open"] == 100.0

    def test_create_initial_state_with_sentiment(self):
        """Test create_initial_state with sentiment data."""
        sentiment: List[Dict[str, Any]] = [
            {"text": "SOL is great", "source": "twitter", "score": 0.8}
        ]
        state = create_initial_state(
            asset_symbol="SOLUSD",
            sentiment_data=sentiment
        )

        assert len(state["sentiment_data"]) == 1
        assert state["sentiment_data"][0]["source"] == "twitter"

    def test_create_initial_state_with_all_data(self):
        """Test create_initial_state with all data provided."""
        candles: List[CandleData] = [
            {
                "timestamp": datetime.now(timezone.utc),
                "open": 100.0,
                "high": 105.0,
                "low": 98.0,
                "close": 103.0,
                "volume": 10000.0
            }
        ]
        sentiment: List[Dict[str, Any]] = [
            {"text": "Bullish!", "source": "telegram"}
        ]
        state = create_initial_state(
            asset_symbol="BTCUSD",
            candles_data=candles,
            sentiment_data=sentiment
        )

        assert state["asset_symbol"] == "BTCUSD"
        assert len(state["candles_data"]) == 1
        assert len(state["sentiment_data"]) == 1
        # Output fields should be None
        assert state["technical_analysis"] is None
        assert state["final_decision"] is None
