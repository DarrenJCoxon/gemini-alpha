"""
Signal Factor Types and Enumerations for Multi-Factor Confirmation System.

Story 5.3: Multi-Factor Confirmation System

This module defines the factor types, results, and analysis structures
for the multi-factor confirmation system that requires multiple confirming
signals before entering trades.

Factor Confluence Model:
    BUY Signal Requirements (3+ of 6):
    - EXTREME_FEAR: Fear & Greed < 25
    - RSI_OVERSOLD: RSI < 30
    - PRICE_AT_SUPPORT: Within 3% of SMA200
    - VOLUME_CAPITULATION: Volume > 2x average
    - BULLISH_TECHNICALS: Technical signal bullish
    - VISION_VALIDATED: Vision agent confirms

    SELL Signal Requirements (2+ of 5):
    - EXTREME_GREED: Fear & Greed > 75
    - RSI_OVERBOUGHT: RSI > 70
    - PRICE_AT_RESISTANCE: Extended > 6% above average
    - VOLUME_EXHAUSTION: Volume < 50% of average
    - BEARISH_TECHNICALS: Technical signal bearish
"""

from dataclasses import dataclass
from enum import Enum
from typing import List


class BuyFactor(str, Enum):
    """
    Enumeration of factors that can trigger a BUY signal.

    Each factor represents a market condition that, when combined
    with other factors, suggests a buying opportunity (contrarian strategy).
    """
    EXTREME_FEAR = "EXTREME_FEAR"           # Fear & Greed < 25
    RSI_OVERSOLD = "RSI_OVERSOLD"           # RSI < 30
    PRICE_AT_SUPPORT = "PRICE_AT_SUPPORT"   # Price near support level
    VOLUME_CAPITULATION = "VOLUME_CAPITULATION"  # Volume spike > 2x avg
    BULLISH_TECHNICALS = "BULLISH_TECHNICALS"    # Technical signal bullish
    VISION_VALIDATED = "VISION_VALIDATED"        # Vision agent confirms


class SellFactor(str, Enum):
    """
    Enumeration of factors that can trigger a SELL signal.

    Each factor represents a market condition that, when combined
    with other factors, suggests a selling opportunity.
    """
    EXTREME_GREED = "EXTREME_GREED"         # Fear & Greed > 75
    RSI_OVERBOUGHT = "RSI_OVERBOUGHT"       # RSI > 70
    PRICE_AT_RESISTANCE = "PRICE_AT_RESISTANCE"  # Price near resistance
    VOLUME_EXHAUSTION = "VOLUME_EXHAUSTION"      # Volume declining
    BEARISH_TECHNICALS = "BEARISH_TECHNICALS"    # Technical signal bearish
    VISION_BEARISH = "VISION_BEARISH"            # Vision detects reversal


@dataclass
class FactorResult:
    """
    Result of evaluating a single factor.

    Contains the evaluation result, actual value, threshold used,
    weight for scoring, and human-readable reasoning.

    Attributes:
        factor: The factor name (from BuyFactor or SellFactor enum)
        triggered: Whether the factor condition was met
        value: The actual value that was evaluated
        threshold: The threshold value used for comparison
        weight: Factor importance (1.0 = normal, 1.5 = primary, 0.75 = supplementary)
        reasoning: Human-readable explanation of the evaluation
    """
    factor: str
    triggered: bool
    value: float
    threshold: float
    weight: float  # Factor importance (1.0 = normal, 2.0 = double weight)
    reasoning: str


@dataclass
class MultiFactorAnalysis:
    """
    Complete multi-factor analysis result.

    Contains the aggregated results from evaluating all factors,
    including which factors were triggered, the overall signal,
    and confidence metrics.

    Attributes:
        signal_type: The resulting signal - "BUY", "SELL", or "HOLD"
        factors_triggered: List of FactorResults that were triggered
        factors_not_triggered: List of FactorResults that were not triggered
        total_factors_checked: Total number of factors evaluated
        factors_met: Count of factors that were triggered
        weighted_score: Sum of weights for triggered factors
        min_factors_required: Minimum factors needed to pass threshold
        passes_threshold: Whether the minimum factor count was met
        confidence: Confidence percentage based on weighted scoring
        reasoning: Human-readable summary of the analysis
    """
    signal_type: str  # "BUY", "SELL", "HOLD"
    factors_triggered: List[FactorResult]
    factors_not_triggered: List[FactorResult]
    total_factors_checked: int
    factors_met: int
    weighted_score: float
    min_factors_required: int
    passes_threshold: bool
    confidence: float
    reasoning: str
