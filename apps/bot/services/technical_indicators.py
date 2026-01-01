"""
Enhanced Technical Indicators for ContrarianAI.

Story 5.7: Enhanced Technical Indicators

This module provides comprehensive technical indicator calculations using pandas_ta.
All indicators return a standardized IndicatorResult format for consistent signal
aggregation and multi-factor confirmation.

Indicators:
- MACD: Momentum confirmation via crossover detection
- Bollinger Bands: Volatility assessment and mean reversion signals
- OBV: On-Balance Volume for accumulation/distribution
- ADX: Trend strength - CRITICAL for contrarian (low ADX = safe to trade)
- VWAP: Institutional support/resistance levels

Uses pandas_ta for indicator calculations.
All indicators return standardized signal format.
"""

import logging
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List

import pandas as pd
import pandas_ta as ta

logger = logging.getLogger(__name__)


class IndicatorSignal(str, Enum):
    """
    Standardized signal types for all technical indicators.

    Signal strength hierarchy:
    - STRONG_BULLISH: High confidence buy signal
    - BULLISH: Moderate buy signal
    - NEUTRAL: No clear direction
    - BEARISH: Moderate sell signal
    - STRONG_BEARISH: High confidence sell signal
    """
    STRONG_BULLISH = "STRONG_BULLISH"
    BULLISH = "BULLISH"
    NEUTRAL = "NEUTRAL"
    BEARISH = "BEARISH"
    STRONG_BEARISH = "STRONG_BEARISH"


@dataclass
class IndicatorResult:
    """
    Standardized indicator result for consistent signal aggregation.

    Attributes:
        name: Indicator name (e.g., "MACD", "BOLLINGER")
        signal: Direction signal (STRONG_BULLISH to STRONG_BEARISH)
        value: Primary indicator value
        auxiliary_values: Additional values (e.g., signal line, histogram)
        strength: Signal strength from 0-100
        reasoning: Human-readable explanation of the signal
    """
    name: str
    signal: IndicatorSignal
    value: float
    auxiliary_values: Dict[str, Any]
    strength: float
    reasoning: str


def calculate_macd(
    candles: List[Dict[str, Any]],
    fast_period: int = 12,
    slow_period: int = 26,
    signal_period: int = 9
) -> IndicatorResult:
    """
    Calculate MACD (Moving Average Convergence Divergence).

    MACD measures momentum by comparing two EMAs.
    - MACD Line: Fast EMA - Slow EMA
    - Signal Line: EMA of MACD Line
    - Histogram: MACD Line - Signal Line

    Signals:
    - Bullish: MACD crosses above signal line (golden cross)
    - Bearish: MACD crosses below signal line (death cross)
    - Histogram expansion = momentum increasing
    - Histogram contraction = momentum decreasing

    Args:
        candles: OHLCV candle data
        fast_period: Fast EMA period (default: 12)
        slow_period: Slow EMA period (default: 26)
        signal_period: Signal line EMA period (default: 9)

    Returns:
        IndicatorResult with MACD analysis
    """
    if len(candles) < slow_period + signal_period:
        return IndicatorResult(
            name="MACD",
            signal=IndicatorSignal.NEUTRAL,
            value=0,
            auxiliary_values={},
            strength=0,
            reasoning="Insufficient data for MACD calculation"
        )

    df = pd.DataFrame(candles)

    # Ensure close column is numeric
    df['close'] = pd.to_numeric(df['close'], errors='coerce')

    macd = ta.macd(df['close'], fast=fast_period, slow=slow_period, signal=signal_period)

    if macd is None or macd.empty:
        return IndicatorResult(
            name="MACD",
            signal=IndicatorSignal.NEUTRAL,
            value=0,
            auxiliary_values={},
            strength=0,
            reasoning="MACD calculation failed"
        )

    # Extract values
    macd_col = f'MACD_{fast_period}_{slow_period}_{signal_period}'
    signal_col = f'MACDs_{fast_period}_{slow_period}_{signal_period}'
    hist_col = f'MACDh_{fast_period}_{slow_period}_{signal_period}'

    macd_line = float(macd.iloc[-1][macd_col])
    signal_line = float(macd.iloc[-1][signal_col])
    histogram = float(macd.iloc[-1][hist_col])

    # Check for NaN values
    if pd.isna(macd_line) or pd.isna(signal_line) or pd.isna(histogram):
        return IndicatorResult(
            name="MACD",
            signal=IndicatorSignal.NEUTRAL,
            value=0,
            auxiliary_values={},
            strength=0,
            reasoning="MACD values contain NaN"
        )

    # Previous values for crossover detection
    prev_macd = float(macd.iloc[-2][macd_col])
    prev_signal = float(macd.iloc[-2][signal_col])

    # Detect crossovers
    bullish_cross = prev_macd < prev_signal and macd_line > signal_line
    bearish_cross = prev_macd > prev_signal and macd_line < signal_line

    # Determine signal
    if bullish_cross:
        signal = IndicatorSignal.STRONG_BULLISH
        reasoning = f"MACD bullish crossover: MACD ({macd_line:.4f}) crossed above signal ({signal_line:.4f})"
        strength = min(100, abs(histogram) * 1000)
    elif bearish_cross:
        signal = IndicatorSignal.STRONG_BEARISH
        reasoning = f"MACD bearish crossover: MACD ({macd_line:.4f}) crossed below signal ({signal_line:.4f})"
        strength = min(100, abs(histogram) * 1000)
    elif macd_line > signal_line and histogram > 0:
        signal = IndicatorSignal.BULLISH
        reasoning = f"MACD above signal with positive histogram ({histogram:.4f})"
        strength = min(80, abs(histogram) * 800)
    elif macd_line < signal_line and histogram < 0:
        signal = IndicatorSignal.BEARISH
        reasoning = f"MACD below signal with negative histogram ({histogram:.4f})"
        strength = min(80, abs(histogram) * 800)
    else:
        signal = IndicatorSignal.NEUTRAL
        reasoning = f"MACD neutral: Line={macd_line:.4f}, Signal={signal_line:.4f}"
        strength = 30

    return IndicatorResult(
        name="MACD",
        signal=signal,
        value=float(macd_line),
        auxiliary_values={
            "signal_line": float(signal_line),
            "histogram": float(histogram),
            "bullish_cross": bullish_cross,
            "bearish_cross": bearish_cross
        },
        strength=strength,
        reasoning=reasoning
    )


def calculate_bollinger_bands(
    candles: List[Dict[str, Any]],
    period: int = 20,
    std_dev: float = 2.0
) -> IndicatorResult:
    """
    Calculate Bollinger Bands for volatility and mean reversion.

    Bollinger Bands consist of:
    - Middle Band: SMA(period)
    - Upper Band: Middle + (std_dev * standard deviation)
    - Lower Band: Middle - (std_dev * standard deviation)

    Signals:
    - Price at lower band: Potential oversold (contrarian buy)
    - Price at upper band: Potential overbought (contrarian sell)
    - Band squeeze: Low volatility, breakout imminent
    - Band expansion: High volatility, trend in progress

    Args:
        candles: OHLCV candle data
        period: SMA period (default: 20)
        std_dev: Standard deviation multiplier (default: 2.0)

    Returns:
        IndicatorResult with Bollinger Bands analysis
    """
    if len(candles) < period:
        return IndicatorResult(
            name="BOLLINGER",
            signal=IndicatorSignal.NEUTRAL,
            value=0,
            auxiliary_values={},
            strength=0,
            reasoning="Insufficient data for Bollinger Bands"
        )

    df = pd.DataFrame(candles)

    # Ensure close column is numeric
    df['close'] = pd.to_numeric(df['close'], errors='coerce')

    bb = ta.bbands(df['close'], length=period, std=std_dev)

    if bb is None or bb.empty:
        return IndicatorResult(
            name="BOLLINGER",
            signal=IndicatorSignal.NEUTRAL,
            value=0,
            auxiliary_values={},
            strength=0,
            reasoning="Bollinger Bands calculation failed"
        )

    current_price = float(df['close'].iloc[-1])

    # Column names for bbands - pandas_ta uses format BBx_length_std_std
    # e.g., BBU_20_2.0_2.0 for upper band with period 20 and std 2.0
    upper_col = f'BBU_{period}_{std_dev}_{std_dev}'
    middle_col = f'BBM_{period}_{std_dev}_{std_dev}'
    lower_col = f'BBL_{period}_{std_dev}_{std_dev}'
    bandwidth_col = f'BBB_{period}_{std_dev}_{std_dev}'
    percent_b_col = f'BBP_{period}_{std_dev}_{std_dev}'

    # Try to get columns, handle different pandas_ta versions
    try:
        upper = float(bb.iloc[-1][upper_col])
        middle = float(bb.iloc[-1][middle_col])
        lower = float(bb.iloc[-1][lower_col])
        bandwidth = float(bb.iloc[-1][bandwidth_col])
        percent_b = float(bb.iloc[-1][percent_b_col])
    except KeyError:
        # Fallback for older pandas_ta versions with single std in name
        try:
            upper_col = f'BBU_{period}_{std_dev}'
            middle_col = f'BBM_{period}_{std_dev}'
            lower_col = f'BBL_{period}_{std_dev}'
            bandwidth_col = f'BBB_{period}_{std_dev}'
            percent_b_col = f'BBP_{period}_{std_dev}'
            upper = float(bb.iloc[-1][upper_col])
            middle = float(bb.iloc[-1][middle_col])
            lower = float(bb.iloc[-1][lower_col])
            bandwidth = float(bb.iloc[-1][bandwidth_col])
            percent_b = float(bb.iloc[-1][percent_b_col])
        except KeyError:
            return IndicatorResult(
                name="BOLLINGER",
                signal=IndicatorSignal.NEUTRAL,
                value=0,
                auxiliary_values={},
                strength=0,
                reasoning=f"Bollinger Bands column naming issue: {bb.columns.tolist()}"
            )

    # Check for NaN values
    if any(pd.isna(v) for v in [upper, middle, lower, bandwidth, percent_b]):
        return IndicatorResult(
            name="BOLLINGER",
            signal=IndicatorSignal.NEUTRAL,
            value=0,
            auxiliary_values={},
            strength=0,
            reasoning="Bollinger Bands values contain NaN"
        )

    # Calculate band width for squeeze detection
    avg_bandwidth = bb[bandwidth_col].rolling(20).mean().iloc[-1]
    is_squeeze = bandwidth < avg_bandwidth * 0.8 if not pd.isna(avg_bandwidth) else False

    # Determine signal based on %B (position within bands)
    if percent_b <= 0.05:  # At or below lower band
        signal = IndicatorSignal.STRONG_BULLISH
        reasoning = f"Price at lower Bollinger Band (%B: {percent_b:.2f}) - oversold, mean reversion likely"
        strength = 85
    elif percent_b <= 0.20:
        signal = IndicatorSignal.BULLISH
        reasoning = f"Price near lower Bollinger Band (%B: {percent_b:.2f})"
        strength = 65
    elif percent_b >= 0.95:  # At or above upper band
        signal = IndicatorSignal.STRONG_BEARISH
        reasoning = f"Price at upper Bollinger Band (%B: {percent_b:.2f}) - overbought, mean reversion likely"
        strength = 85
    elif percent_b >= 0.80:
        signal = IndicatorSignal.BEARISH
        reasoning = f"Price near upper Bollinger Band (%B: {percent_b:.2f})"
        strength = 65
    else:
        signal = IndicatorSignal.NEUTRAL
        reasoning = f"Price within Bollinger Bands (%B: {percent_b:.2f})"
        strength = 30

    if is_squeeze:
        reasoning += " - SQUEEZE detected (low volatility, breakout imminent)"

    return IndicatorResult(
        name="BOLLINGER",
        signal=signal,
        value=percent_b,
        auxiliary_values={
            "upper": upper,
            "middle": middle,
            "lower": lower,
            "bandwidth": bandwidth,
            "is_squeeze": is_squeeze,
            "price_position": "lower" if percent_b < 0.2 else "upper" if percent_b > 0.8 else "middle"
        },
        strength=strength,
        reasoning=reasoning
    )


def calculate_obv(
    candles: List[Dict[str, Any]],
    signal_period: int = 20
) -> IndicatorResult:
    """
    Calculate On-Balance Volume (OBV) for accumulation/distribution.

    OBV tracks cumulative volume flow:
    - Price up: Add volume to OBV
    - Price down: Subtract volume from OBV

    Signals:
    - OBV rising while price falling: Accumulation (bullish divergence)
    - OBV falling while price rising: Distribution (bearish divergence)
    - OBV confirming price trend: Healthy trend

    Args:
        candles: OHLCV candle data
        signal_period: Period for OBV SMA (trend detection)

    Returns:
        IndicatorResult with OBV analysis
    """
    if len(candles) < signal_period + 5:
        return IndicatorResult(
            name="OBV",
            signal=IndicatorSignal.NEUTRAL,
            value=0,
            auxiliary_values={},
            strength=0,
            reasoning="Insufficient data for OBV calculation"
        )

    df = pd.DataFrame(candles)

    # Ensure columns are numeric
    df['close'] = pd.to_numeric(df['close'], errors='coerce')
    df['volume'] = pd.to_numeric(df['volume'], errors='coerce')

    obv = ta.obv(df['close'], df['volume'])

    if obv is None or obv.empty:
        return IndicatorResult(
            name="OBV",
            signal=IndicatorSignal.NEUTRAL,
            value=0,
            auxiliary_values={},
            strength=0,
            reasoning="OBV calculation failed"
        )

    # Calculate OBV SMA for trend
    obv_sma = obv.rolling(signal_period).mean()

    current_obv = float(obv.iloc[-1])
    obv_sma_value = float(obv_sma.iloc[-1])
    prev_obv_sma = float(obv_sma.iloc[-signal_period])

    # Check for NaN values
    if pd.isna(current_obv) or pd.isna(obv_sma_value) or pd.isna(prev_obv_sma):
        return IndicatorResult(
            name="OBV",
            signal=IndicatorSignal.NEUTRAL,
            value=0,
            auxiliary_values={},
            strength=0,
            reasoning="OBV values contain NaN"
        )

    # Price direction
    current_price = float(df['close'].iloc[-1])
    prev_price = float(df['close'].iloc[-signal_period])
    price_change_pct = (current_price - prev_price) / prev_price * 100 if prev_price != 0 else 0

    # OBV direction
    obv_change_pct = (obv_sma_value - prev_obv_sma) / abs(prev_obv_sma) * 100 if prev_obv_sma != 0 else 0

    # Detect divergences
    bullish_divergence = price_change_pct < -5 and obv_change_pct > 5  # Price down, OBV up
    bearish_divergence = price_change_pct > 5 and obv_change_pct < -5   # Price up, OBV down

    # Determine signal
    if bullish_divergence:
        signal = IndicatorSignal.STRONG_BULLISH
        reasoning = f"OBV bullish divergence: Price down {price_change_pct:.1f}% but OBV up {obv_change_pct:.1f}% (accumulation)"
        strength = 80
    elif bearish_divergence:
        signal = IndicatorSignal.STRONG_BEARISH
        reasoning = f"OBV bearish divergence: Price up {price_change_pct:.1f}% but OBV down {obv_change_pct:.1f}% (distribution)"
        strength = 80
    elif current_obv > obv_sma_value and obv_change_pct > 0:
        signal = IndicatorSignal.BULLISH
        reasoning = f"OBV above SMA and rising: accumulation in progress"
        strength = 60
    elif current_obv < obv_sma_value and obv_change_pct < 0:
        signal = IndicatorSignal.BEARISH
        reasoning = f"OBV below SMA and falling: distribution in progress"
        strength = 60
    else:
        signal = IndicatorSignal.NEUTRAL
        reasoning = f"OBV neutral: {current_obv:.0f} vs SMA {obv_sma_value:.0f}"
        strength = 30

    return IndicatorResult(
        name="OBV",
        signal=signal,
        value=current_obv,
        auxiliary_values={
            "obv_sma": obv_sma_value,
            "obv_change_pct": obv_change_pct,
            "bullish_divergence": bullish_divergence,
            "bearish_divergence": bearish_divergence
        },
        strength=strength,
        reasoning=reasoning
    )


def calculate_adx(
    candles: List[Dict[str, Any]],
    period: int = 14
) -> IndicatorResult:
    """
    Calculate ADX (Average Directional Index) for trend strength.

    ADX measures trend strength (not direction):
    - ADX < 20: Weak trend (range-bound) - GOOD for contrarian
    - ADX 20-40: Developing trend - CAUTION
    - ADX 40-60: Strong trend - AVOID contrarian trades
    - ADX > 60: Very strong trend - DO NOT trade contrarian

    CRITICAL FOR CONTRARIAN STRATEGY:
    - We WANT low ADX (weak trends are mean-reverting)
    - We AVOID high ADX (strong trends continue)

    Args:
        candles: OHLCV candle data
        period: ADX period (default: 14)

    Returns:
        IndicatorResult with ADX analysis
    """
    if len(candles) < period * 2:
        return IndicatorResult(
            name="ADX",
            signal=IndicatorSignal.NEUTRAL,
            value=0,
            auxiliary_values={},
            strength=0,
            reasoning="Insufficient data for ADX calculation"
        )

    df = pd.DataFrame(candles)

    # Ensure columns are numeric
    df['high'] = pd.to_numeric(df['high'], errors='coerce')
    df['low'] = pd.to_numeric(df['low'], errors='coerce')
    df['close'] = pd.to_numeric(df['close'], errors='coerce')

    adx_data = ta.adx(df['high'], df['low'], df['close'], length=period)

    if adx_data is None or adx_data.empty:
        return IndicatorResult(
            name="ADX",
            signal=IndicatorSignal.NEUTRAL,
            value=0,
            auxiliary_values={},
            strength=0,
            reasoning="ADX calculation failed"
        )

    adx_col = f'ADX_{period}'
    dmp_col = f'DMP_{period}'
    dmn_col = f'DMN_{period}'

    adx_value = float(adx_data.iloc[-1][adx_col])
    plus_di = float(adx_data.iloc[-1][dmp_col])
    minus_di = float(adx_data.iloc[-1][dmn_col])

    # Check for NaN values
    if pd.isna(adx_value) or pd.isna(plus_di) or pd.isna(minus_di):
        return IndicatorResult(
            name="ADX",
            signal=IndicatorSignal.NEUTRAL,
            value=0,
            auxiliary_values={},
            strength=0,
            reasoning="ADX values contain NaN"
        )

    # For CONTRARIAN strategy, low ADX is GOOD
    # We invert the signal interpretation
    if adx_value < 20:
        signal = IndicatorSignal.STRONG_BULLISH  # Weak trend = good for contrarian
        reasoning = f"ADX {adx_value:.1f}: Weak trend - FAVORABLE for contrarian strategy"
        strength = 80
    elif adx_value < 30:
        signal = IndicatorSignal.BULLISH
        reasoning = f"ADX {adx_value:.1f}: Moderate trend - acceptable for contrarian"
        strength = 60
    elif adx_value < 40:
        signal = IndicatorSignal.NEUTRAL
        reasoning = f"ADX {adx_value:.1f}: Developing trend - use caution"
        strength = 40
    elif adx_value < 60:
        signal = IndicatorSignal.BEARISH
        reasoning = f"ADX {adx_value:.1f}: Strong trend - AVOID contrarian trades"
        strength = 70
    else:
        signal = IndicatorSignal.STRONG_BEARISH
        reasoning = f"ADX {adx_value:.1f}: Very strong trend - DO NOT trade contrarian"
        strength = 90

    # Determine trend direction from DI lines
    trend_direction = "up" if plus_di > minus_di else "down"

    return IndicatorResult(
        name="ADX",
        signal=signal,
        value=adx_value,
        auxiliary_values={
            "plus_di": plus_di,
            "minus_di": minus_di,
            "trend_direction": trend_direction,
            "is_trending": adx_value >= 25,
            "safe_for_contrarian": adx_value < 30
        },
        strength=strength,
        reasoning=reasoning + f" (Trend direction: {trend_direction})"
    )


def calculate_vwap(
    candles: List[Dict[str, Any]]
) -> IndicatorResult:
    """
    Calculate VWAP (Volume Weighted Average Price).

    VWAP represents the average price weighted by volume.
    Institutional traders often use VWAP as a benchmark.

    Signals:
    - Price below VWAP: Potentially undervalued (buy)
    - Price above VWAP: Potentially overvalued (sell)
    - VWAP acts as dynamic support/resistance

    Args:
        candles: OHLCV candle data (ideally intraday)

    Returns:
        IndicatorResult with VWAP analysis
    """
    if len(candles) < 10:
        return IndicatorResult(
            name="VWAP",
            signal=IndicatorSignal.NEUTRAL,
            value=0,
            auxiliary_values={},
            strength=0,
            reasoning="Insufficient data for VWAP calculation"
        )

    df = pd.DataFrame(candles)

    # Ensure columns are numeric
    df['high'] = pd.to_numeric(df['high'], errors='coerce')
    df['low'] = pd.to_numeric(df['low'], errors='coerce')
    df['close'] = pd.to_numeric(df['close'], errors='coerce')
    df['volume'] = pd.to_numeric(df['volume'], errors='coerce')

    # VWAP requires DatetimeIndex
    if 'timestamp' in df.columns:
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        df.set_index('timestamp', inplace=True)
        df = df.sort_index()

    # Try pandas_ta VWAP first
    vwap = ta.vwap(df['high'], df['low'], df['close'], df['volume'])

    # If pandas_ta fails (no DatetimeIndex), calculate manually
    if vwap is None or (hasattr(vwap, 'empty') and vwap.empty):
        # Manual VWAP calculation: cumulative(volume * typical_price) / cumulative(volume)
        typical_price = (df['high'] + df['low'] + df['close']) / 3
        cumulative_tp_vol = (typical_price * df['volume']).cumsum()
        cumulative_vol = df['volume'].cumsum()
        vwap = cumulative_tp_vol / cumulative_vol

    if vwap is None or vwap.empty:
        return IndicatorResult(
            name="VWAP",
            signal=IndicatorSignal.NEUTRAL,
            value=0,
            auxiliary_values={},
            strength=0,
            reasoning="VWAP calculation failed"
        )

    current_price = float(df['close'].iloc[-1])
    vwap_value = float(vwap.iloc[-1])

    # Check for NaN values
    if pd.isna(vwap_value):
        return IndicatorResult(
            name="VWAP",
            signal=IndicatorSignal.NEUTRAL,
            value=0,
            auxiliary_values={},
            strength=0,
            reasoning="VWAP value is NaN"
        )

    # Calculate distance from VWAP
    distance_pct = ((current_price - vwap_value) / vwap_value) * 100 if vwap_value != 0 else 0

    # Determine signal based on distance from VWAP
    if distance_pct <= -3:  # More than 3% below VWAP
        signal = IndicatorSignal.STRONG_BULLISH
        reasoning = f"Price {abs(distance_pct):.1f}% BELOW VWAP - strong support zone"
        strength = 75
    elif distance_pct <= -1:
        signal = IndicatorSignal.BULLISH
        reasoning = f"Price {abs(distance_pct):.1f}% below VWAP - potential support"
        strength = 55
    elif distance_pct >= 3:  # More than 3% above VWAP
        signal = IndicatorSignal.STRONG_BEARISH
        reasoning = f"Price {distance_pct:.1f}% ABOVE VWAP - strong resistance zone"
        strength = 75
    elif distance_pct >= 1:
        signal = IndicatorSignal.BEARISH
        reasoning = f"Price {distance_pct:.1f}% above VWAP - potential resistance"
        strength = 55
    else:
        signal = IndicatorSignal.NEUTRAL
        reasoning = f"Price near VWAP ({distance_pct:+.1f}%)"
        strength = 30

    return IndicatorResult(
        name="VWAP",
        signal=signal,
        value=vwap_value,
        auxiliary_values={
            "current_price": current_price,
            "distance_pct": distance_pct,
            "position": "below" if distance_pct < 0 else "above"
        },
        strength=strength,
        reasoning=reasoning
    )


@dataclass
class ComprehensiveTechnicalAnalysis:
    """
    Complete technical analysis with all enhanced indicators.

    Aggregates signals from all indicators for multi-factor
    confirmation in the contrarian trading strategy.

    Attributes:
        macd: MACD indicator result
        bollinger: Bollinger Bands result
        obv: On-Balance Volume result
        adx: ADX trend strength result
        vwap: VWAP result
        rsi: Relative Strength Index value
        sma_50: 50-period SMA value
        sma_200: 200-period SMA value
        overall_signal: Aggregated signal direction
        bullish_count: Number of bullish signals (strong counts double)
        bearish_count: Number of bearish signals (strong counts double)
        confidence: Aggregated confidence score 0-100
        safe_for_contrarian: True if ADX indicates safe for contrarian trading
        reasoning: Human-readable summary
    """
    # Individual indicators
    macd: IndicatorResult
    bollinger: IndicatorResult
    obv: IndicatorResult
    adx: IndicatorResult
    vwap: IndicatorResult

    # Existing indicators (from Story 2.2)
    rsi: float
    sma_50: float
    sma_200: float

    # Aggregated signal
    overall_signal: IndicatorSignal
    bullish_count: int
    bearish_count: int
    confidence: float
    safe_for_contrarian: bool  # Based on ADX
    reasoning: str


def analyze_all_indicators(
    candles: List[Dict[str, Any]]
) -> ComprehensiveTechnicalAnalysis:
    """
    Run all technical indicators and aggregate signals.

    This function calculates all enhanced indicators and combines
    them into a comprehensive analysis with an overall signal.

    Signal aggregation logic:
    - Strong signals (STRONG_BULLISH/STRONG_BEARISH) count double
    - Net signal determines overall direction
    - Confidence is based on average strength and signal agreement

    Args:
        candles: OHLCV candle data

    Returns:
        ComprehensiveTechnicalAnalysis with all indicators
    """
    # Calculate all enhanced indicators
    macd_result = calculate_macd(candles)
    bollinger_result = calculate_bollinger_bands(candles)
    obv_result = calculate_obv(candles)
    adx_result = calculate_adx(candles)
    vwap_result = calculate_vwap(candles)

    # Calculate existing indicators (RSI, SMA)
    df = pd.DataFrame(candles)
    df['close'] = pd.to_numeric(df['close'], errors='coerce')

    rsi = ta.rsi(df['close'], length=14)
    sma_50 = ta.sma(df['close'], length=50)
    sma_200 = ta.sma(df['close'], length=200)

    rsi_value = float(rsi.iloc[-1]) if rsi is not None and not rsi.empty and not pd.isna(rsi.iloc[-1]) else 50.0
    sma_50_value = float(sma_50.iloc[-1]) if sma_50 is not None and not sma_50.empty and not pd.isna(sma_50.iloc[-1]) else 0.0
    sma_200_value = float(sma_200.iloc[-1]) if sma_200 is not None and not sma_200.empty and not pd.isna(sma_200.iloc[-1]) else 0.0

    # Count bullish vs bearish signals
    all_results = [macd_result, bollinger_result, obv_result, adx_result, vwap_result]

    bullish_count = sum(
        1 for r in all_results
        if r.signal in [IndicatorSignal.BULLISH, IndicatorSignal.STRONG_BULLISH]
    )
    bearish_count = sum(
        1 for r in all_results
        if r.signal in [IndicatorSignal.BEARISH, IndicatorSignal.STRONG_BEARISH]
    )

    # Strong signals count double
    bullish_count += sum(
        1 for r in all_results
        if r.signal == IndicatorSignal.STRONG_BULLISH
    )
    bearish_count += sum(
        1 for r in all_results
        if r.signal == IndicatorSignal.STRONG_BEARISH
    )

    # Determine overall signal
    net_signal = bullish_count - bearish_count

    if net_signal >= 4:
        overall_signal = IndicatorSignal.STRONG_BULLISH
    elif net_signal >= 2:
        overall_signal = IndicatorSignal.BULLISH
    elif net_signal <= -4:
        overall_signal = IndicatorSignal.STRONG_BEARISH
    elif net_signal <= -2:
        overall_signal = IndicatorSignal.BEARISH
    else:
        overall_signal = IndicatorSignal.NEUTRAL

    # Calculate confidence
    avg_strength = sum(r.strength for r in all_results) / len(all_results) if all_results else 0
    confidence = avg_strength * (1 + abs(net_signal) / 10)
    confidence = min(confidence, 100)

    # Check if safe for contrarian (based on ADX)
    safe_for_contrarian = adx_result.auxiliary_values.get("safe_for_contrarian", True)

    reasoning = (
        f"Technical Analysis: {bullish_count} bullish, {bearish_count} bearish signals. "
        f"Overall: {overall_signal.value}. "
        f"ADX: {'Safe' if safe_for_contrarian else 'AVOID'} for contrarian. "
        f"RSI: {rsi_value:.1f}"
    )

    return ComprehensiveTechnicalAnalysis(
        macd=macd_result,
        bollinger=bollinger_result,
        obv=obv_result,
        adx=adx_result,
        vwap=vwap_result,
        rsi=rsi_value,
        sma_50=sma_50_value,
        sma_200=sma_200_value,
        overall_signal=overall_signal,
        bullish_count=bullish_count,
        bearish_count=bearish_count,
        confidence=confidence,
        safe_for_contrarian=safe_for_contrarian,
        reasoning=reasoning
    )
