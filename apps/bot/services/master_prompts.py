"""
Master Node Prompts for the Council of AI Agents.

Story 2.4: Master Node & Signal Logging

This module contains the system and user prompts for the Master Node,
which synthesizes inputs from the three specialist agents (Sentiment,
Technical, Vision) and makes final trading decisions.

The Master Node acts as a Risk Manager applying strict contrarian
trading logic to exploit retail trader emotions.
"""

MASTER_SYSTEM_PROMPT = """You are the MASTER NODE of a contrarian crypto trading council.

Your role is to synthesize inputs from three specialist agents and make a final trading decision.

## CONTRARIAN TRADING PHILOSOPHY
We exploit retail trader emotions. When the crowd panics (extreme fear), we look for buying opportunities.
When the crowd is euphoric (extreme greed), we look to sell.

## INPUT AGENTS
1. **Sentiment Agent**: Provides fear_score (0-100, lower = more fear)
2. **Technical Agent**: Provides signal (BULLISH/BEARISH/NEUTRAL) and strength (0-100)
3. **Vision Agent**: Provides pattern analysis and validity check

## DECISION RULES (STRICT - DO NOT DEVIATE)

### BUY Signal Requirements (ALL must be true):
- fear_score < 20 (extreme fear - crowd is panicking)
- technical_signal = "BULLISH"
- vision_is_valid = true (no scam wicks detected)

### SELL Signal Requirements (ANY can trigger):
- fear_score > 80 (extreme greed - crowd is euphoric)
- technical_signal = "BEARISH" with strength > 70
- vision detected bearish reversal pattern

### HOLD Signal:
- All other cases

## OUTPUT FORMAT (JSON)
{
    "action": "BUY|SELL|HOLD",
    "confidence": <0-100>,
    "reasoning": "<detailed explanation of decision>",
    "risk_assessment": "LOW|MEDIUM|HIGH",
    "key_factors": ["factor1", "factor2", "factor3"]
}

## CRITICAL RULES
1. NEVER recommend BUY unless ALL three BUY conditions are met
2. When in doubt, HOLD - capital preservation is priority
3. Explain your reasoning clearly for audit trail
4. Consider the strength values, not just the signals
5. Output ONLY valid JSON"""

MASTER_USER_PROMPT_TEMPLATE = """## COUNCIL SESSION: {asset_symbol}
Timestamp: {timestamp}

### SENTIMENT ANALYSIS
- Fear Score: {fear_score}/100 (0=extreme fear, 100=extreme greed)
- Summary: {sentiment_summary}
- Sources Analyzed: {source_count}

### TECHNICAL ANALYSIS
- Signal: {technical_signal}
- Strength: {technical_strength}/100
- RSI: {rsi}
- SMA50: ${sma_50}
- SMA200: ${sma_200}
- Volume Delta: {volume_delta}%
- Reasoning: {technical_reasoning}

### VISION ANALYSIS
- Patterns Detected: {patterns}
- Confidence: {vision_confidence}/100
- Valid Signal: {vision_valid}
- Description: {vision_description}

---

Based on the above inputs, make your trading decision.
Remember: BUY only if fear_score < 20 AND technical_signal = BULLISH AND vision_valid = true."""


def build_master_prompt(
    asset_symbol: str,
    timestamp: str,
    sentiment_analysis: dict,
    technical_analysis: dict,
    vision_analysis: dict
) -> str:
    """
    Build the user prompt for Master Node synthesis.

    Combines all agent analyses into a formatted prompt for the LLM
    to make a final trading decision.

    Args:
        asset_symbol: Trading pair symbol (e.g., "SOLUSD")
        timestamp: ISO timestamp of the council session
        sentiment_analysis: Output from Sentiment Agent
        technical_analysis: Output from Technical Agent
        vision_analysis: Output from Vision Agent

    Returns:
        Formatted user prompt string for the Master Node LLM
    """
    # Extract patterns list and format as comma-separated string
    patterns_list = vision_analysis.get("patterns_detected", [])
    patterns_str = ", ".join(patterns_list) if patterns_list else "None"

    # Format vision validity as human-readable
    vision_valid = "Yes" if vision_analysis.get("is_valid", False) else "No"

    return MASTER_USER_PROMPT_TEMPLATE.format(
        asset_symbol=asset_symbol,
        timestamp=timestamp,
        fear_score=sentiment_analysis.get("fear_score", 50),
        sentiment_summary=sentiment_analysis.get("summary", "N/A"),
        source_count=sentiment_analysis.get("source_count", 0),
        technical_signal=technical_analysis.get("signal", "NEUTRAL"),
        technical_strength=technical_analysis.get("strength", 0),
        rsi=technical_analysis.get("rsi", 50),
        sma_50=technical_analysis.get("sma_50", 0),
        sma_200=technical_analysis.get("sma_200", 0),
        volume_delta=technical_analysis.get("volume_delta", 0),
        technical_reasoning=technical_analysis.get("reasoning", "N/A"),
        patterns=patterns_str,
        vision_confidence=vision_analysis.get("confidence_score", 0),
        vision_valid=vision_valid,
        vision_description=vision_analysis.get("description", "N/A")
    )
