"""
Factor Checkers for Multi-Factor Confirmation System.

Story 5.3: Multi-Factor Confirmation
Story 5.7: Enhanced Technical Indicators

This module provides functions to check each signal factor
against technical analysis data. Each checker returns a
FactorResult indicating whether the factor was triggered.

Factor results are aggregated to determine overall signal
strength and confidence for trading decisions.
"""

from dataclasses import dataclass
from typing import Any, Dict, List

from services.signal_factors import BuyFactor, FactorWeight, SellFactor


@dataclass
class FactorResult:
    """
    Result of checking a single factor.

    Attributes:
        factor: Factor name (from BuyFactor or SellFactor)
        triggered: True if the factor condition is met
        value: Current value of the indicator
        threshold: Threshold for triggering the factor
        weight: Weight multiplier for this factor
        reasoning: Human-readable explanation
    """
    factor: str
    triggered: bool
    value: float
    threshold: float
    weight: float
    reasoning: str


# =============================================================================
# MACD Factor Checkers
# =============================================================================

def check_macd_bullish(technical_analysis: Dict[str, Any]) -> FactorResult:
    """
    Check if MACD shows bullish signal.

    Triggers on:
    - MACD bullish crossover
    - MACD above signal line with positive histogram

    Args:
        technical_analysis: Dict from Technical Agent with macd key

    Returns:
        FactorResult with triggered status
    """
    macd = technical_analysis.get("macd", {})
    signal = macd.get("signal", "NEUTRAL")
    histogram = macd.get("histogram", 0)
    bullish_cross = macd.get("bullish_cross", False)

    triggered = signal in ["STRONG_BULLISH", "BULLISH"] or bullish_cross

    reasoning = f"MACD signal: {signal}"
    if bullish_cross:
        reasoning += " (bullish crossover detected)"

    return FactorResult(
        factor=BuyFactor.MACD_BULLISH.value,
        triggered=triggered,
        value=histogram,
        threshold=0,
        weight=FactorWeight.MACD.value,
        reasoning=reasoning
    )


def check_macd_bearish(technical_analysis: Dict[str, Any]) -> FactorResult:
    """
    Check if MACD shows bearish signal.

    Triggers on:
    - MACD bearish crossover
    - MACD below signal line with negative histogram

    Args:
        technical_analysis: Dict from Technical Agent with macd key

    Returns:
        FactorResult with triggered status
    """
    macd = technical_analysis.get("macd", {})
    signal = macd.get("signal", "NEUTRAL")
    histogram = macd.get("histogram", 0)
    bearish_cross = macd.get("bearish_cross", False)

    triggered = signal in ["STRONG_BEARISH", "BEARISH"] or bearish_cross

    reasoning = f"MACD signal: {signal}"
    if bearish_cross:
        reasoning += " (bearish crossover detected)"

    return FactorResult(
        factor=SellFactor.MACD_BEARISH.value,
        triggered=triggered,
        value=histogram,
        threshold=0,
        weight=FactorWeight.MACD.value,
        reasoning=reasoning
    )


# =============================================================================
# Bollinger Bands Factor Checkers
# =============================================================================

def check_bollinger_oversold(technical_analysis: Dict[str, Any]) -> FactorResult:
    """
    Check if price is at/below lower Bollinger Band (oversold).

    Triggers when %B <= 0.20 (price at lower band region).
    Strong signal when %B <= 0.05.

    Args:
        technical_analysis: Dict from Technical Agent with bollinger key

    Returns:
        FactorResult with triggered status
    """
    bollinger = technical_analysis.get("bollinger", {})
    percent_b = bollinger.get("percent_b", 0.5)
    signal = bollinger.get("signal", "NEUTRAL")

    # Trigger if price is in lower band region
    triggered = percent_b <= 0.20 or signal in ["STRONG_BULLISH", "BULLISH"]

    return FactorResult(
        factor=BuyFactor.BOLLINGER_OVERSOLD.value,
        triggered=triggered,
        value=percent_b,
        threshold=0.20,
        weight=FactorWeight.BOLLINGER.value,
        reasoning=f"Bollinger %B: {percent_b:.2f} ({'oversold' if triggered else 'normal'})"
    )


def check_bollinger_overbought(technical_analysis: Dict[str, Any]) -> FactorResult:
    """
    Check if price is at/above upper Bollinger Band (overbought).

    Triggers when %B >= 0.80 (price at upper band region).
    Strong signal when %B >= 0.95.

    Args:
        technical_analysis: Dict from Technical Agent with bollinger key

    Returns:
        FactorResult with triggered status
    """
    bollinger = technical_analysis.get("bollinger", {})
    percent_b = bollinger.get("percent_b", 0.5)
    signal = bollinger.get("signal", "NEUTRAL")

    # Trigger if price is in upper band region
    triggered = percent_b >= 0.80 or signal in ["STRONG_BEARISH", "BEARISH"]

    return FactorResult(
        factor=SellFactor.BOLLINGER_OVERBOUGHT.value,
        triggered=triggered,
        value=percent_b,
        threshold=0.80,
        weight=FactorWeight.BOLLINGER.value,
        reasoning=f"Bollinger %B: {percent_b:.2f} ({'overbought' if triggered else 'normal'})"
    )


# =============================================================================
# OBV Factor Checkers
# =============================================================================

def check_obv_accumulation(technical_analysis: Dict[str, Any]) -> FactorResult:
    """
    Check if OBV shows accumulation (bullish).

    Triggers on:
    - Bullish divergence (price down, OBV up)
    - OBV rising above its SMA

    Args:
        technical_analysis: Dict from Technical Agent with obv key

    Returns:
        FactorResult with triggered status
    """
    obv = technical_analysis.get("obv", {})
    signal = obv.get("signal", "NEUTRAL")
    bullish_divergence = obv.get("bullish_divergence", False)

    triggered = bullish_divergence or signal in ["STRONG_BULLISH", "BULLISH"]

    reasoning = f"OBV signal: {signal}"
    if bullish_divergence:
        reasoning += " (BULLISH DIVERGENCE - strong accumulation)"

    return FactorResult(
        factor=BuyFactor.OBV_ACCUMULATION.value,
        triggered=triggered,
        value=1.0 if triggered else 0.0,
        threshold=0.5,
        weight=FactorWeight.OBV.value,
        reasoning=reasoning
    )


def check_obv_distribution(technical_analysis: Dict[str, Any]) -> FactorResult:
    """
    Check if OBV shows distribution (bearish).

    Triggers on:
    - Bearish divergence (price up, OBV down)
    - OBV falling below its SMA

    Args:
        technical_analysis: Dict from Technical Agent with obv key

    Returns:
        FactorResult with triggered status
    """
    obv = technical_analysis.get("obv", {})
    signal = obv.get("signal", "NEUTRAL")
    bearish_divergence = obv.get("bearish_divergence", False)

    triggered = bearish_divergence or signal in ["STRONG_BEARISH", "BEARISH"]

    reasoning = f"OBV signal: {signal}"
    if bearish_divergence:
        reasoning += " (BEARISH DIVERGENCE - distribution warning)"

    return FactorResult(
        factor=SellFactor.OBV_DISTRIBUTION.value,
        triggered=triggered,
        value=1.0 if triggered else 0.0,
        threshold=0.5,
        weight=FactorWeight.OBV.value,
        reasoning=reasoning
    )


# =============================================================================
# ADX Factor Checkers - CRITICAL FOR CONTRARIAN
# =============================================================================

def check_adx_weak_trend(technical_analysis: Dict[str, Any]) -> FactorResult:
    """
    Check if ADX indicates weak trend (good for contrarian).

    CRITICAL: This is the most important factor for contrarian strategy.
    - ADX < 20: Weak trend - IDEAL for contrarian
    - ADX 20-30: Moderate - acceptable
    - ADX > 30: AVOID contrarian trades

    Triggers when ADX < 30 (safe_for_contrarian = True).

    Args:
        technical_analysis: Dict from Technical Agent with adx key

    Returns:
        FactorResult with triggered status
    """
    adx = technical_analysis.get("adx", {})
    adx_value = adx.get("value", 50)
    safe = adx.get("safe_for_contrarian", False)

    triggered = safe

    if adx_value < 20:
        reasoning = f"ADX: {adx_value:.1f} - IDEAL for contrarian (weak trend)"
    elif adx_value < 30:
        reasoning = f"ADX: {adx_value:.1f} - acceptable for contrarian"
    else:
        reasoning = f"ADX: {adx_value:.1f} - AVOID contrarian (strong trend)"

    return FactorResult(
        factor=BuyFactor.ADX_WEAK_TREND.value,
        triggered=triggered,
        value=adx_value,
        threshold=30,  # Below 30 is safe
        weight=FactorWeight.ADX.value,  # Higher weight - important for contrarian
        reasoning=reasoning
    )


def check_adx_strong_trend(technical_analysis: Dict[str, Any]) -> FactorResult:
    """
    Check if ADX indicates strong trend (WARNING for contrarian).

    CRITICAL: Strong trends mean contrarian trades are risky.
    - ADX > 40: Strong trend - AVOID contrarian
    - ADX > 60: Very strong - DO NOT trade contrarian

    Triggers when ADX >= 30 (is_trending = True).

    Args:
        technical_analysis: Dict from Technical Agent with adx key

    Returns:
        FactorResult with triggered status
    """
    adx = technical_analysis.get("adx", {})
    adx_value = adx.get("value", 50)
    is_trending = adx.get("is_trending", False)
    trend_direction = adx.get("trend_direction", "unknown")

    # Trigger warning when trend is strong
    triggered = is_trending or adx_value >= 30

    if adx_value >= 60:
        reasoning = f"ADX: {adx_value:.1f} - VERY STRONG {trend_direction} trend - DO NOT trade contrarian"
    elif adx_value >= 40:
        reasoning = f"ADX: {adx_value:.1f} - STRONG {trend_direction} trend - AVOID contrarian"
    elif adx_value >= 30:
        reasoning = f"ADX: {adx_value:.1f} - developing {trend_direction} trend - use caution"
    else:
        reasoning = f"ADX: {adx_value:.1f} - no strong trend (safe for contrarian)"

    return FactorResult(
        factor=SellFactor.ADX_STRONG_TREND.value,
        triggered=triggered,
        value=adx_value,
        threshold=30,  # Above 30 is trending
        weight=FactorWeight.ADX.value,
        reasoning=reasoning
    )


# =============================================================================
# VWAP Factor Checkers
# =============================================================================

def check_vwap_below(technical_analysis: Dict[str, Any]) -> FactorResult:
    """
    Check if price is below VWAP (potential support).

    VWAP is used by institutions as fair value benchmark.
    Price below VWAP may indicate value opportunity.

    Triggers when distance_pct <= -1% (price below VWAP).

    Args:
        technical_analysis: Dict from Technical Agent with vwap key

    Returns:
        FactorResult with triggered status
    """
    vwap = technical_analysis.get("vwap", {})
    distance_pct = vwap.get("distance_pct", 0)
    position = vwap.get("position", "neutral")

    triggered = distance_pct <= -1 or position == "below"

    return FactorResult(
        factor=BuyFactor.VWAP_BELOW.value,
        triggered=triggered,
        value=distance_pct,
        threshold=-1.0,
        weight=FactorWeight.VWAP.value,
        reasoning=f"Price {abs(distance_pct):.1f}% {'below' if distance_pct < 0 else 'above'} VWAP"
    )


def check_vwap_above(technical_analysis: Dict[str, Any]) -> FactorResult:
    """
    Check if price is above VWAP (potential resistance).

    VWAP is used by institutions as fair value benchmark.
    Price above VWAP may indicate overextension.

    Triggers when distance_pct >= 1% (price above VWAP).

    Args:
        technical_analysis: Dict from Technical Agent with vwap key

    Returns:
        FactorResult with triggered status
    """
    vwap = technical_analysis.get("vwap", {})
    distance_pct = vwap.get("distance_pct", 0)
    position = vwap.get("position", "neutral")

    triggered = distance_pct >= 1 or position == "above"

    return FactorResult(
        factor=SellFactor.VWAP_ABOVE.value,
        triggered=triggered,
        value=distance_pct,
        threshold=1.0,
        weight=FactorWeight.VWAP.value,
        reasoning=f"Price {abs(distance_pct):.1f}% {'above' if distance_pct > 0 else 'below'} VWAP"
    )


# =============================================================================
# Aggregation Functions
# =============================================================================

def check_all_buy_factors(technical_analysis: Dict[str, Any]) -> List[FactorResult]:
    """
    Check all buy factors from enhanced indicators.

    Returns list of FactorResults for each buy factor check.
    Only includes factors with data in technical_analysis.

    Args:
        technical_analysis: Dict from Technical Agent

    Returns:
        List of FactorResult for each checked factor
    """
    results = []

    # MACD
    if "macd" in technical_analysis:
        results.append(check_macd_bullish(technical_analysis))

    # Bollinger Bands
    if "bollinger" in technical_analysis:
        results.append(check_bollinger_oversold(technical_analysis))

    # OBV
    if "obv" in technical_analysis:
        results.append(check_obv_accumulation(technical_analysis))

    # ADX - Critical for contrarian
    if "adx" in technical_analysis:
        results.append(check_adx_weak_trend(technical_analysis))

    # VWAP
    if "vwap" in technical_analysis:
        results.append(check_vwap_below(technical_analysis))

    return results


def check_all_sell_factors(technical_analysis: Dict[str, Any]) -> List[FactorResult]:
    """
    Check all sell factors from enhanced indicators.

    Returns list of FactorResults for each sell factor check.
    Only includes factors with data in technical_analysis.

    Args:
        technical_analysis: Dict from Technical Agent

    Returns:
        List of FactorResult for each checked factor
    """
    results = []

    # MACD
    if "macd" in technical_analysis:
        results.append(check_macd_bearish(technical_analysis))

    # Bollinger Bands
    if "bollinger" in technical_analysis:
        results.append(check_bollinger_overbought(technical_analysis))

    # OBV
    if "obv" in technical_analysis:
        results.append(check_obv_distribution(technical_analysis))

    # ADX - Strong trend warning
    if "adx" in technical_analysis:
        results.append(check_adx_strong_trend(technical_analysis))

    # VWAP
    if "vwap" in technical_analysis:
        results.append(check_vwap_above(technical_analysis))

    return results


def calculate_factor_score(results: List[FactorResult]) -> float:
    """
    Calculate weighted score from factor results.

    Sums the weighted triggers:
    score = sum(weight for each triggered factor)

    Args:
        results: List of FactorResult from factor checks

    Returns:
        Total weighted score (0 if no triggered factors)
    """
    return sum(r.weight for r in results if r.triggered)


def count_triggered_factors(results: List[FactorResult]) -> int:
    """
    Count number of triggered factors.

    Args:
        results: List of FactorResult from factor checks

    Returns:
        Number of triggered factors
    """
    return sum(1 for r in results if r.triggered)
