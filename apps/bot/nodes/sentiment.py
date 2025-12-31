"""
Sentiment Analysis Agent Node.

Story 2.2: Sentiment & Technical Agents

This node analyzes social sentiment data from various sources
(LunarCrush, Bluesky, Telegram) to generate a fear/greed score.

Uses Gemini Flash for fast, cost-effective sentiment analysis
following the ContrarianAI trading philosophy.
"""

import logging
from typing import Dict, Any

from core.state import GraphState, SentimentAnalysis
from services.sentiment_utils import (
    SENTIMENT_SYSTEM_PROMPT,
    format_sentiment_data_for_prompt,
    parse_sentiment_response
)

logger = logging.getLogger(__name__)


def sentiment_node(state: GraphState) -> Dict[str, Any]:
    """
    Sentiment Analysis Agent - Analyzes social sentiment data.

    Uses Gemini Flash to analyze sentiment entries and calculate
    a fear/greed score based on contrarian trading principles:
    - Low fear score (0-20) = extreme fear = potential BUY opportunity
    - High fear score (80-100) = extreme greed = potential SELL opportunity

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

    # Handle empty sentiment data
    if not sentiment_data:
        logger.warning(f"[SentimentAgent] No sentiment data available for {asset}")
        sentiment_analysis: SentimentAnalysis = {
            "fear_score": 50,  # Neutral when no data
            "summary": "No sentiment data available for analysis",
            "source_count": 0
        }
        return {"sentiment_analysis": sentiment_analysis}

    try:
        # Format data for prompt
        formatted_data = format_sentiment_data_for_prompt(sentiment_data)

        # Build user prompt
        user_prompt = f"""Analyze the following social media and news data for {asset}:

{formatted_data}

Provide your sentiment analysis as JSON."""

        # Try to call Gemini Flash
        try:
            from config import get_gemini_flash_model

            model = get_gemini_flash_model()
            response = model.generate_content([
                SENTIMENT_SYSTEM_PROMPT,
                user_prompt
            ])

            # Parse response
            parsed = parse_sentiment_response(response.text)

            sentiment_analysis = {
                "fear_score": parsed["fear_score"],
                "summary": parsed["summary"],
                "source_count": len(sentiment_data)
            }

            logger.info(f"[SentimentAgent] Fear Score: {parsed['fear_score']}/100")
            logger.debug(f"[SentimentAgent] Emotion: {parsed['dominant_emotion']}")
            logger.debug(f"[SentimentAgent] Summary: {parsed['summary'][:100]}...")

        except ValueError as e:
            # API key not configured - use fallback
            logger.warning(f"[SentimentAgent] Gemini not configured: {e}")
            sentiment_analysis = _fallback_sentiment_analysis(sentiment_data)

        except Exception as e:
            # Other Gemini errors - use fallback
            logger.error(f"[SentimentAgent] Gemini error: {str(e)}")
            sentiment_analysis = _fallback_sentiment_analysis(sentiment_data)

    except Exception as e:
        logger.error(f"[SentimentAgent] Error during analysis: {str(e)}")
        sentiment_analysis = {
            "fear_score": 50,
            "summary": f"Error during sentiment analysis: {str(e)}",
            "source_count": len(sentiment_data)
        }

    # Return only the fields to update (LangGraph merge pattern)
    return {"sentiment_analysis": sentiment_analysis}


def _fallback_sentiment_analysis(sentiment_data: list) -> SentimentAnalysis:
    """
    Provide fallback sentiment analysis when Gemini is unavailable.

    Uses simple keyword-based heuristics to estimate sentiment
    when the LLM cannot be called.

    Args:
        sentiment_data: List of sentiment entries

    Returns:
        SentimentAnalysis dict with estimated values
    """
    # Simple keyword-based fallback
    fear_keywords = ['crash', 'dump', 'panic', 'sell', 'bear', 'down', 'drop', 'fear', 'worried', 'scared']
    greed_keywords = ['moon', 'pump', 'buy', 'bull', 'up', 'rise', 'fomo', 'ath', 'million', 'rich']

    fear_count = 0
    greed_count = 0

    for entry in sentiment_data:
        text = entry.get("text", entry.get("content", entry.get("raw_text", ""))).lower()
        for keyword in fear_keywords:
            if keyword in text:
                fear_count += 1
        for keyword in greed_keywords:
            if keyword in text:
                greed_count += 1

    total = fear_count + greed_count
    if total == 0:
        fear_score = 50  # Neutral
    else:
        # Score goes up with greed, down with fear
        fear_score = int((greed_count / total) * 100)

    if fear_score < 30:
        emotion = "FEAR"
    elif fear_score > 70:
        emotion = "GREED"
    else:
        emotion = "NEUTRAL"

    return {
        "fear_score": fear_score,
        "summary": f"Fallback analysis: {emotion} sentiment detected (keyword-based). "
                   f"Fear keywords: {fear_count}, Greed keywords: {greed_count}",
        "source_count": len(sentiment_data)
    }
