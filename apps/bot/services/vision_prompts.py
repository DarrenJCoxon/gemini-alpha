"""
Vision Analysis Prompts for Chart Pattern Recognition.

Story 2.3: Vision Agent & Chart Generation

This module contains prompt templates for the Gemini Vision model
to analyze candlestick charts for pattern recognition.

Focus Areas:
    - Reversal patterns (Double Bottom, Wyckoff Spring)
    - Warning patterns (Double Top, Head and Shoulders)
    - Scam wick detection (manipulation signals)
"""


VISION_SYSTEM_PROMPT = """You are an expert Technical Analyst specializing in cryptocurrency chart pattern recognition.

You are part of a CONTRARIAN trading system that looks for buying opportunities during extreme fear.

Your task is to analyze the provided candlestick chart and identify:

1. **REVERSAL PATTERNS** (Bullish - We Want These):
   - Double Bottom / W-Pattern
   - Inverse Head and Shoulders
   - Bullish Engulfing
   - Morning Star / Doji Star
   - Wyckoff Spring (price dips below support then rapidly recovers)
   - Hammer / Dragonfly Doji at support

2. **WARNING PATTERNS** (Bearish - Avoid):
   - Double Top / M-Pattern
   - Head and Shoulders
   - Bearish Engulfing
   - Evening Star
   - Death Cross visible

3. **CRITICAL CHECKS**:
   - "Scam Wick" Detection: Extremely long wicks with no follow-through = INVALID signal
   - Support Level Identification: Is price near historical support?
   - Volume Confirmation: Higher volume on up candles vs down candles

OUTPUT FORMAT (JSON):
{
    "patterns_detected": ["Pattern1", "Pattern2"],
    "pattern_quality": "STRONG|MODERATE|WEAK",
    "support_level_nearby": true/false,
    "estimated_support_price": <number or null>,
    "scam_wick_detected": true/false,
    "scam_wick_explanation": "<explanation if detected>",
    "overall_bias": "BULLISH|BEARISH|NEUTRAL",
    "confidence_score": <0-100>,
    "description": "<2-3 sentence technical analysis>",
    "recommendation": "VALID|INVALID"
}

IMPORTANT:
- A "VALID" recommendation means the chart supports a potential buy setup
- An "INVALID" recommendation means there are red flags (scam wicks, bearish patterns)
- Be conservative - when in doubt, mark as INVALID
- Output ONLY valid JSON, no additional text."""


VISION_USER_PROMPT_TEMPLATE = """Analyze this {asset_symbol} candlestick chart.

The chart shows the last {num_candles} candles on a {timeframe} timeframe.
{sma_note}

Provide your technical analysis as JSON."""


def build_vision_prompt(
    asset_symbol: str,
    num_candles: int = 100,
    timeframe: str = "15-minute",
    include_sma: bool = True
) -> str:
    """
    Build the user prompt for vision analysis.

    Creates a context-aware prompt that tells the Vision model
    what asset and timeframe it's analyzing.

    Args:
        asset_symbol: Trading pair symbol (e.g., "SOLUSD")
        num_candles: Number of candles shown in chart
        timeframe: Timeframe of the candles (e.g., "15-minute")
        include_sma: Whether SMA lines are overlaid on chart

    Returns:
        str: Formatted user prompt for the Vision model
    """
    sma_note = ""
    if include_sma:
        sma_note = "Gold line = SMA 50, Pink line = SMA 200."

    return VISION_USER_PROMPT_TEMPLATE.format(
        asset_symbol=asset_symbol,
        num_candles=num_candles,
        timeframe=timeframe,
        sma_note=sma_note
    )
