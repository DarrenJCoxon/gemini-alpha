"""
Signal Factors for Multi-Factor Confirmation System.

Story 5.3: Multi-Factor Confirmation
Story 5.7: Enhanced Technical Indicators

This module defines the factor enums for buy and sell signals.
Each factor represents a condition that contributes to the
overall trading decision confidence.

Factors are checked by factor_checkers.py and aggregated
in the decision logic to determine trade entry/exit.
"""

from enum import Enum


class BuyFactor(str, Enum):
    """
    Buy signal factors for multi-factor confirmation.

    Each factor represents a bullish condition that supports
    a potential buy decision. Multiple triggered factors
    increase overall confidence.

    Existing factors (Story 5.3):
    - RSI_OVERSOLD: RSI below 30 (or 40 for moderate)
    - PRICE_BELOW_SMA200: Price below 200 SMA (potential support)
    - FEAR_HIGH: Fear/Greed index showing high fear (contrarian buy)
    - VOLUME_SPIKE: Unusual volume indicating accumulation

    Enhanced indicator factors (Story 5.7):
    - MACD_BULLISH: MACD bullish crossover or above signal
    - BOLLINGER_OVERSOLD: Price at/below lower Bollinger Band
    - OBV_ACCUMULATION: OBV showing accumulation (bullish divergence)
    - ADX_WEAK_TREND: Weak trend (ADX < 30) - good for contrarian
    - VWAP_BELOW: Price below VWAP (potential support)
    """
    # Existing factors
    RSI_OVERSOLD = "RSI_OVERSOLD"
    PRICE_BELOW_SMA200 = "PRICE_BELOW_SMA200"
    FEAR_HIGH = "FEAR_HIGH"
    VOLUME_SPIKE = "VOLUME_SPIKE"
    GOLDEN_CROSS = "GOLDEN_CROSS"

    # Enhanced indicator factors (Story 5.7)
    MACD_BULLISH = "MACD_BULLISH"
    BOLLINGER_OVERSOLD = "BOLLINGER_OVERSOLD"
    OBV_ACCUMULATION = "OBV_ACCUMULATION"
    ADX_WEAK_TREND = "ADX_WEAK_TREND"
    VWAP_BELOW = "VWAP_BELOW"


class SellFactor(str, Enum):
    """
    Sell signal factors for multi-factor confirmation.

    Each factor represents a bearish condition that supports
    a potential sell decision. Multiple triggered factors
    increase overall confidence.

    Existing factors (Story 5.3):
    - RSI_OVERBOUGHT: RSI above 70 (or 60 for moderate)
    - PRICE_ABOVE_SMA200: Price above 200 SMA (potential resistance)
    - GREED_HIGH: Fear/Greed index showing high greed (contrarian sell)
    - VOLUME_DECLINE: Declining volume on rally (bearish)

    Enhanced indicator factors (Story 5.7):
    - MACD_BEARISH: MACD bearish crossover or below signal
    - BOLLINGER_OVERBOUGHT: Price at/above upper Bollinger Band
    - OBV_DISTRIBUTION: OBV showing distribution (bearish divergence)
    - ADX_STRONG_TREND: Strong trend (ADX > 30) - avoid contrarian
    - VWAP_ABOVE: Price above VWAP (potential resistance)
    """
    # Existing factors
    RSI_OVERBOUGHT = "RSI_OVERBOUGHT"
    PRICE_ABOVE_SMA200 = "PRICE_ABOVE_SMA200"
    GREED_HIGH = "GREED_HIGH"
    VOLUME_DECLINE = "VOLUME_DECLINE"
    DEATH_CROSS = "DEATH_CROSS"

    # Enhanced indicator factors (Story 5.7)
    MACD_BEARISH = "MACD_BEARISH"
    BOLLINGER_OVERBOUGHT = "BOLLINGER_OVERBOUGHT"
    OBV_DISTRIBUTION = "OBV_DISTRIBUTION"
    ADX_STRONG_TREND = "ADX_STRONG_TREND"
    VWAP_ABOVE = "VWAP_ABOVE"


class FactorWeight(float, Enum):
    """
    Weight multipliers for different factor categories.

    Higher weights indicate more important factors.
    ADX_WEAK_TREND has highest weight because it's
    CRITICAL for contrarian strategy success.
    """
    STANDARD = 1.0
    IMPORTANT = 1.25
    CRITICAL = 1.5

    # Factor-specific weights
    RSI = 1.0
    SMA = 1.0
    FEAR_GREED = 1.0
    VOLUME = 0.8
    MACD = 1.0
    BOLLINGER = 1.0
    OBV = 1.0
    ADX = 1.25  # Important for contrarian
    VWAP = 0.9
