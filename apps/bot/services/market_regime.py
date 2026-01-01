"""
Market Regime Detection Module.

Story 5.1: Market Regime Filter

This module implements market regime detection using 200 DMA and 50/200 DMA
crossover to identify BULL, BEAR, and CHOP market conditions.

Market Regime Filter acts as a "pre-filter" before the Council makes trading
decisions, preventing catching falling knives in downtrends.

Classification Logic:
    BULL: Price > 200 DMA AND Golden Cross (SMA50 > SMA200)
    BEAR: Price < 200 DMA AND Death Cross (SMA50 < SMA200)
    CHOP: Mixed signals (price and crossover disagree)
"""

from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple
import logging

import pandas as pd
import pandas_ta as ta

logger = logging.getLogger(__name__)


class MarketRegime(str, Enum):
    """
    Market regime classification.

    BULL: Uptrend - normal contrarian operation, buy on fear
    BEAR: Downtrend - reduced position sizes, stricter signals
    CHOP: Sideways - reduce activity, wait for clarity
    """
    BULL = "BULL"
    BEAR = "BEAR"
    CHOP = "CHOP"


@dataclass
class RegimeAnalysis:
    """
    Complete regime analysis result.

    Contains all information about the current market regime including
    technical indicators and reasoning for the classification.
    """
    regime: MarketRegime
    price_vs_200dma: float      # Percentage above/below 200 DMA
    sma_50: float
    sma_200: float
    golden_cross: bool          # SMA50 > SMA200
    death_cross: bool           # SMA50 < SMA200
    trend_strength: float       # 0-100, how strong is the trend
    confidence: float           # 0-100, confidence in regime detection
    reasoning: str              # Human-readable explanation

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "regime": self.regime.value,
            "price_vs_200dma": self.price_vs_200dma,
            "sma_50": self.sma_50,
            "sma_200": self.sma_200,
            "golden_cross": self.golden_cross,
            "death_cross": self.death_cross,
            "trend_strength": self.trend_strength,
            "confidence": self.confidence,
            "reasoning": self.reasoning,
        }


def calculate_dma(
    candles: List[Dict[str, Any]],
    period: int = 200
) -> Optional[float]:
    """
    Calculate Daily Moving Average for given period.

    Uses pandas_ta for accurate SMA calculation from OHLCV candle data.

    Args:
        candles: Daily OHLCV data (need period + buffer candles)
        period: DMA period (default: 200)

    Returns:
        Current DMA value or None if insufficient data
    """
    if len(candles) < period:
        logger.warning(f"Insufficient candles for {period} DMA: have {len(candles)}")
        return None

    df = pd.DataFrame(candles)

    # Ensure close column exists and is numeric
    if 'close' not in df.columns:
        logger.warning("Candles data missing 'close' column")
        return None

    df['close'] = pd.to_numeric(df['close'], errors='coerce')

    sma = ta.sma(df['close'], length=period)

    if sma is None or sma.empty or pd.isna(sma.iloc[-1]):
        return None

    return float(sma.iloc[-1])


def detect_sma_crossover(
    candles: List[Dict[str, Any]],
    fast_period: int = 50,
    slow_period: int = 200
) -> Tuple[bool, bool, float, float]:
    """
    Detect Golden Cross (bullish) and Death Cross (bearish).

    Golden Cross: SMA50 crosses above SMA200 (bullish signal)
    Death Cross: SMA50 crosses below SMA200 (bearish signal)

    Args:
        candles: Daily OHLCV data
        fast_period: Fast SMA period (default: 50)
        slow_period: Slow SMA period (default: 200)

    Returns:
        Tuple of (golden_cross, death_cross, sma_fast, sma_slow)
        - golden_cross: True if SMA50 > SMA200
        - death_cross: True if SMA50 < SMA200
        - sma_fast: Current fast SMA value
        - sma_slow: Current slow SMA value
    """
    if len(candles) < slow_period:
        logger.warning(f"Insufficient candles for crossover detection: have {len(candles)}, need {slow_period}")
        return False, False, 0.0, 0.0

    df = pd.DataFrame(candles)

    # Ensure close column exists and is numeric
    if 'close' not in df.columns:
        logger.warning("Candles data missing 'close' column")
        return False, False, 0.0, 0.0

    df['close'] = pd.to_numeric(df['close'], errors='coerce')

    sma_fast = ta.sma(df['close'], length=fast_period)
    sma_slow = ta.sma(df['close'], length=slow_period)

    if sma_fast is None or sma_slow is None:
        return False, False, 0.0, 0.0

    current_fast = float(sma_fast.iloc[-1]) if not pd.isna(sma_fast.iloc[-1]) else 0.0
    current_slow = float(sma_slow.iloc[-1]) if not pd.isna(sma_slow.iloc[-1]) else 0.0

    golden_cross = current_fast > current_slow
    death_cross = current_fast < current_slow

    return golden_cross, death_cross, current_fast, current_slow


def classify_market_regime(
    candles: List[Dict[str, Any]],
    current_price: Optional[float] = None,
    fast_period: int = 50,
    slow_period: int = 200
) -> RegimeAnalysis:
    """
    Classify market regime based on price action and moving averages.

    Classification Logic:
    - BULL: Price > 200 DMA AND Golden Cross (SMA50 > SMA200)
    - BEAR: Price < 200 DMA AND Death Cross (SMA50 < SMA200)
    - CHOP: Mixed signals (price and crossover disagree)

    Args:
        candles: Daily OHLCV data (need 200+ candles)
        current_price: Optional override for current price
        fast_period: Fast MA period (default: 50)
        slow_period: Slow MA period (default: 200)

    Returns:
        RegimeAnalysis with full context
    """
    # Handle insufficient data case
    if not candles or len(candles) < slow_period:
        logger.warning(f"Insufficient candles for regime detection: have {len(candles) if candles else 0}, need {slow_period}")
        return RegimeAnalysis(
            regime=MarketRegime.CHOP,
            price_vs_200dma=0.0,
            sma_50=0.0,
            sma_200=0.0,
            golden_cross=False,
            death_cross=False,
            trend_strength=0,
            confidence=0,
            reasoning="Insufficient data for regime detection"
        )

    # Get current price
    if current_price is None:
        try:
            current_price = float(candles[-1]['close'])
        except (KeyError, TypeError, ValueError) as e:
            logger.warning(f"Could not extract current price from candles: {e}")
            return RegimeAnalysis(
                regime=MarketRegime.CHOP,
                price_vs_200dma=0.0,
                sma_50=0.0,
                sma_200=0.0,
                golden_cross=False,
                death_cross=False,
                trend_strength=0,
                confidence=0,
                reasoning="Could not determine current price"
            )

    # Calculate 200 DMA
    dma_200 = calculate_dma(candles, period=slow_period)

    # Handle insufficient data
    if dma_200 is None:
        return RegimeAnalysis(
            regime=MarketRegime.CHOP,
            price_vs_200dma=0.0,
            sma_50=0.0,
            sma_200=0.0,
            golden_cross=False,
            death_cross=False,
            trend_strength=0,
            confidence=0,
            reasoning="Insufficient data for regime detection"
        )

    # Detect crossover
    golden_cross, death_cross, sma_50, sma_200 = detect_sma_crossover(
        candles, fast_period=fast_period, slow_period=slow_period
    )

    # Calculate price position relative to 200 DMA
    price_vs_200dma = ((current_price - dma_200) / dma_200) * 100
    above_200dma = current_price > dma_200

    # Classify regime
    if above_200dma and golden_cross:
        regime = MarketRegime.BULL
        trend_strength = min(100, abs(price_vs_200dma) * 5)  # Scale by distance
        confidence = 85
        reasoning = (
            f"BULL: Price ${current_price:,.2f} is {price_vs_200dma:.1f}% above "
            f"200 DMA (${dma_200:,.2f}), Golden Cross active"
        )

    elif not above_200dma and death_cross:
        regime = MarketRegime.BEAR
        trend_strength = min(100, abs(price_vs_200dma) * 5)
        confidence = 85
        reasoning = (
            f"BEAR: Price ${current_price:,.2f} is {abs(price_vs_200dma):.1f}% below "
            f"200 DMA (${dma_200:,.2f}), Death Cross active"
        )

    else:
        # Mixed signals - CHOP
        regime = MarketRegime.CHOP
        trend_strength = 30  # Low trend strength in chop
        confidence = 60

        if above_200dma and death_cross:
            reasoning = (
                f"CHOP: Price above 200 DMA but Death Cross present - "
                f"conflicting signals (Price: ${current_price:,.2f}, "
                f"DMA200: ${dma_200:,.2f})"
            )
        elif not above_200dma and golden_cross:
            reasoning = (
                f"CHOP: Price below 200 DMA but Golden Cross present - "
                f"conflicting signals (Price: ${current_price:,.2f}, "
                f"DMA200: ${dma_200:,.2f})"
            )
        else:
            reasoning = (
                f"CHOP: Unable to determine clear trend direction "
                f"(Price: ${current_price:,.2f}, DMA200: ${dma_200:,.2f})"
            )

    logger.info(f"[MarketRegime] {regime.value}: {reasoning}")

    return RegimeAnalysis(
        regime=regime,
        price_vs_200dma=price_vs_200dma,
        sma_50=sma_50,
        sma_200=sma_200,
        golden_cross=golden_cross,
        death_cross=death_cross,
        trend_strength=trend_strength,
        confidence=confidence,
        reasoning=reasoning
    )


def get_default_regime() -> RegimeAnalysis:
    """
    Get default CHOP regime for fallback scenarios.

    Used when regime detection fails or has low confidence.
    Defaults to CHOP (most conservative) to prevent losses.

    Returns:
        RegimeAnalysis with CHOP regime and zero confidence
    """
    return RegimeAnalysis(
        regime=MarketRegime.CHOP,
        price_vs_200dma=0.0,
        sma_50=0.0,
        sma_200=0.0,
        golden_cross=False,
        death_cross=False,
        trend_strength=0,
        confidence=0,
        reasoning="Default CHOP regime - insufficient data or detection failure"
    )
