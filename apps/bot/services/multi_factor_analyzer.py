"""
Multi-Factor Analyzer for Trading Signal Confirmation.

Story 5.3: Multi-Factor Confirmation System

This module provides functions to analyze multiple trading factors
and determine if sufficient confluence exists for a BUY or SELL signal.

Factor Confluence Model:
    BUY Signal: Requires 3+ of 6 factors to pass threshold
    SELL Signal: Requires 2+ of 5 factors to pass threshold

    If neither threshold is met, the result is HOLD.

Confidence Calculation:
    Confidence = (Sum of triggered weights / Sum of all weights) * 100
"""

import logging
from typing import Any, Dict

from config import get_config
from services.factor_checkers import (
    check_bearish_technicals,
    check_bullish_technicals,
    check_extreme_fear,
    check_extreme_greed,
    check_price_at_resistance,
    check_price_at_support,
    check_rsi_overbought,
    check_rsi_oversold,
    check_vision_bearish,
    check_vision_validated,
    check_volume_capitulation,
    check_volume_exhaustion,
)
from services.signal_factors import MultiFactorAnalysis

logger = logging.getLogger(__name__)


def analyze_buy_factors(
    sentiment_analysis: Dict[str, Any],
    technical_analysis: Dict[str, Any],
    vision_analysis: Dict[str, Any],
    current_price: float
) -> MultiFactorAnalysis:
    """
    Analyze all BUY factors and determine if enough are met.

    Evaluates 6 factors for buy signal:
    1. EXTREME_FEAR: Fear & Greed < 25
    2. RSI_OVERSOLD: RSI < 30
    3. PRICE_AT_SUPPORT: Price within 3% of SMA200
    4. VOLUME_CAPITULATION: Volume > 2x average
    5. BULLISH_TECHNICALS: Technical signal bullish
    6. VISION_VALIDATED: Vision confirms setup

    Args:
        sentiment_analysis: Output from Sentiment Agent
        technical_analysis: Output from Technical Agent
        vision_analysis: Output from Vision Agent
        current_price: Current asset price

    Returns:
        MultiFactorAnalysis with detailed breakdown of all factors
    """
    config = get_config()
    factors_triggered = []
    factors_not_triggered = []

    # Check all buy factors
    all_factors = [
        check_extreme_fear(sentiment_analysis),
        check_rsi_oversold(technical_analysis),
        check_price_at_support(technical_analysis, current_price),
        check_volume_capitulation(technical_analysis),
        check_bullish_technicals(technical_analysis),
        check_vision_validated(vision_analysis),
    ]

    # Separate triggered vs not triggered
    for factor in all_factors:
        if factor.triggered:
            factors_triggered.append(factor)
        else:
            factors_not_triggered.append(factor)

    # Calculate metrics
    factors_met = len(factors_triggered)
    total_factors = len(all_factors)
    min_required = config.multi_factor.min_factors_buy

    # Calculate weighted score
    weighted_score = sum(f.weight for f in factors_triggered)
    max_possible_weight = sum(f.weight for f in all_factors)
    confidence = (weighted_score / max_possible_weight) * 100 if max_possible_weight > 0 else 0

    passes_threshold = factors_met >= min_required

    # Build reasoning
    triggered_names = [f.factor for f in factors_triggered]
    reasoning = (
        f"BUY factors: {factors_met}/{total_factors} met (min: {min_required}). "
        f"Triggered: {', '.join(triggered_names) or 'None'}. "
        f"{'PASSES' if passes_threshold else 'FAILS'} threshold."
    )

    logger.info(f"[MultiFactorAnalysis] {reasoning}")

    return MultiFactorAnalysis(
        signal_type="BUY" if passes_threshold else "HOLD",
        factors_triggered=factors_triggered,
        factors_not_triggered=factors_not_triggered,
        total_factors_checked=total_factors,
        factors_met=factors_met,
        weighted_score=weighted_score,
        min_factors_required=min_required,
        passes_threshold=passes_threshold,
        confidence=confidence,
        reasoning=reasoning
    )


def analyze_sell_factors(
    sentiment_analysis: Dict[str, Any],
    technical_analysis: Dict[str, Any],
    vision_analysis: Dict[str, Any],
    current_price: float
) -> MultiFactorAnalysis:
    """
    Analyze all SELL factors and determine if enough are met.

    Evaluates 5 factors for sell signal:
    1. EXTREME_GREED: Fear & Greed > 75
    2. RSI_OVERBOUGHT: RSI > 70
    3. PRICE_AT_RESISTANCE: Price extended above SMA200
    4. VOLUME_EXHAUSTION: Volume declining
    5. BEARISH_TECHNICALS: Technical signal bearish

    Args:
        sentiment_analysis: Output from Sentiment Agent
        technical_analysis: Output from Technical Agent
        vision_analysis: Output from Vision Agent
        current_price: Current asset price

    Returns:
        MultiFactorAnalysis with detailed breakdown of all factors
    """
    config = get_config()
    factors_triggered = []
    factors_not_triggered = []

    # Check all sell factors
    all_factors = [
        check_extreme_greed(sentiment_analysis),
        check_rsi_overbought(technical_analysis),
        check_price_at_resistance(technical_analysis, current_price),
        check_volume_exhaustion(technical_analysis),
        check_bearish_technicals(technical_analysis),
    ]

    for factor in all_factors:
        if factor.triggered:
            factors_triggered.append(factor)
        else:
            factors_not_triggered.append(factor)

    factors_met = len(factors_triggered)
    total_factors = len(all_factors)
    min_required = config.multi_factor.min_factors_sell

    weighted_score = sum(f.weight for f in factors_triggered)
    max_possible_weight = sum(f.weight for f in all_factors)
    confidence = (weighted_score / max_possible_weight) * 100 if max_possible_weight > 0 else 0

    passes_threshold = factors_met >= min_required

    triggered_names = [f.factor for f in factors_triggered]
    reasoning = (
        f"SELL factors: {factors_met}/{total_factors} met (min: {min_required}). "
        f"Triggered: {', '.join(triggered_names) or 'None'}. "
        f"{'PASSES' if passes_threshold else 'FAILS'} threshold."
    )

    logger.info(f"[MultiFactorAnalysis] {reasoning}")

    return MultiFactorAnalysis(
        signal_type="SELL" if passes_threshold else "HOLD",
        factors_triggered=factors_triggered,
        factors_not_triggered=factors_not_triggered,
        total_factors_checked=total_factors,
        factors_met=factors_met,
        weighted_score=weighted_score,
        min_factors_required=min_required,
        passes_threshold=passes_threshold,
        confidence=confidence,
        reasoning=reasoning
    )


def analyze_all_factors(
    sentiment_analysis: Dict[str, Any],
    technical_analysis: Dict[str, Any],
    vision_analysis: Dict[str, Any],
    current_price: float
) -> Dict[str, MultiFactorAnalysis]:
    """
    Analyze both BUY and SELL factors.

    Convenience function that runs both buy and sell analysis
    and returns the results for comparison.

    Args:
        sentiment_analysis: Output from Sentiment Agent
        technical_analysis: Output from Technical Agent
        vision_analysis: Output from Vision Agent
        current_price: Current asset price

    Returns:
        Dict with 'buy' and 'sell' MultiFactorAnalysis results
    """
    buy_analysis = analyze_buy_factors(
        sentiment_analysis,
        technical_analysis,
        vision_analysis,
        current_price
    )

    sell_analysis = analyze_sell_factors(
        sentiment_analysis,
        technical_analysis,
        vision_analysis,
        current_price
    )

    return {
        "buy": buy_analysis,
        "sell": sell_analysis
    }
