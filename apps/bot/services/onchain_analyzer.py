"""
On-chain signal analyzer for Story 5.6: On-Chain Data Integration.

This module analyzes on-chain metrics to generate trading signals:
- Exchange flows (accumulation/distribution)
- Whale activity (smart money movements)
- Funding rates (squeeze detection)
- Stablecoin reserves (buying power)

Integrates with the multi-factor confirmation system (Story 5.3).
"""

from datetime import datetime, timezone, timedelta
from decimal import Decimal
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
from enum import Enum
import logging

from sqlmodel import select

from config import get_config
from database import get_session_maker
from models.onchain import (
    ExchangeFlow,
    WhaleActivity,
    FundingRate,
    StablecoinReserves
)

logger = logging.getLogger(__name__)
config = get_config()


class OnChainSignal(str, Enum):
    """On-chain signal classification."""
    STRONG_ACCUMULATION = "STRONG_ACCUMULATION"  # Heavy buying
    ACCUMULATION = "ACCUMULATION"                # Moderate buying
    NEUTRAL = "NEUTRAL"
    DISTRIBUTION = "DISTRIBUTION"                # Moderate selling
    STRONG_DISTRIBUTION = "STRONG_DISTRIBUTION"  # Heavy selling


@dataclass
class OnChainAnalysis:
    """Comprehensive on-chain analysis result."""

    # Overall signal
    signal: OnChainSignal
    confidence: float

    # Exchange flows
    net_flow_signal: str  # "accumulation", "distribution", "neutral"
    net_flow_value_usd: Decimal
    net_flow_vs_avg: float  # Multiple of average

    # Whale activity
    whale_signal: str  # "buying", "selling", "neutral"
    whale_buy_sell_ratio: float
    whale_activity_level: str  # "high", "normal", "low"

    # Funding rates
    funding_signal: str  # "short_squeeze_risk", "long_squeeze_risk", "neutral"
    avg_funding_rate: Decimal
    funding_extreme: bool

    # Stablecoin reserves
    stablecoin_signal: str  # "dry_powder_high", "dry_powder_low", "neutral"
    reserves_change_7d_pct: float

    # Reasoning
    reasoning: str
    factors: List[str]


async def analyze_exchange_flows(
    symbol: str,
    lookback_hours: int = 24
) -> Dict[str, Any]:
    """
    Analyze exchange inflow/outflow for accumulation/distribution.

    Negative net flow = Accumulation (more leaving exchanges) = Bullish
    Positive net flow = Distribution (more entering exchanges) = Bearish

    Args:
        symbol: Trading symbol to analyze
        lookback_hours: Hours of data to analyze

    Returns:
        Dict with signal, net_flow_usd, vs_average, data_available
    """
    cutoff = datetime.now(timezone.utc) - timedelta(hours=lookback_hours)

    session_maker = get_session_maker()
    async with session_maker() as session:
        result = await session.execute(
            select(ExchangeFlow)
            .where(ExchangeFlow.asset_symbol == symbol)
            .where(ExchangeFlow.timestamp >= cutoff)
            .order_by(ExchangeFlow.timestamp.desc())
        )
        flows = result.scalars().all()

    if not flows:
        return {
            "signal": "neutral",
            "net_flow_usd": Decimal("0"),
            "vs_average": 0.0,
            "data_available": False
        }

    total_net_flow = sum(f.net_flow_usd for f in flows)
    avg_net_flow = total_net_flow / len(flows)

    # Compare to 7-day average if available
    vs_avg = 0.0
    if flows[0].avg_net_flow_7d and flows[0].avg_net_flow_7d != 0:
        vs_avg = float(avg_net_flow / flows[0].avg_net_flow_7d)

    # Determine signal based on net flow and spike multiplier
    spike_mult = config.onchain.exchange_flow_spike_mult
    avg_abs = abs(float(avg_net_flow)) if avg_net_flow else 1.0

    if float(total_net_flow) < -spike_mult * avg_abs:
        signal = "strong_accumulation"
    elif float(total_net_flow) < 0:
        signal = "accumulation"
    elif float(total_net_flow) > spike_mult * avg_abs:
        signal = "strong_distribution"
    elif float(total_net_flow) > 0:
        signal = "distribution"
    else:
        signal = "neutral"

    return {
        "signal": signal,
        "net_flow_usd": total_net_flow,
        "vs_average": vs_avg,
        "data_available": True
    }


async def analyze_whale_activity(
    symbol: str,
    lookback_hours: int = 24
) -> Dict[str, Any]:
    """
    Analyze whale transaction patterns.

    Buy/Sell ratio > 1.2 = Whales accumulating
    Buy/Sell ratio < 0.8 = Whales distributing

    Args:
        symbol: Trading symbol to analyze
        lookback_hours: Hours of data to analyze

    Returns:
        Dict with signal, buy_sell_ratio, activity_level, data_available
    """
    cutoff = datetime.now(timezone.utc) - timedelta(hours=lookback_hours)

    session_maker = get_session_maker()
    async with session_maker() as session:
        result = await session.execute(
            select(WhaleActivity)
            .where(WhaleActivity.asset_symbol == symbol)
            .where(WhaleActivity.timestamp >= cutoff)
            .order_by(WhaleActivity.timestamp.desc())
        )
        activity = result.scalars().all()

    if not activity:
        return {
            "signal": "neutral",
            "buy_sell_ratio": 1.0,
            "activity_level": "unknown",
            "total_transactions": 0,
            "data_available": False
        }

    total_buy = sum(float(a.whale_buy_volume or 0) for a in activity)
    total_sell = sum(float(a.whale_sell_volume or 0) for a in activity)
    total_count = sum(a.large_tx_count for a in activity)

    # Calculate buy/sell ratio (avoid division by zero)
    if total_sell > 0:
        buy_sell_ratio = total_buy / total_sell
    else:
        buy_sell_ratio = float('inf') if total_buy > 0 else 1.0

    # Compare to average activity level
    activity_level = "unknown"
    if activity[0].avg_large_tx_count_7d:
        avg_count = activity[0].avg_large_tx_count_7d * (lookback_hours / 24)
        if total_count > avg_count * 2:
            activity_level = "high"
        elif total_count < avg_count * 0.5:
            activity_level = "low"
        else:
            activity_level = "normal"

    # Determine signal
    if buy_sell_ratio > 2.0:
        signal = "strong_buying"
    elif buy_sell_ratio > 1.2:
        signal = "buying"
    elif buy_sell_ratio < 0.5:
        signal = "strong_selling"
    elif buy_sell_ratio < 0.8:
        signal = "selling"
    else:
        signal = "neutral"

    return {
        "signal": signal,
        "buy_sell_ratio": buy_sell_ratio,
        "activity_level": activity_level,
        "total_transactions": total_count,
        "data_available": True
    }


async def analyze_funding_rates(
    symbol: str,
    lookback_hours: int = 24
) -> Dict[str, Any]:
    """
    Analyze funding rates for squeeze risk.

    Extremely positive = Market heavily long, long squeeze risk
    Extremely negative = Market heavily short, short squeeze risk (bullish)

    Args:
        symbol: Trading symbol to analyze
        lookback_hours: Hours of data to analyze

    Returns:
        Dict with signal, avg_rate, is_extreme, data_available
    """
    cutoff = datetime.now(timezone.utc) - timedelta(hours=lookback_hours)

    session_maker = get_session_maker()
    async with session_maker() as session:
        result = await session.execute(
            select(FundingRate)
            .where(FundingRate.asset_symbol == symbol)
            .where(FundingRate.timestamp >= cutoff)
            .order_by(FundingRate.timestamp.desc())
        )
        rates = result.scalars().all()

    if not rates:
        return {
            "signal": "neutral",
            "avg_rate": Decimal("0"),
            "is_extreme": False,
            "data_available": False
        }

    avg_rate = sum(r.funding_rate for r in rates) / len(rates)
    threshold = Decimal(str(config.onchain.funding_rate_extreme_threshold))

    is_extreme = abs(avg_rate) >= threshold

    if avg_rate < -threshold:
        signal = "short_squeeze_risk"  # Market heavily short = bullish
    elif avg_rate > threshold:
        signal = "long_squeeze_risk"   # Market heavily long = bearish
    else:
        signal = "neutral"

    return {
        "signal": signal,
        "avg_rate": avg_rate,
        "is_extreme": is_extreme,
        "data_available": True
    }


async def analyze_stablecoin_reserves() -> Dict[str, Any]:
    """
    Analyze stablecoin reserves as buying power indicator.

    Rising reserves = More dry powder ready to buy = Bullish
    Falling reserves = Less buying power available = Bearish

    Returns:
        Dict with signal, change_7d_pct, total_reserves, data_available
    """
    session_maker = get_session_maker()
    async with session_maker() as session:
        result = await session.execute(
            select(StablecoinReserves)
            .order_by(StablecoinReserves.timestamp.desc())
            .limit(2)
        )
        reserves = result.scalars().all()

    if len(reserves) < 1:
        return {
            "signal": "neutral",
            "change_7d_pct": 0.0,
            "total_reserves": 0.0,
            "data_available": False
        }

    latest = reserves[0]
    change_7d = float(latest.change_7d_pct or 0)

    if change_7d > 10:
        signal = "dry_powder_high"
    elif change_7d < -10:
        signal = "dry_powder_low"
    else:
        signal = "neutral"

    return {
        "signal": signal,
        "change_7d_pct": change_7d,
        "total_reserves": float(latest.total_reserves_usd),
        "data_available": True
    }


async def get_onchain_analysis(symbol: str) -> OnChainAnalysis:
    """
    Get comprehensive on-chain analysis for an asset.

    Combines all on-chain signals:
    - Exchange flows
    - Whale activity
    - Funding rates
    - Stablecoin reserves

    Args:
        symbol: Trading symbol to analyze

    Returns:
        OnChainAnalysis with comprehensive metrics
    """
    # Gather all analyses
    flow_analysis = await analyze_exchange_flows(symbol)
    whale_analysis = await analyze_whale_activity(symbol)
    funding_analysis = await analyze_funding_rates(symbol)
    stablecoin_analysis = await analyze_stablecoin_reserves()

    # Count bullish/bearish factors
    factors = []
    bullish_count = 0
    bearish_count = 0

    # Exchange flows
    if "accumulation" in flow_analysis["signal"]:
        weight = 2 if "strong" in flow_analysis["signal"] else 1
        bullish_count += weight
        factors.append(f"Exchange flows show {flow_analysis['signal']}")
    elif "distribution" in flow_analysis["signal"]:
        weight = 2 if "strong" in flow_analysis["signal"] else 1
        bearish_count += weight
        factors.append(f"Exchange flows show {flow_analysis['signal']}")

    # Whale activity
    if "buying" in whale_analysis["signal"]:
        weight = 2 if "strong" in whale_analysis["signal"] else 1
        bullish_count += weight
        factors.append(f"Whales are {whale_analysis['signal']}")
    elif "selling" in whale_analysis["signal"]:
        weight = 2 if "strong" in whale_analysis["signal"] else 1
        bearish_count += weight
        factors.append(f"Whales are {whale_analysis['signal']}")

    # Funding rates
    if funding_analysis["signal"] == "short_squeeze_risk":
        bullish_count += 1
        factors.append("Short squeeze risk (negative funding)")
    elif funding_analysis["signal"] == "long_squeeze_risk":
        bearish_count += 1
        factors.append("Long squeeze risk (positive funding)")

    # Stablecoin reserves
    if stablecoin_analysis["signal"] == "dry_powder_high":
        bullish_count += 1
        factors.append("High stablecoin reserves (buying power)")
    elif stablecoin_analysis["signal"] == "dry_powder_low":
        bearish_count += 1
        factors.append("Low stablecoin reserves")

    # Determine overall signal
    net_signal = bullish_count - bearish_count

    if net_signal >= 4:
        signal = OnChainSignal.STRONG_ACCUMULATION
    elif net_signal >= 2:
        signal = OnChainSignal.ACCUMULATION
    elif net_signal <= -4:
        signal = OnChainSignal.STRONG_DISTRIBUTION
    elif net_signal <= -2:
        signal = OnChainSignal.DISTRIBUTION
    else:
        signal = OnChainSignal.NEUTRAL

    # Calculate confidence based on data availability
    data_available_count = sum([
        flow_analysis.get("data_available", False),
        whale_analysis.get("data_available", False),
        funding_analysis.get("data_available", False),
        stablecoin_analysis.get("data_available", False)
    ])

    # Confidence formula: base on data availability and signal strength
    confidence = (data_available_count / 4) * 100 * (1 + abs(net_signal) / 8)
    confidence = min(confidence, 100)

    # Build reasoning
    reasoning = (
        f"On-chain analysis: {bullish_count} bullish factors, "
        f"{bearish_count} bearish factors. Signal: {signal.value}. "
        f"Key factors: {'; '.join(factors) if factors else 'None detected'}"
    )

    return OnChainAnalysis(
        signal=signal,
        confidence=confidence,
        net_flow_signal=flow_analysis["signal"],
        net_flow_value_usd=flow_analysis.get("net_flow_usd", Decimal("0")),
        net_flow_vs_avg=flow_analysis.get("vs_average", 0.0),
        whale_signal=whale_analysis["signal"],
        whale_buy_sell_ratio=whale_analysis.get("buy_sell_ratio", 1.0),
        whale_activity_level=whale_analysis.get("activity_level", "unknown"),
        funding_signal=funding_analysis["signal"],
        avg_funding_rate=funding_analysis.get("avg_rate", Decimal("0")),
        funding_extreme=funding_analysis.get("is_extreme", False),
        stablecoin_signal=stablecoin_analysis["signal"],
        reserves_change_7d_pct=stablecoin_analysis.get("change_7d_pct", 0.0),
        reasoning=reasoning,
        factors=factors
    )


# Export all functions and classes
__all__ = [
    "OnChainSignal",
    "OnChainAnalysis",
    "analyze_exchange_flows",
    "analyze_whale_activity",
    "analyze_funding_rates",
    "analyze_stablecoin_reserves",
    "get_onchain_analysis",
]
