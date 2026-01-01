"""
Signal factors for multi-factor confirmation system (Story 5.3 & 5.6).

This module defines the buy and sell factors used in the multi-factor
confirmation system, including on-chain factors from Story 5.6.

Buy Factors (Bullish):
- Technical indicators
- Sentiment signals
- On-chain accumulation
- Funding rate squeeze risk

Sell Factors (Bearish):
- Technical indicators
- Sentiment signals
- On-chain distribution
- Funding rate squeeze risk
"""

from enum import Enum
from dataclasses import dataclass
from typing import Optional


class BuyFactor(str, Enum):
    """
    Bullish factors that indicate buying opportunity.

    Each factor contributes to the multi-factor confirmation score.
    """
    # Technical Factors
    RSI_OVERSOLD = "RSI_OVERSOLD"                    # RSI < 30
    MACD_BULLISH_CROSS = "MACD_BULLISH_CROSS"       # MACD crosses above signal
    PRICE_ABOVE_SMA = "PRICE_ABOVE_SMA"             # Price above 50-day SMA
    SUPPORT_BOUNCE = "SUPPORT_BOUNCE"               # Price bouncing off support

    # Sentiment Factors
    SENTIMENT_BULLISH = "SENTIMENT_BULLISH"          # Positive sentiment score
    FEAR_GREED_EXTREME_FEAR = "FEAR_GREED_EXTREME_FEAR"  # Extreme fear = buy opportunity

    # On-Chain Factors (Story 5.6)
    ONCHAIN_ACCUMULATION = "ONCHAIN_ACCUMULATION"   # Exchange outflows, whale buying
    FUNDING_SHORT_SQUEEZE = "FUNDING_SHORT_SQUEEZE"  # Negative funding = squeeze potential
    STABLECOIN_DRY_POWDER = "STABLECOIN_DRY_POWDER"  # High stablecoin reserves


class SellFactor(str, Enum):
    """
    Bearish factors that indicate selling opportunity.

    Each factor contributes to the multi-factor confirmation score.
    """
    # Technical Factors
    RSI_OVERBOUGHT = "RSI_OVERBOUGHT"               # RSI > 70
    MACD_BEARISH_CROSS = "MACD_BEARISH_CROSS"       # MACD crosses below signal
    PRICE_BELOW_SMA = "PRICE_BELOW_SMA"             # Price below 50-day SMA
    RESISTANCE_REJECTION = "RESISTANCE_REJECTION"   # Price rejected at resistance

    # Sentiment Factors
    SENTIMENT_BEARISH = "SENTIMENT_BEARISH"         # Negative sentiment score
    FEAR_GREED_EXTREME_GREED = "FEAR_GREED_EXTREME_GREED"  # Extreme greed = sell signal

    # On-Chain Factors (Story 5.6)
    ONCHAIN_DISTRIBUTION = "ONCHAIN_DISTRIBUTION"   # Exchange inflows, whale selling
    FUNDING_LONG_SQUEEZE = "FUNDING_LONG_SQUEEZE"   # Positive funding = squeeze potential


@dataclass
class FactorResult:
    """
    Result of checking a single factor.

    Contains the factor type, whether it was triggered, and the
    actual values that were checked.
    """
    factor: str
    triggered: bool
    value: float
    threshold: float
    weight: float = 1.0
    reasoning: str = ""


@dataclass
class MultiFactorResult:
    """
    Aggregated result from multi-factor analysis.

    Contains the overall signal direction, confidence, and
    individual factor results.
    """
    signal: str  # "BUY", "SELL", "HOLD"
    buy_score: float
    sell_score: float
    confidence: float
    buy_factors: list[FactorResult]
    sell_factors: list[FactorResult]
    reasoning: str


# Factor weights for scoring
FACTOR_WEIGHTS = {
    # Buy factors
    BuyFactor.RSI_OVERSOLD.value: 1.0,
    BuyFactor.MACD_BULLISH_CROSS.value: 1.0,
    BuyFactor.PRICE_ABOVE_SMA.value: 0.75,
    BuyFactor.SUPPORT_BOUNCE.value: 1.0,
    BuyFactor.SENTIMENT_BULLISH.value: 0.75,
    BuyFactor.FEAR_GREED_EXTREME_FEAR.value: 1.0,
    BuyFactor.ONCHAIN_ACCUMULATION.value: 1.5,  # On-chain weighted higher
    BuyFactor.FUNDING_SHORT_SQUEEZE.value: 0.75,
    BuyFactor.STABLECOIN_DRY_POWDER.value: 0.5,

    # Sell factors
    SellFactor.RSI_OVERBOUGHT.value: 1.0,
    SellFactor.MACD_BEARISH_CROSS.value: 1.0,
    SellFactor.PRICE_BELOW_SMA.value: 0.75,
    SellFactor.RESISTANCE_REJECTION.value: 1.0,
    SellFactor.SENTIMENT_BEARISH.value: 0.75,
    SellFactor.FEAR_GREED_EXTREME_GREED.value: 1.0,
    SellFactor.ONCHAIN_DISTRIBUTION.value: 1.5,  # On-chain weighted higher
    SellFactor.FUNDING_LONG_SQUEEZE.value: 0.75,
}


def get_factor_weight(factor: str) -> float:
    """
    Get the weight for a factor.

    Args:
        factor: Factor name

    Returns:
        Weight multiplier (default 1.0)
    """
    return FACTOR_WEIGHTS.get(factor, 1.0)


def calculate_multi_factor_score(
    buy_factors: list[FactorResult],
    sell_factors: list[FactorResult]
) -> MultiFactorResult:
    """
    Calculate the multi-factor confirmation score.

    Aggregates buy and sell factors to determine overall signal.

    Args:
        buy_factors: List of triggered buy factors
        sell_factors: List of triggered sell factors

    Returns:
        MultiFactorResult with overall signal and scores
    """
    # Calculate weighted scores
    buy_score = sum(
        f.weight if f.triggered else 0
        for f in buy_factors
    )
    sell_score = sum(
        f.weight if f.triggered else 0
        for f in sell_factors
    )

    # Determine signal based on net score
    net_score = buy_score - sell_score

    if net_score >= 2.0:
        signal = "BUY"
    elif net_score <= -2.0:
        signal = "SELL"
    else:
        signal = "HOLD"

    # Calculate confidence
    total_possible = len(buy_factors) + len(sell_factors)
    if total_possible > 0:
        triggered_count = sum(
            1 for f in buy_factors + sell_factors if f.triggered
        )
        base_confidence = (triggered_count / total_possible) * 100
        # Boost confidence for stronger signals
        confidence = min(base_confidence * (1 + abs(net_score) / 8), 100)
    else:
        confidence = 0.0

    # Build reasoning
    triggered_buys = [f for f in buy_factors if f.triggered]
    triggered_sells = [f for f in sell_factors if f.triggered]

    buy_reasons = [f"{f.factor}: {f.reasoning}" for f in triggered_buys]
    sell_reasons = [f"{f.factor}: {f.reasoning}" for f in triggered_sells]

    reasoning = (
        f"Multi-factor: {signal} signal with {confidence:.1f}% confidence. "
        f"Buy score: {buy_score:.2f}, Sell score: {sell_score:.2f}. "
        f"Buy factors: {', '.join(buy_reasons) if buy_reasons else 'None'}. "
        f"Sell factors: {', '.join(sell_reasons) if sell_reasons else 'None'}."
    )

    return MultiFactorResult(
        signal=signal,
        buy_score=buy_score,
        sell_score=sell_score,
        confidence=confidence,
        buy_factors=buy_factors,
        sell_factors=sell_factors,
        reasoning=reasoning
    )


# Export all
__all__ = [
    "BuyFactor",
    "SellFactor",
    "FactorResult",
    "MultiFactorResult",
    "FACTOR_WEIGHTS",
    "get_factor_weight",
    "calculate_multi_factor_score",
]
