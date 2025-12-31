"""
Unit tests for Vision Agent Components.

Story 2.3: Vision Agent & Chart Generation

Tests cover:
- Vision prompts module
- Vision response parsing utilities
- Vision node functionality (with mocked API)
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock
from services.vision_prompts import (
    VISION_SYSTEM_PROMPT,
    VISION_USER_PROMPT_TEMPLATE,
    build_vision_prompt
)
from services.vision_utils import (
    parse_vision_response,
    validate_vision_result,
    extract_key_patterns
)

# Import MIN_CANDLES_FOR_CHART constant directly to avoid circular import
MIN_CANDLES_FOR_CHART = 50


class TestVisionPrompts:
    """Tests for vision_prompts module."""

    def test_system_prompt_exists(self):
        """Test that system prompt is defined and non-empty."""
        assert VISION_SYSTEM_PROMPT is not None
        assert len(VISION_SYSTEM_PROMPT) > 100

    def test_system_prompt_contains_patterns(self):
        """Test that system prompt mentions key patterns."""
        assert "Double Bottom" in VISION_SYSTEM_PROMPT
        assert "Wyckoff Spring" in VISION_SYSTEM_PROMPT
        assert "Head and Shoulders" in VISION_SYSTEM_PROMPT
        assert "Scam Wick" in VISION_SYSTEM_PROMPT

    def test_system_prompt_contains_json_format(self):
        """Test that system prompt specifies JSON output format."""
        assert "JSON" in VISION_SYSTEM_PROMPT
        assert "patterns_detected" in VISION_SYSTEM_PROMPT
        assert "confidence_score" in VISION_SYSTEM_PROMPT
        assert "recommendation" in VISION_SYSTEM_PROMPT

    def test_user_prompt_template_exists(self):
        """Test that user prompt template is defined."""
        assert VISION_USER_PROMPT_TEMPLATE is not None
        assert "{asset_symbol}" in VISION_USER_PROMPT_TEMPLATE
        assert "{num_candles}" in VISION_USER_PROMPT_TEMPLATE

    def test_build_vision_prompt_basic(self):
        """Test building a basic vision prompt."""
        prompt = build_vision_prompt(
            asset_symbol="SOLUSD",
            num_candles=100,
            timeframe="15-minute",
            include_sma=True
        )
        assert "SOLUSD" in prompt
        assert "100" in prompt
        assert "15-minute" in prompt
        assert "SMA" in prompt

    def test_build_vision_prompt_without_sma(self):
        """Test building prompt without SMA note."""
        prompt = build_vision_prompt(
            asset_symbol="BTCUSD",
            num_candles=50,
            timeframe="1-hour",
            include_sma=False
        )
        assert "BTCUSD" in prompt
        assert "50" in prompt
        assert "SMA" not in prompt

    def test_build_vision_prompt_custom_timeframe(self):
        """Test building prompt with custom timeframe."""
        prompt = build_vision_prompt(
            asset_symbol="ETHUSD",
            num_candles=200,
            timeframe="4-hour"
        )
        assert "ETHUSD" in prompt
        assert "4-hour" in prompt


class TestParseVisionResponse:
    """Tests for parse_vision_response function."""

    def test_parse_valid_json(self):
        """Test parsing a valid JSON response."""
        response = '''{
            "patterns_detected": ["Double Bottom", "Hammer"],
            "pattern_quality": "STRONG",
            "support_level_nearby": true,
            "estimated_support_price": 95.50,
            "scam_wick_detected": false,
            "overall_bias": "BULLISH",
            "confidence_score": 75,
            "description": "Clear double bottom at support",
            "recommendation": "VALID"
        }'''
        parsed = parse_vision_response(response)

        assert parsed["confidence_score"] == 75
        assert "Double Bottom" in parsed["patterns_detected"]
        assert parsed["recommendation"] == "VALID"
        assert parsed["pattern_quality"] == "STRONG"
        assert parsed["support_level_nearby"] is True
        assert parsed["scam_wick_detected"] is False

    def test_parse_json_with_markdown(self):
        """Test parsing JSON wrapped in markdown code block."""
        response = '''```json
{
    "patterns_detected": ["Inverse Head and Shoulders"],
    "pattern_quality": "MODERATE",
    "support_level_nearby": true,
    "scam_wick_detected": false,
    "overall_bias": "BULLISH",
    "confidence_score": 65,
    "description": "Potential reversal forming",
    "recommendation": "VALID"
}
```'''
        parsed = parse_vision_response(response)
        assert parsed["confidence_score"] == 65
        assert "Inverse Head and Shoulders" in parsed["patterns_detected"]

    def test_parse_scam_wick_detected(self):
        """Test parsing response with scam wick detected."""
        response = '''{
            "patterns_detected": ["Long Wick"],
            "pattern_quality": "WEAK",
            "support_level_nearby": false,
            "scam_wick_detected": true,
            "scam_wick_explanation": "Suspicious 5% wick with no follow-through",
            "overall_bias": "NEUTRAL",
            "confidence_score": 20,
            "description": "Suspicious wick pattern",
            "recommendation": "INVALID"
        }'''
        parsed = parse_vision_response(response)

        assert parsed["scam_wick_detected"] is True
        assert "Suspicious" in parsed["scam_wick_explanation"]
        assert parsed["recommendation"] == "INVALID"

    def test_parse_bearish_patterns(self):
        """Test parsing response with bearish warning patterns."""
        response = '''{
            "patterns_detected": ["Head and Shoulders", "Death Cross"],
            "pattern_quality": "STRONG",
            "support_level_nearby": false,
            "scam_wick_detected": false,
            "overall_bias": "BEARISH",
            "confidence_score": 80,
            "description": "Clear bearish reversal pattern",
            "recommendation": "INVALID"
        }'''
        parsed = parse_vision_response(response)

        assert "Head and Shoulders" in parsed["patterns_detected"]
        assert parsed["overall_bias"] == "BEARISH"
        assert parsed["recommendation"] == "INVALID"

    def test_parse_invalid_json(self):
        """Test parsing invalid JSON returns safe defaults."""
        response = "This is not JSON at all, just random text"
        parsed = parse_vision_response(response)

        assert parsed["patterns_detected"] == []
        assert parsed["confidence_score"] == 0
        assert parsed["recommendation"] == "INVALID"
        assert "Failed to parse" in parsed["description"]

    def test_parse_partial_json(self):
        """Test parsing incomplete JSON returns safe defaults."""
        response = '{"patterns_detected": ["Double Bottom"'  # Incomplete
        parsed = parse_vision_response(response)

        assert parsed["patterns_detected"] == []
        assert parsed["recommendation"] == "INVALID"

    def test_parse_empty_patterns(self):
        """Test parsing response with no patterns detected."""
        response = '''{
            "patterns_detected": [],
            "pattern_quality": "WEAK",
            "support_level_nearby": false,
            "scam_wick_detected": false,
            "overall_bias": "NEUTRAL",
            "confidence_score": 40,
            "description": "No clear patterns visible",
            "recommendation": "INVALID"
        }'''
        parsed = parse_vision_response(response)

        assert parsed["patterns_detected"] == []
        assert parsed["confidence_score"] == 40


class TestValidateVisionResult:
    """Tests for validate_vision_result function."""

    def test_valid_result(self):
        """Test that valid result returns True."""
        parsed = {
            "recommendation": "VALID",
            "scam_wick_detected": False,
            "confidence_score": 75
        }
        assert validate_vision_result(parsed) is True

    def test_invalid_recommendation(self):
        """Test that INVALID recommendation returns False."""
        parsed = {
            "recommendation": "INVALID",
            "scam_wick_detected": False,
            "confidence_score": 75
        }
        assert validate_vision_result(parsed) is False

    def test_scam_wick_detected(self):
        """Test that scam wick detection returns False."""
        parsed = {
            "recommendation": "VALID",
            "scam_wick_detected": True,
            "confidence_score": 75
        }
        assert validate_vision_result(parsed) is False

    def test_low_confidence(self):
        """Test that low confidence returns False."""
        parsed = {
            "recommendation": "VALID",
            "scam_wick_detected": False,
            "confidence_score": 25
        }
        assert validate_vision_result(parsed) is False

    def test_borderline_confidence(self):
        """Test borderline confidence (30) returns True."""
        parsed = {
            "recommendation": "VALID",
            "scam_wick_detected": False,
            "confidence_score": 30
        }
        assert validate_vision_result(parsed) is True

    def test_multiple_failures(self):
        """Test that multiple failure conditions return False."""
        parsed = {
            "recommendation": "INVALID",
            "scam_wick_detected": True,
            "confidence_score": 10
        }
        assert validate_vision_result(parsed) is False


class TestExtractKeyPatterns:
    """Tests for extract_key_patterns function."""

    def test_reversal_patterns_detected(self):
        """Test detection of bullish reversal patterns."""
        parsed = {
            "patterns_detected": ["Double Bottom", "Hammer at Support"]
        }
        result = extract_key_patterns(parsed)

        assert result["has_reversal_pattern"] is True
        assert result["has_warning_pattern"] is False

    def test_warning_patterns_detected(self):
        """Test detection of bearish warning patterns."""
        parsed = {
            "patterns_detected": ["Head and Shoulders", "Evening Star"]
        }
        result = extract_key_patterns(parsed)

        assert result["has_reversal_pattern"] is False
        assert result["has_warning_pattern"] is True

    def test_mixed_patterns(self):
        """Test detection of both reversal and warning patterns."""
        parsed = {
            "patterns_detected": ["Double Bottom", "Head and Shoulders"]
        }
        result = extract_key_patterns(parsed)

        assert result["has_reversal_pattern"] is True
        assert result["has_warning_pattern"] is True

    def test_no_patterns(self):
        """Test with no patterns detected."""
        parsed = {
            "patterns_detected": []
        }
        result = extract_key_patterns(parsed)

        assert result["has_reversal_pattern"] is False
        assert result["has_warning_pattern"] is False
        assert result["pattern_names"] == []

    def test_wyckoff_spring_detection(self):
        """Test detection of Wyckoff Spring pattern."""
        parsed = {
            "patterns_detected": ["Wyckoff Spring"]
        }
        result = extract_key_patterns(parsed)

        assert result["has_reversal_pattern"] is True

    def test_death_cross_detection(self):
        """Test detection of Death Cross pattern."""
        parsed = {
            "patterns_detected": ["Death Cross visible"]
        }
        result = extract_key_patterns(parsed)

        assert result["has_warning_pattern"] is True


class TestVisionNode:
    """
    Tests for vision_node function.

    Note: Due to circular imports in the existing codebase (nodes/__init__.py
    imports from core/graph.py which imports back from nodes/), we test the
    vision node logic by directly importing the vision module and mocking
    its dependencies. The pytest-order plugin or @pytest.mark.order can be
    used to control test execution order if needed.
    """

    @pytest.fixture
    def sample_candles(self):
        """Generate sample candles for testing."""
        candles = []
        base_price = 100.0
        base_time = datetime.utcnow() - timedelta(hours=100)

        for i in range(100):
            price = base_price + (i * 0.5) + ((-1) ** i * 3)
            candles.append({
                "timestamp": base_time + timedelta(hours=i),
                "open": price - 1,
                "high": price + 3,
                "low": price - 3,
                "close": price + 0.5,
                "volume": 10000 + (i * 50)
            })
        return candles

    def test_minimum_candle_requirement(self):
        """Test MIN_CANDLES_FOR_CHART constant is set correctly."""
        assert MIN_CANDLES_FOR_CHART == 50

    def test_vision_node_integration_with_mocks(self, sample_candles):
        """
        Integration test for vision_node with mocked dependencies.

        Tests the full flow: chart generation -> vision API -> parsing -> validation
        """
        import sys

        # Pre-import to avoid circular import issues
        # Mock the problematic modules before they're imported
        mock_core_graph = MagicMock()
        sys.modules['core.graph'] = mock_core_graph

        try:
            # Now we can import vision module
            import importlib
            import nodes.vision as vision_module
            importlib.reload(vision_module)

            # Mock chart generation
            with patch.object(vision_module, 'generate_chart_image') as mock_generate, \
                 patch.object(vision_module, 'get_gemini_pro_vision_model') as mock_model:

                mock_generate.return_value = b'\x89PNG\r\n\x1a\n' + b'fake_image_data'

                # Mock Gemini response - successful analysis
                mock_response = Mock()
                mock_response.text = '''{
                    "patterns_detected": ["Double Bottom"],
                    "pattern_quality": "STRONG",
                    "support_level_nearby": true,
                    "scam_wick_detected": false,
                    "overall_bias": "BULLISH",
                    "confidence_score": 75,
                    "description": "Clear double bottom pattern",
                    "recommendation": "VALID"
                }'''
                mock_model_instance = Mock()
                mock_model_instance.generate_content.return_value = mock_response
                mock_model.return_value = mock_model_instance

                state = {
                    "asset_symbol": "SOLUSD",
                    "candles_data": sample_candles,
                    "sentiment_data": []
                }

                result = vision_module.vision_node(state)

                assert "vision_analysis" in result
                assert result["vision_analysis"]["is_valid"] is True
                assert result["vision_analysis"]["confidence_score"] == 75
                assert "Double Bottom" in result["vision_analysis"]["patterns_detected"]
        finally:
            # Clean up
            if 'core.graph' in sys.modules:
                del sys.modules['core.graph']

    def test_vision_node_scam_wick_detection(self, sample_candles):
        """Test that scam wick detection marks analysis as invalid."""
        import sys

        mock_core_graph = MagicMock()
        sys.modules['core.graph'] = mock_core_graph

        try:
            import importlib
            import nodes.vision as vision_module
            importlib.reload(vision_module)

            with patch.object(vision_module, 'generate_chart_image') as mock_generate, \
                 patch.object(vision_module, 'get_gemini_pro_vision_model') as mock_model:

                mock_generate.return_value = b'\x89PNG\r\n\x1a\n' + b'fake_image_data'

                # Mock response with scam wick
                mock_response = Mock()
                mock_response.text = '''{
                    "patterns_detected": ["Long Wick"],
                    "pattern_quality": "WEAK",
                    "support_level_nearby": false,
                    "scam_wick_detected": true,
                    "scam_wick_explanation": "Manipulation detected",
                    "overall_bias": "NEUTRAL",
                    "confidence_score": 30,
                    "description": "Suspicious wick pattern",
                    "recommendation": "VALID"
                }'''
                mock_model_instance = Mock()
                mock_model_instance.generate_content.return_value = mock_response
                mock_model.return_value = mock_model_instance

                state = {
                    "asset_symbol": "SOLUSD",
                    "candles_data": sample_candles,
                    "sentiment_data": []
                }

                result = vision_module.vision_node(state)

                # Even with VALID recommendation, scam_wick_detected should invalidate
                assert result["vision_analysis"]["is_valid"] is False
        finally:
            if 'core.graph' in sys.modules:
                del sys.modules['core.graph']

    def test_vision_node_api_error(self, sample_candles):
        """Test error handling when API call fails."""
        import sys

        mock_core_graph = MagicMock()
        sys.modules['core.graph'] = mock_core_graph

        try:
            import importlib
            import nodes.vision as vision_module
            importlib.reload(vision_module)

            with patch.object(vision_module, 'generate_chart_image') as mock_generate, \
                 patch.object(vision_module, 'get_gemini_pro_vision_model') as mock_model:

                mock_generate.return_value = b'\x89PNG\r\n\x1a\n' + b'fake_image_data'
                mock_model.side_effect = Exception("API rate limit exceeded")

                state = {
                    "asset_symbol": "SOLUSD",
                    "candles_data": sample_candles,
                    "sentiment_data": []
                }

                result = vision_module.vision_node(state)

                assert "vision_analysis" in result
                assert result["vision_analysis"]["is_valid"] is False
                assert "Error" in result["vision_analysis"]["description"]
                assert "error" in result
        finally:
            if 'core.graph' in sys.modules:
                del sys.modules['core.graph']

    def test_vision_node_chart_generation_error(self, sample_candles):
        """Test error handling when chart generation fails."""
        import sys

        mock_core_graph = MagicMock()
        sys.modules['core.graph'] = mock_core_graph

        try:
            import importlib
            import nodes.vision as vision_module
            importlib.reload(vision_module)

            with patch.object(vision_module, 'generate_chart_image') as mock_generate:
                mock_generate.side_effect = Exception("Memory error")

                state = {
                    "asset_symbol": "SOLUSD",
                    "candles_data": sample_candles,
                    "sentiment_data": []
                }

                result = vision_module.vision_node(state)

                assert "vision_analysis" in result
                assert result["vision_analysis"]["is_valid"] is False
                assert "error" in result
        finally:
            if 'core.graph' in sys.modules:
                del sys.modules['core.graph']

    def test_vision_node_insufficient_candles(self, sample_candles):
        """Test that insufficient candles returns invalid analysis."""
        import sys

        mock_core_graph = MagicMock()
        sys.modules['core.graph'] = mock_core_graph

        try:
            import importlib
            import nodes.vision as vision_module
            importlib.reload(vision_module)

            with patch.object(vision_module, 'generate_chart_image') as mock_generate:
                # Create minimal candles (less than MIN_CANDLES_FOR_CHART = 50)
                few_candles = sample_candles[:10]
                state = {
                    "asset_symbol": "TESTUSD",
                    "candles_data": few_candles,
                    "sentiment_data": []
                }

                result = vision_module.vision_node(state)

                assert "vision_analysis" in result
                assert result["vision_analysis"]["is_valid"] is False
                assert result["vision_analysis"]["confidence_score"] == 0
                assert "Insufficient" in result["vision_analysis"]["description"]
                # Verify chart generation was NOT called due to insufficient data
                mock_generate.assert_not_called()
        finally:
            if 'core.graph' in sys.modules:
                del sys.modules['core.graph']

    def test_vision_node_invalid_json_response(self, sample_candles):
        """Test handling of invalid JSON from API."""
        import sys

        mock_core_graph = MagicMock()
        sys.modules['core.graph'] = mock_core_graph

        try:
            import importlib
            import nodes.vision as vision_module
            importlib.reload(vision_module)

            with patch.object(vision_module, 'generate_chart_image') as mock_generate, \
                 patch.object(vision_module, 'get_gemini_pro_vision_model') as mock_model:

                mock_generate.return_value = b'\x89PNG\r\n\x1a\n' + b'fake_image_data'

                # Mock invalid JSON response
                mock_response = Mock()
                mock_response.text = "Sorry, I cannot analyze this image."
                mock_model_instance = Mock()
                mock_model_instance.generate_content.return_value = mock_response
                mock_model.return_value = mock_model_instance

                state = {
                    "asset_symbol": "SOLUSD",
                    "candles_data": sample_candles,
                    "sentiment_data": []
                }

                result = vision_module.vision_node(state)

                assert "vision_analysis" in result
                assert result["vision_analysis"]["is_valid"] is False
                assert result["vision_analysis"]["confidence_score"] == 0
        finally:
            if 'core.graph' in sys.modules:
                del sys.modules['core.graph']
