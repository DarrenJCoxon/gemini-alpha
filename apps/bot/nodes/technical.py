"""
Technical Analysis Agent Node.

Story 2.2: Sentiment & Technical Agents
Story 5.7: Enhanced Technical Indicators

This node performs comprehensive technical analysis on price candle data
using enhanced indicators: MACD, Bollinger Bands, OBV, ADX, VWAP, RSI, SMAs.

Implements the "Data Agent" in the Council of AI Agents,
processing raw OHLCV data into structured trading signals.

ADX is CRITICAL for contrarian strategy:
- Low ADX (< 30): Safe to trade contrarian
- High ADX (> 30): AVOID contrarian trades
"""

import logging
from typing import Any, Dict

from core.state import GraphState, TechnicalAnalysis
from services.technical_indicators import (
    IndicatorSignal,
    analyze_all_indicators,
)
from services.technical_utils import (
    calculate_rsi,
    calculate_smas,
    calculate_volume_delta,
    candles_to_dataframe,
)

logger = logging.getLogger(__name__)


def technical_node(state: GraphState) -> Dict[str, Any]:
    """
    Technical Analysis Agent with enhanced indicators.

    Calculates comprehensive technical indicators from candles_data
    and generates a trading signal with strength and reasoning based on:
    - MACD: Momentum confirmation via crossover detection
    - Bollinger Bands: Volatility and mean reversion signals
    - OBV: Accumulation/distribution divergence detection
    - ADX: Trend strength (CRITICAL - low ADX = safe for contrarian)
    - VWAP: Institutional support/resistance levels
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

    # Minimum data check (need at least 200 for enhanced indicators)
    if len(candles) < 200:
        logger.warning(f"[TechnicalAgent] Limited data: {len(candles)} candles (200+ recommended)")

        # Fall back to basic analysis if we have at least 14 candles
        if len(candles) >= 14:
            try:
                df = candles_to_dataframe(candles)
                rsi = calculate_rsi(df)
                sma_50, sma_200 = calculate_smas(df)
                volume_delta = calculate_volume_delta(df)

                technical_analysis: TechnicalAnalysis = {
                    "signal": "NEUTRAL",
                    "strength": 30,
                    "rsi": round(rsi, 2),
                    "sma_50": round(sma_50, 2),
                    "sma_200": round(sma_200, 2),
                    "volume_delta": round(volume_delta, 2),
                    "reasoning": f"Limited candle data ({len(candles)} < 200) - basic analysis only"
                }
                return {"technical_analysis": technical_analysis}
            except Exception as e:
                logger.error(f"[TechnicalAgent] Error in fallback analysis: {str(e)}")

        # Not enough data for any analysis
        technical_analysis = {
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
        # Convert candles to list of dicts if necessary
        candle_list = candles if isinstance(candles, list) else list(candles)

        # Run comprehensive analysis with all enhanced indicators
        analysis = analyze_all_indicators(candle_list)

        # Map indicator signal to trading signal
        if analysis.overall_signal in [IndicatorSignal.STRONG_BULLISH, IndicatorSignal.BULLISH]:
            signal = "BULLISH"
        elif analysis.overall_signal in [IndicatorSignal.STRONG_BEARISH, IndicatorSignal.BEARISH]:
            signal = "BEARISH"
        else:
            signal = "NEUTRAL"

        # Reduce strength if ADX says avoid contrarian
        strength = analysis.confidence
        if not analysis.safe_for_contrarian:
            strength = max(0, strength - 30)
            signal = "NEUTRAL"  # Override to neutral if strong trend
            logger.warning(f"[TechnicalAgent] ADX indicates strong trend - dampening signal")

        # Calculate volume delta for backward compatibility
        df = candles_to_dataframe(candle_list)
        volume_delta = calculate_volume_delta(df)

        technical_analysis = {
            "signal": signal,
            "strength": int(strength),
            "rsi": round(analysis.rsi, 2),
            "sma_50": round(analysis.sma_50, 2),
            "sma_200": round(analysis.sma_200, 2),
            "volume_delta": round(volume_delta, 2),
            "reasoning": analysis.reasoning,

            # Enhanced indicators (Story 5.7)
            "macd": {
                "value": round(analysis.macd.value, 6),
                "signal": analysis.macd.signal.value,
                "histogram": round(analysis.macd.auxiliary_values.get("histogram", 0), 6),
                "bullish_cross": analysis.macd.auxiliary_values.get("bullish_cross", False),
                "bearish_cross": analysis.macd.auxiliary_values.get("bearish_cross", False),
            },
            "bollinger": {
                "percent_b": round(analysis.bollinger.value, 4),
                "signal": analysis.bollinger.signal.value,
                "upper": round(analysis.bollinger.auxiliary_values.get("upper", 0), 2),
                "middle": round(analysis.bollinger.auxiliary_values.get("middle", 0), 2),
                "lower": round(analysis.bollinger.auxiliary_values.get("lower", 0), 2),
                "is_squeeze": analysis.bollinger.auxiliary_values.get("is_squeeze", False),
            },
            "obv": {
                "signal": analysis.obv.signal.value,
                "bullish_divergence": analysis.obv.auxiliary_values.get("bullish_divergence", False),
                "bearish_divergence": analysis.obv.auxiliary_values.get("bearish_divergence", False),
            },
            "adx": {
                "value": round(analysis.adx.value, 2),
                "safe_for_contrarian": analysis.safe_for_contrarian,
                "trend_direction": analysis.adx.auxiliary_values.get("trend_direction", "unknown"),
                "is_trending": analysis.adx.auxiliary_values.get("is_trending", False),
            },
            "vwap": {
                "value": round(analysis.vwap.value, 2),
                "distance_pct": round(analysis.vwap.auxiliary_values.get("distance_pct", 0), 2),
                "position": analysis.vwap.auxiliary_values.get("position", "neutral"),
            },

            # Aggregation summary
            "indicator_summary": {
                "bullish_count": analysis.bullish_count,
                "bearish_count": analysis.bearish_count,
                "overall_signal": analysis.overall_signal.value,
                "confidence": round(analysis.confidence, 2),
            }
        }

        logger.info(
            f"[TechnicalAgent] Signal: {signal} (Strength: {int(strength)}) "
            f"ADX: {analysis.adx.value:.1f} ({'Safe' if analysis.safe_for_contrarian else 'AVOID'})"
        )
        logger.debug(
            f"[TechnicalAgent] RSI: {analysis.rsi:.2f}, "
            f"MACD: {analysis.macd.signal.value}, "
            f"BB: {analysis.bollinger.signal.value}"
        )

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
