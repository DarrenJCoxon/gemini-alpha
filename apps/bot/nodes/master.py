"""
Master Synthesis Node.

Story 2.1: LangGraph State Machine Setup (Stub Implementation)

This node synthesizes all agent analyses into a final trading decision,
applying contrarian trading principles and risk management rules.

Future Implementation (Story 2.4):
    - Gather technical, sentiment, and vision analyses
    - Apply contrarian logic (buy fear, sell greed)
    - Check for conflicting signals
    - Generate final BUY/SELL/HOLD with confidence
    - Log decision to database for audit trail
"""

import logging
from datetime import datetime, timezone
from typing import Any, Dict

from core.state import FinalDecision, GraphState

logger = logging.getLogger(__name__)


def master_node(state: GraphState) -> Dict[str, Any]:
    """
    Master Synthesis Node - Makes final trading decision.

    This stub implementation returns a HOLD decision.
    Full implementation in Story 2.4 will:
    - Synthesize technical, sentiment, and vision analyses
    - Apply contrarian trading logic
    - Weight signals based on confidence scores
    - Generate final decision with reasoning

    Args:
        state: Current GraphState with all agent analyses

    Returns:
        Dict with final_decision field populated

    Note:
        Returns dict with only the fields to update (LangGraph pattern),
        not the full state. LangGraph merges this with existing state.

    Decision Logic (Stub):
        Always returns HOLD with 50% confidence as placeholder.

    Decision Logic (Future - Story 2.4):
        - If fear_score < 30 and technical bullish -> BUY (contrarian)
        - If fear_score > 70 and technical bearish -> SELL (contrarian)
        - If vision detects scam_wick -> HOLD (safety)
        - Otherwise -> HOLD
    """
    asset = state.get("asset_symbol", "UNKNOWN")

    # Get agent analyses (may be None if agents haven't run yet)
    technical = state.get("technical_analysis")
    sentiment = state.get("sentiment_analysis")
    vision = state.get("vision_analysis")

    logger.info(f"[MasterNode] Synthesizing decision for {asset}")
    logger.info(f"[MasterNode] Technical: {technical}")
    logger.info(f"[MasterNode] Sentiment: {sentiment}")
    logger.info(f"[MasterNode] Vision: {vision}")

    # Stub implementation - returns HOLD decision
    # TODO: Implement synthesis logic in Story 2.4
    reasoning_parts = []

    if technical:
        reasoning_parts.append(f"Technical signal: {technical.get('signal', 'N/A')}")
    if sentiment:
        reasoning_parts.append(f"Fear score: {sentiment.get('fear_score', 'N/A')}")
    if vision:
        reasoning_parts.append(f"Chart valid: {vision.get('is_valid', 'N/A')}")

    reasoning = (
        "Stub implementation - defaulting to HOLD. "
        f"Inputs: {', '.join(reasoning_parts) if reasoning_parts else 'None available'}. "
        "Awaiting Story 2.4 for full synthesis logic."
    )

    final_decision: FinalDecision = {
        "action": "HOLD",
        "confidence": 50,
        "reasoning": reasoning,
        "timestamp": datetime.now(timezone.utc)
    }

    logger.info(f"[MasterNode] Decision: {final_decision['action']} ({final_decision['confidence']}%)")

    # Return only the fields to update (LangGraph merge pattern)
    return {"final_decision": final_decision}
