"""
LangGraph State Definitions for the Council of AI Agents.

Story 2.1: LangGraph State Machine Setup

This module defines the GraphState TypedDict that carries trading context
between different AI agents in the decision-making pipeline.

State Flow:
    Start -> SentimentAgent -> TechnicalAgent -> VisionAgent -> MasterNode -> End

Each agent receives the full state, processes its designated fields,
and passes the enriched state to the next agent in the pipeline.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional, TypedDict


class CandleData(TypedDict):
    """
    OHLCV candle data from exchange (Kraken).

    Represents a single price candle for technical analysis
    and chart visualization.

    Attributes:
        timestamp: UTC timestamp of the candle
        open: Opening price in USD
        high: Highest price during the period
        low: Lowest price during the period
        close: Closing price in USD
        volume: Trading volume in base currency
    """
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float


class TechnicalAnalysis(TypedDict):
    """
    Output from the Technical Analysis Agent.

    Contains technical indicator values and trading signal
    derived from price and volume data.

    Attributes:
        signal: Trading signal - "BULLISH", "BEARISH", or "NEUTRAL"
        strength: Signal strength from 0-100 (higher = stronger conviction)
        rsi: Relative Strength Index (0-100)
        sma_50: 50-period Simple Moving Average
        sma_200: 200-period Simple Moving Average
        volume_delta: Volume change percentage vs average
        reasoning: Explanation of the technical analysis
    """
    signal: str  # "BULLISH", "BEARISH", "NEUTRAL"
    strength: int  # 0-100
    rsi: float
    sma_50: float
    sma_200: float
    volume_delta: float
    reasoning: str


class SentimentAnalysis(TypedDict):
    """
    Output from the Sentiment Analysis Agent.

    Contains aggregated sentiment metrics from social sources
    and crypto-specific fear/greed indicators.

    Attributes:
        fear_score: Fear/Greed score 0-100 (lower = more fear, higher = more greed)
        summary: Natural language summary of sentiment landscape
        source_count: Number of sentiment sources analyzed
    """
    fear_score: int  # 0-100 (lower = more fear)
    summary: str
    source_count: int


class VisionAnalysis(TypedDict):
    """
    Output from the Vision Analysis Agent.

    Contains chart pattern analysis from visual inspection
    of generated candlestick charts using vision LLM.

    Attributes:
        patterns_detected: List of pattern names found (e.g., "head_and_shoulders")
        confidence_score: Pattern detection confidence 0-100
        description: Natural language description of chart observations
        is_valid: False if "scam wick" or manipulation detected
    """
    patterns_detected: List[str]
    confidence_score: int  # 0-100
    description: str
    is_valid: bool  # False if "scam wick" detected


class FinalDecision(TypedDict):
    """
    Final trading decision from the Master Node.

    Synthesizes all agent analyses into a single trading action
    with confidence rating and explanation.

    Attributes:
        action: Trading action - "BUY", "SELL", or "HOLD"
        confidence: Decision confidence 0-100
        reasoning: Explanation of the decision rationale
        timestamp: UTC timestamp when decision was made
    """
    action: str  # "BUY", "SELL", "HOLD"
    confidence: int  # 0-100
    reasoning: str
    timestamp: datetime


class MultiFactorAnalysisState(TypedDict, total=False):
    """
    Multi-factor analysis result state (Story 5.3).

    Contains the aggregated results from multi-factor confirmation
    analysis, including which factors were triggered for BUY and SELL.

    Attributes:
        action: The suggested action from multi-factor analysis
        buy_factors_met: Number of BUY factors that were triggered
        sell_factors_met: Number of SELL factors that were triggered
        buy_factors_triggered: List of BUY factor names that were triggered
        sell_factors_triggered: List of SELL factor names that were triggered
        confidence: Confidence percentage based on weighted factor scoring
        reasoning: Human-readable summary of the multi-factor analysis
    """
    action: str
    buy_factors_met: int
    sell_factors_met: int
    buy_factors_triggered: List[str]
    sell_factors_triggered: List[str]
    confidence: float
    reasoning: str


class GraphState(TypedDict):
    """
    Main state container for the Council of AI Agents.

    This TypedDict is passed through all nodes in the LangGraph
    state machine. Each agent reads its required inputs and
    writes its analysis outputs to the appropriate fields.

    Input Fields (provided at start):
        asset_symbol: Trading pair symbol (e.g., "SOLUSD")
        candles_data: Historical OHLCV data for analysis
        sentiment_data: Raw sentiment entries from database

    Output Fields (populated by agents):
        technical_analysis: Populated by TechnicalAgent
        sentiment_analysis: Populated by SentimentAgent
        vision_analysis: Populated by VisionAgent
        final_decision: Populated by MasterNode

    Error Handling:
        error: Contains error message if any agent fails,
               allowing graceful degradation instead of crash

    Example:
        initial_state = GraphState(
            asset_symbol="SOLUSD",
            candles_data=[...],
            sentiment_data=[...],
            technical_analysis=None,
            sentiment_analysis=None,
            vision_analysis=None,
            final_decision=None,
            error=None
        )
        final_state = graph.invoke(initial_state)
    """
    # Input fields (provided at graph entry)
    asset_symbol: str
    candles_data: List[CandleData]
    sentiment_data: List[Dict[str, Any]]

    # Output fields (populated by agents)
    technical_analysis: Optional[TechnicalAnalysis]
    sentiment_analysis: Optional[SentimentAnalysis]
    vision_analysis: Optional[VisionAnalysis]
    final_decision: Optional[FinalDecision]

    # Multi-factor analysis (Story 5.3)
    multi_factor_analysis: Optional[MultiFactorAnalysisState]

    # Regime analysis (Story 5.1 - optional, for future integration)
    regime_analysis: Optional[Dict[str, Any]]

    # Error handling
    error: Optional[str]


def create_initial_state(
    asset_symbol: str,
    candles_data: Optional[List[CandleData]] = None,
    sentiment_data: Optional[List[Dict[str, Any]]] = None
) -> GraphState:
    """
    Factory function to create a properly initialized GraphState.

    Creates a GraphState with all fields properly initialized,
    with input data and None for output fields that will be
    populated by the agents.

    Args:
        asset_symbol: Trading pair symbol (e.g., "SOLUSD")
        candles_data: Optional list of OHLCV candle data
        sentiment_data: Optional list of sentiment entries

    Returns:
        GraphState: Initialized state ready for graph invocation

    Example:
        state = create_initial_state(
            asset_symbol="BTCUSD",
            candles_data=candles_from_db,
            sentiment_data=sentiment_from_db
        )
    """
    return GraphState(
        asset_symbol=asset_symbol,
        candles_data=candles_data or [],
        sentiment_data=sentiment_data or [],
        technical_analysis=None,
        sentiment_analysis=None,
        vision_analysis=None,
        final_decision=None,
        multi_factor_analysis=None,
        regime_analysis=None,
        error=None
    )
