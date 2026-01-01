"""
Tests for services/master_prompts.py

Story 2.4: Master Node & Signal Logging

Tests for the Master Node prompt templates and prompt building.
"""

import pytest

from services.master_prompts import (
    MASTER_SYSTEM_PROMPT,
    MASTER_USER_PROMPT_TEMPLATE,
    build_master_prompt,
)


# =============================================================================
# Test Constants
# =============================================================================


class TestMasterSystemPrompt:
    """Tests for MASTER_SYSTEM_PROMPT constant."""

    def test_system_prompt_exists(self):
        """Test system prompt is defined."""
        assert MASTER_SYSTEM_PROMPT is not None
        assert len(MASTER_SYSTEM_PROMPT) > 0

    def test_system_prompt_mentions_master_node(self):
        """Test system prompt mentions Master Node role."""
        assert "MASTER NODE" in MASTER_SYSTEM_PROMPT

    def test_system_prompt_has_decision_rules(self):
        """Test system prompt contains decision rules."""
        assert "DECISION RULES" in MASTER_SYSTEM_PROMPT

    def test_system_prompt_has_buy_conditions(self):
        """Test system prompt specifies BUY conditions."""
        assert "BUY" in MASTER_SYSTEM_PROMPT
        assert "fear_score < 20" in MASTER_SYSTEM_PROMPT

    def test_system_prompt_has_sell_conditions(self):
        """Test system prompt specifies SELL conditions."""
        assert "SELL" in MASTER_SYSTEM_PROMPT
        assert "fear_score > 80" in MASTER_SYSTEM_PROMPT

    def test_system_prompt_has_hold_conditions(self):
        """Test system prompt specifies HOLD conditions."""
        assert "HOLD" in MASTER_SYSTEM_PROMPT

    def test_system_prompt_requires_json_output(self):
        """Test system prompt requires JSON output format."""
        assert "JSON" in MASTER_SYSTEM_PROMPT
        assert '"action"' in MASTER_SYSTEM_PROMPT

    def test_system_prompt_has_contrarian_philosophy(self):
        """Test system prompt explains contrarian philosophy."""
        assert "contrarian" in MASTER_SYSTEM_PROMPT.lower()
        assert "fear" in MASTER_SYSTEM_PROMPT.lower()
        assert "greed" in MASTER_SYSTEM_PROMPT.lower()


class TestMasterUserPromptTemplate:
    """Tests for MASTER_USER_PROMPT_TEMPLATE constant."""

    def test_template_exists(self):
        """Test user prompt template is defined."""
        assert MASTER_USER_PROMPT_TEMPLATE is not None
        assert len(MASTER_USER_PROMPT_TEMPLATE) > 0

    def test_template_has_placeholders(self):
        """Test template has required placeholders."""
        required_placeholders = [
            "{asset_symbol}",
            "{timestamp}",
            "{fear_score}",
            "{technical_signal}",
            "{vision_valid}",
        ]
        for placeholder in required_placeholders:
            assert placeholder in MASTER_USER_PROMPT_TEMPLATE

    def test_template_has_sections(self):
        """Test template has all analysis sections."""
        assert "SENTIMENT ANALYSIS" in MASTER_USER_PROMPT_TEMPLATE
        assert "TECHNICAL ANALYSIS" in MASTER_USER_PROMPT_TEMPLATE
        assert "VISION ANALYSIS" in MASTER_USER_PROMPT_TEMPLATE


# =============================================================================
# Test build_master_prompt
# =============================================================================


class TestBuildMasterPrompt:
    """Tests for build_master_prompt function."""

    @pytest.fixture
    def sample_inputs(self):
        """Sample inputs for build_master_prompt."""
        return {
            "asset_symbol": "SOLUSD",
            "timestamp": "2025-01-01T00:00:00",
            "sentiment_analysis": {
                "fear_score": 15,
                "summary": "Extreme fear in the market",
                "source_count": 50,
            },
            "technical_analysis": {
                "signal": "BULLISH",
                "strength": 75,
                "rsi": 28,
                "sma_50": 110.50,
                "sma_200": 100.25,
                "volume_delta": 40,
                "reasoning": "Oversold bounce detected",
            },
            "vision_analysis": {
                "patterns_detected": ["Double Bottom", "Bullish Divergence"],
                "confidence_score": 70,
                "description": "Clear reversal pattern forming",
                "is_valid": True,
            },
        }

    def test_returns_string(self, sample_inputs):
        """Test build_master_prompt returns a string."""
        result = build_master_prompt(**sample_inputs)
        assert isinstance(result, str)

    def test_includes_asset_symbol(self, sample_inputs):
        """Test prompt includes the asset symbol."""
        result = build_master_prompt(**sample_inputs)
        assert "SOLUSD" in result

    def test_includes_timestamp(self, sample_inputs):
        """Test prompt includes the timestamp."""
        result = build_master_prompt(**sample_inputs)
        assert "2025-01-01T00:00:00" in result

    def test_includes_fear_score(self, sample_inputs):
        """Test prompt includes the fear score."""
        result = build_master_prompt(**sample_inputs)
        assert "15" in result
        assert "/100" in result

    def test_includes_technical_signal(self, sample_inputs):
        """Test prompt includes the technical signal."""
        result = build_master_prompt(**sample_inputs)
        assert "BULLISH" in result

    def test_includes_technical_strength(self, sample_inputs):
        """Test prompt includes the technical strength."""
        result = build_master_prompt(**sample_inputs)
        assert "75" in result

    def test_includes_rsi(self, sample_inputs):
        """Test prompt includes the RSI value."""
        result = build_master_prompt(**sample_inputs)
        assert "28" in result

    def test_includes_sma_values(self, sample_inputs):
        """Test prompt includes SMA values."""
        result = build_master_prompt(**sample_inputs)
        assert "110.5" in result
        assert "100.25" in result

    def test_includes_patterns(self, sample_inputs):
        """Test prompt includes detected patterns."""
        result = build_master_prompt(**sample_inputs)
        assert "Double Bottom" in result
        assert "Bullish Divergence" in result

    def test_includes_vision_valid_yes(self, sample_inputs):
        """Test prompt shows 'Yes' when vision is valid."""
        result = build_master_prompt(**sample_inputs)
        assert "Valid Signal: Yes" in result

    def test_includes_vision_valid_no(self, sample_inputs):
        """Test prompt shows 'No' when vision is not valid."""
        sample_inputs["vision_analysis"]["is_valid"] = False
        result = build_master_prompt(**sample_inputs)
        assert "Valid Signal: No" in result

    def test_handles_empty_patterns(self, sample_inputs):
        """Test prompt handles empty patterns list."""
        sample_inputs["vision_analysis"]["patterns_detected"] = []
        result = build_master_prompt(**sample_inputs)
        assert "Patterns Detected: None" in result

    def test_handles_missing_values_with_defaults(self):
        """Test prompt handles missing values with defaults."""
        result = build_master_prompt(
            asset_symbol="BTCUSD",
            timestamp="2025-01-01",
            sentiment_analysis={},
            technical_analysis={},
            vision_analysis={},
        )
        # Should use defaults and not crash
        assert "BTCUSD" in result
        assert "N/A" in result  # Default for missing values
        assert "50" in result  # Default fear_score

    def test_handles_partial_sentiment(self, sample_inputs):
        """Test prompt handles partial sentiment data."""
        sample_inputs["sentiment_analysis"] = {"fear_score": 25}
        result = build_master_prompt(**sample_inputs)
        assert "25" in result
        assert "N/A" in result  # Default for missing summary

    def test_handles_partial_technical(self, sample_inputs):
        """Test prompt handles partial technical data."""
        sample_inputs["technical_analysis"] = {"signal": "BEARISH"}
        result = build_master_prompt(**sample_inputs)
        assert "BEARISH" in result

    def test_handles_partial_vision(self, sample_inputs):
        """Test prompt handles partial vision data."""
        sample_inputs["vision_analysis"] = {"confidence_score": 80}
        result = build_master_prompt(**sample_inputs)
        assert "80" in result

    def test_prompt_structure(self, sample_inputs):
        """Test prompt has proper structure."""
        result = build_master_prompt(**sample_inputs)

        # Check section headers are present
        assert "### SENTIMENT ANALYSIS" in result
        assert "### TECHNICAL ANALYSIS" in result
        assert "### VISION ANALYSIS" in result

        # Check it ends with the decision reminder
        assert "BUY only if fear_score < 20" in result


# =============================================================================
# Integration Tests
# =============================================================================


class TestPromptIntegration:
    """Integration tests for prompt building."""

    def test_full_prompt_with_real_data(self):
        """Test building a complete prompt with realistic data."""
        prompt = build_master_prompt(
            asset_symbol="ETHUSD",
            timestamp="2025-12-31T12:00:00Z",
            sentiment_analysis={
                "fear_score": 18,
                "summary": "Market showing extreme fear after recent crash",
                "source_count": 150,
            },
            technical_analysis={
                "signal": "BULLISH",
                "strength": 72,
                "rsi": 25.5,
                "sma_50": 2450.00,
                "sma_200": 2200.00,
                "volume_delta": 85.3,
                "reasoning": "RSI oversold with bullish divergence",
            },
            vision_analysis={
                "patterns_detected": ["Double Bottom", "Bullish Engulfing"],
                "confidence_score": 78,
                "description": "Clear double bottom with volume confirmation",
                "is_valid": True,
            },
        )

        # Verify key data points
        assert "ETHUSD" in prompt
        assert "18/100" in prompt
        assert "BULLISH" in prompt
        assert "72/100" in prompt
        assert "Double Bottom" in prompt
        assert "Yes" in prompt  # Valid Signal

    def test_combined_with_system_prompt(self):
        """Test user prompt can be combined with system prompt."""
        user_prompt = build_master_prompt(
            asset_symbol="SOLUSD",
            timestamp="2025-01-01T00:00:00",
            sentiment_analysis={"fear_score": 50},
            technical_analysis={"signal": "NEUTRAL"},
            vision_analysis={"is_valid": True},
        )

        full_prompt = f"{MASTER_SYSTEM_PROMPT}\n\n{user_prompt}"

        # Both prompts should be present
        assert "MASTER NODE" in full_prompt
        assert "COUNCIL SESSION" in full_prompt
        assert "SOLUSD" in full_prompt
