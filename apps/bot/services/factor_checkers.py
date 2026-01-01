"""
Factor checker functions for multi-factor confirmation system (Story 5.3 & 5.6).

This module provides the actual checking logic for each factor:
- On-chain factors (Story 5.6)
- Technical factors
- Sentiment factors

Each checker returns a FactorResult indicating whether the factor
was triggered and the values used for the decision.
"""

from typing import Optional
import logging

from services.signal_factors import (
    BuyFactor,
    SellFactor,
    FactorResult,
    get_factor_weight,
)
from services.onchain_analyzer import (
    get_onchain_analysis,
    OnChainSignal,
)

logger = logging.getLogger(__name__)


# =============================================================================
# On-Chain Factor Checkers (Story 5.6)
# =============================================================================


async def check_onchain_accumulation(symbol: str) -> FactorResult:
    """
    Check if on-chain data shows accumulation.

    Triggered when:
    - Exchange flows show accumulation (outflows > inflows)
    - Whale activity shows buying
    - On-chain signal is ACCUMULATION or STRONG_ACCUMULATION

    Args:
        symbol: Trading symbol to analyze

    Returns:
        FactorResult with trigger status and reasoning
    """
    try:
        analysis = await get_onchain_analysis(symbol)

        triggered = analysis.signal in [
            OnChainSignal.ACCUMULATION,
            OnChainSignal.STRONG_ACCUMULATION
        ]

        # Give extra weight to strong accumulation
        weight = 1.5 if analysis.signal == OnChainSignal.STRONG_ACCUMULATION else 1.0
        weight *= get_factor_weight(BuyFactor.ONCHAIN_ACCUMULATION.value)

        # Truncate reasoning for cleaner display
        reasoning_short = analysis.reasoning[:100]
        if len(analysis.reasoning) > 100:
            reasoning_short += "..."

        return FactorResult(
            factor=BuyFactor.ONCHAIN_ACCUMULATION.value,
            triggered=triggered,
            value=analysis.confidence,
            threshold=50,
            weight=weight,
            reasoning=f"On-chain: {analysis.signal.value} ({reasoning_short})"
        )

    except Exception as e:
        logger.error(f"Error checking on-chain accumulation for {symbol}: {e}")
        return FactorResult(
            factor=BuyFactor.ONCHAIN_ACCUMULATION.value,
            triggered=False,
            value=0,
            threshold=50,
            weight=1.0,
            reasoning=f"Error: {str(e)}"
        )


async def check_funding_short_squeeze(symbol: str) -> FactorResult:
    """
    Check if funding rates indicate short squeeze potential.

    Triggered when:
    - Funding rate is extremely negative (< -0.1%)
    - Market is heavily short
    - Short squeeze risk is elevated

    Args:
        symbol: Trading symbol to analyze

    Returns:
        FactorResult with trigger status and reasoning
    """
    try:
        analysis = await get_onchain_analysis(symbol)

        triggered = analysis.funding_signal == "short_squeeze_risk"
        weight = get_factor_weight(BuyFactor.FUNDING_SHORT_SQUEEZE.value)

        # Convert funding rate to percentage for display
        rate_pct = float(analysis.avg_funding_rate) * 100

        return FactorResult(
            factor=BuyFactor.FUNDING_SHORT_SQUEEZE.value,
            triggered=triggered,
            value=rate_pct,
            threshold=-0.05,  # -0.05% funding rate
            weight=weight,
            reasoning=f"Funding rate: {rate_pct:.3f}% (squeeze risk: {triggered})"
        )

    except Exception as e:
        logger.error(f"Error checking funding short squeeze for {symbol}: {e}")
        return FactorResult(
            factor=BuyFactor.FUNDING_SHORT_SQUEEZE.value,
            triggered=False,
            value=0,
            threshold=-0.05,
            weight=0.75,
            reasoning=f"Error: {str(e)}"
        )


async def check_stablecoin_dry_powder() -> FactorResult:
    """
    Check if stablecoin reserves indicate high buying power.

    Triggered when:
    - Stablecoin reserves on exchanges are rising
    - 7-day change > 10%
    - Indicates "dry powder" ready to buy

    Returns:
        FactorResult with trigger status and reasoning
    """
    try:
        # Get any symbol's analysis (stablecoin data is market-wide)
        analysis = await get_onchain_analysis("BTCUSD")

        triggered = analysis.stablecoin_signal == "dry_powder_high"
        weight = get_factor_weight(BuyFactor.STABLECOIN_DRY_POWDER.value)

        return FactorResult(
            factor=BuyFactor.STABLECOIN_DRY_POWDER.value,
            triggered=triggered,
            value=analysis.reserves_change_7d_pct,
            threshold=10.0,  # 10% increase threshold
            weight=weight,
            reasoning=f"Stablecoin reserves 7d change: {analysis.reserves_change_7d_pct:.1f}%"
        )

    except Exception as e:
        logger.error(f"Error checking stablecoin dry powder: {e}")
        return FactorResult(
            factor=BuyFactor.STABLECOIN_DRY_POWDER.value,
            triggered=False,
            value=0,
            threshold=10.0,
            weight=0.5,
            reasoning=f"Error: {str(e)}"
        )


async def check_onchain_distribution(symbol: str) -> FactorResult:
    """
    Check if on-chain data shows distribution.

    Triggered when:
    - Exchange flows show distribution (inflows > outflows)
    - Whale activity shows selling
    - On-chain signal is DISTRIBUTION or STRONG_DISTRIBUTION

    Args:
        symbol: Trading symbol to analyze

    Returns:
        FactorResult with trigger status and reasoning
    """
    try:
        analysis = await get_onchain_analysis(symbol)

        triggered = analysis.signal in [
            OnChainSignal.DISTRIBUTION,
            OnChainSignal.STRONG_DISTRIBUTION
        ]

        # Give extra weight to strong distribution
        weight = 1.5 if analysis.signal == OnChainSignal.STRONG_DISTRIBUTION else 1.0
        weight *= get_factor_weight(SellFactor.ONCHAIN_DISTRIBUTION.value)

        # Truncate reasoning for cleaner display
        reasoning_short = analysis.reasoning[:100]
        if len(analysis.reasoning) > 100:
            reasoning_short += "..."

        return FactorResult(
            factor=SellFactor.ONCHAIN_DISTRIBUTION.value,
            triggered=triggered,
            value=analysis.confidence,
            threshold=50,
            weight=weight,
            reasoning=f"On-chain: {analysis.signal.value} ({reasoning_short})"
        )

    except Exception as e:
        logger.error(f"Error checking on-chain distribution for {symbol}: {e}")
        return FactorResult(
            factor=SellFactor.ONCHAIN_DISTRIBUTION.value,
            triggered=False,
            value=0,
            threshold=50,
            weight=1.0,
            reasoning=f"Error: {str(e)}"
        )


async def check_funding_long_squeeze(symbol: str) -> FactorResult:
    """
    Check if funding rates indicate long squeeze potential.

    Triggered when:
    - Funding rate is extremely positive (> 0.1%)
    - Market is heavily long
    - Long squeeze risk is elevated

    Args:
        symbol: Trading symbol to analyze

    Returns:
        FactorResult with trigger status and reasoning
    """
    try:
        analysis = await get_onchain_analysis(symbol)

        triggered = analysis.funding_signal == "long_squeeze_risk"
        weight = get_factor_weight(SellFactor.FUNDING_LONG_SQUEEZE.value)

        # Convert funding rate to percentage for display
        rate_pct = float(analysis.avg_funding_rate) * 100

        return FactorResult(
            factor=SellFactor.FUNDING_LONG_SQUEEZE.value,
            triggered=triggered,
            value=rate_pct,
            threshold=0.05,  # 0.05% funding rate
            weight=weight,
            reasoning=f"Funding rate: {rate_pct:.3f}% (squeeze risk: {triggered})"
        )

    except Exception as e:
        logger.error(f"Error checking funding long squeeze for {symbol}: {e}")
        return FactorResult(
            factor=SellFactor.FUNDING_LONG_SQUEEZE.value,
            triggered=False,
            value=0,
            threshold=0.05,
            weight=0.75,
            reasoning=f"Error: {str(e)}"
        )


# =============================================================================
# Aggregate On-Chain Checks
# =============================================================================


async def get_onchain_buy_factors(symbol: str) -> list[FactorResult]:
    """
    Get all on-chain buy factors for a symbol.

    Args:
        symbol: Trading symbol to analyze

    Returns:
        List of FactorResults for on-chain buy factors
    """
    factors = []

    # Check all on-chain buy factors
    factors.append(await check_onchain_accumulation(symbol))
    factors.append(await check_funding_short_squeeze(symbol))
    factors.append(await check_stablecoin_dry_powder())

    return factors


async def get_onchain_sell_factors(symbol: str) -> list[FactorResult]:
    """
    Get all on-chain sell factors for a symbol.

    Args:
        symbol: Trading symbol to analyze

    Returns:
        List of FactorResults for on-chain sell factors
    """
    factors = []

    # Check all on-chain sell factors
    factors.append(await check_onchain_distribution(symbol))
    factors.append(await check_funding_long_squeeze(symbol))

    return factors


async def get_all_onchain_factors(symbol: str) -> tuple[list[FactorResult], list[FactorResult]]:
    """
    Get all on-chain factors (buy and sell) for a symbol.

    Args:
        symbol: Trading symbol to analyze

    Returns:
        Tuple of (buy_factors, sell_factors)
    """
    buy_factors = await get_onchain_buy_factors(symbol)
    sell_factors = await get_onchain_sell_factors(symbol)

    return buy_factors, sell_factors


# Export all
__all__ = [
    # On-chain buy factors
    "check_onchain_accumulation",
    "check_funding_short_squeeze",
    "check_stablecoin_dry_powder",
    # On-chain sell factors
    "check_onchain_distribution",
    "check_funding_long_squeeze",
    # Aggregate functions
    "get_onchain_buy_factors",
    "get_onchain_sell_factors",
    "get_all_onchain_factors",
]
