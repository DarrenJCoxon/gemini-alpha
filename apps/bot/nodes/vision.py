"""
Vision Analysis Agent Node.

Story 2.1: LangGraph State Machine Setup (Stub Implementation)

This node generates candlestick charts and uses Gemini Vision
to analyze chart patterns and detect potential manipulation.

Future Implementation (Story 2.3):
    - Generate candlestick chart image from candles_data
    - Send image to Gemini Vision for pattern analysis
    - Detect head_and_shoulders, double_tops, support/resistance
    - Flag "scam wicks" and manipulation patterns
"""

import logging
from typing import Any, Dict, List

from core.state import GraphState, VisionAnalysis

logger = logging.getLogger(__name__)


def vision_node(state: GraphState) -> Dict[str, Any]:
    """
    Vision Analysis Agent - Analyzes chart patterns visually.

    This stub implementation returns default analysis values.
    Full implementation in Story 2.3 will:
    - Generate candlestick chart image from candles_data
    - Use Vertex AI Gemini Vision to analyze chart
    - Detect patterns (head_and_shoulders, double_bottom, etc.)
    - Flag potential manipulation ("scam wick" detection)

    Args:
        state: Current GraphState containing candles_data

    Returns:
        Dict with vision_analysis field populated

    Note:
        Returns dict with only the fields to update (LangGraph pattern),
        not the full state. LangGraph merges this with existing state.
    """
    asset = state.get("asset_symbol", "UNKNOWN")
    candles = state.get("candles_data", [])

    logger.info(f"[VisionAgent] Processing {asset} chart with {len(candles)} candles")

    # Stub implementation - returns default analysis
    # TODO: Implement chart generation and vision analysis in Story 2.3
    patterns_detected: List[str] = []
    vision_analysis: VisionAnalysis = {
        "patterns_detected": patterns_detected,
        "confidence_score": 50,
        "description": "Stub implementation - no chart patterns analyzed. Awaiting Story 2.3.",
        "is_valid": True  # Default to valid (no manipulation detected)
    }

    logger.info(f"[VisionAgent] Patterns detected: {patterns_detected}, Valid: {vision_analysis['is_valid']}")

    # Return only the fields to update (LangGraph merge pattern)
    return {"vision_analysis": vision_analysis}
