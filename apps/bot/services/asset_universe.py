"""
Asset Universe Configuration for the Contrarian AI Trading Bot.

Story 5.2: Asset Universe Reduction

This module provides:
- AssetTier enum for tier classification
- TierConfig dataclass for tier configuration
- Default tier configurations with allocation limits and thresholds
- Excluded assets list (meme coins, micro-caps)
- Helper functions for tier lookups and asset universe management

The asset universe is reduced from 30 to ~10 high-quality assets
with tiered allocation limits to focus on liquid, established coins.
"""

import os
from dataclasses import dataclass
from decimal import Decimal
from enum import Enum
from typing import Dict, List, Optional


class AssetTier(str, Enum):
    """
    Asset tier classification for allocation limits.

    Tier 1: BTC, ETH - 60% max allocation (highest liquidity)
    Tier 2: SOL, AVAX, LINK - 30% max allocation (strong fundamentals)
    Tier 3: High conviction picks - 10% max allocation (configurable)
    Excluded: Meme coins, micro-caps, risky assets - not tradeable
    """

    TIER_1 = "TIER_1"
    TIER_2 = "TIER_2"
    TIER_3 = "TIER_3"
    EXCLUDED = "EXCLUDED"


@dataclass
class TierConfig:
    """
    Configuration for a specific asset tier.

    Attributes:
        max_allocation_percent: Maximum portfolio allocation percentage for this tier
        min_volume_24h: Minimum 24h trading volume in USD required for this tier
        min_market_cap: Minimum market cap in USD required for this tier
        assets: List of asset symbols in this tier
    """

    max_allocation_percent: Decimal
    min_volume_24h: Decimal
    min_market_cap: Decimal
    assets: List[str]


# Default tier configuration
# These values are based on Story 5.2 requirements
DEFAULT_TIER_CONFIG: Dict[AssetTier, TierConfig] = {
    AssetTier.TIER_1: TierConfig(
        max_allocation_percent=Decimal("60.0"),
        min_volume_24h=Decimal("1000000000"),  # $1B daily volume
        min_market_cap=Decimal("50000000000"),  # $50B market cap
        assets=["BTCUSD", "ETHUSD"],
    ),
    AssetTier.TIER_2: TierConfig(
        max_allocation_percent=Decimal("30.0"),
        min_volume_24h=Decimal("100000000"),  # $100M daily volume
        min_market_cap=Decimal("5000000000"),  # $5B market cap
        assets=["SOLUSD", "AVAXUSD", "LINKUSD"],
    ),
    AssetTier.TIER_3: TierConfig(
        max_allocation_percent=Decimal("10.0"),
        min_volume_24h=Decimal("50000000"),  # $50M daily volume
        min_market_cap=Decimal("1000000000"),  # $1B market cap
        assets=[],  # Configurable via environment variable
    ),
}


# Meme coins and micro-caps to explicitly exclude
EXCLUDED_ASSETS: List[str] = [
    # Meme coins
    "DOGEUSD",
    "SHIBUSD",
    "PEPEUSD",
    "FLOKIUSD",
    "BONKUSD",
    "MEMEUSD",
    "WOJAKUSD",
    # Add any other micro-cap or risky assets here
]


# Exclusion reasons for documentation and logging
EXCLUSION_REASONS: Dict[str, str] = {
    "DOGEUSD": "Meme coin - high volatility, unpredictable",
    "SHIBUSD": "Meme coin - no fundamental value",
    "PEPEUSD": "Meme coin - speculative only",
    "FLOKIUSD": "Meme coin - community driven",
    "BONKUSD": "Meme coin - Solana ecosystem meme",
    "MEMEUSD": "Meme coin - self-explanatory",
    "WOJAKUSD": "Meme coin - community-driven speculation",
}


def get_tier_3_assets() -> List[str]:
    """
    Get Tier 3 assets from environment variable.

    Tier 3 assets are configurable high-conviction picks that can be
    updated without code changes.

    Environment variable format: TIER_3_ASSETS="AAVEUSD,UNIUSD,ARBUSD"

    Returns:
        List of asset symbols in Tier 3, or empty list if not configured
    """
    assets_str = os.getenv("TIER_3_ASSETS", "")
    if not assets_str:
        return []
    return [a.strip().upper() for a in assets_str.split(",") if a.strip()]


def get_full_asset_universe() -> List[str]:
    """
    Get complete list of tradeable assets across all tiers.

    Returns the combined asset list from Tier 1, Tier 2, and Tier 3.
    This should typically be 8-10 assets as per Story 5.2 requirements.

    Returns:
        List of tradeable asset symbols
    """
    assets: List[str] = []
    assets.extend(DEFAULT_TIER_CONFIG[AssetTier.TIER_1].assets)
    assets.extend(DEFAULT_TIER_CONFIG[AssetTier.TIER_2].assets)
    assets.extend(get_tier_3_assets())
    return assets


def get_asset_tier(symbol: str) -> AssetTier:
    """
    Determine the tier for a given asset symbol.

    Checks membership in each tier and returns the appropriate tier.
    Unknown assets default to EXCLUDED for safety.

    Args:
        symbol: Asset symbol (e.g., "BTCUSD", "DOGEUSD")

    Returns:
        AssetTier enum value for the asset
    """
    symbol = symbol.upper()

    # Check if explicitly excluded
    if symbol in EXCLUDED_ASSETS:
        return AssetTier.EXCLUDED

    # Check Tier 1
    if symbol in DEFAULT_TIER_CONFIG[AssetTier.TIER_1].assets:
        return AssetTier.TIER_1

    # Check Tier 2
    if symbol in DEFAULT_TIER_CONFIG[AssetTier.TIER_2].assets:
        return AssetTier.TIER_2

    # Check Tier 3 (configurable via environment)
    if symbol in get_tier_3_assets():
        return AssetTier.TIER_3

    # Unknown assets are excluded by default
    return AssetTier.EXCLUDED


def get_max_allocation(tier: AssetTier) -> Decimal:
    """
    Get maximum allocation percentage for a tier.

    Args:
        tier: AssetTier enum value

    Returns:
        Maximum allocation percentage (e.g., 60.0 for Tier 1)
        Returns 0 for excluded assets
    """
    if tier in DEFAULT_TIER_CONFIG:
        return DEFAULT_TIER_CONFIG[tier].max_allocation_percent
    return Decimal("0")


def get_tier_config(tier: AssetTier) -> Optional[TierConfig]:
    """
    Get the full configuration for a tier.

    Args:
        tier: AssetTier enum value

    Returns:
        TierConfig object or None for excluded tier
    """
    return DEFAULT_TIER_CONFIG.get(tier)


def get_exclusion_reason(symbol: str) -> Optional[str]:
    """
    Get the exclusion reason for an asset.

    Args:
        symbol: Asset symbol

    Returns:
        Reason string if asset is excluded, None otherwise
    """
    symbol = symbol.upper()
    if symbol in EXCLUSION_REASONS:
        return EXCLUSION_REASONS[symbol]
    if symbol in EXCLUDED_ASSETS:
        return "Excluded asset - does not meet criteria"
    if get_asset_tier(symbol) == AssetTier.EXCLUDED:
        return "Unknown asset - not in approved universe"
    return None


def is_tradeable(symbol: str) -> bool:
    """
    Check if an asset is tradeable (not excluded).

    Args:
        symbol: Asset symbol

    Returns:
        True if asset is in Tier 1, 2, or 3; False if excluded
    """
    return get_asset_tier(symbol) != AssetTier.EXCLUDED
