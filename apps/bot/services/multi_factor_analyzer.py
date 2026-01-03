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
    # Story 5.11: NEW Trend-Confirmed Pullback factors
    check_trend_uptrend,
    check_rsi_pullback_zone,
    check_structure_intact,
    check_price_at_ema,
    check_fear_confirmation,
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

    Story 5.11: REVISED to use TREND-CONFIRMED PULLBACK strategy.

    PRIMARY FACTORS (Trend Pullback - professional approach):
    1. TREND_UPTREND: Confirmed uptrend (ADX > 20, bullish signal)
    2. RSI_PULLBACK_ZONE: RSI 40-55 (prime entry zone)
    3. STRUCTURE_INTACT: Higher Highs/Lows holding
    4. PRICE_AT_EMA: Near SMA50 support
    5. BULLISH_TECHNICALS: Technical signal bullish
    6. FEAR_CONFIRMATION: Fear < 50 (not extreme, just confirmation)

    Requires 2+ factors to trigger BUY (lowered from 3 for responsiveness).

    Args:
        sentiment_analysis: Output from Sentiment Agent
        technical_analysis: Output from Technical Agent
        vision_analysis: Output from Vision Agent (IGNORED - not adding value)
        current_price: Current asset price

    Returns:
        MultiFactorAnalysis with detailed breakdown of all factors
    """
    config = get_config()
    factors_triggered = []
    factors_not_triggered = []

    # Story 5.11: NEW Trend-Confirmed Pullback factors
    # Vision removed - was blocking valid trades with 0 confidence
    all_factors = [
        check_trend_uptrend(technical_analysis),
        check_rsi_pullback_zone(technical_analysis),
        check_structure_intact(technical_analysis),
        check_price_at_ema(technical_analysis, current_price),
        check_bullish_technicals(technical_analysis),
        check_fear_confirmation(sentiment_analysis),
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

    Story 5.11: REVISED for trend-following exits.

    SELL FACTORS:
    1. EXTREME_GREED: Fear & Greed > 75 (take profits in euphoria)
    2. RSI_OVERBOUGHT: RSI > 70 (extended, likely to pull back)
    3. PRICE_AT_RESISTANCE: Price extended above SMA200
    4. BEARISH_TECHNICALS: Technical signal bearish

    Note: VOLUME_EXHAUSTION removed - was too sensitive and triggering constantly.

    Args:
        sentiment_analysis: Output from Sentiment Agent
        technical_analysis: Output from Technical Agent
        vision_analysis: Output from Vision Agent (IGNORED)
        current_price: Current asset price

    Returns:
        MultiFactorAnalysis with detailed breakdown of all factors
    """
    config = get_config()
    factors_triggered = []
    factors_not_triggered = []

    # Story 5.11: Simplified sell factors
    # VOLUME_EXHAUSTION removed - too sensitive, was triggering on every session
    all_factors = [
        check_extreme_greed(sentiment_analysis),
        check_rsi_overbought(technical_analysis),
        check_price_at_resistance(technical_analysis, current_price),
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
