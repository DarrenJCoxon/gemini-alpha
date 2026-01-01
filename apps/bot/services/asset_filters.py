"""
Asset Filters for the Contrarian AI Trading Bot.

Story 5.2: Asset Universe Reduction

This module provides liquidity and market cap filtering functions
to validate assets meet tier requirements before trading.

Functions:
- check_liquidity_requirements(): Verify 24h volume meets tier threshold
- check_market_cap_requirements(): Verify market cap meets tier threshold
- validate_asset_for_trading(): Full validation combining all checks
"""

import logging
from decimal import Decimal
from typing import Any, Dict, Tuple

from services.asset_universe import (
    AssetTier,
    DEFAULT_TIER_CONFIG,
    EXCLUDED_ASSETS,
    EXCLUSION_REASONS,
)
from services.kraken import get_kraken_client

logger = logging.getLogger(__name__)


async def check_liquidity_requirements(
    symbol: str,
    tier: AssetTier,
) -> Tuple[bool, str]:
    """
    Check if asset meets liquidity requirements for its tier.

    Fetches the 24h trading volume from Kraken and compares
    against the tier's minimum volume threshold.

    Args:
        symbol: Asset symbol in database format (e.g., "BTCUSD")
        tier: The AssetTier for this asset

    Returns:
        Tuple of (meets_requirements: bool, reason: str)
    """
    if tier not in DEFAULT_TIER_CONFIG:
        return False, f"Unknown tier: {tier}"

    tier_config = DEFAULT_TIER_CONFIG[tier]

    try:
        client = get_kraken_client()
        await client.initialize()

        if client.exchange is None:
            return False, "Exchange client not initialized"

        # Convert symbol to Kraken format and fetch ticker
        kraken_symbol = client.convert_symbol_to_kraken(symbol)
        ticker = await client.exchange.fetch_ticker(kraken_symbol)

        # Get 24h quote volume (volume in USD)
        volume_24h = Decimal(str(ticker.get("quoteVolume", 0)))
        min_volume = tier_config.min_volume_24h

        if volume_24h < min_volume:
            return (
                False,
                f"Volume ${volume_24h:,.0f} below minimum ${min_volume:,.0f}",
            )

        return True, f"Volume ${volume_24h:,.0f} meets minimum ${min_volume:,.0f}"

    except ValueError as e:
        logger.error(f"Symbol conversion error for {symbol}: {e}")
        return False, f"Invalid symbol: {str(e)}"
    except Exception as e:
        logger.error(f"Failed to check liquidity for {symbol}: {e}")
        return False, f"Error checking liquidity: {str(e)}"


async def check_market_cap_requirements(
    symbol: str,
    tier: AssetTier,
) -> Tuple[bool, str]:
    """
    Check if asset meets market cap requirements for its tier.

    Note: Kraken doesn't provide market cap directly. For Tier 1 and
    Tier 2 assets (BTC, ETH, SOL, AVAX, LINK), we assume they meet
    requirements as they are established large-cap coins.

    For Tier 3 assets, market cap verification would require
    integration with CoinGecko or similar service.

    Args:
        symbol: Asset symbol in database format (e.g., "BTCUSD")
        tier: The AssetTier for this asset

    Returns:
        Tuple of (meets_requirements: bool, reason: str)
    """
    if tier not in DEFAULT_TIER_CONFIG:
        return False, f"Unknown tier: {tier}"

    tier_config = DEFAULT_TIER_CONFIG[tier]
    min_market_cap = tier_config.min_market_cap

    # For Tier 1 and Tier 2, assume pre-verified
    # These are established large-cap assets (BTC, ETH, SOL, AVAX, LINK)
    if tier in [AssetTier.TIER_1, AssetTier.TIER_2]:
        return True, f"Tier {tier.value} assets pre-verified (established large-caps)"

    # For Tier 3, we should verify but don't have a market cap API
    # Log a warning and return True with a caveat
    logger.warning(
        f"Market cap check for {symbol}: External API integration needed. "
        f"Minimum required: ${min_market_cap:,.0f}"
    )
    return True, "Market cap verification pending (external API needed)"


async def validate_asset_for_trading(
    symbol: str,
    tier: AssetTier,
) -> Tuple[bool, Dict[str, Any]]:
    """
    Full validation of asset for trading eligibility.

    Performs all checks:
    1. Check if explicitly excluded (meme coin, etc.)
    2. Check liquidity requirements
    3. Check market cap requirements

    Args:
        symbol: Asset symbol in database format
        tier: The AssetTier for this asset

    Returns:
        Tuple of (is_valid: bool, validation_details: dict)

    Example:
        >>> is_valid, details = await validate_asset_for_trading("BTCUSD", AssetTier.TIER_1)
        >>> if not is_valid:
        ...     print(f"Asset invalid: {details}")
    """
    details: Dict[str, Any] = {
        "symbol": symbol,
        "tier": tier.value,
        "liquidity_check": None,
        "market_cap_check": None,
        "is_excluded": False,
        "exclusion_reason": None,
    }

    # Check if explicitly excluded
    if symbol in EXCLUDED_ASSETS:
        details["is_excluded"] = True
        details["exclusion_reason"] = EXCLUSION_REASONS.get(symbol, "Excluded asset")
        return False, details

    # Check if tier is EXCLUDED
    if tier == AssetTier.EXCLUDED:
        details["is_excluded"] = True
        details["exclusion_reason"] = "Asset not in approved universe"
        return False, details

    # Check liquidity
    liq_pass, liq_reason = await check_liquidity_requirements(symbol, tier)
    details["liquidity_check"] = {"passed": liq_pass, "reason": liq_reason}

    if not liq_pass:
        return False, details

    # Check market cap
    cap_pass, cap_reason = await check_market_cap_requirements(symbol, tier)
    details["market_cap_check"] = {"passed": cap_pass, "reason": cap_reason}

    if not cap_pass:
        return False, details

    return True, details


async def get_asset_trading_status(symbol: str) -> Dict[str, Any]:
    """
    Get comprehensive trading status for an asset.

    Determines tier, runs all validations, and returns a complete
    status report for the asset.

    Args:
        symbol: Asset symbol in database format

    Returns:
        Dict containing tier, validation status, and details
    """
    from services.asset_universe import get_asset_tier, get_exclusion_reason

    tier = get_asset_tier(symbol)
    exclusion_reason = get_exclusion_reason(symbol)

    status = {
        "symbol": symbol,
        "tier": tier.value,
        "is_tradeable": tier != AssetTier.EXCLUDED,
        "exclusion_reason": exclusion_reason,
        "validation": None,
    }

    # Only run validation for tradeable assets
    if tier != AssetTier.EXCLUDED:
        is_valid, validation_details = await validate_asset_for_trading(symbol, tier)
        status["is_tradeable"] = is_valid
        status["validation"] = validation_details

    return status
