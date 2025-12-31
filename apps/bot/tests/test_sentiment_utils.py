"""
Unit tests for Sentiment Analysis Utilities.

Story 2.2: Sentiment & Technical Agents

Tests cover:
- Sentiment prompt formatting
- JSON response parsing
- Sentiment signal calculation
- Edge cases and error handling
"""

import pytest
from services.sentiment_utils import (
    SENTIMENT_SYSTEM_PROMPT,
    format_sentiment_data_for_prompt,
    parse_sentiment_response,
    calculate_sentiment_signal
)


class TestFormatSentimentDataForPrompt:
    """Tests for format_sentiment_data_for_prompt function."""

    def test_format_empty_data(self):
        """Test formatting with empty data list."""
        result = format_sentiment_data_for_prompt([])
        assert result == "No sentiment data available."

    def test_format_single_entry(self):
        """Test formatting with single entry."""
        data = [{"text": "Bitcoin is crashing!", "source": "twitter"}]
        result = format_sentiment_data_for_prompt(data)
        assert "[twitter]" in result
        assert "Bitcoin is crashing!" in result
        assert result.startswith("1.")

    def test_format_multiple_entries(self):
        """Test formatting with multiple entries."""
        data = [
            {"text": "Bitcoin crashing!", "source": "twitter"},
            {"text": "HODL strong", "source": "reddit"},
            {"text": "Market update", "source": "news"}
        ]
        result = format_sentiment_data_for_prompt(data)
        assert "[twitter]" in result
        assert "[reddit]" in result
        assert "[news]" in result
        assert "1." in result
        assert "2." in result
        assert "3." in result

    def test_format_with_content_key(self):
        """Test formatting with 'content' key instead of 'text'."""
        data = [{"content": "Great news for crypto!", "source": "telegram"}]
        result = format_sentiment_data_for_prompt(data)
        assert "Great news for crypto!" in result

    def test_format_with_raw_text_key(self):
        """Test formatting with 'raw_text' key."""
        data = [{"raw_text": "Selling everything!", "source": "bluesky"}]
        result = format_sentiment_data_for_prompt(data)
        assert "Selling everything!" in result

    def test_format_limits_to_20_entries(self):
        """Test that formatting limits to 20 entries."""
        data = [{"text": f"Entry {i}", "source": "test"} for i in range(30)]
        result = format_sentiment_data_for_prompt(data)
        assert "20." in result
        assert "21." not in result

    def test_format_handles_missing_source(self):
        """Test handling of missing source field."""
        data = [{"text": "No source here"}]
        result = format_sentiment_data_for_prompt(data)
        assert "[unknown]" in result

    def test_format_handles_empty_text(self):
        """Test handling of empty text fields."""
        data = [
            {"text": "", "source": "twitter"},
            {"text": "Valid text", "source": "reddit"}
        ]
        result = format_sentiment_data_for_prompt(data)
        # Empty text should be skipped
        assert "Valid text" in result


class TestParseSentimentResponse:
    """Tests for parse_sentiment_response function."""

    def test_parse_valid_json(self):
        """Test parsing valid JSON response."""
        response = '{"fear_score": 25, "dominant_emotion": "FEAR", "summary": "Market panic", "key_themes": ["crash", "selloff"]}'
        parsed = parse_sentiment_response(response)

        assert parsed["fear_score"] == 25
        assert parsed["dominant_emotion"] == "FEAR"
        assert parsed["summary"] == "Market panic"
        assert parsed["key_themes"] == ["crash", "selloff"]

    def test_parse_json_with_markdown_code_block(self):
        """Test parsing JSON wrapped in markdown code block."""
        response = '```json\n{"fear_score": 75, "dominant_emotion": "GREED", "summary": "FOMO", "key_themes": []}\n```'
        parsed = parse_sentiment_response(response)

        assert parsed["fear_score"] == 75
        assert parsed["dominant_emotion"] == "GREED"

    def test_parse_json_with_simple_code_block(self):
        """Test parsing JSON wrapped in simple code block."""
        response = '```\n{"fear_score": 50, "dominant_emotion": "NEUTRAL", "summary": "Mixed", "key_themes": ["balanced"]}\n```'
        parsed = parse_sentiment_response(response)

        assert parsed["fear_score"] == 50
        assert parsed["dominant_emotion"] == "NEUTRAL"

    def test_parse_invalid_json(self):
        """Test parsing invalid JSON returns defaults."""
        response = "This is not JSON at all"
        parsed = parse_sentiment_response(response)

        assert parsed["fear_score"] == 50
        assert parsed["dominant_emotion"] == "NEUTRAL"
        assert "Failed to parse" in parsed["summary"]
        assert parsed["key_themes"] == []

    def test_parse_clamps_fear_score(self):
        """Test that fear score is clamped to 0-100."""
        # Score above 100
        response = '{"fear_score": 150, "dominant_emotion": "GREED", "summary": "Test", "key_themes": []}'
        parsed = parse_sentiment_response(response)
        assert parsed["fear_score"] == 100

        # Score below 0
        response = '{"fear_score": -50, "dominant_emotion": "FEAR", "summary": "Test", "key_themes": []}'
        parsed = parse_sentiment_response(response)
        assert parsed["fear_score"] == 0

    def test_parse_handles_float_fear_score(self):
        """Test handling of float fear score."""
        response = '{"fear_score": 45.7, "dominant_emotion": "NEUTRAL", "summary": "Test", "key_themes": []}'
        parsed = parse_sentiment_response(response)
        assert parsed["fear_score"] == 45  # Should be converted to int

    def test_parse_normalizes_invalid_emotion(self):
        """Test that invalid emotion is normalized to NEUTRAL."""
        response = '{"fear_score": 50, "dominant_emotion": "UNKNOWN", "summary": "Test", "key_themes": []}'
        parsed = parse_sentiment_response(response)
        assert parsed["dominant_emotion"] == "NEUTRAL"

    def test_parse_handles_missing_fields(self):
        """Test handling of missing fields in JSON."""
        response = '{"fear_score": 30}'
        parsed = parse_sentiment_response(response)

        assert parsed["fear_score"] == 30
        assert parsed["dominant_emotion"] == "NEUTRAL"
        assert "Unable to determine" in parsed["summary"]
        assert parsed["key_themes"] == []

    def test_parse_handles_non_list_themes(self):
        """Test handling of non-list key_themes."""
        response = '{"fear_score": 50, "dominant_emotion": "NEUTRAL", "summary": "Test", "key_themes": "not a list"}'
        parsed = parse_sentiment_response(response)
        assert parsed["key_themes"] == []

    def test_parse_filters_empty_themes(self):
        """Test that empty themes are filtered out."""
        response = '{"fear_score": 50, "dominant_emotion": "NEUTRAL", "summary": "Test", "key_themes": ["valid", "", null, "theme"]}'
        parsed = parse_sentiment_response(response)
        # null/None would be filtered, empty strings too
        assert "" not in parsed["key_themes"]


class TestCalculateSentimentSignal:
    """Tests for calculate_sentiment_signal function."""

    def test_extreme_fear_buy_signal(self):
        """Test extreme fear produces buy signal."""
        signal, strength, reasoning = calculate_sentiment_signal(10)

        assert signal == "BUY"
        assert strength >= 80
        assert "extreme fear" in reasoning.lower()

    def test_elevated_fear_buy_signal(self):
        """Test elevated fear produces buy signal."""
        signal, strength, reasoning = calculate_sentiment_signal(30)

        assert signal == "BUY"
        assert strength >= 40
        assert "accumulation" in reasoning.lower() or "fear" in reasoning.lower()

    def test_extreme_greed_sell_signal(self):
        """Test extreme greed produces sell signal."""
        signal, strength, reasoning = calculate_sentiment_signal(90)

        assert signal == "SELL"
        assert strength >= 80
        assert "extreme greed" in reasoning.lower()

    def test_elevated_greed_sell_signal(self):
        """Test elevated greed produces sell signal."""
        signal, strength, reasoning = calculate_sentiment_signal(70)

        assert signal == "SELL"
        assert strength >= 50
        assert "distribution" in reasoning.lower() or "greed" in reasoning.lower()

    def test_neutral_hold_signal(self):
        """Test neutral sentiment produces hold signal."""
        signal, strength, reasoning = calculate_sentiment_signal(50)

        assert signal == "HOLD"
        assert strength == 50
        assert "neutral" in reasoning.lower()

    def test_signal_at_boundary_low(self):
        """Test signal at low fear boundary (20)."""
        signal, strength, reasoning = calculate_sentiment_signal(20)
        assert signal == "BUY"  # Should still be buy at boundary

    def test_signal_at_boundary_high(self):
        """Test signal at high greed boundary (80)."""
        signal, strength, reasoning = calculate_sentiment_signal(80)
        assert signal == "SELL"  # Should be sell at boundary

    def test_signal_just_inside_neutral(self):
        """Test signal just inside neutral range."""
        signal, strength, reasoning = calculate_sentiment_signal(40)
        assert signal == "HOLD"

        signal, strength, reasoning = calculate_sentiment_signal(64)
        assert signal == "HOLD"

    def test_strength_bounds(self):
        """Test that strength is always in valid range."""
        for fear_score in [0, 10, 20, 30, 40, 50, 60, 70, 80, 90, 100]:
            signal, strength, reasoning = calculate_sentiment_signal(fear_score)
            assert 0 <= strength <= 100


class TestSentimentSystemPrompt:
    """Tests for SENTIMENT_SYSTEM_PROMPT."""

    def test_prompt_mentions_fear_greed(self):
        """Test that prompt mentions fear and greed concepts."""
        assert "fear" in SENTIMENT_SYSTEM_PROMPT.lower()
        assert "greed" in SENTIMENT_SYSTEM_PROMPT.lower()

    def test_prompt_specifies_json_format(self):
        """Test that prompt specifies JSON output format."""
        assert "json" in SENTIMENT_SYSTEM_PROMPT.lower()
        assert "fear_score" in SENTIMENT_SYSTEM_PROMPT

    def test_prompt_mentions_contrarian(self):
        """Test that prompt mentions contrarian trading."""
        assert "contrarian" in SENTIMENT_SYSTEM_PROMPT.lower()

    def test_prompt_explains_score_meaning(self):
        """Test that prompt explains what scores mean."""
        assert "0" in SENTIMENT_SYSTEM_PROMPT or "zero" in SENTIMENT_SYSTEM_PROMPT.lower()
        assert "100" in SENTIMENT_SYSTEM_PROMPT
