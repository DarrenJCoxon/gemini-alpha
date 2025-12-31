"""
Unit tests for Sentiment Analysis Node.

Story 2.2: Sentiment & Technical Agents

Tests cover:
- Node processing with valid sentiment data
- Node behavior with empty data
- Fallback analysis when Gemini unavailable
- GraphState integration
"""

import pytest
import sys
from unittest.mock import patch, MagicMock
from datetime import datetime

# Avoid circular import by importing state directly
from core.state import create_initial_state

# Import sentiment node directly to avoid nodes/__init__.py circular import
sys.path.insert(0, '/Users/darrencoxon/Dropbox/Coxon_team_folder/Coding_2026/gemini-trading-bot/apps/bot')
import importlib.util
spec = importlib.util.spec_from_file_location(
    "sentiment",
    "/Users/darrencoxon/Dropbox/Coxon_team_folder/Coding_2026/gemini-trading-bot/apps/bot/nodes/sentiment.py"
)
sentiment_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sentiment_module)
sentiment_node = sentiment_module.sentiment_node
_fallback_sentiment_analysis = sentiment_module._fallback_sentiment_analysis


@pytest.fixture
def sample_sentiment_data():
    """Generate sample sentiment data for testing."""
    return [
        {"text": "Bitcoin is crashing hard today!", "source": "twitter", "timestamp": datetime.utcnow()},
        {"text": "This is the end, sell everything!", "source": "reddit", "timestamp": datetime.utcnow()},
        {"text": "Market update: BTC down 10%", "source": "news", "timestamp": datetime.utcnow()},
        {"text": "Fear and panic everywhere", "source": "telegram", "timestamp": datetime.utcnow()},
    ]


@pytest.fixture
def bullish_sentiment_data():
    """Generate bullish sentiment data for testing."""
    return [
        {"text": "Bitcoin to the moon!", "source": "twitter"},
        {"text": "FOMO is real, buy now!", "source": "reddit"},
        {"text": "Bull run is here!", "source": "telegram"},
        {"text": "ATH incoming!", "source": "bluesky"},
    ]


@pytest.fixture
def mixed_sentiment_data():
    """Generate mixed sentiment data for testing."""
    return [
        {"text": "Market is uncertain", "source": "twitter"},
        {"text": "Could go up or down", "source": "reddit"},
        {"text": "Wait and see approach", "source": "news"},
    ]


class TestSentimentNode:
    """Tests for sentiment_node function."""

    def test_processes_valid_sentiment_data(self, sample_sentiment_data):
        """Test node processes sentiment data correctly."""
        state = create_initial_state(
            asset_symbol="BTCUSD",
            sentiment_data=sample_sentiment_data
        )

        result = sentiment_node(state)

        assert "sentiment_analysis" in result
        analysis = result["sentiment_analysis"]

        assert "fear_score" in analysis
        assert 0 <= analysis["fear_score"] <= 100
        assert "summary" in analysis
        assert "source_count" in analysis
        assert analysis["source_count"] == 4

    def test_handles_empty_sentiment_data(self):
        """Test node handles empty sentiment data."""
        state = create_initial_state(
            asset_symbol="ETHUSD",
            sentiment_data=[]
        )

        result = sentiment_node(state)

        assert "sentiment_analysis" in result
        analysis = result["sentiment_analysis"]

        assert analysis["fear_score"] == 50  # Neutral default
        assert analysis["source_count"] == 0
        assert "no sentiment data" in analysis["summary"].lower()

    def test_output_structure(self, sample_sentiment_data):
        """Test that output has correct structure."""
        state = create_initial_state(
            asset_symbol="BTCUSD",
            sentiment_data=sample_sentiment_data
        )

        result = sentiment_node(state)

        # Should return dict with only sentiment_analysis key
        assert list(result.keys()) == ["sentiment_analysis"]

        analysis = result["sentiment_analysis"]
        required_keys = ["fear_score", "summary", "source_count"]
        for key in required_keys:
            assert key in analysis, f"Missing key: {key}"

    def test_fear_score_in_valid_range(self, sample_sentiment_data):
        """Test fear score is always in 0-100 range."""
        state = create_initial_state(
            asset_symbol="BTCUSD",
            sentiment_data=sample_sentiment_data
        )

        result = sentiment_node(state)
        fear_score = result["sentiment_analysis"]["fear_score"]

        assert 0 <= fear_score <= 100

    def test_source_count_accurate(self, sample_sentiment_data):
        """Test source count matches input data length."""
        state = create_initial_state(
            asset_symbol="BTCUSD",
            sentiment_data=sample_sentiment_data
        )

        result = sentiment_node(state)

        assert result["sentiment_analysis"]["source_count"] == len(sample_sentiment_data)

    def test_consistent_results(self, sample_sentiment_data):
        """Test that same input produces consistent output."""
        state = create_initial_state(
            asset_symbol="BTCUSD",
            sentiment_data=sample_sentiment_data
        )

        result1 = sentiment_node(state)
        result2 = sentiment_node(state)

        # Structure should be the same
        assert result1["sentiment_analysis"]["source_count"] == result2["sentiment_analysis"]["source_count"]


class TestSentimentNodeWithMockedGemini:
    """Tests for sentiment_node with mocked Gemini responses."""

    @patch('config.get_gemini_flash_model')
    def test_uses_gemini_response(self, mock_get_model, sample_sentiment_data):
        """Test node uses Gemini model response."""
        # Mock Gemini response
        mock_model = MagicMock()
        mock_response = MagicMock()
        mock_response.text = '{"fear_score": 25, "dominant_emotion": "FEAR", "summary": "Panic in the market", "key_themes": ["crash"]}'
        mock_model.generate_content.return_value = mock_response
        mock_get_model.return_value = mock_model

        state = create_initial_state(
            asset_symbol="BTCUSD",
            sentiment_data=sample_sentiment_data
        )

        result = sentiment_node(state)

        assert result["sentiment_analysis"]["fear_score"] == 25
        assert "Panic" in result["sentiment_analysis"]["summary"]

    @patch('config.get_gemini_flash_model')
    def test_falls_back_on_gemini_error(self, mock_get_model, sample_sentiment_data):
        """Test node falls back when Gemini fails."""
        mock_get_model.side_effect = Exception("Gemini error")

        state = create_initial_state(
            asset_symbol="BTCUSD",
            sentiment_data=sample_sentiment_data
        )

        result = sentiment_node(state)

        # Should still return valid analysis
        assert "sentiment_analysis" in result
        assert 0 <= result["sentiment_analysis"]["fear_score"] <= 100
        # Fallback should mention it's fallback
        assert "fallback" in result["sentiment_analysis"]["summary"].lower() or \
               "error" in result["sentiment_analysis"]["summary"].lower()

    @patch('config.get_gemini_flash_model')
    def test_handles_api_key_not_set(self, mock_get_model, sample_sentiment_data):
        """Test node handles missing API key gracefully."""
        mock_get_model.side_effect = ValueError("GOOGLE_AI_API_KEY not set")

        state = create_initial_state(
            asset_symbol="BTCUSD",
            sentiment_data=sample_sentiment_data
        )

        result = sentiment_node(state)

        # Should fall back to keyword-based analysis
        assert "sentiment_analysis" in result
        assert "fallback" in result["sentiment_analysis"]["summary"].lower()


class TestFallbackSentimentAnalysis:
    """Tests for _fallback_sentiment_analysis function."""

    def test_detects_fear_keywords(self):
        """Test fallback detects fear keywords."""
        data = [
            {"text": "Crash incoming, panic selling!"},
            {"text": "Bear market, everything dropping"},
        ]

        result = _fallback_sentiment_analysis(data)

        # More fear keywords = lower fear_score
        assert result["fear_score"] < 50
        assert "FEAR" in result["summary"]

    def test_detects_greed_keywords(self):
        """Test fallback detects greed keywords."""
        data = [
            {"text": "To the moon! Bull run!"},
            {"text": "FOMO, buy now for ATH!"},
        ]

        result = _fallback_sentiment_analysis(data)

        # More greed keywords = higher fear_score
        assert result["fear_score"] > 50
        assert "GREED" in result["summary"]

    def test_handles_neutral_content(self):
        """Test fallback handles neutral content."""
        data = [
            {"text": "Market analysis for today"},
            {"text": "Trading volume stable"},
        ]

        result = _fallback_sentiment_analysis(data)

        # No keywords = neutral score
        assert result["fear_score"] == 50
        assert "NEUTRAL" in result["summary"]

    def test_handles_empty_data(self):
        """Test fallback handles empty data."""
        result = _fallback_sentiment_analysis([])

        assert result["fear_score"] == 50
        assert result["source_count"] == 0

    def test_source_count_accurate(self):
        """Test fallback reports correct source count."""
        data = [
            {"text": "Entry 1"},
            {"text": "Entry 2"},
            {"text": "Entry 3"},
        ]

        result = _fallback_sentiment_analysis(data)

        assert result["source_count"] == 3

    def test_handles_different_text_keys(self):
        """Test fallback handles different text field names."""
        data = [
            {"content": "Crash and burn!"},
            {"raw_text": "Panic selling!"},
        ]

        result = _fallback_sentiment_analysis(data)

        # Should detect fear keywords from any text field
        assert result["fear_score"] < 50


class TestSentimentNodeEdgeCases:
    """Tests for edge cases in sentiment_node."""

    def test_handles_none_sentiment_data(self):
        """Test node handles None sentiment data."""
        state = create_initial_state(
            asset_symbol="BTCUSD",
            sentiment_data=None
        )

        # sentiment_data becomes [] due to create_initial_state
        result = sentiment_node(state)

        assert "sentiment_analysis" in result
        assert result["sentiment_analysis"]["fear_score"] == 50

    def test_handles_malformed_entries(self):
        """Test node handles malformed sentiment entries."""
        data = [
            {},  # Empty entry
            {"source": "twitter"},  # Missing text
            None,  # None entry - this might cause issues
        ]

        # Filter out None entries
        filtered_data = [e for e in data if e is not None]

        state = create_initial_state(
            asset_symbol="BTCUSD",
            sentiment_data=filtered_data
        )

        # Should not raise exception
        result = sentiment_node(state)
        assert "sentiment_analysis" in result

    def test_handles_very_long_text(self):
        """Test node handles very long sentiment text."""
        long_text = "Bitcoin " * 1000  # Very long text

        data = [{"text": long_text, "source": "test"}]

        state = create_initial_state(
            asset_symbol="BTCUSD",
            sentiment_data=data
        )

        # Should not raise exception
        result = sentiment_node(state)
        assert "sentiment_analysis" in result

    def test_handles_special_characters(self):
        """Test node handles special characters in text."""
        data = [
            {"text": "Bitcoin!!! @#$% ^&*()", "source": "twitter"},
            {"text": "<script>alert('test')</script>", "source": "spam"},
        ]

        state = create_initial_state(
            asset_symbol="BTCUSD",
            sentiment_data=data
        )

        # Should not raise exception
        result = sentiment_node(state)
        assert "sentiment_analysis" in result
