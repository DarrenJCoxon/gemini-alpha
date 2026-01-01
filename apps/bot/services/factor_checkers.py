"""
Individual Factor Checking Functions for Multi-Factor Confirmation System.

Story 5.3: Multi-Factor Confirmation System

This module provides individual factor checking functions that evaluate
specific market conditions against configurable thresholds. Each function
returns a FactorResult indicating whether the condition was met.

Factor Categories:
    BUY Factors:
        - check_extreme_fear: Fear & Greed < threshold
        - check_rsi_oversold: RSI < threshold
        - check_price_at_support: Price within X% of SMA200
        - check_volume_capitulation: Volume > 2x average
        - check_bullish_technicals: Technical signal is BULLISH
        - check_vision_validated: Vision agent confirms setup

    SELL Factors:
        - check_extreme_greed: Fear & Greed > threshold
        - check_rsi_overbought: RSI > threshold
        - check_price_at_resistance: Price extended above SMA200
        - check_volume_exhaustion: Volume < 50% average
        - check_bearish_technicals: Technical signal is BEARISH
"""

from typing import Any, Dict

from config import get_config
from services.signal_factors import BuyFactor, FactorResult, SellFactor


def check_extreme_fear(sentiment_analysis: Dict[str, Any]) -> FactorResult:
    """
    Check if Fear & Greed indicates extreme fear.

    Extreme fear is a contrarian BUY signal - when the market is
    fearful, it may be oversold and due for a reversal.

    Args:
        sentiment_analysis: Output from Sentiment Agent containing fear_score

    Returns:
        FactorResult with triggered=True if fear_score < threshold
    """
    config = get_config()
    mf_config = config.multi_factor
    fear_score = sentiment_analysis.get("fear_score", 50)
    threshold = mf_config.extreme_fear_threshold

    triggered = fear_score < threshold

    return FactorResult(
        factor=BuyFactor.EXTREME_FEAR.value,
        triggered=triggered,
        value=float(fear_score),
        threshold=float(threshold),
        weight=1.5,  # Higher weight for primary factor
        reasoning=f"Fear score {fear_score} {'<' if triggered else '>='} {threshold}"
    )


def check_extreme_greed(sentiment_analysis: Dict[str, Any]) -> FactorResult:
    """
    Check if Fear & Greed indicates extreme greed.

    Extreme greed is a contrarian SELL signal - when the market is
    greedy, it may be overbought and due for a correction.

    Args:
        sentiment_analysis: Output from Sentiment Agent containing fear_score

    Returns:
        FactorResult with triggered=True if fear_score > threshold
    """
    config = get_config()
    mf_config = config.multi_factor
    fear_score = sentiment_analysis.get("fear_score", 50)
    threshold = mf_config.extreme_greed_threshold

    triggered = fear_score > threshold

    return FactorResult(
        factor=SellFactor.EXTREME_GREED.value,
        triggered=triggered,
        value=float(fear_score),
        threshold=float(threshold),
        weight=1.5,
        reasoning=f"Fear score {fear_score} {'>' if triggered else '<='} {threshold}"
    )


def check_rsi_oversold(technical_analysis: Dict[str, Any]) -> FactorResult:
    """
    Check if RSI indicates oversold condition.

    Oversold RSI (below threshold) suggests the asset may be
    due for a bounce and is a BUY factor.

    Args:
        technical_analysis: Output from Technical Agent containing rsi

    Returns:
        FactorResult with triggered=True if RSI < threshold
    """
    config = get_config()
    mf_config = config.multi_factor
    rsi = technical_analysis.get("rsi", 50)
    threshold = mf_config.rsi_oversold_threshold

    triggered = rsi < threshold

    return FactorResult(
        factor=BuyFactor.RSI_OVERSOLD.value,
        triggered=triggered,
        value=float(rsi),
        threshold=float(threshold),
        weight=1.0,
        reasoning=f"RSI {rsi:.1f} {'<' if triggered else '>='} {threshold}"
    )


def check_rsi_overbought(technical_analysis: Dict[str, Any]) -> FactorResult:
    """
    Check if RSI indicates overbought condition.

    Overbought RSI (above threshold) suggests the asset may be
    due for a correction and is a SELL factor.

    Args:
        technical_analysis: Output from Technical Agent containing rsi

    Returns:
        FactorResult with triggered=True if RSI > threshold
    """
    config = get_config()
    mf_config = config.multi_factor
    rsi = technical_analysis.get("rsi", 50)
    threshold = mf_config.rsi_overbought_threshold

    triggered = rsi > threshold

    return FactorResult(
        factor=SellFactor.RSI_OVERBOUGHT.value,
        triggered=triggered,
        value=float(rsi),
        threshold=float(threshold),
        weight=1.0,
        reasoning=f"RSI {rsi:.1f} {'>' if triggered else '<='} {threshold}"
    )


def check_price_at_support(
    technical_analysis: Dict[str, Any],
    current_price: float
) -> FactorResult:
    """
    Check if price is near key support level.

    Support levels considered:
    - Within X% of SMA200 (long-term support in uptrend)
    - Price slightly above the moving average is ideal

    Args:
        technical_analysis: Output from Technical Agent containing sma_200
        current_price: Current asset price

    Returns:
        FactorResult with triggered=True if price is within support zone
    """
    config = get_config()
    mf_config = config.multi_factor
    sma_200 = technical_analysis.get("sma_200", 0)
    proximity_pct = mf_config.support_proximity_pct

    if sma_200 <= 0 or current_price <= 0:
        return FactorResult(
            factor=BuyFactor.PRICE_AT_SUPPORT.value,
            triggered=False,
            value=0,
            threshold=proximity_pct,
            weight=1.0,
            reasoning="SMA200 or price not available"
        )

    # Check proximity to SMA200 (support in uptrend)
    distance_to_sma = ((current_price - sma_200) / sma_200) * 100

    # Price is at support if within proximity_pct above SMA200
    # (slightly above the moving average)
    triggered = 0 <= distance_to_sma <= proximity_pct

    return FactorResult(
        factor=BuyFactor.PRICE_AT_SUPPORT.value,
        triggered=triggered,
        value=distance_to_sma,
        threshold=proximity_pct,
        weight=1.0,
        reasoning=f"Price {distance_to_sma:+.1f}% from SMA200 (support zone: 0-{proximity_pct}%)"
    )


def check_price_at_resistance(
    technical_analysis: Dict[str, Any],
    current_price: float
) -> FactorResult:
    """
    Check if price is near key resistance level.

    For resistance, we look at how extended price is above
    the long-term average. Extended prices may be due for pullback.

    Args:
        technical_analysis: Output from Technical Agent containing sma_200
        current_price: Current asset price

    Returns:
        FactorResult with triggered=True if price is extended above SMA200
    """
    config = get_config()
    mf_config = config.multi_factor
    sma_200 = technical_analysis.get("sma_200", 0)
    proximity_pct = mf_config.resistance_proximity_pct

    if sma_200 <= 0 or current_price <= 0:
        return FactorResult(
            factor=SellFactor.PRICE_AT_RESISTANCE.value,
            triggered=False,
            value=0,
            threshold=proximity_pct,
            weight=1.0,
            reasoning="SMA200 or price not available"
        )

    # For resistance, look at how extended price is above average
    distance_to_sma = ((current_price - sma_200) / sma_200) * 100

    # Extended if more than 2x the proximity threshold above
    extended_threshold = proximity_pct * 2
    triggered = distance_to_sma > extended_threshold

    return FactorResult(
        factor=SellFactor.PRICE_AT_RESISTANCE.value,
        triggered=triggered,
        value=distance_to_sma,
        threshold=extended_threshold,
        weight=1.0,
        reasoning=f"Price {distance_to_sma:+.1f}% from SMA200 (extended: >{extended_threshold}%)"
    )


def check_volume_capitulation(technical_analysis: Dict[str, Any]) -> FactorResult:
    """
    Check for volume capitulation spike.

    Capitulation: Volume > 2x the 20-period average indicates
    panic selling and potential bottom formation.

    Args:
        technical_analysis: Output from Technical Agent containing volume_delta

    Returns:
        FactorResult with triggered=True if volume is significantly above average
    """
    config = get_config()
    mf_config = config.multi_factor
    volume_delta = technical_analysis.get("volume_delta", 0)  # Percentage above average
    threshold = (mf_config.volume_capitulation_mult - 1) * 100  # Convert to percentage

    # volume_delta is already percentage above average
    triggered = volume_delta >= threshold

    return FactorResult(
        factor=BuyFactor.VOLUME_CAPITULATION.value,
        triggered=triggered,
        value=float(volume_delta),
        threshold=threshold,
        weight=1.0,
        reasoning=f"Volume {volume_delta:+.0f}% vs avg (capitulation: >={threshold:.0f}%)"
    )


def check_volume_exhaustion(technical_analysis: Dict[str, Any]) -> FactorResult:
    """
    Check for volume exhaustion (declining volume at highs).

    Volume exhaustion at price highs suggests weakening momentum
    and potential reversal.

    Args:
        technical_analysis: Output from Technical Agent containing volume_delta

    Returns:
        FactorResult with triggered=True if volume is significantly below average
    """
    config = get_config()
    mf_config = config.multi_factor
    volume_delta = technical_analysis.get("volume_delta", 0)
    threshold = (mf_config.volume_exhaustion_mult - 1) * 100  # Negative percentage

    # Volume exhaustion if significantly below average
    triggered = volume_delta <= threshold

    return FactorResult(
        factor=SellFactor.VOLUME_EXHAUSTION.value,
        triggered=triggered,
        value=float(volume_delta),
        threshold=threshold,
        weight=0.75,  # Lower weight - supplementary factor
        reasoning=f"Volume {volume_delta:+.0f}% vs avg (exhaustion: <={threshold:.0f}%)"
    )


def check_bullish_technicals(technical_analysis: Dict[str, Any]) -> FactorResult:
    """
    Check if technical signal is bullish with sufficient strength.

    A bullish technical signal with high strength confirms
    the overall buy setup.

    Args:
        technical_analysis: Output from Technical Agent

    Returns:
        FactorResult with triggered=True if signal is BULLISH with strength >= 50
    """
    signal = technical_analysis.get("signal", "NEUTRAL")
    strength = technical_analysis.get("strength", 0)

    triggered = signal == "BULLISH" and strength >= 50

    return FactorResult(
        factor=BuyFactor.BULLISH_TECHNICALS.value,
        triggered=triggered,
        value=float(strength),
        threshold=50.0,
        weight=1.0,
        reasoning=f"Technical signal: {signal} (strength: {strength})"
    )


def check_bearish_technicals(technical_analysis: Dict[str, Any]) -> FactorResult:
    """
    Check if technical signal is bearish with sufficient strength.

    A bearish technical signal with high strength confirms
    the overall sell setup.

    Args:
        technical_analysis: Output from Technical Agent

    Returns:
        FactorResult with triggered=True if signal is BEARISH with strength >= 50
    """
    signal = technical_analysis.get("signal", "NEUTRAL")
    strength = technical_analysis.get("strength", 0)

    triggered = signal == "BEARISH" and strength >= 50

    return FactorResult(
        factor=SellFactor.BEARISH_TECHNICALS.value,
        triggered=triggered,
        value=float(strength),
        threshold=50.0,
        weight=1.0,
        reasoning=f"Technical signal: {signal} (strength: {strength})"
    )


def check_vision_validated(vision_analysis: Dict[str, Any]) -> FactorResult:
    """
    Check if vision agent validated the setup.

    Vision validation provides additional confirmation that
    the chart pattern supports the trade.

    Args:
        vision_analysis: Output from Vision Agent

    Returns:
        FactorResult with triggered=True if vision is valid with confidence >= 50
    """
    is_valid = vision_analysis.get("is_valid", False)
    confidence = vision_analysis.get("confidence_score", 0)

    triggered = is_valid and confidence >= 50

    return FactorResult(
        factor=BuyFactor.VISION_VALIDATED.value,
        triggered=triggered,
        value=float(confidence),
        threshold=50.0,
        weight=0.75,  # Supplementary confirmation
        reasoning=f"Vision valid: {is_valid} (confidence: {confidence})"
    )


def check_vision_bearish(vision_analysis: Dict[str, Any]) -> FactorResult:
    """
    Check if vision agent detected bearish patterns.

    Vision detecting bearish patterns (like head and shoulders,
    double top) with high confidence supports a sell decision.

    Args:
        vision_analysis: Output from Vision Agent

    Returns:
        FactorResult with triggered=True if bearish patterns detected
    """
    patterns = vision_analysis.get("patterns_detected", [])
    confidence = vision_analysis.get("confidence_score", 0)

    # Bearish patterns to look for
    bearish_patterns = [
        "head_and_shoulders",
        "head and shoulders",
        "double_top",
        "double top",
        "rising_wedge",
        "rising wedge",
        "bearish_divergence",
        "bearish divergence"
    ]

    # Check if any bearish pattern is detected
    has_bearish_pattern = any(
        pattern.lower() in [p.lower() for p in patterns]
        for pattern in bearish_patterns
    )

    triggered = has_bearish_pattern and confidence >= 50

    return FactorResult(
        factor=SellFactor.VISION_BEARISH.value,
        triggered=triggered,
        value=float(confidence),
        threshold=50.0,
        weight=0.75,  # Supplementary confirmation
        reasoning=f"Bearish patterns: {patterns} (confidence: {confidence})"
    )
