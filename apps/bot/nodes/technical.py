"""
Technical Analysis Agent Node.

Story 2.2: Sentiment & Technical Agents

This node performs technical analysis on price candle data
using indicators like RSI, moving averages, and volume analysis.

Implements the "Data Agent" in the Council of AI Agents,
processing raw OHLCV data into structured trading signals.
"""

import logging
from typing import Dict, Any

from core.state import GraphState, TechnicalAnalysis
from services.technical_utils import (
    candles_to_dataframe,
    calculate_rsi,
    calculate_smas,
    calculate_volume_delta,
    calculate_technical_signal
)

logger = logging.getLogger(__name__)


def technical_node(state: GraphState) -> Dict[str, Any]:
    """
    Technical Analysis Agent - Processes price data for trading signals.

    Calculates technical indicators from candles_data and generates
    a trading signal with strength and reasoning based on:
    - RSI (14-period): Momentum/overbought/oversold
    - SMA 50/200: Trend direction and crossovers
    - Volume Delta: Buying/selling pressure

    Args:
        state: Current GraphState containing candles_data

    Returns:
        Dict with technical_analysis field populated

    Note:
        Returns dict with only the fields to update (LangGraph pattern),
        not the full state. LangGraph merges this with existing state.
    """
    asset = state.get("asset_symbol", "UNKNOWN")
    candles = state.get("candles_data", [])

    logger.info(f"[TechnicalAgent] Analyzing {asset} with {len(candles)} candles")

    # Minimum data check (need at least 14 for RSI)
    if len(candles) < 14:
        logger.warning(f"[TechnicalAgent] Insufficient data: {len(candles)} candles")
        technical_analysis: TechnicalAnalysis = {
            "signal": "NEUTRAL",
            "strength": 0,
            "rsi": 50.0,
            "sma_50": 0.0,
            "sma_200": 0.0,
            "volume_delta": 0.0,
            "reasoning": f"Insufficient candle data for analysis ({len(candles)} < 14 required)"
        }
        return {"technical_analysis": technical_analysis}

    try:
        # Convert candles to DataFrame
        df = candles_to_dataframe(candles)
        current_price = float(df['close'].iloc[-1])

        # Calculate indicators
        rsi = calculate_rsi(df)
        sma_50, sma_200 = calculate_smas(df)
        volume_delta = calculate_volume_delta(df)

        # Generate signal
        signal, strength, reasoning = calculate_technical_signal(
            rsi, sma_50, sma_200, current_price, volume_delta
        )

        technical_analysis = {
            "signal": signal,
            "strength": strength,
            "rsi": round(rsi, 2),
            "sma_50": round(sma_50, 2),
            "sma_200": round(sma_200, 2),
            "volume_delta": round(volume_delta, 2),
            "reasoning": reasoning
        }

        logger.info(f"[TechnicalAgent] Signal: {signal} (Strength: {strength})")
        logger.debug(f"[TechnicalAgent] RSI: {rsi:.2f}, SMA50: {sma_50:.2f}, SMA200: {sma_200:.2f}")

    except Exception as e:
        logger.error(f"[TechnicalAgent] Error during analysis: {str(e)}")
        technical_analysis = {
            "signal": "NEUTRAL",
            "strength": 0,
            "rsi": 50.0,
            "sma_50": 0.0,
            "sma_200": 0.0,
            "volume_delta": 0.0,
            "reasoning": f"Error during analysis: {str(e)}"
        }
        # Note: We don't set state["error"] here since we return a dict
        # The error is captured in the reasoning field

    # Return only the fields to update (LangGraph merge pattern)
    return {"technical_analysis": technical_analysis}
