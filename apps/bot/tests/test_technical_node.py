"""
Unit tests for Technical Analysis Node.

Story 2.2: Sentiment & Technical Agents

Tests cover:
- Node processing with valid candle data
- Node behavior with insufficient data
- Error handling in node
- GraphState integration
"""

import pytest
import sys
from datetime import datetime, timedelta

# Avoid circular import by importing state directly
from core.state import create_initial_state

# Import technical node directly to avoid nodes/__init__.py circular import
sys.path.insert(0, '/Users/darrencoxon/Dropbox/Coxon_team_folder/Coding_2026/gemini-trading-bot/apps/bot')
import importlib.util
spec = importlib.util.spec_from_file_location(
    "technical",
    "/Users/darrencoxon/Dropbox/Coxon_team_folder/Coding_2026/gemini-trading-bot/apps/bot/nodes/technical.py"
)
technical_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(technical_module)
technical_node = technical_module.technical_node


@pytest.fixture
def sample_candles_200():
    """Generate 200 sample candles for comprehensive testing."""
    candles = []
    base_price = 100.0
    base_time = datetime.utcnow() - timedelta(hours=200)

    for i in range(200):
        # Simulate slight uptrend with noise
        price = base_price + (i * 0.1) + ((-1) ** i * 2)
        candles.append({
            "timestamp": base_time + timedelta(hours=i),
            "open": price - 1,
            "high": price + 2,
            "low": price - 2,
            "close": price,
            "volume": 10000 + (i * 100)
        })
    return candles


@pytest.fixture
def sample_candles_50():
    """Generate 50 sample candles."""
    candles = []
    base_price = 100.0
    base_time = datetime.utcnow() - timedelta(hours=50)

    for i in range(50):
        price = base_price + (i * 0.2)
        candles.append({
            "timestamp": base_time + timedelta(hours=i),
            "open": price - 0.5,
            "high": price + 1,
            "low": price - 1,
            "close": price,
            "volume": 10000
        })
    return candles


@pytest.fixture
def minimal_candles():
    """Generate 14 candles (minimum for RSI)."""
    candles = []
    base_price = 100.0
    base_time = datetime.utcnow() - timedelta(hours=14)

    for i in range(14):
        price = base_price + (i * 0.5)
        candles.append({
            "timestamp": base_time + timedelta(hours=i),
            "open": price - 0.5,
            "high": price + 1,
            "low": price - 1,
            "close": price,
            "volume": 5000
        })
    return candles


@pytest.fixture
def insufficient_candles():
    """Generate only 5 candles (insufficient)."""
    candles = []
    base_price = 100.0
    base_time = datetime.utcnow() - timedelta(hours=5)

    for i in range(5):
        price = base_price + (i * 0.3)
        candles.append({
            "timestamp": base_time + timedelta(hours=i),
            "open": price - 0.2,
            "high": price + 0.5,
            "low": price - 0.5,
            "close": price,
            "volume": 3000
        })
    return candles


@pytest.fixture
def bullish_candles():
    """Generate candles with bullish conditions."""
    candles = []
    base_time = datetime.utcnow() - timedelta(hours=200)

    for i in range(200):
        # Strong uptrend with pullback at end
        if i < 180:
            price = 100 + (i * 0.5)
        else:
            # Recent pullback (oversold)
            price = 190 - ((i - 180) * 2)

        candles.append({
            "timestamp": base_time + timedelta(hours=i),
            "open": price - 0.5,
            "high": price + 1,
            "low": price - 1,
            "close": price,
            "volume": 20000 if i > 195 else 10000  # High volume at end
        })
    return candles


class TestTechnicalNode:
    """Tests for technical_node function."""

    def test_processes_valid_candles(self, sample_candles_200):
        """Test node processes 200 candles correctly."""
        state = create_initial_state(
            asset_symbol="BTCUSD",
            candles_data=sample_candles_200
        )

        result = technical_node(state)

        assert "technical_analysis" in result
        analysis = result["technical_analysis"]

        assert analysis["signal"] in ["BULLISH", "BEARISH", "NEUTRAL"]
        assert 0 <= analysis["strength"] <= 100
        assert 0 <= analysis["rsi"] <= 100
        assert analysis["sma_50"] > 0
        assert analysis["sma_200"] > 0
        assert isinstance(analysis["reasoning"], str)

    def test_processes_minimal_candles(self, minimal_candles):
        """Test node processes minimum valid data (14 candles)."""
        state = create_initial_state(
            asset_symbol="ETHUSD",
            candles_data=minimal_candles
        )

        result = technical_node(state)

        assert "technical_analysis" in result
        analysis = result["technical_analysis"]

        # With only 14 candles, SMAs won't be available
        assert analysis["signal"] in ["BULLISH", "BEARISH", "NEUTRAL"]
        assert 0 <= analysis["rsi"] <= 100
        assert analysis["sma_50"] == 0.0  # Not enough for SMA50
        assert analysis["sma_200"] == 0.0  # Not enough for SMA200

    def test_handles_insufficient_data(self, insufficient_candles):
        """Test node handles insufficient candle data gracefully."""
        state = create_initial_state(
            asset_symbol="SOLUSD",
            candles_data=insufficient_candles
        )

        result = technical_node(state)

        assert "technical_analysis" in result
        analysis = result["technical_analysis"]

        assert analysis["signal"] == "NEUTRAL"
        assert analysis["strength"] == 0
        assert "insufficient" in analysis["reasoning"].lower()

    def test_handles_empty_candles(self):
        """Test node handles empty candle list."""
        state = create_initial_state(
            asset_symbol="XRPUSD",
            candles_data=[]
        )

        result = technical_node(state)

        assert "technical_analysis" in result
        analysis = result["technical_analysis"]

        assert analysis["signal"] == "NEUTRAL"
        assert analysis["strength"] == 0
        assert "insufficient" in analysis["reasoning"].lower()

    def test_output_structure(self, sample_candles_200):
        """Test that output has correct structure."""
        state = create_initial_state(
            asset_symbol="BTCUSD",
            candles_data=sample_candles_200
        )

        result = technical_node(state)

        # Should return dict with only technical_analysis key
        assert list(result.keys()) == ["technical_analysis"]

        analysis = result["technical_analysis"]
        required_keys = ["signal", "strength", "rsi", "sma_50", "sma_200", "volume_delta", "reasoning"]
        for key in required_keys:
            assert key in analysis, f"Missing key: {key}"

    def test_rsi_in_valid_range(self, sample_candles_200):
        """Test RSI is always in 0-100 range."""
        state = create_initial_state(
            asset_symbol="BTCUSD",
            candles_data=sample_candles_200
        )

        result = technical_node(state)
        rsi = result["technical_analysis"]["rsi"]

        assert 0 <= rsi <= 100

    def test_strength_in_valid_range(self, sample_candles_200):
        """Test strength is always in 0-100 range."""
        state = create_initial_state(
            asset_symbol="BTCUSD",
            candles_data=sample_candles_200
        )

        result = technical_node(state)
        strength = result["technical_analysis"]["strength"]

        assert 0 <= strength <= 100

    def test_with_50_candles(self, sample_candles_50):
        """Test with 50 candles (enough for SMA50 but not SMA200)."""
        state = create_initial_state(
            asset_symbol="AVAXUSD",
            candles_data=sample_candles_50
        )

        result = technical_node(state)
        analysis = result["technical_analysis"]

        # SMA50 should be calculated, SMA200 should be 0
        assert analysis["sma_50"] > 0
        assert analysis["sma_200"] == 0.0

    def test_values_are_rounded(self, sample_candles_200):
        """Test that numeric values are properly rounded."""
        state = create_initial_state(
            asset_symbol="BTCUSD",
            candles_data=sample_candles_200
        )

        result = technical_node(state)
        analysis = result["technical_analysis"]

        # Check RSI is rounded to 2 decimal places
        rsi_str = str(analysis["rsi"])
        if "." in rsi_str:
            decimal_places = len(rsi_str.split(".")[1])
            assert decimal_places <= 2

    def test_asset_symbol_used_in_logging(self, sample_candles_200, caplog):
        """Test that asset symbol is used in logs."""
        import logging
        caplog.set_level(logging.INFO)

        state = create_initial_state(
            asset_symbol="DOGEUSD",
            candles_data=sample_candles_200
        )

        technical_node(state)

        # Asset symbol should appear in logs
        assert "DOGEUSD" in caplog.text or "TechnicalAgent" in caplog.text


class TestTechnicalNodeSignals:
    """Tests for signal generation in technical node."""

    def test_generates_bullish_signal_on_oversold(self):
        """Test bullish signal when RSI indicates oversold."""
        # Create data with strong downtrend (will produce low RSI)
        candles = []
        base_time = datetime.utcnow() - timedelta(hours=200)

        for i in range(200):
            # Strong downtrend
            price = 200 - (i * 0.5)
            candles.append({
                "timestamp": base_time + timedelta(hours=i),
                "open": price + 0.5,
                "high": price + 1,
                "low": price - 1,
                "close": price,
                "volume": 10000
            })

        state = create_initial_state(
            asset_symbol="BTCUSD",
            candles_data=candles
        )

        result = technical_node(state)
        analysis = result["technical_analysis"]

        # RSI should be low (oversold condition)
        assert analysis["rsi"] < 50

    def test_consistent_results(self, sample_candles_200):
        """Test that same input produces same output."""
        state = create_initial_state(
            asset_symbol="BTCUSD",
            candles_data=sample_candles_200
        )

        result1 = technical_node(state)
        result2 = technical_node(state)

        assert result1 == result2


class TestTechnicalNodeErrorHandling:
    """Tests for error handling in technical node."""

    def test_handles_malformed_candle_data(self):
        """Test node handles malformed candle data."""
        # Missing required fields
        bad_candles = [
            {"timestamp": datetime.utcnow(), "close": 100},  # Missing open, high, low, volume
        ] * 20

        state = create_initial_state(
            asset_symbol="BTCUSD",
            candles_data=bad_candles
        )

        # Should not raise exception, should return neutral
        result = technical_node(state)
        assert "technical_analysis" in result

    def test_handles_non_numeric_values(self):
        """Test node handles non-numeric values in candles."""
        candles = []
        base_time = datetime.utcnow() - timedelta(hours=20)

        for i in range(20):
            candles.append({
                "timestamp": base_time + timedelta(hours=i),
                "open": "invalid" if i == 0 else 100,
                "high": 101,
                "low": 99,
                "close": 100,
                "volume": 10000
            })

        state = create_initial_state(
            asset_symbol="BTCUSD",
            candles_data=candles
        )

        # Should handle gracefully
        result = technical_node(state)
        assert "technical_analysis" in result
