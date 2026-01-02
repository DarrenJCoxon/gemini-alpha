"""
Trend Analysis Module for ContrarianAI.

Story 5.11: Trend-Confirmed Pullback Trading

This module replaces pure fear-based entry with intelligent trend detection
and pullback identification. Key insight from research:
- Trend following beats contrarian in bull markets
- "Buy the dip" only works in confirmed uptrends
- RSI 40-50 in uptrend is prime entry (not extreme 30)
- Smart money buys pullbacks, retail buys tops/bottoms

Market Structure Analysis:
- Higher Highs + Higher Lows = UPTREND (buy pullbacks)
- Lower Highs + Lower Lows = DOWNTREND (avoid or short)
- No clear pattern = SIDEWAYS (range trade with caution)

Pullback Detection:
- Price retraced to support (EMA, previous structure)
- Volume declining (healthy consolidation, not panic)
- RSI in 40-55 range (pulled back but not capitulation)
- Structure intact (last Higher Low not broken)
"""

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Literal, Optional, Tuple

import pandas as pd
import pandas_ta as ta

logger = logging.getLogger(__name__)


@dataclass
class SwingPoint:
    """Represents a swing high or swing low in price action."""
    index: int
    price: float
    type: Literal["HIGH", "LOW"]
    timestamp: Optional[Any] = None


@dataclass
class TrendAnalysis:
    """
    Comprehensive trend analysis result.

    Contains market structure, trend strength, pullback status,
    and entry opportunity assessment.
    """
    # Market structure
    direction: Literal["UPTREND", "DOWNTREND", "SIDEWAYS"]
    structure_intact: bool  # Is the last HL/LH intact?
    swing_points: List[SwingPoint] = field(default_factory=list)

    # Trend strength
    strength: float = 0.0  # 0-100 (ADX-based)
    ema_position: Literal["ABOVE", "BELOW", "AT"] = "AT"
    ema_distance_pct: float = 0.0  # % from EMA

    # Pullback detection
    is_pullback: bool = False
    pullback_depth_pct: float = 0.0  # % from recent high/low
    pullback_to_support: bool = False  # Price near EMA or structure
    volume_healthy: bool = False  # Declining volume on pullback

    # RSI context
    rsi_value: float = 50.0
    rsi_zone: Literal["OVERSOLD", "PULLBACK", "NEUTRAL", "EXTENDED", "OVERBOUGHT"] = "NEUTRAL"

    # Entry opportunity
    entry_type: Literal["TREND_PULLBACK", "CONTRARIAN_EXTREME", "NO_OPPORTUNITY"] = "NO_OPPORTUNITY"
    entry_score: float = 0.0  # 0-100 opportunity score
    entry_reasons: List[str] = field(default_factory=list)

    # Raw data for debugging
    current_price: float = 0.0
    ema_20: float = 0.0
    ema_50: float = 0.0
    adx: float = 0.0
    recent_high: float = 0.0
    recent_low: float = 0.0


def detect_swing_points(
    df: pd.DataFrame,
    lookback: int = 5,
    min_swings: int = 4
) -> List[SwingPoint]:
    """
    Detect swing highs and lows for market structure analysis.

    A swing high is a high surrounded by lower highs on both sides.
    A swing low is a low surrounded by higher lows on both sides.

    Args:
        df: DataFrame with 'high' and 'low' columns
        lookback: Number of candles to check on each side
        min_swings: Minimum swings to return

    Returns:
        List of SwingPoint objects sorted by index
    """
    swings = []

    if len(df) < lookback * 2 + 1:
        return swings

    highs = df['high'].values
    lows = df['low'].values

    for i in range(lookback, len(df) - lookback):
        # Check for swing high
        is_swing_high = True
        for j in range(1, lookback + 1):
            if highs[i] <= highs[i - j] or highs[i] <= highs[i + j]:
                is_swing_high = False
                break

        if is_swing_high:
            swings.append(SwingPoint(
                index=i,
                price=float(highs[i]),
                type="HIGH",
                timestamp=df.index[i] if hasattr(df.index[i], 'isoformat') else None
            ))

        # Check for swing low
        is_swing_low = True
        for j in range(1, lookback + 1):
            if lows[i] >= lows[i - j] or lows[i] >= lows[i + j]:
                is_swing_low = False
                break

        if is_swing_low:
            swings.append(SwingPoint(
                index=i,
                price=float(lows[i]),
                type="LOW",
                timestamp=df.index[i] if hasattr(df.index[i], 'isoformat') else None
            ))

    # Sort by index
    swings.sort(key=lambda x: x.index)

    return swings


def classify_market_structure(
    swings: List[SwingPoint],
    current_price: float
) -> Tuple[Literal["UPTREND", "DOWNTREND", "SIDEWAYS"], bool]:
    """
    Classify market structure from swing points.

    UPTREND: Higher Highs + Higher Lows
    DOWNTREND: Lower Highs + Lower Lows
    SIDEWAYS: Mixed or unclear pattern

    Args:
        swings: List of swing points
        current_price: Current market price

    Returns:
        (direction, structure_intact) tuple
    """
    if len(swings) < 4:
        return ("SIDEWAYS", False)

    # Get recent swings (last 4 for 2 cycles)
    recent = swings[-4:]

    # Separate highs and lows
    highs = [s for s in recent if s.type == "HIGH"]
    lows = [s for s in recent if s.type == "LOW"]

    if len(highs) < 2 or len(lows) < 2:
        return ("SIDEWAYS", False)

    # Check for Higher Highs and Higher Lows (uptrend)
    hh = highs[-1].price > highs[-2].price if len(highs) >= 2 else False
    hl = lows[-1].price > lows[-2].price if len(lows) >= 2 else False

    # Check for Lower Highs and Lower Lows (downtrend)
    lh = highs[-1].price < highs[-2].price if len(highs) >= 2 else False
    ll = lows[-1].price < lows[-2].price if len(lows) >= 2 else False

    # Determine structure
    if hh and hl:
        # Uptrend - check if structure intact (price above last HL)
        last_hl = lows[-1].price
        structure_intact = current_price > last_hl
        return ("UPTREND", structure_intact)

    elif lh and ll:
        # Downtrend - check if structure intact (price below last LH)
        last_lh = highs[-1].price
        structure_intact = current_price < last_lh
        return ("DOWNTREND", structure_intact)

    else:
        # Mixed signals - sideways/ranging
        return ("SIDEWAYS", False)


def calculate_rsi_zone(
    rsi: float,
    trend: Literal["UPTREND", "DOWNTREND", "SIDEWAYS"]
) -> Literal["OVERSOLD", "PULLBACK", "NEUTRAL", "EXTENDED", "OVERBOUGHT"]:
    """
    Determine RSI zone with trend context.

    In uptrends:
    - RSI 40-55 = PULLBACK (buy zone)
    - RSI > 70 = EXTENDED (but don't sell immediately in uptrend)

    In downtrends:
    - RSI 45-60 = PULLBACK (potential short zone)
    - RSI < 30 = OVERSOLD (but don't buy in downtrend!)
    """
    if trend == "UPTREND":
        if rsi < 30:
            return "OVERSOLD"
        elif rsi < 40:
            return "PULLBACK"  # Deep pullback
        elif rsi < 55:
            return "PULLBACK"  # Normal pullback - prime buy zone
        elif rsi < 70:
            return "NEUTRAL"
        else:
            return "EXTENDED"  # Strong momentum, wait for pullback

    elif trend == "DOWNTREND":
        if rsi > 70:
            return "OVERBOUGHT"
        elif rsi > 55:
            return "PULLBACK"  # Bounce in downtrend
        elif rsi > 40:
            return "NEUTRAL"
        else:
            return "OVERSOLD"  # Don't buy oversold in downtrend!

    else:  # SIDEWAYS
        if rsi < 30:
            return "OVERSOLD"
        elif rsi > 70:
            return "OVERBOUGHT"
        elif 40 <= rsi <= 60:
            return "NEUTRAL"
        else:
            return "PULLBACK" if rsi < 45 else "EXTENDED"


def analyze_trend(
    candles: List[Dict[str, Any]],
    fear_greed_index: Optional[int] = None
) -> TrendAnalysis:
    """
    Comprehensive trend and pullback analysis.

    This is the main entry point for trend analysis. It:
    1. Detects market structure (HH/HL vs LH/LL)
    2. Calculates trend strength (ADX)
    3. Identifies pullback opportunities
    4. Scores entry quality

    Args:
        candles: OHLCV candle data (minimum 50 recommended)
        fear_greed_index: Optional Fear & Greed index (0-100)

    Returns:
        TrendAnalysis with full market context
    """
    result = TrendAnalysis(
        direction="SIDEWAYS",
        structure_intact=False
    )

    if len(candles) < 30:
        result.entry_reasons.append("Insufficient data")
        return result

    # Convert to DataFrame
    df = pd.DataFrame(candles)
    for col in ['open', 'high', 'low', 'close', 'volume']:
        df[col] = pd.to_numeric(df[col], errors='coerce')

    current_price = float(df['close'].iloc[-1])
    result.current_price = current_price

    # Calculate EMAs
    ema_20 = ta.ema(df['close'], length=20)
    ema_50 = ta.ema(df['close'], length=50)

    if ema_20 is not None and not ema_20.empty:
        result.ema_20 = float(ema_20.iloc[-1])
    if ema_50 is not None and not ema_50.empty:
        result.ema_50 = float(ema_50.iloc[-1])

    # EMA position
    if result.ema_50 > 0:
        ema_dist = ((current_price - result.ema_50) / result.ema_50) * 100
        result.ema_distance_pct = ema_dist
        if ema_dist > 1:
            result.ema_position = "ABOVE"
        elif ema_dist < -1:
            result.ema_position = "BELOW"
        else:
            result.ema_position = "AT"

    # Calculate ADX for trend strength
    try:
        adx_data = ta.adx(df['high'], df['low'], df['close'], length=14)
        if adx_data is not None and not adx_data.empty:
            adx_col = [c for c in adx_data.columns if c.startswith('ADX_')]
            if adx_col:
                result.adx = float(adx_data.iloc[-1][adx_col[0]])
                result.strength = min(100, result.adx * 2)  # Scale ADX to 0-100
    except Exception as e:
        logger.debug(f"ADX calculation error: {e}")

    # Calculate RSI
    try:
        rsi = ta.rsi(df['close'], length=14)
        if rsi is not None and not rsi.empty:
            result.rsi_value = float(rsi.iloc[-1])
    except Exception as e:
        logger.debug(f"RSI calculation error: {e}")

    # Detect swing points and classify structure
    result.swing_points = detect_swing_points(df)
    result.direction, result.structure_intact = classify_market_structure(
        result.swing_points,
        current_price
    )

    # Calculate RSI zone with trend context
    result.rsi_zone = calculate_rsi_zone(result.rsi_value, result.direction)

    # Get recent high/low for pullback calculation
    lookback = min(20, len(df))
    result.recent_high = float(df['high'].tail(lookback).max())
    result.recent_low = float(df['low'].tail(lookback).min())

    # Calculate pullback depth
    if result.direction == "UPTREND" and result.recent_high > 0:
        result.pullback_depth_pct = ((result.recent_high - current_price) / result.recent_high) * 100
    elif result.direction == "DOWNTREND" and result.recent_low > 0:
        result.pullback_depth_pct = ((current_price - result.recent_low) / result.recent_low) * 100

    # Check if pullback to support (price near EMA)
    if result.ema_20 > 0:
        ema20_dist = abs((current_price - result.ema_20) / result.ema_20) * 100
        result.pullback_to_support = ema20_dist < 3  # Within 3% of EMA

    # Check volume health (declining on pullback = healthy)
    try:
        if len(df) >= 5:
            recent_vol = df['volume'].tail(3).mean()
            prev_vol = df['volume'].tail(10).head(7).mean()
            if prev_vol > 0:
                vol_ratio = recent_vol / prev_vol
                result.volume_healthy = vol_ratio < 0.8  # Volume declined 20%+
    except Exception as e:
        logger.debug(f"Volume analysis error: {e}")

    # Determine if this is a pullback
    result.is_pullback = (
        result.direction == "UPTREND" and
        result.structure_intact and
        result.pullback_depth_pct >= 3 and  # At least 3% pullback
        result.pullback_depth_pct <= 15 and  # Not more than 15% (structure break risk)
        result.rsi_zone in ["PULLBACK", "OVERSOLD"]
    )

    # Determine entry type and score
    _calculate_entry_opportunity(result, fear_greed_index)

    return result


def _calculate_entry_opportunity(
    result: TrendAnalysis,
    fear_greed_index: Optional[int]
) -> None:
    """
    Calculate entry opportunity type and score.

    Priority:
    1. TREND_PULLBACK: Best opportunity (uptrend + pullback + structure intact)
    2. CONTRARIAN_EXTREME: Fallback (extreme fear in any market)
    3. NO_OPPORTUNITY: No clear edge
    """
    score = 0.0
    reasons = []

    # Check for TREND_PULLBACK opportunity (primary strategy)
    if (result.direction == "UPTREND" and
        result.structure_intact and
        result.is_pullback):

        result.entry_type = "TREND_PULLBACK"

        # Score components for trend pullback
        # Trend alignment (20 pts max)
        if result.adx >= 25:
            score += 20
            reasons.append(f"Strong trend ADX {result.adx:.1f}")
        elif result.adx >= 20:
            score += 15
            reasons.append(f"Moderate trend ADX {result.adx:.1f}")
        else:
            score += 10
            reasons.append(f"Weak trend ADX {result.adx:.1f}")

        # Structure intact (15 pts)
        if result.structure_intact:
            score += 15
            reasons.append("Structure intact (HL held)")

        # RSI in pullback zone (20 pts max)
        if 40 <= result.rsi_value <= 50:
            score += 20
            reasons.append(f"RSI in prime zone ({result.rsi_value:.1f})")
        elif 35 <= result.rsi_value < 40 or 50 < result.rsi_value <= 55:
            score += 15
            reasons.append(f"RSI pullback ({result.rsi_value:.1f})")
        elif result.rsi_value < 35:
            score += 10
            reasons.append(f"RSI deep pullback ({result.rsi_value:.1f})")

        # Pullback to support (15 pts)
        if result.pullback_to_support:
            score += 15
            reasons.append("Price at EMA support")

        # Healthy volume (12 pts)
        if result.volume_healthy:
            score += 12
            reasons.append("Volume declining (healthy)")

        # Fear & Greed confirmation (10 pts)
        if fear_greed_index is not None:
            if fear_greed_index < 50:
                score += 10
                reasons.append(f"Fear present ({fear_greed_index})")
            elif fear_greed_index < 75:
                score += 5
                reasons.append(f"Neutral sentiment ({fear_greed_index})")

        # EMA position bonus (8 pts)
        if result.ema_position == "ABOVE":
            score += 8
            reasons.append("Price above 50 EMA")

    # Check for CONTRARIAN_EXTREME (fallback for extreme fear)
    elif (fear_greed_index is not None and
          fear_greed_index < 25 and
          result.rsi_value < 30):

        result.entry_type = "CONTRARIAN_EXTREME"

        # Extreme fear scores (max ~60, smaller position recommended)
        fear_intensity = (25 - fear_greed_index) / 25
        score += 30 * fear_intensity
        reasons.append(f"Extreme fear ({fear_greed_index})")

        rsi_intensity = (30 - result.rsi_value) / 30
        score += 20 * rsi_intensity
        reasons.append(f"RSI oversold ({result.rsi_value:.1f})")

        # Penalty for downtrend (contrarian is risky in downtrends)
        if result.direction == "DOWNTREND":
            score *= 0.5
            reasons.append("WARNING: Downtrend active")

    else:
        result.entry_type = "NO_OPPORTUNITY"

        # Log why no opportunity
        if result.direction == "DOWNTREND":
            reasons.append("Downtrend - avoid buying")
        elif result.direction == "SIDEWAYS":
            reasons.append("Sideways - no clear trend")
        elif not result.structure_intact:
            reasons.append("Structure broken")
        elif not result.is_pullback:
            if result.rsi_value > 60:
                reasons.append("RSI too high - wait for pullback")
            elif result.pullback_depth_pct < 3:
                reasons.append("No pullback yet")

    result.entry_score = min(100, score)
    result.entry_reasons = reasons


def get_trend_summary(analysis: TrendAnalysis) -> str:
    """
    Get human-readable trend summary for logging/display.
    """
    icon = {
        "UPTREND": "▲",
        "DOWNTREND": "▼",
        "SIDEWAYS": "─"
    }.get(analysis.direction, "?")

    structure = "✓" if analysis.structure_intact else "✗"

    return (
        f"{analysis.direction} {icon} | "
        f"ADX: {analysis.adx:.1f} | "
        f"RSI: {analysis.rsi_value:.1f} ({analysis.rsi_zone}) | "
        f"Structure: {structure} | "
        f"Entry: {analysis.entry_type} ({analysis.entry_score:.0f})"
    )
