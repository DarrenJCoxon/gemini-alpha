"""
Asset seeding script for quality asset universe.

Story 5.2: Asset Universe Reduction

This script seeds the database with quality assets (8-10) instead of
the original 30 assets. Each asset is assigned a tier with appropriate
allocation limits and requirements.

Usage:
    python -m scripts.seed_assets

Or from the project root:
    cd apps/bot && source .venv/bin/activate && python -m scripts.seed_assets
"""

import asyncio
import os
import sys
from decimal import Decimal
from typing import List

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

from models import Asset
from services.asset_universe import (
    get_full_asset_universe,
    get_asset_tier,
    get_max_allocation,
    EXCLUDED_ASSETS,
    EXCLUSION_REASONS,
    DEFAULT_TIER_CONFIG,
    AssetTier,
)


# Asset name mappings (symbol -> display name)
ASSET_NAMES = {
    "BTCUSD": "Bitcoin",
    "ETHUSD": "Ethereum",
    "SOLUSD": "Solana",
    "AVAXUSD": "Avalanche",
    "LINKUSD": "Chainlink",
    "AAVEUSD": "Aave",
    "UNIUSD": "Uniswap",
    "ARBUSD": "Arbitrum",
    "OPUSD": "Optimism",
    "MATICUSD": "Polygon",
    "ATOMUSD": "Cosmos",
    "DOTUSD": "Polkadot",
    "ADAUSD": "Cardano",
    # Meme coins (excluded)
    "DOGEUSD": "Dogecoin",
    "SHIBUSD": "Shiba Inu",
    "PEPEUSD": "Pepe",
    "FLOKIUSD": "Floki",
    "BONKUSD": "Bonk",
}


async def seed_quality_assets(session: AsyncSession) -> dict:
    """
    Seed database with quality asset universe (8-10 assets).

    Creates or updates assets with tier assignments, allocation limits,
    and volume/market cap thresholds.

    Args:
        session: Database session

    Returns:
        Dict with seeding statistics
    """
    # Get all tradeable assets
    asset_symbols = get_full_asset_universe()

    stats = {
        "total": len(asset_symbols),
        "created": 0,
        "updated": 0,
        "errors": [],
    }

    print(f"\nSeeding {len(asset_symbols)} quality assets...")
    print(f"{'='*60}")

    for symbol in asset_symbols:
        tier = get_asset_tier(symbol)
        tier_config = DEFAULT_TIER_CONFIG.get(tier)

        try:
            # Check for existing asset
            statement = select(Asset).where(Asset.symbol == symbol)
            result = await session.execute(statement)
            existing = result.scalar_one_or_none()

            if existing:
                # Update existing asset with tier info
                existing.tier = tier.value
                existing.max_allocation_percent = get_max_allocation(tier)
                existing.min_volume_24h = tier_config.min_volume_24h if tier_config else None
                existing.min_market_cap = tier_config.min_market_cap if tier_config else None
                existing.is_meme_coin = False
                existing.is_active = True
                existing.exclusion_reason = None
                session.add(existing)
                stats["updated"] += 1
                print(f"  Updated: {symbol} ({tier.value})")
            else:
                # Create new asset
                asset = Asset(
                    symbol=symbol,
                    name=ASSET_NAMES.get(symbol, symbol.replace("USD", "")),
                    is_active=True,
                    tier=tier.value,
                    max_allocation_percent=get_max_allocation(tier),
                    min_volume_24h=tier_config.min_volume_24h if tier_config else None,
                    min_market_cap=tier_config.min_market_cap if tier_config else None,
                    is_meme_coin=False,
                )
                session.add(asset)
                stats["created"] += 1
                print(f"  Created: {symbol} ({tier.value})")

        except Exception as e:
            error_msg = f"Error processing {symbol}: {str(e)}"
            stats["errors"].append(error_msg)
            print(f"  ERROR: {error_msg}")

    await session.commit()
    return stats


async def deactivate_excluded_assets(session: AsyncSession) -> dict:
    """
    Mark excluded assets as inactive with exclusion reasons.

    Updates any existing assets that are now excluded (meme coins, etc.)
    to have is_active=False and appropriate exclusion reasons.

    Args:
        session: Database session

    Returns:
        Dict with deactivation statistics
    """
    stats = {
        "total": len(EXCLUDED_ASSETS),
        "deactivated": 0,
        "not_found": 0,
    }

    print(f"\nProcessing {len(EXCLUDED_ASSETS)} excluded assets...")
    print(f"{'='*60}")

    for symbol in EXCLUDED_ASSETS:
        statement = select(Asset).where(Asset.symbol == symbol)
        result = await session.execute(statement)
        asset = result.scalar_one_or_none()

        if asset:
            asset.is_active = False
            asset.tier = AssetTier.EXCLUDED.value
            asset.exclusion_reason = EXCLUSION_REASONS.get(symbol, "Excluded asset")
            asset.is_meme_coin = True
            asset.max_allocation_percent = Decimal("0")
            session.add(asset)
            stats["deactivated"] += 1
            print(f"  Deactivated: {symbol} - {asset.exclusion_reason}")
        else:
            stats["not_found"] += 1
            print(f"  Not found: {symbol}")

    await session.commit()
    return stats


async def deactivate_non_universe_assets(session: AsyncSession) -> dict:
    """
    Deactivate any active assets not in the quality universe.

    This handles the transition from 30 assets to 8-10 by marking
    previously active assets that are not in the new universe as inactive.

    Args:
        session: Database session

    Returns:
        Dict with deactivation statistics
    """
    quality_universe = set(get_full_asset_universe())

    stats = {
        "checked": 0,
        "deactivated": 0,
    }

    print(f"\nDeactivating assets not in quality universe...")
    print(f"Quality universe: {quality_universe}")
    print(f"{'='*60}")

    # Get all active assets
    statement = select(Asset).where(Asset.is_active == True)  # noqa: E712
    result = await session.execute(statement)
    active_assets = result.scalars().all()

    for asset in active_assets:
        stats["checked"] += 1

        if asset.symbol not in quality_universe:
            asset.is_active = False
            if not asset.tier or asset.tier != AssetTier.EXCLUDED.value:
                asset.tier = AssetTier.EXCLUDED.value
            if not asset.exclusion_reason:
                asset.exclusion_reason = "Not in quality asset universe"
            session.add(asset)
            stats["deactivated"] += 1
            print(f"  Deactivated: {asset.symbol}")

    await session.commit()
    return stats


async def run_seed() -> bool:
    """Run the complete seeding process."""
    # Load environment variables
    load_dotenv()

    # Get database URL
    database_url = os.getenv("DATABASE_URL", "")
    if not database_url:
        print("ERROR: DATABASE_URL environment variable is not set")
        return False

    # Convert to async driver
    if database_url.startswith("postgres://"):
        database_url = database_url.replace("postgres://", "postgresql+asyncpg://", 1)
    elif database_url.startswith("postgresql://"):
        database_url = database_url.replace("postgresql://", "postgresql+asyncpg://", 1)

    print(f"Connecting to database...")

    try:
        # Create engine and session
        engine = create_async_engine(database_url, echo=False)
        async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

        async with async_session() as session:
            # Step 1: Seed quality assets
            quality_stats = await seed_quality_assets(session)

            # Step 2: Deactivate excluded assets
            excluded_stats = await deactivate_excluded_assets(session)

            # Step 3: Deactivate non-universe assets
            non_universe_stats = await deactivate_non_universe_assets(session)

            # Print summary
            print(f"\n{'='*60}")
            print("SEED SUMMARY")
            print(f"{'='*60}")
            print(f"\nQuality Assets:")
            print(f"  Created: {quality_stats['created']}")
            print(f"  Updated: {quality_stats['updated']}")
            print(f"  Errors: {len(quality_stats['errors'])}")

            print(f"\nExcluded Assets:")
            print(f"  Deactivated: {excluded_stats['deactivated']}")
            print(f"  Not found: {excluded_stats['not_found']}")

            print(f"\nNon-Universe Assets:")
            print(f"  Checked: {non_universe_stats['checked']}")
            print(f"  Deactivated: {non_universe_stats['deactivated']}")

            # Count final active assets
            statement = select(Asset).where(Asset.is_active == True)  # noqa: E712
            result = await session.execute(statement)
            active_count = len(result.scalars().all())

            print(f"\nFinal active asset count: {active_count}")
            print(f"{'='*60}\n")

            if quality_stats["errors"]:
                print("Errors encountered:")
                for error in quality_stats["errors"]:
                    print(f"  - {error}")
                return False

            return True

    except Exception as e:
        print(f"\nERROR: Seed failed: {e}")
        return False
    finally:
        await engine.dispose()


def main() -> None:
    """Main entry point."""
    success = asyncio.run(run_seed())
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
