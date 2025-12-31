"""
APScheduler configuration for the Contrarian AI Trading Bot.

This module provides the scheduler setup and the main ingestion jobs:
- OHLCV data fetching from Kraken at 15-minute intervals (Story 1.3)
- Sentiment data fetching from LunarCrush/socials at 15-minute intervals (Story 1.4)

Based on Story 1.3: Kraken Data Ingestor requirements.
Based on Story 1.4: Sentiment Ingestor requirements.
"""

import asyncio
import logging
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlmodel.ext.asyncio.session import AsyncSession

from config import get_config
from database import get_session_maker
from models import Asset, Candle, SentimentLog
from services.kraken import get_kraken_client, KrakenClient
from services.sentiment import (
    SentimentService,
    get_sentiment_service,
    AssetRotator,
    save_sentiment_log,
)

# Configure logging
logger = logging.getLogger("kraken_ingestor")


async def get_active_assets(session: AsyncSession) -> list[Asset]:
    """
    Fetch all active assets from the database.

    Args:
        session: Database session

    Returns:
        List of active Asset objects
    """
    from sqlmodel import select

    statement = select(Asset).where(Asset.is_active == True)  # noqa: E712
    result = await session.execute(statement)
    assets = result.scalars().all()
    return list(assets)


async def upsert_candle(
    session: AsyncSession,
    asset_id: str,
    candle_data: dict[str, Any],
) -> bool:
    """
    Upsert a single candle into the database.

    Uses PostgreSQL ON CONFLICT DO UPDATE to handle duplicates.

    Args:
        session: Database session
        asset_id: Asset ID from database
        candle_data: Dict with timestamp, open, high, low, close, volume, timeframe

    Returns:
        True if upsert was successful
    """
    from sqlalchemy.dialects.postgresql import insert

    try:
        stmt = insert(Candle).values(
            asset_id=asset_id,
            timestamp=candle_data["timestamp"],
            timeframe=candle_data["timeframe"],
            open=candle_data["open"],
            high=candle_data["high"],
            low=candle_data["low"],
            close=candle_data["close"],
            volume=candle_data["volume"],
        )

        # On conflict, update all price/volume fields
        stmt = stmt.on_conflict_do_update(
            index_elements=["assetId", "timestamp", "timeframe"],
            set_={
                "open": stmt.excluded.open,
                "high": stmt.excluded.high,
                "low": stmt.excluded.low,
                "close": stmt.excluded.close,
                "volume": stmt.excluded.volume,
            }
        )

        await session.execute(stmt)
        return True

    except Exception as e:
        logger.error(f"Failed to upsert candle for asset {asset_id}: {e}")
        return False


async def update_asset_price(
    session: AsyncSession,
    asset_id: str,
    last_price: Decimal,
) -> None:
    """
    Update the last price and timestamp for an asset.

    Args:
        session: Database session
        asset_id: Asset ID
        last_price: Latest close price
    """
    from sqlmodel import select

    try:
        statement = select(Asset).where(Asset.id == asset_id)
        result = await session.execute(statement)
        asset = result.scalar_one_or_none()

        if asset:
            asset.last_price = last_price
            asset.last_updated = datetime.now(timezone.utc)
            session.add(asset)

    except Exception as e:
        logger.error(f"Failed to update asset price for {asset_id}: {e}")


async def ingest_single_asset(
    kraken_client: KrakenClient,
    session: AsyncSession,
    asset: Asset,
) -> tuple[bool, int]:
    """
    Fetch and upsert candle data for a single asset.

    Args:
        kraken_client: Kraken API client
        session: Database session
        asset: Asset to fetch data for

    Returns:
        Tuple of (success: bool, candle_count: int)
    """
    try:
        # Fetch OHLCV data
        candles = await kraken_client.fetch_ohlcv_for_asset(
            asset.symbol,
            timeframe="15m",
            limit=1,
        )

        if not candles:
            logger.warning(f"No candle data returned for {asset.symbol}")
            return False, 0

        # Upsert each candle
        upserted_count = 0
        for candle_data in candles:
            if await upsert_candle(session, asset.id, candle_data):
                upserted_count += 1

                # Update asset's last price
                await update_asset_price(
                    session,
                    asset.id,
                    candle_data["close"],
                )

        return True, upserted_count

    except ValueError as e:
        # Invalid symbol mapping
        logger.error(f"Symbol mapping error for {asset.symbol}: {e}")
        return False, 0

    except Exception as e:
        logger.error(f"Error fetching data for {asset.symbol}: {e}")
        return False, 0


async def ingest_kraken_data() -> dict[str, Any]:
    """
    Main ingestion job function called by scheduler.

    Fetches OHLCV data for all active assets and upserts to database.
    Processes assets in batches with rate limiting.

    Returns:
        Dict with ingestion statistics
    """
    start_time = datetime.now(timezone.utc)
    logger.info(f"Starting Kraken ingestion at {start_time.isoformat()}")

    config = get_config()
    kraken_client = get_kraken_client()

    # Initialize client
    await kraken_client.initialize()

    stats = {
        "start_time": start_time.isoformat(),
        "total_assets": 0,
        "successful": 0,
        "failed": 0,
        "candles_upserted": 0,
        "errors": [],
    }

    try:
        # Get async session
        session_maker = get_session_maker()
        async with session_maker() as session:
            # Fetch active assets
            assets = await get_active_assets(session)
            stats["total_assets"] = len(assets)

            if not assets:
                logger.warning("No active assets found in database")
                return stats

            logger.info(f"Processing {len(assets)} active assets")

            # Process assets in batches of 5
            batch_size = 5
            for i in range(0, len(assets), batch_size):
                batch = assets[i:i + batch_size]

                for asset in batch:
                    success, count = await ingest_single_asset(
                        kraken_client,
                        session,
                        asset,
                    )

                    if success:
                        stats["successful"] += 1
                        stats["candles_upserted"] += count
                    else:
                        stats["failed"] += 1

                    # Rate limiting delay between API calls
                    await asyncio.sleep(config.kraken.rate_limit_ms / 1000)

                # Commit after each batch
                await session.commit()
                logger.info(f"Processed {min(i + batch_size, len(assets))}/{len(assets)} assets")

    except Exception as e:
        error_msg = f"Ingestion error: {str(e)}"
        logger.error(error_msg)
        stats["errors"].append(error_msg)

    # Calculate duration
    end_time = datetime.now(timezone.utc)
    duration = (end_time - start_time).total_seconds()
    stats["end_time"] = end_time.isoformat()
    stats["duration_seconds"] = duration

    # Log summary
    logger.info(
        f"Kraken ingestion complete. "
        f"Success: {stats['successful']}/{stats['total_assets']}, "
        f"Candles: {stats['candles_upserted']}, "
        f"Duration: {duration:.2f}s"
    )

    # Log alert if any failures
    if stats["failed"] > 0:
        logger.warning(f"Ingestion completed with {stats['failed']} failed assets")

    # Log critical alert if all failed
    if stats["total_assets"] > 0 and stats["successful"] == 0:
        logger.critical("ALERT: Complete ingestion cycle failure - no assets processed successfully")

    return stats


# Sentiment ingestion logger
sentiment_logger = logging.getLogger("sentiment_ingestor")

# Global asset rotator for LunarCrush rate limiting
_asset_rotator: AssetRotator | None = None


async def ingest_sentiment_data() -> dict[str, Any]:
    """
    Main ingestion job function for sentiment data.

    Fetches sentiment for active assets and saves to database.
    Uses rotation strategy to stay within LunarCrush API limits.

    Returns:
        Dict with ingestion statistics
    """
    start_time = datetime.now(timezone.utc)
    sentiment_logger.info(f"Starting sentiment ingestion at {start_time.isoformat()}")

    config = get_config()
    sentiment_service = get_sentiment_service()

    stats = {
        "start_time": start_time.isoformat(),
        "total_assets": 0,
        "successful": 0,
        "failed": 0,
        "lunarcrush_calls": 0,
        "errors": [],
    }

    try:
        # Get async session
        session_maker = get_session_maker()
        async with session_maker() as session:
            # Fetch active assets
            assets = await get_active_assets(session)
            stats["total_assets"] = len(assets)

            if not assets:
                sentiment_logger.warning("No active assets found in database")
                return stats

            # Initialize or update rotator
            global _asset_rotator
            if _asset_rotator is None:
                _asset_rotator = AssetRotator(
                    assets,
                    num_groups=config.lunarcrush.rotation_groups,
                )

            # Get current group for LunarCrush (to respect API limits)
            current_group = _asset_rotator.get_current_group()
            sentiment_logger.info(
                f"Processing group {_asset_rotator.current_group_index + 1}/"
                f"{config.lunarcrush.rotation_groups} "
                f"({len(current_group)} assets for LunarCrush)"
            )

            # Check remaining LunarCrush quota
            remaining_quota = sentiment_service.lunarcrush.get_remaining_quota()
            sentiment_logger.info(f"LunarCrush quota remaining: {remaining_quota}")

            # Process all assets for social data, but only current group for LunarCrush
            for asset in assets:
                try:
                    # Determine if this asset should fetch LunarCrush data
                    fetch_lunarcrush = asset in current_group

                    # Fetch sentiment from all sources
                    sentiment = await sentiment_service.fetch_all_sentiment(
                        asset.symbol,
                        fetch_lunarcrush=fetch_lunarcrush,
                        fetch_socials=True,
                    )

                    if fetch_lunarcrush and sentiment.lunarcrush is not None:
                        stats["lunarcrush_calls"] += 1

                    # Save to database
                    await save_sentiment_log(
                        session,
                        asset_id=asset.id,
                        source="aggregated",
                        sentiment=sentiment,
                    )

                    stats["successful"] += 1

                except Exception as e:
                    stats["failed"] += 1
                    error_msg = f"Error processing {asset.symbol}: {str(e)}"
                    stats["errors"].append(error_msg)
                    sentiment_logger.error(error_msg)

                # Small delay between assets
                await asyncio.sleep(0.1)

            # Commit all changes
            await session.commit()

            # Advance rotator for next cycle
            _asset_rotator.advance()

    except Exception as e:
        error_msg = f"Sentiment ingestion error: {str(e)}"
        sentiment_logger.error(error_msg)
        stats["errors"].append(error_msg)

    # Calculate duration
    end_time = datetime.now(timezone.utc)
    duration = (end_time - start_time).total_seconds()
    stats["end_time"] = end_time.isoformat()
    stats["duration_seconds"] = duration

    # Log summary
    sentiment_logger.info(
        f"Sentiment ingestion complete. "
        f"Success: {stats['successful']}/{stats['total_assets']}, "
        f"LunarCrush calls: {stats['lunarcrush_calls']}, "
        f"Duration: {duration:.2f}s"
    )

    # Log alert if any failures
    if stats["failed"] > 0:
        sentiment_logger.warning(
            f"Sentiment ingestion completed with {stats['failed']} failed assets"
        )

    # Log critical alert if all failed
    if stats["total_assets"] > 0 and stats["successful"] == 0:
        sentiment_logger.critical(
            "ALERT: Complete sentiment ingestion cycle failure - "
            "no assets processed successfully"
        )

    return stats


def create_scheduler() -> AsyncIOScheduler:
    """
    Create and configure the APScheduler instance.

    Returns:
        Configured AsyncIOScheduler
    """
    config = get_config()

    scheduler = AsyncIOScheduler(timezone=config.scheduler.timezone)

    # Add the Kraken ingestion job (Story 1.3)
    scheduler.add_job(
        ingest_kraken_data,
        CronTrigger(minute=config.scheduler.ingest_cron_minutes),
        id="kraken_ingest",
        name="Kraken OHLCV Ingestion",
        replace_existing=True,
        max_instances=1,  # Prevent overlapping executions
    )

    logger.info(
        f"Scheduler configured with Kraken ingestion at minutes: {config.scheduler.ingest_cron_minutes}"
    )

    # Add the Sentiment ingestion job (Story 1.4)
    # Runs at the same 15-minute intervals but slightly offset to avoid conflicts
    scheduler.add_job(
        ingest_sentiment_data,
        CronTrigger(minute=config.scheduler.ingest_cron_minutes),
        id="sentiment_ingest",
        name="Sentiment Data Ingestion",
        replace_existing=True,
        max_instances=1,  # Prevent overlapping executions
    )

    sentiment_logger.info(
        f"Scheduler configured with Sentiment ingestion at minutes: {config.scheduler.ingest_cron_minutes}"
    )

    return scheduler


# Global scheduler instance
_scheduler: AsyncIOScheduler | None = None


def get_scheduler() -> AsyncIOScheduler:
    """Get or create the global scheduler instance."""
    global _scheduler
    if _scheduler is None:
        _scheduler = create_scheduler()
    return _scheduler
