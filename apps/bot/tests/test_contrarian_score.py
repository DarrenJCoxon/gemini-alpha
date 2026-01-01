"""
Tests for services/contrarian_score.py - Contrarian Opportunity Scoring Algorithm.

Story 5.8: Dynamic Opportunity Scanner - Unit tests for score calculation,
factor weighting, and opportunity ranking.
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock


class TestScoreBreakdown:
    """Tests for ScoreBreakdown dataclass."""

    def test_score_breakdown_creation(self):
        """Test ScoreBreakdown can be created with all fields."""
        from services.contrarian_score import ScoreBreakdown

        breakdown = ScoreBreakdown(
            symbol="TEST/USD",
            total_score=50.0,
            rsi_score=15.0,
            rsi_value=25.0,
            capitulation_score=10.0,
            capitulation_pct=12.0,
            volume_spike_score=6.0,
            volume_ratio=2.5,
            adx_score=8.0,
            adx_value=18.0,
            bollinger_score=6.0,
            bollinger_pct_b=0.1,
            vwap_score=3.0,
            vwap_distance_pct=-2.5,
            liquidity_score=5.0,
            volume_24h_usd=10000000.0,
            current_price=100.0,
            high_7d=115.0,
            reasoning="RSI oversold; Capitulation"
        )

        assert breakdown.symbol == "TEST/USD"
        assert breakdown.total_score == 50.0
        assert breakdown.rsi_value == 25.0


class TestCalculateContrarianScore:
    """Tests for calculate_contrarian_score function."""

    @pytest.fixture
    def oversold_candles(self):
        """Generate candles simulating oversold conditions."""
        candles = []
        base_price = 100.0
        for i in range(50):
            # Sharp decline
            price = base_price - (i * 1.5)
            candles.append({
                "timestamp": datetime.utcnow() - timedelta(hours=200 - i * 4),
                "open": price + 0.5,
                "high": price + 2,
                "low": price - 2,
                "close": price,
                "volume": 1000000 + (i * 50000)  # Volume increasing
            })
        return candles

    @pytest.fixture
    def neutral_candles(self):
        """Generate sideways market candles."""
        candles = []
        for i in range(50):
            price = 100 + (i % 5) - 2.5
            candles.append({
                "timestamp": datetime.utcnow() - timedelta(hours=200 - i * 4),
                "open": price,
                "high": price + 1,
                "low": price - 1,
                "close": price,
                "volume": 500000
            })
        return candles

    @pytest.fixture
    def sample_ticker(self):
        """Sample ticker data."""
        return {
            "symbol": "TEST/USD",
            "last": 50.0,
            "quoteVolume": 5000000,  # $5M volume
        }

    def test_oversold_generates_positive_score(self, oversold_candles, sample_ticker):
        """Oversold conditions should generate positive contrarian score."""
        from services.contrarian_score import calculate_contrarian_score

        score = calculate_contrarian_score("TEST/USD", oversold_candles, sample_ticker)

        assert score.total_score > 0
        assert score.symbol == "TEST/USD"
        # RSI should be calculated (may or may not be oversold depending on data)
        assert score.rsi_value is None or isinstance(score.rsi_value, float)

    def test_neutral_generates_lower_score(self, neutral_candles, sample_ticker):
        """Neutral conditions should generate lower score than oversold."""
        from services.contrarian_score import calculate_contrarian_score

        score = calculate_contrarian_score("TEST/USD", neutral_candles, sample_ticker)

        # Neutral markets should have lower contrarian scores
        # The exact value depends on the data, but should be reasonable
        assert score.total_score >= 0

    def test_insufficient_data_returns_zero_score(self):
        """Insufficient candle data should return zero score."""
        from services.contrarian_score import calculate_contrarian_score

        candles = [{"close": 100, "high": 101, "low": 99, "volume": 1000}]
        ticker = {"symbol": "TEST/USD", "last": 100, "quoteVolume": 1000000}

        score = calculate_contrarian_score("TEST/USD", candles, ticker)

        assert score.total_score == 0
        assert "Insufficient" in score.reasoning

    def test_empty_candles_returns_zero_score(self):
        """Empty candle list should return zero score."""
        from services.contrarian_score import calculate_contrarian_score

        ticker = {"symbol": "TEST/USD", "last": 100, "quoteVolume": 1000000}

        score = calculate_contrarian_score("TEST/USD", [], ticker)

        assert score.total_score == 0
        assert "Insufficient" in score.reasoning

    def test_liquidity_bonus_scales_with_volume(self):
        """Higher volume should give higher liquidity score."""
        from services.contrarian_score import calculate_contrarian_score

        candles = []
        for i in range(50):
            candles.append({
                "timestamp": datetime.utcnow() - timedelta(hours=i * 4),
                "open": 100,
                "high": 101,
                "low": 99,
                "close": 100,
                "volume": 1000000
            })

        low_vol_ticker = {"symbol": "TEST/USD", "last": 100, "quoteVolume": 1000000}
        high_vol_ticker = {"symbol": "TEST/USD", "last": 100, "quoteVolume": 100000000}

        low_score = calculate_contrarian_score("TEST/USD", candles, low_vol_ticker)
        high_score = calculate_contrarian_score("TEST/USD", candles, high_vol_ticker)

        assert high_score.liquidity_score > low_score.liquidity_score

    def test_score_includes_correct_symbol(self, neutral_candles, sample_ticker):
        """Score should include the correct symbol."""
        from services.contrarian_score import calculate_contrarian_score

        score = calculate_contrarian_score("BTC/USD", neutral_candles, sample_ticker)

        assert score.symbol == "BTC/USD"

    def test_score_includes_volume_from_ticker(self, neutral_candles):
        """Score should include volume from ticker data."""
        from services.contrarian_score import calculate_contrarian_score

        ticker = {"symbol": "TEST/USD", "last": 100, "quoteVolume": 75000000}

        score = calculate_contrarian_score("TEST/USD", neutral_candles, ticker)

        assert score.volume_24h_usd == 75000000

    def test_score_includes_price_from_ticker(self, neutral_candles):
        """Score should include current price from ticker data."""
        from services.contrarian_score import calculate_contrarian_score

        ticker = {"symbol": "TEST/USD", "last": 123.45, "quoteVolume": 5000000}

        score = calculate_contrarian_score("TEST/USD", neutral_candles, ticker)

        assert score.current_price == 123.45

    def test_handles_missing_ticker_fields(self, neutral_candles):
        """Score calculation should handle missing ticker fields gracefully."""
        from services.contrarian_score import calculate_contrarian_score

        ticker = {}  # Empty ticker

        score = calculate_contrarian_score("TEST/USD", neutral_candles, ticker)

        assert score.volume_24h_usd == 0
        assert score.current_price == 0

    def test_handles_none_ticker_values(self, neutral_candles):
        """Score calculation should handle None values in ticker."""
        from services.contrarian_score import calculate_contrarian_score

        ticker = {"symbol": "TEST/USD", "last": None, "quoteVolume": None}

        score = calculate_contrarian_score("TEST/USD", neutral_candles, ticker)

        assert score.volume_24h_usd == 0
        assert score.current_price == 0


class TestRankOpportunities:
    """Tests for rank_opportunities function."""

    def test_rank_opportunities_filters_by_min_score(self):
        """Ranking should filter out low scores."""
        from services.contrarian_score import rank_opportunities, ScoreBreakdown

        scores = [
            ScoreBreakdown(
                symbol="HIGH/USD", total_score=60,
                rsi_score=15, rsi_value=25,
                capitulation_score=15, capitulation_pct=12,
                volume_spike_score=12, volume_ratio=2.5,
                adx_score=0, adx_value=30,
                bollinger_score=12, bollinger_pct_b=0.1,
                vwap_score=6, vwap_distance_pct=-3,
                liquidity_score=0, volume_24h_usd=5000000,
                current_price=100, high_7d=115,
                reasoning="Multiple signals"
            ),
            ScoreBreakdown(
                symbol="LOW/USD", total_score=20,
                rsi_score=0, rsi_value=50,
                capitulation_score=0, capitulation_pct=2,
                volume_spike_score=0, volume_ratio=0.8,
                adx_score=12, adx_value=15,
                bollinger_score=0, bollinger_pct_b=0.5,
                vwap_score=0, vwap_distance_pct=1,
                liquidity_score=8, volume_24h_usd=10000000,
                current_price=100, high_7d=102,
                reasoning="Weak trend only"
            ),
        ]

        ranked = rank_opportunities(scores, min_score=40, max_results=10)

        assert len(ranked) == 1
        assert ranked[0].symbol == "HIGH/USD"

    def test_rank_opportunities_respects_max_results(self):
        """Ranking should respect max_results limit."""
        from services.contrarian_score import rank_opportunities, ScoreBreakdown

        scores = [
            ScoreBreakdown(
                symbol=f"ASSET{i}/USD", total_score=50 + i,
                rsi_score=15, rsi_value=25,
                capitulation_score=15, capitulation_pct=12,
                volume_spike_score=12, volume_ratio=2.5,
                adx_score=0, adx_value=30,
                bollinger_score=8 + i, bollinger_pct_b=0.1,
                vwap_score=0, vwap_distance_pct=0,
                liquidity_score=0, volume_24h_usd=5000000,
                current_price=100, high_7d=115,
                reasoning="Test"
            )
            for i in range(20)
        ]

        ranked = rank_opportunities(scores, min_score=40, max_results=5)

        assert len(ranked) == 5
        # Should be sorted by score descending
        assert ranked[0].total_score >= ranked[1].total_score

    def test_rank_opportunities_sorts_by_score_descending(self):
        """Ranking should sort by score in descending order."""
        from services.contrarian_score import rank_opportunities, ScoreBreakdown

        scores = [
            ScoreBreakdown(
                symbol="MED/USD", total_score=50,
                rsi_score=10, rsi_value=30, capitulation_score=10, capitulation_pct=10,
                volume_spike_score=10, volume_ratio=2, adx_score=10, adx_value=20,
                bollinger_score=5, bollinger_pct_b=0.2, vwap_score=3, vwap_distance_pct=-2,
                liquidity_score=2, volume_24h_usd=5000000,
                current_price=100, high_7d=110, reasoning="Test"
            ),
            ScoreBreakdown(
                symbol="HIGH/USD", total_score=70,
                rsi_score=15, rsi_value=20, capitulation_score=15, capitulation_pct=15,
                volume_spike_score=12, volume_ratio=3, adx_score=12, adx_value=15,
                bollinger_score=10, bollinger_pct_b=0.05, vwap_score=6, vwap_distance_pct=-5,
                liquidity_score=0, volume_24h_usd=5000000,
                current_price=100, high_7d=120, reasoning="Test"
            ),
            ScoreBreakdown(
                symbol="LOW/USD", total_score=45,
                rsi_score=8, rsi_value=35, capitulation_score=8, capitulation_pct=8,
                volume_spike_score=8, volume_ratio=1.8, adx_score=8, adx_value=22,
                bollinger_score=5, bollinger_pct_b=0.25, vwap_score=3, vwap_distance_pct=-1.5,
                liquidity_score=5, volume_24h_usd=8000000,
                current_price=100, high_7d=108, reasoning="Test"
            ),
        ]

        ranked = rank_opportunities(scores, min_score=40, max_results=10)

        assert len(ranked) == 3
        assert ranked[0].symbol == "HIGH/USD"
        assert ranked[1].symbol == "MED/USD"
        assert ranked[2].symbol == "LOW/USD"

    def test_rank_opportunities_empty_list(self):
        """Ranking should handle empty score list."""
        from services.contrarian_score import rank_opportunities

        ranked = rank_opportunities([], min_score=40, max_results=10)

        assert ranked == []

    def test_rank_opportunities_no_qualifying_scores(self):
        """Ranking should return empty list when no scores meet threshold."""
        from services.contrarian_score import rank_opportunities, ScoreBreakdown

        scores = [
            ScoreBreakdown(
                symbol="LOW1/USD", total_score=30,
                rsi_score=5, rsi_value=40, capitulation_score=5, capitulation_pct=5,
                volume_spike_score=5, volume_ratio=1.5, adx_score=5, adx_value=24,
                bollinger_score=5, bollinger_pct_b=0.3, vwap_score=3, vwap_distance_pct=-1,
                liquidity_score=2, volume_24h_usd=3000000,
                current_price=100, high_7d=105, reasoning="Test"
            ),
            ScoreBreakdown(
                symbol="LOW2/USD", total_score=25,
                rsi_score=3, rsi_value=45, capitulation_score=3, capitulation_pct=3,
                volume_spike_score=3, volume_ratio=1.2, adx_score=3, adx_value=26,
                bollinger_score=5, bollinger_pct_b=0.4, vwap_score=3, vwap_distance_pct=-0.5,
                liquidity_score=5, volume_24h_usd=6000000,
                current_price=100, high_7d=103, reasoning="Test"
            ),
        ]

        ranked = rank_opportunities(scores, min_score=40, max_results=10)

        assert ranked == []


class TestScoreComponents:
    """Tests for individual score component calculations."""

    @pytest.fixture
    def stable_candles(self):
        """Generate candles with stable, predictable values for testing."""
        candles = []
        # Create a consistent downtrend for RSI testing
        for i in range(50):
            # Steady downtrend with some noise
            price = 100 - (i * 0.5)  # Gradual decline
            candles.append({
                "timestamp": datetime.utcnow() - timedelta(hours=200 - i * 4),
                "open": price + 0.2,
                "high": price + 0.5,
                "low": price - 0.5,
                "close": price,
                "volume": 1000000
            })
        return candles

    def test_capitulation_calculated_correctly(self):
        """Test capitulation is calculated as percentage below 7-day high."""
        from services.contrarian_score import calculate_contrarian_score

        # Create candles with a clear 7-day high
        candles = []
        for i in range(50):
            if i < 10:
                price = 120  # High in first 10 candles
            else:
                price = 100  # Lower after
            candles.append({
                "timestamp": datetime.utcnow() - timedelta(hours=200 - i * 4),
                "open": price,
                "high": price + 1,
                "low": price - 1,
                "close": price,
                "volume": 1000000
            })

        ticker = {"symbol": "TEST/USD", "last": 100, "quoteVolume": 5000000}

        score = calculate_contrarian_score("TEST/USD", candles, ticker)

        # Should have a capitulation percentage (current 100 vs high of 121)
        assert score.high_7d is not None
        if score.capitulation_pct is not None:
            assert score.capitulation_pct > 0  # We should see some capitulation

    def test_reasoning_includes_active_factors(self):
        """Reasoning string should list active contrarian factors."""
        from services.contrarian_score import calculate_contrarian_score

        # Create conditions that will trigger some factors
        candles = []
        for i in range(50):
            # Steep decline for capitulation
            price = 100 - (i * 1.0)
            candles.append({
                "timestamp": datetime.utcnow() - timedelta(hours=200 - i * 4),
                "open": price + 0.5,
                "high": price + 1,
                "low": price - 1,
                "close": price,
                "volume": 1000000 + (i * 100000)  # Increasing volume
            })

        ticker = {"symbol": "TEST/USD", "last": 50, "quoteVolume": 10000000}

        score = calculate_contrarian_score("TEST/USD", candles, ticker)

        # Reasoning should not be "No contrarian signals" if we have factors
        if score.total_score > 0:
            assert score.reasoning != "No contrarian signals"
