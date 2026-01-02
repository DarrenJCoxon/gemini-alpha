"""
Master Node Prompts for the Council of AI Agents.

Story 2.4: Master Node & Signal Logging
Story 5.11: Trend-Confirmed Pullback Trading

This module contains the system and user prompts for the Master Node,
which synthesizes inputs from the three specialist agents (Sentiment,
Technical, Vision) and makes final trading decisions.

STRATEGY SHIFT (Story 5.11):
- Primary: Buy pullbacks in confirmed uptrends (trend-following)
- Secondary: Extreme contrarian plays only at fear < 25 + RSI < 30
- Key insight: "Buy the dip" only works in confirmed uptrends
"""

MASTER_SYSTEM_PROMPT = """You are the MASTER NODE of a trend-confirmed crypto trading council.

Your role is to synthesize inputs from specialist agents and make trading decisions that:
1. PRIMARILY buy pullbacks in confirmed uptrends (professional approach)
2. SECONDARILY take extreme contrarian positions only at extreme fear levels

## REVISED TRADING PHILOSOPHY (Story 5.11)
Research shows trend-following beats pure contrarian in crypto. We now:
- Buy pullbacks in uptrends (RSI 40-55 zone, not extreme 30)
- Confirm uptrend structure (Higher Highs + Higher Lows intact)
- Use fear/greed as CONFIRMATION, not primary signal
- Reserve contrarian trades for extreme fear only (< 25)

## INPUT AGENTS
1. **Sentiment Agent**: Provides fear_score (0-100, lower = more fear)
2. **Technical Agent**: Provides signal, RSI, trend direction, and structure
3. **Vision Agent**: Provides pattern analysis and validity check

## MARKET REGIMES
- **UPTREND**: Higher Highs + Higher Lows pattern confirmed
- **DOWNTREND**: Lower Highs + Lower Lows - AVOID buying
- **SIDEWAYS**: Range-bound - trade with caution

## DECISION RULES (REVISED)

### TREND PULLBACK BUY (PRIMARY - Best opportunities)
Requirements (ALL must be true):
- Market in UPTREND with structure intact
- RSI between 40-55 (pulled back but not capitulating)
- Price at or near support (EMA or previous structure)
- technical_signal = "BULLISH" or "NEUTRAL"
- vision_is_valid = true (no scam wicks)
Confidence: 70-90

### CONTRARIAN EXTREME BUY (SECONDARY - Smaller positions)
Requirements (ALL must be true):
- fear_score < 25 (extreme fear only)
- RSI < 30 (oversold extreme)
- vision_is_valid = true
- Use HALF normal position size
Confidence: 50-70 (lower due to higher risk)

WARNING: Do NOT buy oversold in a DOWNTREND - that's catching falling knives!

### SELL Signal Requirements (ANY can trigger):
- fear_score > 80 (extreme greed)
- RSI > 75 with divergence
- Market structure break (last Higher Low violated)
- vision detected bearish reversal pattern

### HOLD Signal:
- Market in DOWNTREND (wait for structure change)
- RSI > 60 in uptrend (wait for pullback)
- No clear setup - capital preservation priority
- When in doubt, HOLD

## OUTPUT FORMAT (JSON)
{
    "action": "BUY|SELL|HOLD",
    "confidence": <0-100>,
    "reasoning": "<detailed explanation including trend context>",
    "risk_assessment": "LOW|MEDIUM|HIGH",
    "key_factors": ["factor1", "factor2", "factor3"],
    "entry_type": "TREND_PULLBACK|CONTRARIAN_EXTREME|NO_SETUP"
}

## CRITICAL RULES
1. ALWAYS check trend direction before BUY decisions
2. NEVER buy pullbacks in a DOWNTREND
3. RSI 40-50 in uptrend = prime entry zone
4. Extreme contrarian (fear < 25) = smaller positions
5. When in doubt, HOLD - wait for clearer setup
6. Output ONLY valid JSON"""

MASTER_USER_PROMPT_TEMPLATE = """## COUNCIL SESSION: {asset_symbol}
Timestamp: {timestamp}

### MARKET REGIME (Story 5.11)
- Trend Direction: {trend_direction}
- Structure Intact: {structure_intact}
- ADX (Trend Strength): {adx}
- Entry Type Suggested: {entry_type}

### SENTIMENT ANALYSIS
- Fear & Greed Score: {fear_score}/100 (0=extreme fear, 100=extreme greed)
- Summary: {sentiment_summary}
- Sources Analyzed: {source_count}

### TECHNICAL ANALYSIS
- Signal: {technical_signal}
- Strength: {technical_strength}/100
- RSI: {rsi}
- RSI Zone: {rsi_zone}
- Price vs EMA50: {ema_position} ({ema_distance}%)
- SMA50: ${sma_50}
- SMA200: ${sma_200}
- Volume Delta: {volume_delta}%
- Pullback Depth: {pullback_depth}%
- Reasoning: {technical_reasoning}

### VISION ANALYSIS
- Patterns Detected: {patterns}
- Confidence: {vision_confidence}/100
- Valid Signal: {vision_valid}
- Description: {vision_description}

---

DECISION FRAMEWORK:
1. If UPTREND + RSI 40-55 + Structure Intact → Consider TREND_PULLBACK BUY
2. If fear_score < 25 + RSI < 30 → Consider CONTRARIAN_EXTREME BUY (smaller size)
3. If DOWNTREND → HOLD regardless of other signals
4. When in doubt → HOLD

Make your trading decision based on the above inputs."""


def build_master_prompt(
    asset_symbol: str,
    timestamp: str,
    sentiment_analysis: dict,
    technical_analysis: dict,
    vision_analysis: dict,
    trend_context: dict = None
) -> str:
    """
    Build the user prompt for Master Node synthesis.

    Combines all agent analyses into a formatted prompt for the LLM
    to make a final trading decision with trend context.

    Args:
        asset_symbol: Trading pair symbol (e.g., "SOLUSD")
        timestamp: ISO timestamp of the council session
        sentiment_analysis: Output from Sentiment Agent
        technical_analysis: Output from Technical Agent
        vision_analysis: Output from Vision Agent
        trend_context: Optional trend analysis from scanner

    Returns:
        Formatted user prompt string for the Master Node LLM
    """
    # Extract patterns list and format as comma-separated string
    patterns_list = vision_analysis.get("patterns_detected", [])
    patterns_str = ", ".join(patterns_list) if patterns_list else "None"

    # Format vision validity as human-readable
    vision_valid = "Yes" if vision_analysis.get("is_valid", False) else "No"

    # Get trend context (from scanner or technical analysis)
    trend_context = trend_context or {}

    # Determine trend direction from technical analysis if not provided
    trend_direction = trend_context.get("direction")
    if not trend_direction:
        tech_signal = technical_analysis.get("signal", "NEUTRAL")
        rsi = technical_analysis.get("rsi", 50)
        if tech_signal == "BULLISH" and rsi < 60:
            trend_direction = "UPTREND"
        elif tech_signal == "BEARISH":
            trend_direction = "DOWNTREND"
        else:
            trend_direction = "SIDEWAYS"

    # Determine RSI zone
    rsi = technical_analysis.get("rsi", 50)
    if rsi < 30:
        rsi_zone = "OVERSOLD"
    elif rsi < 40:
        rsi_zone = "DEEP_PULLBACK"
    elif rsi <= 55:
        rsi_zone = "PULLBACK_ZONE (prime entry)"
    elif rsi < 70:
        rsi_zone = "NEUTRAL"
    else:
        rsi_zone = "OVERBOUGHT"

    # Determine entry type suggestion
    fear_score = sentiment_analysis.get("fear_score", 50)
    structure_intact = trend_context.get("structure_intact", True)

    if trend_direction == "UPTREND" and 40 <= rsi <= 55 and structure_intact:
        entry_type = "TREND_PULLBACK (recommended)"
    elif fear_score < 25 and rsi < 30:
        entry_type = "CONTRARIAN_EXTREME (use smaller size)"
    elif trend_direction == "DOWNTREND":
        entry_type = "NO_SETUP (downtrend active)"
    else:
        entry_type = "WAIT (no clear setup)"

    # Calculate EMA position
    ema_position = trend_context.get("ema_position", "UNKNOWN")
    ema_distance = trend_context.get("ema_distance_pct", 0)

    # Calculate pullback depth
    pullback_depth = trend_context.get("pullback_depth_pct", 0)

    return MASTER_USER_PROMPT_TEMPLATE.format(
        asset_symbol=asset_symbol,
        timestamp=timestamp,
        trend_direction=trend_direction,
        structure_intact="Yes" if structure_intact else "No",
        adx=trend_context.get("adx", 25),
        entry_type=entry_type,
        fear_score=fear_score,
        sentiment_summary=sentiment_analysis.get("summary", "N/A"),
        source_count=sentiment_analysis.get("source_count", 0),
        technical_signal=technical_analysis.get("signal", "NEUTRAL"),
        technical_strength=technical_analysis.get("strength", 0),
        rsi=rsi,
        rsi_zone=rsi_zone,
        ema_position=ema_position,
        ema_distance=f"{ema_distance:.1f}" if ema_distance else "0.0",
        sma_50=technical_analysis.get("sma_50", 0),
        sma_200=technical_analysis.get("sma_200", 0),
        volume_delta=technical_analysis.get("volume_delta", 0),
        pullback_depth=f"{pullback_depth:.1f}" if pullback_depth else "0.0",
        technical_reasoning=technical_analysis.get("reasoning", "N/A"),
        patterns=patterns_str,
        vision_confidence=vision_analysis.get("confidence_score", 0),
        vision_valid=vision_valid,
        vision_description=vision_analysis.get("description", "N/A")
    )
