"""
Seed verification script for the trading bot.

This script verifies that:
1. Python can connect to the database
2. Python can read the seeded Asset data
3. All 30 expected assets are present

Usage:
    python -m scripts.verify_seed

Or from the project root:
    cd apps/bot && source .venv/bin/activate && python -m scripts.verify_seed
"""

import asyncio
import os
import sys
from typing import List

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlalchemy.ext.asyncio import create_async_engine

from models import Asset


# Expected asset symbols
EXPECTED_SYMBOLS = [
    "BTCUSD", "ETHUSD", "SOLUSD", "DOTUSD", "ADAUSD",
    "AVAXUSD", "LINKUSD", "MATICUSD", "ATOMUSD", "UNIUSD",
    "XLMUSD", "ALGOUSD", "NEARUSD", "FILUSD", "APTUSD",
    "ARBUSD", "OPUSD", "INJUSD", "SUIUSD", "TIAUSD",
    "IMXUSD", "RNDRUSD", "GRTUSD", "SANDUSD", "MANAUSD",
    "AAVEUSD", "MKRUSD", "SNXUSD", "COMPUSD", "LDOUSD",
]


async def verify_seed() -> bool:
    """Verify that the database has been seeded correctly."""
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
        # Create engine
        engine = create_async_engine(database_url, echo=False)

        async with AsyncSession(engine) as session:
            # Query all assets
            statement = select(Asset)
            result = await session.exec(statement)
            assets: List[Asset] = result.all()

            print(f"\n{'='*60}")
            print("SEED VERIFICATION RESULTS")
            print(f"{'='*60}\n")

            # Check count
            print(f"Total assets found: {len(assets)}")
            print(f"Expected assets: {len(EXPECTED_SYMBOLS)}")

            if len(assets) != len(EXPECTED_SYMBOLS):
                print(f"\nWARNING: Asset count mismatch!")

            # Check each expected symbol
            found_symbols = {asset.symbol for asset in assets}
            missing = set(EXPECTED_SYMBOLS) - found_symbols
            extra = found_symbols - set(EXPECTED_SYMBOLS)

            if missing:
                print(f"\nMissing symbols: {missing}")
            if extra:
                print(f"\nExtra symbols: {extra}")

            # Print all assets
            print(f"\n{'='*60}")
            print("ASSETS IN DATABASE:")
            print(f"{'='*60}")
            print(f"{'Symbol':<12} {'Name':<20} {'Active':<8} {'Created At'}")
            print(f"{'-'*12} {'-'*20} {'-'*8} {'-'*20}")

            for asset in sorted(assets, key=lambda a: a.symbol):
                active_str = "Yes" if asset.is_active else "No"
                created_str = asset.created_at.strftime("%Y-%m-%d %H:%M:%S") if asset.created_at else "N/A"
                print(f"{asset.symbol:<12} {(asset.name or 'N/A'):<20} {active_str:<8} {created_str}")

            print(f"\n{'='*60}")

            # Final status
            if len(assets) == len(EXPECTED_SYMBOLS) and not missing:
                print("STATUS: VERIFICATION PASSED")
                print(f"{'='*60}\n")
                return True
            else:
                print("STATUS: VERIFICATION FAILED")
                print(f"{'='*60}\n")
                return False

    except Exception as e:
        print(f"\nERROR: Failed to verify seed: {e}")
        return False
    finally:
        await engine.dispose()


def main() -> None:
    """Main entry point."""
    success = asyncio.run(verify_seed())
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
