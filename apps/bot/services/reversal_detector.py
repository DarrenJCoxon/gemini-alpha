"""
Reversal Detection and Confirmation System.

Story 5.9: Basket Trading System

This module provides functions to detect and confirm price reversals,
ensuring we catch coins as they reverse AND hold their reversal pattern.

Key Principles:
- Don't buy falling knives
- Confirm reversal is holding before entry
- Detect volume exhaustion for exits

Detection Methods:
1. MACD Bullish Crossover - Histogram turning positive
2. Higher-Low Pattern - Price above prior swing low
3. Reversal Holding - Price staying above reversal point
4. Volume Exhaustion - High volume climax followed by decline
"""

import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd
import pandas_ta as ta

from config import get_config

logger = logging.getLogger(__name__)


@dataclass
class ReversalSignal:
    """Result of reversal detection analysis."""

    is_reversal: bool
    is_confirmed: bool  # Has the reversal held?
    signal_type: str  # "BULLISH_REVERSAL", "BEARISH_EXHAUSTION", "NONE"
    confidence: float  # 0-100

    # Specific signals
    macd_bullish_cross: bool
    higher_low_formed: bool
    reversal_holding: bool
    volume_exhaustion: bool

    # Values for debugging
    macd_histogram: Optional[float]
    macd_prev_histogram: Optional[float]
    swing_low: Optional[float]
    current_price: float
    candles_since_reversal: int

    reasoning: str


@dataclass
class ExhaustionSignal:
    """Result of volume exhaustion detection."""

    is_exhausted: bool
    confidence: float

    # Pattern detection
    had_volume_climax: bool
    declining_periods: int
    price_failing_highs: bool

    # Values
    climax_volume: Optional[float]
    current_volume: Optional[float]
    volume_decline_pct: Optional[float]

    reasoning: str


def detect_macd_bullish_cross(candles: List[Dict[str, Any]]) -> Tuple[bool, Optional[float], Optional[float]]:
    """
    Detect MACD bullish crossover.

    A bullish cross occurs when:
    - MACD histogram was negative (below zero)
    - MACD histogram is now positive or zero (crossing above)

    Args:
        candles: OHLCV candle data (minimum 30 candles)

    Returns:
        Tuple of (is_bullish_cross, current_histogram, previous_histogram)
    """
    if len(candles) < 30:
        return False, None, None

    try:
        df = pd.DataFrame(candles)
        df['close'] = pd.to_numeric(df['close'], errors='coerce')

        # Calculate MACD
        macd = ta.macd(df['close'], fast=12, slow=26, signal=9)
        if macd is None or macd.empty:
            return False, None, None

        # Find histogram column
        hist_col = [c for c in macd.columns if 'MACDh' in c or 'MACD_12_26_9' in c.upper() and 'h' in c.lower()]
        if not hist_col:
            # Try alternate column names
            for col in macd.columns:
                if 'hist' in col.lower() or col.endswith('_h'):
                    hist_col = [col]
                    break

        if not hist_col:
            logger.debug("MACD histogram column not found")
            return False, None, None

        current_hist = float(macd[hist_col[0]].iloc[-1])
        prev_hist = float(macd[hist_col[0]].iloc[-2])

        # Bullish cross: previous negative, current positive or zero
        is_bullish_cross = prev_hist < 0 and current_hist >= 0

        return is_bullish_cross, current_hist, prev_hist

    except Exception as e:
        logger.debug(f"MACD detection error: {e}")
        return False, None, None


def detect_higher_low(
    candles: List[Dict[str, Any]],
    lookback: int = 20
) -> Tuple[bool, Optional[float], float]:
    """
    Detect higher-low pattern indicating potential reversal.

    A higher-low forms when:
    - Price made a swing low in the past
    - Current price is above that swing low
    - Price is starting to trend upward

    Args:
        candles: OHLCV candle data
        lookback: Number of candles to look back for swing low

    Returns:
        Tuple of (has_higher_low, swing_low_price, current_price)
    """
    if len(candles) < lookback:
        return False, None, 0.0

    try:
        df = pd.DataFrame(candles)
        df['low'] = pd.to_numeric(df['low'], errors='coerce')
        df['close'] = pd.to_numeric(df['close'], errors='coerce')

        # Find the lowest low in the lookback period (excluding last 3 candles)
        lookback_data = df['low'].iloc[-(lookback):-3]
        if lookback_data.empty:
            return False, None, float(df['close'].iloc[-1])

        swing_low = float(lookback_data.min())
        current_price = float(df['close'].iloc[-1])

        # Check if current price is above swing low (higher low forming)
        has_higher_low = current_price > swing_low

        # Additional check: recent lows should be rising
        recent_lows = df['low'].tail(5).values
        rising_lows = all(recent_lows[i] <= recent_lows[i + 1] for i in range(len(recent_lows) - 1))

        # Require both conditions
        is_valid_higher_low = has_higher_low and rising_lows

        return is_valid_higher_low, swing_low, current_price

    except Exception as e:
        logger.debug(f"Higher-low detection error: {e}")
        return False, None, 0.0


def detect_reversal_holding(
    candles: List[Dict[str, Any]],
    min_candles: int = 3
) -> Tuple[bool, int]:
    """
    Detect if a reversal is holding (not immediately failing).

    A reversal is holding when:
    - Price has moved up from recent low
    - It hasn't immediately retraced back to/below the low
    - At least N candles have passed since reversal started

    Args:
        candles: OHLCV candle data
        min_candles: Minimum candles to confirm reversal is holding

    Returns:
        Tuple of (is_holding, candles_since_reversal)
    """
    if len(candles) < min_candles + 5:
        return False, 0

    try:
        df = pd.DataFrame(candles)
        df['close'] = pd.to_numeric(df['close'], errors='coerce')
        df['low'] = pd.to_numeric(df['low'], errors='coerce')

        # Find the lowest point in recent history
        lookback = min(20, len(df) - 1)
        recent_data = df.tail(lookback)

        lowest_idx = recent_data['low'].idxmin()
        lowest_price = float(recent_data.loc[lowest_idx, 'low'])

        # Count candles since the low
        candles_since_low = len(df) - 1 - lowest_idx

        if candles_since_low < min_candles:
            return False, candles_since_low

        # Check if price has stayed above the low since then
        prices_since_low = df['close'].iloc[lowest_idx + 1:]
        current_price = float(df['close'].iloc[-1])

        # Reversal is holding if:
        # 1. Current price > lowest price
        # 2. No close below the lowest price since reversal
        is_holding = (
            current_price > lowest_price and
            all(prices_since_low > lowest_price * 0.98)  # 2% tolerance
        )

        return is_holding, candles_since_low

    except Exception as e:
        logger.debug(f"Reversal holding detection error: {e}")
        return False, 0


def detect_volume_exhaustion(
    candles: List[Dict[str, Any]],
    climax_mult: float = 2.0,
    decline_periods: int = 3
) -> ExhaustionSignal:
    """
    Detect volume exhaustion pattern (signal to sell).

    Volume exhaustion occurs when:
    1. There was a volume climax (2x+ average volume spike)
    2. Volume has been declining for N consecutive periods
    3. Price is failing to make new highs

    This signals buying pressure is exhausting.

    Args:
        candles: OHLCV candle data
        climax_mult: Multiplier for volume climax detection
        decline_periods: Minimum consecutive declining periods

    Returns:
        ExhaustionSignal with detection results
    """
    config = get_config().basket

    if len(candles) < 20:
        return ExhaustionSignal(
            is_exhausted=False,
            confidence=0,
            had_volume_climax=False,
            declining_periods=0,
            price_failing_highs=False,
            climax_volume=None,
            current_volume=None,
            volume_decline_pct=None,
            reasoning="Insufficient data"
        )

    try:
        df = pd.DataFrame(candles)
        df['volume'] = pd.to_numeric(df['volume'], errors='coerce')
        df['high'] = pd.to_numeric(df['high'], errors='coerce')
        df['close'] = pd.to_numeric(df['close'], errors='coerce')

        # Calculate average volume
        avg_volume = df['volume'].rolling(20).mean()

        # Step 1: Look for volume climax in last 10 candles
        recent_volumes = df['volume'].tail(10)
        recent_avg = avg_volume.tail(10)

        had_climax = False
        climax_volume = None
        climax_idx = None

        for i, (vol, avg) in enumerate(zip(recent_volumes, recent_avg)):
            if pd.notna(avg) and vol > avg * climax_mult:
                had_climax = True
                climax_volume = float(vol)
                climax_idx = i
                break

        # Step 2: Check for declining volume since climax
        declining_count = 0
        if climax_idx is not None:
            volumes_since_climax = recent_volumes.iloc[climax_idx:].values
            for i in range(1, len(volumes_since_climax)):
                if volumes_since_climax[i] < volumes_since_climax[i - 1]:
                    declining_count += 1
                else:
                    declining_count = 0  # Reset if volume increases

        current_volume = float(df['volume'].iloc[-1])

        # Step 3: Check if price is failing to make new highs
        recent_highs = df['high'].tail(5)
        highest_high_idx = recent_highs.idxmax()
        candles_since_high = len(df) - 1 - highest_high_idx
        price_failing_highs = candles_since_high >= 2

        # Calculate volume decline percentage
        volume_decline_pct = None
        if climax_volume and climax_volume > 0:
            volume_decline_pct = ((climax_volume - current_volume) / climax_volume) * 100

        # Determine exhaustion
        is_exhausted = (
            had_climax and
            declining_count >= decline_periods and
            price_failing_highs
        )

        # Calculate confidence
        confidence = 0
        if had_climax:
            confidence += 30
        if declining_count >= decline_periods:
            confidence += 35
        if price_failing_highs:
            confidence += 35

        # Build reasoning
        reasons = []
        if had_climax:
            reasons.append(f"Volume climax detected ({climax_volume:,.0f})")
        if declining_count >= decline_periods:
            reasons.append(f"{declining_count} periods of declining volume")
        if price_failing_highs:
            reasons.append(f"Price failing highs for {candles_since_high} candles")

        reasoning = "; ".join(reasons) if reasons else "No exhaustion signals"

        return ExhaustionSignal(
            is_exhausted=is_exhausted,
            confidence=confidence,
            had_volume_climax=had_climax,
            declining_periods=declining_count,
            price_failing_highs=price_failing_highs,
            climax_volume=climax_volume,
            current_volume=current_volume,
            volume_decline_pct=volume_decline_pct,
            reasoning=reasoning
        )

    except Exception as e:
        logger.error(f"Volume exhaustion detection error: {e}")
        return ExhaustionSignal(
            is_exhausted=False,
            confidence=0,
            had_volume_climax=False,
            declining_periods=0,
            price_failing_highs=False,
            climax_volume=None,
            current_volume=None,
            volume_decline_pct=None,
            reasoning=f"Error: {e}"
        )


def detect_bullish_reversal(
    candles: List[Dict[str, Any]],
    require_macd: bool = True,
    require_higher_low: bool = True,
    min_confirmation_candles: int = 3
) -> ReversalSignal:
    """
    Detect bullish reversal with confirmation.

    This is the main entry signal detection. Combines:
    - MACD bullish crossover
    - Higher-low pattern
    - Reversal holding confirmation

    Args:
        candles: OHLCV candle data
        require_macd: Require MACD confirmation
        require_higher_low: Require higher-low pattern
        min_confirmation_candles: Minimum candles for confirmation

    Returns:
        ReversalSignal with full analysis
    """
    config = get_config().basket

    # Use config overrides if available
    require_macd = config.require_macd_confirmation
    require_higher_low = config.require_higher_low
    min_confirmation_candles = config.reversal_confirmation_candles

    if len(candles) < 30:
        return ReversalSignal(
            is_reversal=False,
            is_confirmed=False,
            signal_type="NONE",
            confidence=0,
            macd_bullish_cross=False,
            higher_low_formed=False,
            reversal_holding=False,
            volume_exhaustion=False,
            macd_histogram=None,
            macd_prev_histogram=None,
            swing_low=None,
            current_price=0,
            candles_since_reversal=0,
            reasoning="Insufficient data"
        )

    # Detect each component
    macd_cross, macd_hist, macd_prev = detect_macd_bullish_cross(candles)
    higher_low, swing_low, current_price = detect_higher_low(candles)
    is_holding, candles_since = detect_reversal_holding(candles, min_confirmation_candles)

    # Determine if this is a reversal
    conditions_met = 0
    conditions_required = 0

    if require_macd:
        conditions_required += 1
        if macd_cross:
            conditions_met += 1

    if require_higher_low:
        conditions_required += 1
        if higher_low:
            conditions_met += 1

    # Always check if reversal is holding
    conditions_required += 1
    if is_holding:
        conditions_met += 1

    # Is it a reversal?
    is_reversal = conditions_met >= conditions_required

    # Is it confirmed (holding)?
    is_confirmed = is_reversal and is_holding and candles_since >= min_confirmation_candles

    # Calculate confidence
    confidence = 0
    if macd_cross:
        confidence += 30
    if higher_low:
        confidence += 35
    if is_holding:
        confidence += 35

    # Determine signal type
    if is_confirmed:
        signal_type = "BULLISH_REVERSAL_CONFIRMED"
    elif is_reversal:
        signal_type = "BULLISH_REVERSAL_PENDING"
    else:
        signal_type = "NONE"

    # Build reasoning
    reasons = []
    if macd_cross:
        reasons.append(f"MACD bullish cross (hist: {macd_hist:.4f})")
    elif require_macd:
        reasons.append("MACD not crossed")

    if higher_low:
        reasons.append(f"Higher-low at ${swing_low:.4f}")
    elif require_higher_low:
        reasons.append("No higher-low")

    if is_holding:
        reasons.append(f"Reversal holding ({candles_since} candles)")
    else:
        reasons.append("Reversal not confirmed")

    reasoning = "; ".join(reasons)

    return ReversalSignal(
        is_reversal=is_reversal,
        is_confirmed=is_confirmed,
        signal_type=signal_type,
        confidence=confidence,
        macd_bullish_cross=macd_cross,
        higher_low_formed=higher_low,
        reversal_holding=is_holding,
        volume_exhaustion=False,
        macd_histogram=macd_hist,
        macd_prev_histogram=macd_prev,
        swing_low=swing_low,
        current_price=current_price,
        candles_since_reversal=candles_since,
        reasoning=reasoning
    )


def should_buy_with_reversal(
    candles: List[Dict[str, Any]],
    technical_analysis: Dict[str, Any],
    sentiment_analysis: Dict[str, Any]
) -> Tuple[bool, str, float]:
    """
    Determine if we should buy based on balanced reversal logic.

    Combines:
    - Fear/Greed threshold (relaxed to <40)
    - RSI threshold (relaxed to <35)
    - Bullish reversal confirmation
    - ADX check (allows trending up to 40)

    Args:
        candles: OHLCV data for reversal detection
        technical_analysis: Technical agent output
        sentiment_analysis: Sentiment agent output

    Returns:
        Tuple of (should_buy, reasoning, confidence)
    """
    config = get_config().basket
    reasons = []
    confidence = 0

    # Check Fear & Greed (relaxed threshold)
    fear_score = sentiment_analysis.get("fear_score", 50)
    if fear_score > config.fear_threshold_buy:
        return False, f"Fear score {fear_score} > threshold {config.fear_threshold_buy}", 0
    reasons.append(f"Fear OK ({fear_score})")
    confidence += 20

    # Check RSI (relaxed threshold)
    rsi = technical_analysis.get("rsi", 50)
    if rsi > config.rsi_oversold:
        return False, f"RSI {rsi:.1f} > threshold {config.rsi_oversold}", 0
    reasons.append(f"RSI oversold ({rsi:.1f})")
    confidence += 20

    # Check ADX (allow trending markets up to threshold)
    adx = technical_analysis.get("adx", {}).get("value", 25)
    if adx > config.adx_max_for_entry:
        return False, f"ADX {adx:.1f} > max {config.adx_max_for_entry} (strong trend)", 0
    reasons.append(f"ADX OK ({adx:.1f})")
    confidence += 10

    # Detect reversal confirmation
    reversal = detect_bullish_reversal(candles)

    if not reversal.is_reversal:
        return False, f"No reversal detected: {reversal.reasoning}", 0

    if not reversal.is_confirmed:
        return False, f"Reversal not confirmed: {reversal.reasoning}", confidence

    reasons.append(reversal.reasoning)
    confidence += reversal.confidence * 0.5  # Half weight from reversal

    return True, "; ".join(reasons), min(100, confidence)


def should_sell_with_exhaustion(
    candles: List[Dict[str, Any]],
    technical_analysis: Dict[str, Any],
    sentiment_analysis: Dict[str, Any]
) -> Tuple[bool, str, float]:
    """
    Determine if we should sell based on exhaustion pattern.

    Combines:
    - Fear/Greed threshold (relaxed to >60)
    - RSI threshold (relaxed to >65)
    - Volume exhaustion pattern

    Args:
        candles: OHLCV data for exhaustion detection
        technical_analysis: Technical agent output
        sentiment_analysis: Sentiment agent output

    Returns:
        Tuple of (should_sell, reasoning, confidence)
    """
    config = get_config().basket
    reasons = []
    confidence = 0

    # Check Fear & Greed (relaxed threshold for sell)
    fear_score = sentiment_analysis.get("fear_score", 50)
    if fear_score >= config.greed_threshold_sell:
        reasons.append(f"Greed high ({fear_score})")
        confidence += 30

    # Check RSI (relaxed threshold)
    rsi = technical_analysis.get("rsi", 50)
    if rsi >= config.rsi_overbought:
        reasons.append(f"RSI overbought ({rsi:.1f})")
        confidence += 25

    # Detect volume exhaustion
    exhaustion = detect_volume_exhaustion(
        candles,
        climax_mult=config.volume_climax_mult,
        decline_periods=config.exhaustion_decline_periods
    )

    if exhaustion.is_exhausted:
        reasons.append(exhaustion.reasoning)
        confidence += exhaustion.confidence * 0.45  # Weighted contribution

    # Need at least one strong signal
    if len(reasons) == 0:
        return False, "No sell signals detected", 0

    # Require either exhaustion OR both sentiment indicators
    if not exhaustion.is_exhausted and len(reasons) < 2:
        return False, f"Insufficient sell signals: {'; '.join(reasons)}", confidence

    return True, "; ".join(reasons), min(100, confidence)
