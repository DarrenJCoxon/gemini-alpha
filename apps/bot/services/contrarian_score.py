"""
Trend-Confirmed Opportunity Scoring Algorithm.

Story 5.8: Dynamic Opportunity Scanner
Story 5.11: Trend-Confirmed Pullback Trading

REVISED STRATEGY (from pure contrarian to trend-confirmed):
- Primary: Buy pullbacks in confirmed uptrends (60% weight)
- Secondary: Extreme contrarian (40% weight, smaller positions)

New Scoring Weights:
| Factor                    | Old | New | Logic Change                    |
|---------------------------|-----|-----|---------------------------------|
| RSI Oversold (<30)        | 15  | 5   | Less weight - too extreme       |
| RSI Pullback (40-55)      | 0   | 20  | NEW - prime entry zone          |
| Trend Alignment           | 0   | 20  | NEW - trend confirmation        |
| Structure Intact          | 0   | 15  | NEW - HH/HL pattern holding     |
| Fear & Greed < 50         | 15  | 8   | Confirmation only               |
| Volume spike              | 12  | 0   | REMOVED - pullbacks have LOW vol|
| Volume declining          | 0   | 12  | NEW - healthy consolidation     |
| Price at support/EMA      | 0   | 12  | NEW - structural entry          |
| Bollinger Lower           | 12  | 5   | Keep as secondary               |
| ADX < 25 (weak trend)     | 12  | 0   | REMOVE - we want trends now     |
| ADX > 25 (strong trend)   | 0   | 7   | NEW - prefer trending           |
| Liquidity                 | 10  | 6   | Reduced but still important     |

Max score: ~100 (trend pullback) or ~60 (contrarian extreme)
"""

import logging
import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Literal, Optional, Tuple

import pandas as pd
import pandas_ta as ta

from config import get_config
from services.trend_analyzer import (
    TrendAnalysis,
    analyze_trend,
    get_trend_summary,
)

logger = logging.getLogger(__name__)


@dataclass
class ScoreBreakdown:
    """Detailed breakdown of opportunity score with trend context."""

    symbol: str
    total_score: float

    # Entry type (NEW)
    entry_type: Literal["TREND_PULLBACK", "CONTRARIAN_EXTREME", "NO_OPPORTUNITY"]

    # Trend-based scores (NEW)
    trend_score: float = 0.0
    trend_direction: Literal["UPTREND", "DOWNTREND", "SIDEWAYS"] = "SIDEWAYS"
    structure_score: float = 0.0
    structure_intact: bool = False
    pullback_rsi_score: float = 0.0  # RSI in 40-55 zone
    support_score: float = 0.0  # Price at EMA/structure
    volume_health_score: float = 0.0  # Declining volume

    # Legacy contrarian scores (reduced weights)
    rsi_oversold_score: float = 0.0  # RSI < 30 (extreme)
    rsi_value: Optional[float] = None

    capitulation_score: float = 0.0
    capitulation_pct: Optional[float] = None

    bollinger_score: float = 0.0
    bollinger_pct_b: Optional[float] = None

    liquidity_score: float = 0.0
    volume_24h_usd: float = 0.0

    # ADX (now bonus for trending, not penalty)
    adx_score: float = 0.0
    adx_value: Optional[float] = None

    # Fear & Greed (confirmation only)
    fear_greed_score: float = 0.0
    fear_greed_value: Optional[int] = None

    # Metadata
    current_price: float = 0.0
    high_7d: Optional[float] = None
    ema_20: float = 0.0
    ema_50: float = 0.0
    reasoning: str = ""
    entry_reasons: List[str] = field(default_factory=list)

    # Full trend analysis for reference
    trend_analysis: Optional[TrendAnalysis] = None


def calculate_contrarian_score(
    symbol: str,
    candles: List[Dict[str, Any]],
    ticker_data: Dict[str, Any],
    fear_greed_index: Optional[int] = None,
) -> ScoreBreakdown:
    """
    Calculate comprehensive opportunity score with trend confirmation.

    STRATEGY SHIFT: From pure contrarian to trend-confirmed pullbacks.

    Primary (60% of score): Trend pullback opportunities
    - Uptrend with intact structure (HH/HL)
    - RSI in 40-55 zone (pulled back but not capitulating)
    - Price at support (EMA or previous structure)
    - Volume declining (healthy consolidation)

    Secondary (40% of score): Extreme contrarian
    - Only when Fear & Greed < 25 AND RSI < 30
    - Smaller position sizes recommended

    Args:
        symbol: Trading pair symbol (e.g., "BTC/USD")
        candles: OHLCV candle data (minimum 50 candles recommended)
        ticker_data: Current ticker with volume and price data
        fear_greed_index: Optional Fear & Greed index (0-100)

    Returns:
        ScoreBreakdown with detailed factor analysis
    """
    config = get_config().scanner

    # Initialize breakdown
    breakdown = ScoreBreakdown(
        symbol=symbol,
        total_score=0,
        entry_type="NO_OPPORTUNITY",
        volume_24h_usd=ticker_data.get('quoteVolume', 0) or 0,
        current_price=ticker_data.get('last', 0) or 0,
        fear_greed_value=fear_greed_index,
    )

    reasons = []

    if len(candles) < 30:
        breakdown.reasoning = "Insufficient candle data"
        return breakdown

    # Run comprehensive trend analysis
    trend = analyze_trend(candles, fear_greed_index)
    breakdown.trend_analysis = trend
    breakdown.trend_direction = trend.direction
    breakdown.structure_intact = trend.structure_intact
    breakdown.entry_type = trend.entry_type
    breakdown.rsi_value = trend.rsi_value
    breakdown.adx_value = trend.adx
    breakdown.ema_20 = trend.ema_20
    breakdown.ema_50 = trend.ema_50
    breakdown.current_price = trend.current_price or breakdown.current_price

    # =========================================================================
    # TREND PULLBACK SCORING (Primary Strategy - 60% of total)
    # =========================================================================

    if trend.entry_type == "TREND_PULLBACK":
        # 1. Trend Alignment (20 pts max)
        if trend.adx >= 25:
            breakdown.trend_score = 20
            reasons.append(f"Strong uptrend ADX {trend.adx:.1f}")
        elif trend.adx >= 20:
            breakdown.trend_score = 15
            reasons.append(f"Moderate uptrend ADX {trend.adx:.1f}")
        else:
            breakdown.trend_score = 10
            reasons.append(f"Weak uptrend ADX {trend.adx:.1f}")

        # 2. Structure Intact (15 pts)
        if trend.structure_intact:
            breakdown.structure_score = 15
            reasons.append("Structure intact (Higher Lows held)")

        # 3. RSI Pullback Zone (20 pts max)
        rsi = trend.rsi_value
        if 40 <= rsi <= 50:
            breakdown.pullback_rsi_score = 20
            reasons.append(f"RSI prime zone ({rsi:.1f})")
        elif 35 <= rsi < 40 or 50 < rsi <= 55:
            breakdown.pullback_rsi_score = 15
            reasons.append(f"RSI pullback ({rsi:.1f})")
        elif rsi < 35:
            breakdown.pullback_rsi_score = 10
            reasons.append(f"RSI deep pullback ({rsi:.1f})")

        # 4. Price at Support (12 pts)
        if trend.pullback_to_support:
            breakdown.support_score = 12
            reasons.append("Price at EMA support")

        # 5. Volume Health (12 pts) - declining volume on pullback
        if trend.volume_healthy:
            breakdown.volume_health_score = 12
            reasons.append("Volume declining (healthy)")

        # 6. ADX Bonus for trending (7 pts)
        if trend.adx >= 25:
            breakdown.adx_score = 7
            reasons.append(f"Trending market ADX {trend.adx:.1f}")

    # =========================================================================
    # CONTRARIAN EXTREME SCORING (Secondary - 40% max)
    # =========================================================================

    elif trend.entry_type == "CONTRARIAN_EXTREME":
        # RSI Oversold extreme (5 pts reduced from 15)
        if trend.rsi_value < 30:
            rsi_intensity = (30 - trend.rsi_value) / 30
            breakdown.rsi_oversold_score = 5 * rsi_intensity
            reasons.append(f"RSI extreme oversold ({trend.rsi_value:.1f})")

        # Fear & Greed extreme (8 pts reduced from 15)
        if fear_greed_index is not None and fear_greed_index < 25:
            fear_intensity = (25 - fear_greed_index) / 25
            breakdown.fear_greed_score = 8 * fear_intensity
            reasons.append(f"Extreme fear ({fear_greed_index})")

        # Add warning for downtrend
        if trend.direction == "DOWNTREND":
            reasons.append("⚠️ WARNING: Downtrend active - use smaller size")

    # =========================================================================
    # SHARED FACTORS (Apply to both strategies)
    # =========================================================================

    # Convert to DataFrame for additional calculations
    df = pd.DataFrame(candles)
    df['close'] = pd.to_numeric(df['close'], errors='coerce')
    df['high'] = pd.to_numeric(df['high'], errors='coerce')
    df['low'] = pd.to_numeric(df['low'], errors='coerce')
    df['volume'] = pd.to_numeric(df['volume'], errors='coerce')

    # Bollinger Lower Band (5 pts reduced from 12)
    try:
        bb = ta.bbands(df['close'], length=20, std=2.0)
        if bb is not None and not bb.empty:
            pct_b_col = [c for c in bb.columns if 'BBP' in c]
            if pct_b_col:
                pct_b = float(bb.iloc[-1][pct_b_col[0]])
                if not pd.isna(pct_b):
                    breakdown.bollinger_pct_b = pct_b
                    if pct_b < 0.2:
                        bb_intensity = max(0, (0.2 - pct_b) / 0.2)
                        breakdown.bollinger_score = 5 * bb_intensity
                        reasons.append(f"Bollinger lower %B={pct_b:.2f}")
    except Exception as e:
        logger.debug(f"Bollinger calculation failed for {symbol}: {e}")

    # Price Capitulation (only in extreme contrarian)
    if trend.entry_type == "CONTRARIAN_EXTREME":
        try:
            lookback = min(42, len(df))
            high_7d = df['high'].tail(lookback).max()
            breakdown.high_7d = float(high_7d)
            current_price = breakdown.current_price or float(df['close'].iloc[-1])

            if high_7d > 0:
                cap_pct = ((high_7d - current_price) / high_7d) * 100
                breakdown.capitulation_pct = cap_pct

                if cap_pct >= config.capitulation_threshold_pct:
                    cap_intensity = min(1.0, cap_pct / (config.capitulation_threshold_pct * 2))
                    breakdown.capitulation_score = 10 * cap_intensity
                    reasons.append(f"Capitulation -{cap_pct:.1f}%")
        except Exception as e:
            logger.debug(f"Capitulation calculation failed for {symbol}: {e}")

    # Liquidity Bonus (6 pts reduced from 10)
    try:
        volume_24h = breakdown.volume_24h_usd
        if volume_24h >= config.min_volume_usd:
            log_volume = math.log10(volume_24h)
            log_min = math.log10(config.min_volume_usd)
            log_max = 8  # $100M

            liquidity_intensity = min(1.0, (log_volume - log_min) / (log_max - log_min))
            breakdown.liquidity_score = 6 * liquidity_intensity
    except Exception as e:
        logger.debug(f"Liquidity calculation failed for {symbol}: {e}")

    # Fear & Greed confirmation for trend pullbacks (additional 8 pts if present)
    if trend.entry_type == "TREND_PULLBACK" and fear_greed_index is not None:
        if fear_greed_index < 50:
            fg_bonus = 8 * ((50 - fear_greed_index) / 50)
            breakdown.fear_greed_score = fg_bonus
            reasons.append(f"Fear confirmation ({fear_greed_index})")
        elif fear_greed_index < 75:
            breakdown.fear_greed_score = 3
            reasons.append(f"Neutral sentiment ({fear_greed_index})")

    # =========================================================================
    # CALCULATE TOTAL SCORE
    # =========================================================================

    breakdown.total_score = (
        # Trend pullback factors
        breakdown.trend_score +
        breakdown.structure_score +
        breakdown.pullback_rsi_score +
        breakdown.support_score +
        breakdown.volume_health_score +
        breakdown.adx_score +
        # Contrarian factors
        breakdown.rsi_oversold_score +
        breakdown.capitulation_score +
        # Shared factors
        breakdown.bollinger_score +
        breakdown.liquidity_score +
        breakdown.fear_greed_score
    )

    breakdown.reasoning = "; ".join(reasons) if reasons else "No signals detected"
    breakdown.entry_reasons = reasons

    # Log trend summary
    logger.debug(f"[Score] {symbol}: {get_trend_summary(trend)}")

    return breakdown


def rank_opportunities(
    scores: List[ScoreBreakdown],
    min_score: float = 40,
    max_results: int = 10,
) -> List[ScoreBreakdown]:
    """
    Rank and filter scored opportunities.

    Prioritizes TREND_PULLBACK over CONTRARIAN_EXTREME for same score.

    Args:
        scores: List of ScoreBreakdown objects
        min_score: Minimum score threshold
        max_results: Maximum number of results to return

    Returns:
        Top opportunities sorted by score descending
    """
    # Filter by minimum score
    qualified = [s for s in scores if s.total_score >= min_score]

    # Sort by:
    # 1. Entry type priority (TREND_PULLBACK > CONTRARIAN_EXTREME > NO_OPPORTUNITY)
    # 2. Score descending
    type_priority = {
        "TREND_PULLBACK": 0,
        "CONTRARIAN_EXTREME": 1,
        "NO_OPPORTUNITY": 2
    }

    qualified.sort(
        key=lambda x: (type_priority.get(x.entry_type, 2), -x.total_score)
    )

    return qualified[:max_results]


def get_score_summary(breakdown: ScoreBreakdown) -> str:
    """
    Get human-readable score summary for logging/display.
    """
    type_icon = {
        "TREND_PULLBACK": "📈",
        "CONTRARIAN_EXTREME": "💎",
        "NO_OPPORTUNITY": "⏸️"
    }.get(breakdown.entry_type, "?")

    return (
        f"{type_icon} {breakdown.entry_type}: {breakdown.total_score:.0f} | "
        f"Trend: {breakdown.trend_direction} | "
        f"RSI: {breakdown.rsi_value:.1f if breakdown.rsi_value else 'N/A'} | "
        f"Vol: ${breakdown.volume_24h_usd/1e6:.1f}M"
    )
