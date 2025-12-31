"""
Sentiment Analysis Agent Node.

Story 2.1: LangGraph State Machine Setup (Stub Implementation)

This node analyzes social sentiment data from various sources
(LunarCrush, Bluesky, Telegram) to generate a fear/greed score.

Future Implementation (Story 2.2):
    - Process sentiment_data from database
    - Use Gemini to analyze text sentiment
    - Calculate aggregated fear/greed score
    - Generate natural language summary
"""

import logging
from typing import Dict, Any

from core.state import GraphState, SentimentAnalysis

logger = logging.getLogger(__name__)


def sentiment_node(state: GraphState) -> Dict[str, Any]:
    """
    Sentiment Analysis Agent - Analyzes social sentiment data.

    This stub implementation returns neutral sentiment values.
    Full implementation in Story 2.2 will:
    - Process sentiment entries from sentiment_data
    - Use Vertex AI Gemini for NLP sentiment analysis
    - Calculate fear/greed score based on contrarian principles
    - Generate summary of sentiment landscape

    Args:
        state: Current GraphState containing sentiment_data

    Returns:
        Dict with sentiment_analysis field populated

    Note:
        Returns dict with only the fields to update (LangGraph pattern),
        not the full state. LangGraph merges this with existing state.
    """
    asset = state.get("asset_symbol", "UNKNOWN")
    sentiment_data = state.get("sentiment_data", [])

    logger.info(f"[SentimentAgent] Processing {asset} with {len(sentiment_data)} sentiment entries")

    # Stub implementation - returns neutral sentiment
    # TODO: Implement actual sentiment analysis in Story 2.2
    sentiment_analysis: SentimentAnalysis = {
        "fear_score": 50,
        "summary": "Stub implementation - neutral sentiment. Awaiting Story 2.2 for full analysis.",
        "source_count": len(sentiment_data)
    }

    logger.info(f"[SentimentAgent] Fear score: {sentiment_analysis['fear_score']}")

    # Return only the fields to update (LangGraph merge pattern)
    return {"sentiment_analysis": sentiment_analysis}
