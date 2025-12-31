"""
Technical Analysis Agent Node.

Story 2.1: LangGraph State Machine Setup (Stub Implementation)

This node performs technical analysis on price candle data
using indicators like RSI, moving averages, and volume analysis.

Future Implementation (Story 2.2):
    - Calculate RSI, SMA-50, SMA-200, volume delta
    - Use Gemini to interpret indicator values
    - Generate trading signal with confidence
"""

import logging
from typing import Dict, Any

from core.state import GraphState, TechnicalAnalysis

logger = logging.getLogger(__name__)


def technical_node(state: GraphState) -> Dict[str, Any]:
    """
    Technical Analysis Agent - Processes price data for trading signals.

    This stub implementation returns neutral analysis values.
    Full implementation in Story 2.2 will:
    - Calculate technical indicators from candles_data
    - Use Vertex AI Gemini to interpret indicator patterns
    - Generate signal with strength and reasoning

    Args:
        state: Current GraphState containing candles_data

    Returns:
        Dict with technical_analysis field populated

    Note:
        Returns dict with only the fields to update (LangGraph pattern),
        not the full state. LangGraph merges this with existing state.
    """
    asset = state.get("asset_symbol", "UNKNOWN")
    candles = state.get("candles_data", [])

    logger.info(f"[TechnicalAgent] Processing {asset} with {len(candles)} candles")

    # Stub implementation - returns neutral analysis
    # TODO: Implement actual technical analysis in Story 2.2
    technical_analysis: TechnicalAnalysis = {
        "signal": "NEUTRAL",
        "strength": 50,
        "rsi": 50.0,
        "sma_50": 0.0,
        "sma_200": 0.0,
        "volume_delta": 0.0,
        "reasoning": "Stub implementation - awaiting Story 2.2 for full analysis"
    }

    logger.info(f"[TechnicalAgent] Generated signal: {technical_analysis['signal']}")

    # Return only the fields to update (LangGraph merge pattern)
    return {"technical_analysis": technical_analysis}
