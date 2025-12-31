"""
Sentiment Analysis Utilities for the Trading Bot.

Story 2.2: Sentiment & Technical Agents

This module provides utilities for sentiment analysis using Gemini AI,
including prompt formatting and response parsing for fear/greed analysis.
"""

import json
from typing import List, Dict, Any


SENTIMENT_SYSTEM_PROMPT = """You are a Crypto Sentiment Analyst specializing in detecting market fear and greed.

Analyze the provided social media posts, news headlines, and market commentary.

Focus on identifying:
1. FEAR indicators: panic selling, capitulation, extreme pessimism, "it's going to zero"
2. GREED indicators: FOMO, "to the moon", excessive optimism, price targets
3. NEUTRAL indicators: factual analysis, balanced views

Output your analysis as JSON with this exact structure:
{
    "fear_score": <integer 0-100, where 0=extreme fear, 100=extreme greed>,
    "dominant_emotion": "<FEAR|GREED|NEUTRAL>",
    "summary": "<2-3 sentence summary of overall sentiment>",
    "key_themes": ["<theme1>", "<theme2>", "<theme3>"]
}

IMPORTANT:
- For CONTRARIAN trading, we BUY when fear_score is LOW (extreme fear = buying opportunity)
- A fear_score of 10-20 indicates extreme fear (potential buy signal)
- A fear_score of 80-90 indicates extreme greed (potential sell signal)

Output ONLY valid JSON, no additional text."""


def format_sentiment_data_for_prompt(sentiment_data: List[Dict[str, Any]]) -> str:
    """
    Format sentiment log entries for LLM prompt.

    Converts a list of sentiment entries into a numbered, formatted
    string suitable for input to the Gemini model.

    Args:
        sentiment_data: List of sentiment entries with keys:
            - text or content: The sentiment text
            - source: Source of the sentiment (twitter, reddit, etc.)
            - timestamp: Optional timestamp

    Returns:
        Formatted string with numbered entries, or default message if empty
    """
    if not sentiment_data:
        return "No sentiment data available."

    formatted = []
    # Limit to 20 entries to manage token usage
    for i, entry in enumerate(sentiment_data[:20], 1):
        # Handle both 'text' and 'content' keys
        text = entry.get("text", entry.get("content", entry.get("raw_text", "")))
        source = entry.get("source", "unknown")

        if text:
            formatted.append(f"{i}. [{source}] {text}")

    if not formatted:
        return "No sentiment data available."

    return "\n".join(formatted)


def parse_sentiment_response(response_text: str) -> Dict[str, Any]:
    """
    Parse LLM JSON response to sentiment dict.

    Handles various response formats including markdown code blocks
    and extracts structured sentiment data.

    Args:
        response_text: Raw text response from Gemini

    Returns:
        Dict with:
            - fear_score: 0-100 integer
            - dominant_emotion: FEAR/GREED/NEUTRAL string
            - summary: Text summary
            - key_themes: List of theme strings
    """
    try:
        # Clean up the response text
        response_text = response_text.strip()

        # Handle markdown code blocks
        if response_text.startswith("```json"):
            response_text = response_text[7:]
        if response_text.startswith("```"):
            response_text = response_text[3:]
        if response_text.endswith("```"):
            response_text = response_text[:-3]

        response_text = response_text.strip()

        # Try to parse JSON
        data = json.loads(response_text)

        # Validate and extract fields with defaults
        fear_score = data.get("fear_score", 50)
        if not isinstance(fear_score, (int, float)):
            fear_score = 50
        fear_score = max(0, min(100, int(fear_score)))  # Clamp to 0-100

        dominant_emotion = data.get("dominant_emotion", "NEUTRAL")
        if dominant_emotion not in ["FEAR", "GREED", "NEUTRAL"]:
            dominant_emotion = "NEUTRAL"

        summary = data.get("summary", "Unable to determine sentiment")
        if not isinstance(summary, str):
            summary = str(summary)

        key_themes = data.get("key_themes", [])
        if not isinstance(key_themes, list):
            key_themes = []
        # Ensure all themes are strings
        key_themes = [str(theme) for theme in key_themes if theme]

        return {
            "fear_score": fear_score,
            "dominant_emotion": dominant_emotion,
            "summary": summary,
            "key_themes": key_themes
        }

    except json.JSONDecodeError:
        # Return neutral defaults if parsing fails
        return {
            "fear_score": 50,
            "dominant_emotion": "NEUTRAL",
            "summary": f"Failed to parse LLM response: {response_text[:100]}...",
            "key_themes": []
        }


def calculate_sentiment_signal(fear_score: int) -> tuple[str, int, str]:
    """
    Calculate trading signal from fear score.

    Based on ContrarianAI philosophy:
    - Low fear score = extreme fear = BUY opportunity
    - High fear score = extreme greed = SELL opportunity
    - Middle range = HOLD/neutral

    Args:
        fear_score: Fear/greed score 0-100

    Returns:
        Tuple of (signal, strength, reasoning):
            signal: "BUY", "SELL", or "HOLD"
            strength: Signal strength 0-100
            reasoning: Explanation
    """
    if fear_score <= 20:
        strength = 100 - fear_score  # Lower fear = stronger buy
        return "BUY", strength, f"Extreme fear detected (score: {fear_score}). Contrarian buy opportunity."
    elif fear_score <= 35:
        strength = 70 - fear_score
        return "BUY", max(50, strength), f"Elevated fear (score: {fear_score}). Potential accumulation zone."
    elif fear_score >= 80:
        strength = fear_score  # Higher greed = stronger sell
        return "SELL", strength, f"Extreme greed detected (score: {fear_score}). Contrarian sell opportunity."
    elif fear_score >= 65:
        strength = fear_score - 15
        return "SELL", max(50, strength), f"Elevated greed (score: {fear_score}). Potential distribution zone."
    else:
        return "HOLD", 50, f"Neutral sentiment (score: {fear_score}). No contrarian signal."
