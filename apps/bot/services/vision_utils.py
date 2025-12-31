"""
Vision Response Parsing Utilities.

Story 2.3: Vision Agent & Chart Generation

This module provides utilities for parsing and validating
JSON responses from the Gemini Vision model.
"""

import json
from typing import Any, Dict, Optional


def parse_vision_response(response_text: str) -> Dict[str, Any]:
    """
    Parse Gemini Vision JSON response.

    Handles common response variations:
    - Clean JSON
    - JSON wrapped in markdown code blocks
    - Invalid JSON (returns safe defaults)

    Args:
        response_text: Raw text response from Gemini Vision

    Returns:
        Dict with parsed analysis fields:
            - patterns_detected: List of pattern names
            - pattern_quality: STRONG, MODERATE, or WEAK
            - support_level_nearby: bool
            - scam_wick_detected: bool
            - overall_bias: BULLISH, BEARISH, or NEUTRAL
            - confidence_score: 0-100
            - description: Analysis description
            - recommendation: VALID or INVALID
    """
    try:
        # Clean markdown if present
        text = response_text.strip()

        # Handle ```json ... ``` blocks
        if text.startswith("```json"):
            text = text[7:]
        if text.startswith("```"):
            text = text[3:]
        if text.endswith("```"):
            text = text[:-3]

        data = json.loads(text.strip())

        return {
            "patterns_detected": data.get("patterns_detected", []),
            "pattern_quality": data.get("pattern_quality", "WEAK"),
            "support_level_nearby": data.get("support_level_nearby", False),
            "estimated_support_price": data.get("estimated_support_price"),
            "scam_wick_detected": data.get("scam_wick_detected", False),
            "scam_wick_explanation": data.get("scam_wick_explanation", ""),
            "overall_bias": data.get("overall_bias", "NEUTRAL"),
            "confidence_score": int(data.get("confidence_score", 50)),
            "description": data.get("description", "Unable to analyze chart"),
            "recommendation": data.get("recommendation", "INVALID")
        }
    except json.JSONDecodeError:
        return {
            "patterns_detected": [],
            "pattern_quality": "WEAK",
            "support_level_nearby": False,
            "estimated_support_price": None,
            "scam_wick_detected": False,
            "scam_wick_explanation": "",
            "overall_bias": "NEUTRAL",
            "confidence_score": 0,
            "description": f"Failed to parse vision response: {response_text[:100]}",
            "recommendation": "INVALID"
        }


def validate_vision_result(parsed: Dict[str, Any]) -> bool:
    """
    Validate if vision analysis indicates a valid trading opportunity.

    A result is considered valid if:
    - recommendation is "VALID"
    - No scam wick detected
    - Confidence score is at least 30

    Args:
        parsed: Parsed vision response dictionary

    Returns:
        bool: True if the analysis indicates a valid opportunity
    """
    return (
        parsed.get("recommendation") == "VALID" and
        not parsed.get("scam_wick_detected", False) and
        parsed.get("confidence_score", 0) >= 30
    )


def extract_key_patterns(parsed: Dict[str, Any]) -> Dict[str, bool]:
    """
    Extract presence of key trading patterns from parsed response.

    Categorizes detected patterns into bullish reversal patterns
    and bearish warning patterns for easier decision making.

    Args:
        parsed: Parsed vision response dictionary

    Returns:
        Dict with pattern category flags:
            - has_reversal_pattern: True if bullish reversal detected
            - has_warning_pattern: True if bearish warning detected
            - pattern_names: List of all detected patterns
    """
    patterns = [p.lower() for p in parsed.get("patterns_detected", [])]

    # Bullish reversal patterns
    reversal_patterns = [
        "double bottom", "w-pattern", "inverse head and shoulders",
        "bullish engulfing", "morning star", "doji star",
        "wyckoff spring", "hammer", "dragonfly doji"
    ]

    # Bearish warning patterns
    warning_patterns = [
        "double top", "m-pattern", "head and shoulders",
        "bearish engulfing", "evening star", "death cross"
    ]

    has_reversal = any(
        any(rp in p for rp in reversal_patterns)
        for p in patterns
    )

    has_warning = any(
        any(wp in p for wp in warning_patterns)
        for p in patterns
    )

    return {
        "has_reversal_pattern": has_reversal,
        "has_warning_pattern": has_warning,
        "pattern_names": parsed.get("patterns_detected", [])
    }
