"""
Allocation Manager for the Contrarian AI Trading Bot.

Story 5.2: Asset Universe Reduction

This module enforces tiered allocation limits to prevent over-concentration
in any single tier of assets. It calculates remaining capacity and adjusts
position sizes to stay within allocation limits.

Tier Allocation Limits:
- Tier 1 (BTC, ETH): 60% of portfolio
- Tier 2 (SOL, AVAX, LINK): 30% of portfolio
- Tier 3 (configurable picks): 10% of portfolio

Functions:
- get_tier_allocation_limit(): Calculate max USD for a tier
- check_allocation_capacity(): Check if an allocation fits within limits
- get_current_tier_allocations(): Calculate current allocations from open trades
"""

import logging
from dataclasses import dataclass
from decimal import Decimal
from typing import Dict, List, Optional

from services.asset_universe import (
    AssetTier,
    DEFAULT_TIER_CONFIG,
    get_asset_tier,
)

logger = logging.getLogger(__name__)


@dataclass
class AllocationResult:
    """
    Result of an allocation capacity check.

    Attributes:
        can_allocate: Whether any allocation is possible
        max_amount: Maximum USD amount that can be allocated
        current_allocation: Current USD allocated to this tier
        tier_limit: Maximum USD allocation for this tier
        remaining_capacity: Remaining USD capacity after this allocation
        reason: Human-readable explanation
    """

    can_allocate: bool
    max_amount: Decimal
    current_allocation: Decimal
    tier_limit: Decimal
    remaining_capacity: Decimal
    reason: str


def get_tier_allocation_limit(
    tier: AssetTier,
    portfolio_value: Decimal,
) -> Decimal:
    """
    Calculate maximum USD allocation for a tier based on portfolio value.

    Args:
        tier: The AssetTier to calculate limit for
        portfolio_value: Total portfolio value in USD

    Returns:
        Maximum USD amount that can be allocated to this tier

    Example:
        >>> limit = get_tier_allocation_limit(AssetTier.TIER_1, Decimal("100000"))
        >>> print(limit)  # Decimal("60000") - 60% of $100k
    """
    if tier not in DEFAULT_TIER_CONFIG:
        return Decimal("0")

    max_pct = DEFAULT_TIER_CONFIG[tier].max_allocation_percent
    return (portfolio_value * max_pct) / Decimal("100")


async def check_allocation_capacity(
    symbol: str,
    tier: AssetTier,
    portfolio_value: Decimal,
    current_tier_allocation: Decimal,
    requested_amount: Decimal,
) -> AllocationResult:
    """
    Check if a new allocation fits within tier limits.

    This function is the main allocation enforcement mechanism. It checks
    if the requested allocation can fit within the tier's allocation limit
    and returns the maximum amount that can actually be allocated.

    Args:
        symbol: Asset symbol for logging
        tier: Asset tier
        portfolio_value: Total portfolio value in USD
        current_tier_allocation: Current USD allocated to this tier
        requested_amount: Requested allocation amount in USD

    Returns:
        AllocationResult with capacity details

    Example:
        >>> # Check if we can allocate $10k to BTC with $30k already in Tier 1
        >>> result = await check_allocation_capacity(
        ...     symbol="BTCUSD",
        ...     tier=AssetTier.TIER_1,
        ...     portfolio_value=Decimal("100000"),
        ...     current_tier_allocation=Decimal("30000"),
        ...     requested_amount=Decimal("10000")
        ... )
        >>> if result.can_allocate:
        ...     print(f"Can allocate ${result.max_amount}")
    """
    tier_limit = get_tier_allocation_limit(tier, portfolio_value)
    remaining = tier_limit - current_tier_allocation

    # Log the allocation check
    logger.debug(
        f"Allocation check for {symbol} ({tier.value}): "
        f"Limit=${tier_limit:.2f}, Current=${current_tier_allocation:.2f}, "
        f"Remaining=${remaining:.2f}, Requested=${requested_amount:.2f}"
    )

    # Case 1: No capacity remaining
    if remaining <= Decimal("0"):
        logger.warning(
            f"Allocation blocked for {symbol}: {tier.value} limit reached "
            f"(${tier_limit:,.2f})"
        )
        return AllocationResult(
            can_allocate=False,
            max_amount=Decimal("0"),
            current_allocation=current_tier_allocation,
            tier_limit=tier_limit,
            remaining_capacity=Decimal("0"),
            reason=f"{tier.value} allocation limit reached (${tier_limit:,.2f})",
        )

    # Case 2: Requested amount exceeds remaining capacity
    if requested_amount > remaining:
        logger.info(
            f"Allocation reduced for {symbol}: Requested ${requested_amount:.2f} "
            f"reduced to ${remaining:.2f} to stay within {tier.value} limit"
        )
        return AllocationResult(
            can_allocate=True,
            max_amount=remaining,
            current_allocation=current_tier_allocation,
            tier_limit=tier_limit,
            remaining_capacity=Decimal("0"),
            reason=f"Reduced to ${remaining:,.2f} to stay within {tier.value} limit",
        )

    # Case 3: Full amount can be allocated
    new_remaining = remaining - requested_amount
    return AllocationResult(
        can_allocate=True,
        max_amount=requested_amount,
        current_allocation=current_tier_allocation,
        tier_limit=tier_limit,
        remaining_capacity=new_remaining,
        reason=f"Within {tier.value} allocation limits",
    )


async def get_current_tier_allocations(
    open_trades: List[Dict],
) -> Dict[AssetTier, Decimal]:
    """
    Calculate current allocation per tier from open trades.

    Iterates through open trades, determines each trade's tier based on
    its asset symbol, and sums the position values.

    Args:
        open_trades: List of open Trade records as dicts with 'symbol' and
                    'entry_value' (or 'entry_price' * 'size') keys

    Returns:
        Dict mapping each AssetTier to its current USD allocation

    Example:
        >>> trades = [
        ...     {"symbol": "BTCUSD", "entry_value": 30000},
        ...     {"symbol": "ETHUSD", "entry_value": 20000},
        ...     {"symbol": "SOLUSD", "entry_value": 15000},
        ... ]
        >>> allocations = await get_current_tier_allocations(trades)
        >>> print(allocations[AssetTier.TIER_1])  # 50000 (BTC + ETH)
    """
    allocations: Dict[AssetTier, Decimal] = {tier: Decimal("0") for tier in AssetTier}

    for trade in open_trades:
        symbol = trade.get("symbol", "")
        tier = get_asset_tier(symbol)

        # Calculate position value
        # Support both 'entry_value' key and 'entry_price' * 'size' calculation
        if "entry_value" in trade:
            position_value = Decimal(str(trade["entry_value"]))
        elif "entry_price" in trade and "size" in trade:
            entry_price = Decimal(str(trade["entry_price"]))
            size = Decimal(str(trade["size"]))
            position_value = entry_price * size
        else:
            logger.warning(f"Could not calculate position value for trade: {trade}")
            continue

        allocations[tier] += position_value

    logger.debug(f"Current tier allocations: {allocations}")
    return allocations


def calculate_position_size_for_tier(
    tier: AssetTier,
    portfolio_value: Decimal,
    current_tier_allocation: Decimal,
    base_position_size: Decimal,
) -> Decimal:
    """
    Calculate appropriate position size considering tier limits.

    Reduces position size if needed to stay within tier allocation limits.

    Args:
        tier: Asset tier
        portfolio_value: Total portfolio value in USD
        current_tier_allocation: Current USD allocated to this tier
        base_position_size: Desired base position size in USD

    Returns:
        Adjusted position size that fits within tier limits
    """
    tier_limit = get_tier_allocation_limit(tier, portfolio_value)
    remaining = tier_limit - current_tier_allocation

    if remaining <= Decimal("0"):
        return Decimal("0")

    if base_position_size > remaining:
        return remaining

    return base_position_size


def get_allocation_summary(
    portfolio_value: Decimal,
    tier_allocations: Dict[AssetTier, Decimal],
) -> Dict[str, Dict]:
    """
    Generate a summary of current allocations vs limits.

    Useful for logging, monitoring, and dashboard display.

    Args:
        portfolio_value: Total portfolio value in USD
        tier_allocations: Current allocations by tier

    Returns:
        Dict with allocation summary for each tier
    """
    summary = {}

    for tier in [AssetTier.TIER_1, AssetTier.TIER_2, AssetTier.TIER_3]:
        limit = get_tier_allocation_limit(tier, portfolio_value)
        current = tier_allocations.get(tier, Decimal("0"))
        remaining = limit - current
        used_pct = (current / limit * Decimal("100")) if limit > 0 else Decimal("0")

        summary[tier.value] = {
            "limit": float(limit),
            "current": float(current),
            "remaining": float(remaining),
            "used_percent": float(used_pct),
            "at_limit": remaining <= Decimal("0"),
        }

    return summary
