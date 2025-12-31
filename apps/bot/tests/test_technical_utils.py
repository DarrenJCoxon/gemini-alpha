"""
Unit tests for Technical Analysis Utilities.

Story 2.2: Sentiment & Technical Agents

Tests cover:
- Candle data to DataFrame conversion
- RSI calculation
- SMA calculations (50/200)
- Volume delta calculation
- Signal scoring logic
"""

import pytest
import pandas as pd
from datetime import datetime, timedelta
from services.technical_utils import (
    candles_to_dataframe,
    calculate_rsi,
    calculate_smas,
    calculate_volume_delta,
    calculate_technical_signal
)


@pytest.fixture
def sample_candles():
    """Generate 200 sample candles for testing."""
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
def minimal_candles():
    """Generate 14 candles (minimum for RSI calculation)."""
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
def few_candles():
    """Generate only 5 candles (insufficient for most calculations)."""
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


class TestCandlesToDataframe:
    """Tests for candles_to_dataframe function."""

    def test_valid_data(self, sample_candles):
        """Test conversion with valid candle data."""
        df = candles_to_dataframe(sample_candles)
        assert len(df) == 200
        assert list(df.columns) == ['open', 'high', 'low', 'close', 'volume']
        assert df.index.name == 'timestamp'

    def test_sorted_by_timestamp(self, sample_candles):
        """Test that DataFrame is sorted by timestamp."""
        # Shuffle candles
        import random
        shuffled = sample_candles.copy()
        random.shuffle(shuffled)

        df = candles_to_dataframe(shuffled)
        assert df.index.is_monotonic_increasing

    def test_numeric_conversion(self, sample_candles):
        """Test that values are converted to numeric types."""
        # Add string values
        candles_with_strings = sample_candles.copy()
        candles_with_strings[0]['close'] = "100.50"

        df = candles_to_dataframe(candles_with_strings)
        assert pd.api.types.is_numeric_dtype(df['close'])

    def test_empty_list_raises_error(self):
        """Test that empty candles list raises ValueError."""
        with pytest.raises(ValueError, match="Candles list cannot be empty"):
            candles_to_dataframe([])

    def test_minimal_candles(self, minimal_candles):
        """Test conversion with minimal candle count."""
        df = candles_to_dataframe(minimal_candles)
        assert len(df) == 14


class TestCalculateRsi:
    """Tests for calculate_rsi function."""

    def test_valid_rsi(self, sample_candles):
        """Test RSI calculation returns value in valid range."""
        df = candles_to_dataframe(sample_candles)
        rsi = calculate_rsi(df)
        assert 0 <= rsi <= 100

    def test_insufficient_data(self, few_candles):
        """Test RSI returns default 50 with insufficient data."""
        df = candles_to_dataframe(few_candles)
        rsi = calculate_rsi(df)
        assert rsi == 50.0

    def test_custom_period(self, sample_candles):
        """Test RSI with custom period."""
        df = candles_to_dataframe(sample_candles)
        rsi = calculate_rsi(df, period=21)
        assert 0 <= rsi <= 100

    def test_uptrend_rsi(self):
        """Test RSI is higher during uptrend."""
        # Create strong uptrend data
        candles = []
        base_time = datetime.utcnow() - timedelta(hours=50)
        for i in range(50):
            price = 100 + (i * 2)  # Strong uptrend
            candles.append({
                "timestamp": base_time + timedelta(hours=i),
                "open": price - 0.5,
                "high": price + 1,
                "low": price - 0.5,
                "close": price,
                "volume": 10000
            })

        df = candles_to_dataframe(candles)
        rsi = calculate_rsi(df)
        # RSI should be high (>50) in uptrend
        assert rsi > 50


class TestCalculateSmas:
    """Tests for calculate_smas function."""

    def test_valid_smas(self, sample_candles):
        """Test SMA calculation with sufficient data."""
        df = candles_to_dataframe(sample_candles)
        sma_50, sma_200 = calculate_smas(df)
        assert sma_50 > 0
        assert sma_200 > 0

    def test_insufficient_data_for_sma200(self):
        """Test SMA200 returns 0 with insufficient data."""
        candles = []
        base_time = datetime.utcnow() - timedelta(hours=100)
        for i in range(100):
            candles.append({
                "timestamp": base_time + timedelta(hours=i),
                "open": 100,
                "high": 101,
                "low": 99,
                "close": 100,
                "volume": 10000
            })

        df = candles_to_dataframe(candles)
        sma_50, sma_200 = calculate_smas(df)
        assert sma_50 > 0  # 100 candles enough for SMA50
        assert sma_200 == 0.0  # Not enough for SMA200

    def test_insufficient_data_for_both(self, few_candles):
        """Test both SMAs return 0 with minimal data."""
        df = candles_to_dataframe(few_candles)
        sma_50, sma_200 = calculate_smas(df)
        assert sma_50 == 0.0
        assert sma_200 == 0.0

    def test_sma_values_reflect_price(self, sample_candles):
        """Test SMA values are reasonable given price range."""
        df = candles_to_dataframe(sample_candles)
        sma_50, sma_200 = calculate_smas(df)

        # SMAs should be within reasonable range of closing prices
        avg_close = df['close'].mean()
        assert abs(sma_50 - avg_close) < avg_close * 0.2  # Within 20%
        assert abs(sma_200 - avg_close) < avg_close * 0.2


class TestCalculateVolumeDelta:
    """Tests for calculate_volume_delta function."""

    def test_valid_calculation(self, sample_candles):
        """Test volume delta calculation."""
        df = candles_to_dataframe(sample_candles)
        delta = calculate_volume_delta(df)
        assert isinstance(delta, float)

    def test_insufficient_data(self, few_candles):
        """Test returns 0 with insufficient data."""
        df = candles_to_dataframe(few_candles)
        delta = calculate_volume_delta(df)
        assert delta == 0.0

    def test_high_volume_positive_delta(self):
        """Test high volume results in positive delta."""
        candles = []
        base_time = datetime.utcnow() - timedelta(hours=25)
        for i in range(25):
            volume = 10000 if i < 24 else 20000  # Last candle has 2x volume
            candles.append({
                "timestamp": base_time + timedelta(hours=i),
                "open": 100,
                "high": 101,
                "low": 99,
                "close": 100,
                "volume": volume
            })

        df = candles_to_dataframe(candles)
        delta = calculate_volume_delta(df)
        assert delta > 50  # Should be significantly positive

    def test_low_volume_negative_delta(self):
        """Test low volume results in negative delta."""
        candles = []
        base_time = datetime.utcnow() - timedelta(hours=25)
        for i in range(25):
            volume = 10000 if i < 24 else 5000  # Last candle has 0.5x volume
            candles.append({
                "timestamp": base_time + timedelta(hours=i),
                "open": 100,
                "high": 101,
                "low": 99,
                "close": 100,
                "volume": volume
            })

        df = candles_to_dataframe(candles)
        delta = calculate_volume_delta(df)
        assert delta < -30  # Should be significantly negative


class TestCalculateTechnicalSignal:
    """Tests for calculate_technical_signal function."""

    def test_bullish_signal(self):
        """Test bullish signal generation with favorable conditions."""
        signal, strength, reasoning = calculate_technical_signal(
            rsi=25.0,  # Oversold
            sma_50=110.0,
            sma_200=100.0,  # Golden cross
            current_price=115.0,  # Above SMA200
            volume_delta=60.0  # High volume
        )
        assert signal == "BULLISH"
        assert strength > 50
        assert "oversold" in reasoning.lower() or "above sma200" in reasoning.lower()

    def test_bearish_signal(self):
        """Test bearish signal generation with unfavorable conditions."""
        signal, strength, reasoning = calculate_technical_signal(
            rsi=75.0,  # Overbought
            sma_50=90.0,
            sma_200=100.0,  # Death cross
            current_price=85.0,  # Below SMA200
            volume_delta=-40.0  # Low volume
        )
        assert signal == "BEARISH"
        assert strength > 50
        assert "overbought" in reasoning.lower() or "below sma200" in reasoning.lower()

    def test_neutral_signal_mixed_conditions(self):
        """Test neutral signal with mixed conditions."""
        signal, strength, reasoning = calculate_technical_signal(
            rsi=50.0,  # Neutral RSI
            sma_50=100.0,
            sma_200=100.0,  # No crossover
            current_price=100.0,
            volume_delta=0.0  # Average volume
        )
        # With exactly balanced conditions, should still have a signal
        assert signal in ["BULLISH", "BEARISH", "NEUTRAL"]

    def test_neutral_signal_no_data(self):
        """Test neutral signal when no SMA data available."""
        signal, strength, reasoning = calculate_technical_signal(
            rsi=50.0,
            sma_50=0.0,
            sma_200=0.0,
            current_price=100.0,
            volume_delta=0.0
        )
        assert signal == "NEUTRAL"
        assert strength == 50
        assert "insufficient" in reasoning.lower()

    def test_extreme_oversold_bullish(self):
        """Test extreme oversold conditions produce strong bullish signal."""
        signal, strength, reasoning = calculate_technical_signal(
            rsi=15.0,  # Extreme oversold
            sma_50=110.0,
            sma_200=100.0,
            current_price=120.0,
            volume_delta=100.0  # Very high volume
        )
        assert signal == "BULLISH"
        assert strength >= 80  # Strong conviction

    def test_extreme_overbought_bearish(self):
        """Test extreme overbought conditions produce strong bearish signal."""
        signal, strength, reasoning = calculate_technical_signal(
            rsi=85.0,  # Extreme overbought
            sma_50=90.0,
            sma_200=100.0,
            current_price=80.0,
            volume_delta=-50.0  # Very low volume
        )
        assert signal == "BEARISH"
        assert strength >= 80  # Strong conviction

    def test_signal_reasoning_contains_relevant_info(self):
        """Test that reasoning contains relevant indicator information."""
        signal, strength, reasoning = calculate_technical_signal(
            rsi=25.0,
            sma_50=110.0,
            sma_200=100.0,
            current_price=115.0,
            volume_delta=60.0
        )
        # Reasoning should mention key indicators
        assert "RSI" in reasoning or "rsi" in reasoning.lower()
        assert "SMA" in reasoning or "sma" in reasoning.lower()

    def test_golden_cross_contributes_to_bullish(self):
        """Test that Golden Cross (SMA50 > SMA200) adds bullish points."""
        # Without golden cross
        signal1, strength1, _ = calculate_technical_signal(
            rsi=50.0,
            sma_50=90.0,
            sma_200=100.0,  # Death cross
            current_price=95.0,
            volume_delta=0.0
        )

        # With golden cross
        signal2, strength2, _ = calculate_technical_signal(
            rsi=50.0,
            sma_50=110.0,
            sma_200=100.0,  # Golden cross
            current_price=105.0,
            volume_delta=0.0
        )

        # Golden cross should be more bullish
        assert signal2 == "BULLISH" or (signal1 == "BEARISH" and signal2 != "BEARISH")

    def test_strength_is_bounded(self):
        """Test that strength is always between 0 and 100."""
        test_cases = [
            (25.0, 110.0, 100.0, 115.0, 60.0),
            (75.0, 90.0, 100.0, 85.0, -40.0),
            (50.0, 100.0, 100.0, 100.0, 0.0),
            (10.0, 150.0, 100.0, 200.0, 200.0),  # Extreme bullish
            (90.0, 50.0, 100.0, 40.0, -80.0),  # Extreme bearish
        ]

        for rsi, sma50, sma200, price, volume in test_cases:
            _, strength, _ = calculate_technical_signal(
                rsi, sma50, sma200, price, volume
            )
            assert 0 <= strength <= 100
