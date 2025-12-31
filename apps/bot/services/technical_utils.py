"""
Technical Analysis Utilities for the Trading Bot.

Story 2.2: Sentiment & Technical Agents

This module provides technical analysis calculations using pandas-ta
for indicators like RSI, SMA, and volume delta analysis.
"""

import pandas as pd
import pandas_ta as ta
from typing import List, Dict, Any, Tuple


def candles_to_dataframe(candles: List[Dict[str, Any]]) -> pd.DataFrame:
    """
    Convert candle data list to pandas DataFrame.

    Transforms a list of candle dictionaries into a properly indexed
    DataFrame suitable for pandas-ta indicator calculations.

    Args:
        candles: List of candle dictionaries with keys:
            timestamp, open, high, low, close, volume

    Returns:
        DataFrame with timestamp index and OHLCV columns

    Raises:
        ValueError: If candles list is empty
    """
    if not candles:
        raise ValueError("Candles list cannot be empty")

    df = pd.DataFrame(candles)
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    df.set_index('timestamp', inplace=True)
    df = df.sort_index()

    # Ensure numeric types for calculations
    for col in ['open', 'high', 'low', 'close', 'volume']:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce')

    return df


def calculate_rsi(df: pd.DataFrame, period: int = 14) -> float:
    """
    Calculate RSI (Relative Strength Index) indicator.

    RSI measures momentum by comparing recent gains to recent losses.
    Values below 30 indicate oversold conditions (potential buy),
    values above 70 indicate overbought conditions (potential sell).

    Args:
        df: DataFrame with 'close' column
        period: RSI calculation period (default: 14)

    Returns:
        Current RSI value (0-100), or 50.0 if insufficient data
    """
    if len(df) < period + 1:
        return 50.0

    try:
        rsi = ta.rsi(df['close'], length=period)
        if rsi is None or rsi.empty:
            return 50.0
        last_value = rsi.iloc[-1]
        if pd.isna(last_value):
            return 50.0
        return float(last_value)
    except Exception:
        return 50.0


def calculate_smas(df: pd.DataFrame) -> Tuple[float, float]:
    """
    Calculate SMA 50 and SMA 200 (Simple Moving Averages).

    SMA50 crossing above SMA200 is a "Golden Cross" (bullish).
    SMA50 crossing below SMA200 is a "Death Cross" (bearish).
    Price above both SMAs indicates strong uptrend.

    Args:
        df: DataFrame with 'close' column

    Returns:
        Tuple of (SMA50 value, SMA200 value), 0.0 if insufficient data
    """
    sma_50_value = 0.0
    sma_200_value = 0.0

    try:
        if len(df) >= 50:
            sma_50 = ta.sma(df['close'], length=50)
            if sma_50 is not None and not sma_50.empty:
                last_50 = sma_50.iloc[-1]
                if not pd.isna(last_50):
                    sma_50_value = float(last_50)

        if len(df) >= 200:
            sma_200 = ta.sma(df['close'], length=200)
            if sma_200 is not None and not sma_200.empty:
                last_200 = sma_200.iloc[-1]
                if not pd.isna(last_200):
                    sma_200_value = float(last_200)
    except Exception:
        pass

    return (sma_50_value, sma_200_value)


def calculate_volume_delta(df: pd.DataFrame, period: int = 20) -> float:
    """
    Calculate volume change vs rolling average.

    Measures current volume as percentage change from the average.
    High positive values indicate accumulation (buying pressure).
    High negative values indicate distribution (selling pressure).

    Args:
        df: DataFrame with 'volume' column
        period: Rolling average period (default: 20)

    Returns:
        Volume delta as percentage, e.g., 50.0 means 50% above average
    """
    if len(df) < period:
        return 0.0

    try:
        avg_volume = df['volume'].rolling(period).mean().iloc[-1]
        current_volume = df['volume'].iloc[-1]

        if pd.isna(avg_volume) or avg_volume == 0:
            return 0.0

        delta = ((current_volume - avg_volume) / avg_volume) * 100
        return float(delta)
    except Exception:
        return 0.0


def calculate_technical_signal(
    rsi: float,
    sma_50: float,
    sma_200: float,
    current_price: float,
    volume_delta: float
) -> Tuple[str, int, str]:
    """
    Calculate technical signal based on indicators.

    Uses a points-based scoring system to determine signal direction
    and strength. Follows the ContrarianAI philosophy where extreme
    conditions (oversold/overbought) signal potential reversals.

    Signal Logic:
    - BULLISH: Price > SMA200, RSI < 40 (oversold bounce), positive volume
    - BEARISH: Price < SMA200, RSI > 70 (overbought), negative volume
    - NEUTRAL: Mixed signals or insufficient data

    Args:
        rsi: Current RSI value (0-100)
        sma_50: 50-period SMA value
        sma_200: 200-period SMA value
        current_price: Current asset price
        volume_delta: Volume change percentage

    Returns:
        Tuple of (signal, strength, reasoning):
            signal: "BULLISH", "BEARISH", or "NEUTRAL"
            strength: Signal strength 0-100
            reasoning: Human-readable explanation
    """
    bullish_points = 0
    bearish_points = 0
    reasons = []

    # Price vs SMA200 (Golden Cross territory)
    if sma_200 > 0 and current_price > sma_200:
        bullish_points += 30
        reasons.append(f"Price ${current_price:.2f} above SMA200 ${sma_200:.2f}")
    elif sma_200 > 0:
        bearish_points += 30
        reasons.append(f"Price ${current_price:.2f} below SMA200 ${sma_200:.2f}")

    # RSI conditions
    if rsi < 30:
        bullish_points += 40  # Heavily oversold = buy opportunity
        reasons.append(f"RSI {rsi:.1f} indicates extreme oversold")
    elif rsi < 40:
        bullish_points += 20
        reasons.append(f"RSI {rsi:.1f} indicates oversold")
    elif rsi > 70:
        bearish_points += 40
        reasons.append(f"RSI {rsi:.1f} indicates overbought")
    elif rsi > 60:
        bearish_points += 20
        reasons.append(f"RSI {rsi:.1f} approaching overbought")

    # Volume confirmation
    if volume_delta > 50:
        bullish_points += 15
        reasons.append(f"Volume {volume_delta:.1f}% above average (accumulation)")
    elif volume_delta < -30:
        bearish_points += 15
        reasons.append(f"Volume {volume_delta:.1f}% below average")

    # SMA crossover (50 vs 200)
    if sma_50 > 0 and sma_200 > 0:
        if sma_50 > sma_200:
            bullish_points += 15
            reasons.append("SMA50 above SMA200 (Golden Cross)")
        else:
            bearish_points += 15
            reasons.append("SMA50 below SMA200 (Death Cross)")

    # Determine signal
    total_points = bullish_points + bearish_points
    if total_points == 0:
        return "NEUTRAL", 50, "Insufficient data for analysis"

    if bullish_points > bearish_points:
        strength = min(100, int((bullish_points / total_points) * 100))
        return "BULLISH", strength, " | ".join(reasons)
    elif bearish_points > bullish_points:
        strength = min(100, int((bearish_points / total_points) * 100))
        return "BEARISH", strength, " | ".join(reasons)
    else:
        return "NEUTRAL", 50, " | ".join(reasons)
