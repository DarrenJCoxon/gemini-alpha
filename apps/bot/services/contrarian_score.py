"""
Contrarian Opportunity Scoring Algorithm.

Story 5.8: Dynamic Opportunity Scanner

Scores assets 0-100 based on contrarian trading signals:
- RSI Oversold (15 pts): RSI < 30
- Price Capitulation (15 pts): -10%+ from 7d high
- Volume Spike (12 pts): Volume > 2x 20-day average
- Weak Trend ADX (12 pts): ADX < 25
- Bollinger Lower (12 pts): Price below lower band
- VWAP Discount (6 pts): Price below VWAP
- Liquidity Bonus (10 pts): Log-scaled volume bonus

Total possible score: 82 (factors) + 10 (liquidity) = 92 max
(Slightly under 100 to leave room for exceptional conditions)
"""

import logging
import math
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import pandas as pd
import pandas_ta as ta

from config import get_config

logger = logging.getLogger(__name__)


@dataclass
class ScoreBreakdown:
    """Detailed breakdown of contrarian opportunity score."""

    symbol: str
    total_score: float

    # Individual factor scores
    rsi_score: float
    rsi_value: Optional[float]

    capitulation_score: float
    capitulation_pct: Optional[float]  # % below 7d high

    volume_spike_score: float
    volume_ratio: Optional[float]  # Current vs 20d avg

    adx_score: float
    adx_value: Optional[float]

    bollinger_score: float
    bollinger_pct_b: Optional[float]  # Position within bands

    vwap_score: float
    vwap_distance_pct: Optional[float]  # % below VWAP

    liquidity_score: float
    volume_24h_usd: float

    # Metadata
    current_price: float
    high_7d: Optional[float]
    reasoning: str


def calculate_contrarian_score(
    symbol: str,
    candles: List[Dict[str, Any]],
    ticker_data: Dict[str, Any],
) -> ScoreBreakdown:
    """
    Calculate comprehensive contrarian opportunity score.

    Args:
        symbol: Trading pair symbol (e.g., "BTC/USD")
        candles: OHLCV candle data (minimum 50 candles recommended)
        ticker_data: Current ticker with volume and price data

    Returns:
        ScoreBreakdown with detailed factor analysis
    """
    config = get_config().scanner

    # Initialize score breakdown
    breakdown = ScoreBreakdown(
        symbol=symbol,
        total_score=0,
        rsi_score=0, rsi_value=None,
        capitulation_score=0, capitulation_pct=None,
        volume_spike_score=0, volume_ratio=None,
        adx_score=0, adx_value=None,
        bollinger_score=0, bollinger_pct_b=None,
        vwap_score=0, vwap_distance_pct=None,
        liquidity_score=0,
        volume_24h_usd=ticker_data.get('quoteVolume', 0) or 0,
        current_price=ticker_data.get('last', 0) or 0,
        high_7d=None,
        reasoning=""
    )

    reasons = []

    if len(candles) < 30:
        breakdown.reasoning = "Insufficient candle data"
        return breakdown

    # Convert to DataFrame
    df = pd.DataFrame(candles)
    df['close'] = pd.to_numeric(df['close'], errors='coerce')
    df['high'] = pd.to_numeric(df['high'], errors='coerce')
    df['low'] = pd.to_numeric(df['low'], errors='coerce')
    df['volume'] = pd.to_numeric(df['volume'], errors='coerce')

    # 1. RSI Oversold (15 pts)
    try:
        rsi = ta.rsi(df['close'], length=14)
        if rsi is not None and not rsi.empty:
            rsi_value = float(rsi.iloc[-1])
            if not pd.isna(rsi_value):
                breakdown.rsi_value = rsi_value
                if rsi_value < config.rsi_oversold_threshold:
                    # Scale: RSI 30 = 0%, RSI 20 = 50%, RSI 10 = 100% of weight
                    rsi_intensity = (config.rsi_oversold_threshold - rsi_value) / config.rsi_oversold_threshold
                    breakdown.rsi_score = min(config.weight_rsi_oversold, config.weight_rsi_oversold * rsi_intensity)
                    reasons.append(f"RSI oversold ({rsi_value:.1f})")
    except Exception as e:
        logger.debug(f"RSI calculation failed for {symbol}: {e}")

    # 2. Price Capitulation (15 pts) - % below 7-day high
    try:
        # Get 7-day high (assuming 4h candles, ~42 candles = 7 days)
        lookback = min(42, len(df))
        high_7d = df['high'].tail(lookback).max()
        breakdown.high_7d = float(high_7d)
        current_price = breakdown.current_price or float(df['close'].iloc[-1])

        if high_7d > 0:
            capitulation_pct = ((high_7d - current_price) / high_7d) * 100
            breakdown.capitulation_pct = capitulation_pct

            if capitulation_pct >= config.capitulation_threshold_pct:
                # Scale: 10% drop = 50%, 20% drop = 100% of weight
                cap_intensity = min(1.0, capitulation_pct / (config.capitulation_threshold_pct * 2))
                breakdown.capitulation_score = config.weight_price_capitulation * cap_intensity
                reasons.append(f"Capitulation -{capitulation_pct:.1f}%")
    except Exception as e:
        logger.debug(f"Capitulation calculation failed for {symbol}: {e}")

    # 3. Volume Spike (12 pts)
    try:
        if len(df) >= 20:
            volume_20d_avg = df['volume'].tail(20).mean()
            current_volume = float(df['volume'].iloc[-1])

            if volume_20d_avg > 0:
                volume_ratio = current_volume / volume_20d_avg
                breakdown.volume_ratio = volume_ratio

                if volume_ratio >= config.volume_spike_mult:
                    # Scale: 2x = 50%, 4x = 100% of weight
                    spike_intensity = min(1.0, (volume_ratio - 1) / (config.volume_spike_mult * 2 - 1))
                    breakdown.volume_spike_score = config.weight_volume_spike * spike_intensity
                    reasons.append(f"Volume spike {volume_ratio:.1f}x")
    except Exception as e:
        logger.debug(f"Volume spike calculation failed for {symbol}: {e}")

    # 4. Weak Trend ADX (12 pts)
    try:
        adx_data = ta.adx(df['high'], df['low'], df['close'], length=14)
        if adx_data is not None and not adx_data.empty:
            adx_col = [c for c in adx_data.columns if c.startswith('ADX_')]
            if adx_col:
                adx_value = float(adx_data.iloc[-1][adx_col[0]])
                if not pd.isna(adx_value):
                    breakdown.adx_value = adx_value

                    if adx_value < config.adx_weak_threshold:
                        # Scale: ADX 25 = 0%, ADX 15 = 50%, ADX 5 = 100% of weight
                        adx_intensity = (config.adx_weak_threshold - adx_value) / config.adx_weak_threshold
                        breakdown.adx_score = config.weight_adx_weak * adx_intensity
                        reasons.append(f"Weak trend ADX {adx_value:.1f}")
    except Exception as e:
        logger.debug(f"ADX calculation failed for {symbol}: {e}")

    # 5. Bollinger Lower Band (12 pts)
    try:
        bb = ta.bbands(df['close'], length=20, std=2.0)
        if bb is not None and not bb.empty:
            # Find the percent_b column (position within bands)
            pct_b_col = [c for c in bb.columns if 'BBP' in c]
            if pct_b_col:
                pct_b = float(bb.iloc[-1][pct_b_col[0]])
                if not pd.isna(pct_b):
                    breakdown.bollinger_pct_b = pct_b

                    if pct_b < 0.2:  # Below lower band or near it
                        # Scale: %B 0.2 = 0%, %B 0 = 100% of weight
                        bb_intensity = max(0, (0.2 - pct_b) / 0.2)
                        breakdown.bollinger_score = config.weight_bollinger_lower * bb_intensity
                        reasons.append(f"Bollinger lower %B={pct_b:.2f}")
    except Exception as e:
        logger.debug(f"Bollinger calculation failed for {symbol}: {e}")

    # 6. VWAP Discount (6 pts)
    try:
        vwap = ta.vwap(df['high'], df['low'], df['close'], df['volume'])
        if vwap is not None and not vwap.empty:
            vwap_value = float(vwap.iloc[-1])
            if not pd.isna(vwap_value):
                current_price = breakdown.current_price or float(df['close'].iloc[-1])

                if vwap_value > 0:
                    vwap_distance_pct = ((current_price - vwap_value) / vwap_value) * 100
                    breakdown.vwap_distance_pct = vwap_distance_pct

                    if vwap_distance_pct < -1:  # At least 1% below VWAP
                        # Scale: -1% = 0%, -5% = 100% of weight
                        vwap_intensity = min(1.0, abs(vwap_distance_pct) / 5)
                        breakdown.vwap_score = config.weight_vwap_discount * vwap_intensity
                        reasons.append(f"VWAP discount {vwap_distance_pct:.1f}%")
    except Exception as e:
        logger.debug(f"VWAP calculation failed for {symbol}: {e}")

    # 7. Liquidity Bonus (10 pts) - log-scaled volume
    try:
        volume_24h = breakdown.volume_24h_usd
        if volume_24h >= config.min_volume_usd:
            # Log scale: $1M = 0%, $10M = 50%, $100M+ = 100% of weight
            log_volume = math.log10(volume_24h)
            log_min = math.log10(config.min_volume_usd)  # 6 for $1M
            log_max = 8  # $100M

            liquidity_intensity = min(1.0, (log_volume - log_min) / (log_max - log_min))
            breakdown.liquidity_score = config.weight_liquidity_bonus * liquidity_intensity
    except Exception as e:
        logger.debug(f"Liquidity calculation failed for {symbol}: {e}")

    # Calculate total score
    breakdown.total_score = (
        breakdown.rsi_score +
        breakdown.capitulation_score +
        breakdown.volume_spike_score +
        breakdown.adx_score +
        breakdown.bollinger_score +
        breakdown.vwap_score +
        breakdown.liquidity_score
    )

    breakdown.reasoning = "; ".join(reasons) if reasons else "No contrarian signals"

    return breakdown


def rank_opportunities(
    scores: List[ScoreBreakdown],
    min_score: float = 40,
    max_results: int = 10,
) -> List[ScoreBreakdown]:
    """
    Rank and filter scored opportunities.

    Args:
        scores: List of ScoreBreakdown objects
        min_score: Minimum score threshold
        max_results: Maximum number of results to return

    Returns:
        Top opportunities sorted by score descending
    """
    # Filter by minimum score
    qualified = [s for s in scores if s.total_score >= min_score]

    # Sort by score descending
    qualified.sort(key=lambda x: x.total_score, reverse=True)

    # Return top N
    return qualified[:max_results]
