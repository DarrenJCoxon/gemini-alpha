"""
APScheduler configuration for the Contrarian AI Trading Bot.

This module provides the scheduler setup and the main ingestion jobs:
- OHLCV data fetching from Kraken at 15-minute intervals (Story 1.3)
- Sentiment data fetching from LunarCrush/socials at 15-minute intervals (Story 1.4)
- Position management every 15 minutes (Story 3.3)

Based on Story 1.3: Kraken Data Ingestor requirements.
Based on Story 1.4: Sentiment Ingestor requirements.
Based on Story 3.3: Position Manager requirements.
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

# Council cycle logger
council_logger = logging.getLogger("council_cycle")

# Position manager logger
position_logger = logging.getLogger("position_manager")


async def run_position_check() -> dict[str, Any]:
    """
    Run position management check cycle.

    Story 3.3: Position Manager (Trailing Stops & Exits)

    Called every 15 minutes by scheduler. This MUST run BEFORE the Council
    cycle to ensure we don't hold losing positions while debating new entries.

    Priority Order (CRITICAL - capital preservation first):
    1. Stop Loss - Check and close if price <= stop
    2. Council SELL - Close on reversal signals
    3. Breakeven Trigger - Lock in entry price
    4. Trailing Stop - Maximize profits

    Returns:
        Dict with position check statistics
    """
    from services.position_manager import check_open_positions

    start_time = datetime.now(timezone.utc)
    position_logger.info(f"\n{'='*60}")
    position_logger.info(f"[Position] Starting position check at {start_time.isoformat()}")
    position_logger.info(f"{'='*60}")

    stats = {
        "start_time": start_time.isoformat(),
        "positions_checked": 0,
        "stops_hit": 0,
        "breakevens_triggered": 0,
        "trailing_updates": 0,
        "council_closes": 0,
        "errors": 0,
    }

    try:
        # Run position check (without Council decisions - those come later)
        result = await check_open_positions()
        stats.update(result)

    except Exception as e:
        error_msg = f"Position check error: {str(e)}"
        position_logger.error(f"[Position] {error_msg}")
        stats["errors"] += 1

    # Calculate duration
    end_time = datetime.now(timezone.utc)
    duration = (end_time - start_time).total_seconds()
    stats["end_time"] = end_time.isoformat()
    stats["duration_seconds"] = duration

    position_logger.info(f"[Position] Position check complete")
    position_logger.info(
        f"[Position] Checked: {stats['positions_checked']}, "
        f"Stops Hit: {stats['stops_hit']}, "
        f"Breakevens: {stats['breakevens_triggered']}, "
        f"Trailing: {stats['trailing_updates']}, "
        f"Duration: {duration:.2f}s"
    )
    position_logger.info(f"{'='*60}\n")

    return stats


async def run_council_cycle() -> dict[str, Any]:
    """
    Run council decision cycle for all active assets.

    Story 2.4: Master Node & Signal Logging
    Story 3.1: Kraken Order Execution Service

    Called every 15 minutes by scheduler. Processes each active asset
    through the Council of AI Agents and logs decisions to database.

    BUY signals trigger execute_buy() via the execution service.
    In sandbox mode, orders are logged but not executed on Kraken.

    Returns:
        Dict with cycle statistics
    """
    from core.graph import get_council_graph
    from core.state import create_initial_state
    from services.data_loader import (
        load_candles_for_asset,
        load_sentiment_for_asset,
        get_active_assets as load_active_assets,
    )
    from services.session_logger import log_council_session
    from services.execution import execute_buy, has_open_position
    from services.kraken_execution import get_kraken_execution_client

    start_time = datetime.now(timezone.utc)
    council_logger.info(f"\n{'='*60}")
    council_logger.info(f"[Cycle] Starting council cycle at {start_time.isoformat()}")
    council_logger.info(f"{'='*60}")

    # Check execution mode
    exec_client = get_kraken_execution_client()
    exec_mode = "SANDBOX" if exec_client.is_sandbox else "LIVE"
    council_logger.info(f"[Cycle] Execution mode: {exec_mode}")

    stats = {
        "start_time": start_time.isoformat(),
        "total_assets": 0,
        "processed": 0,
        "skipped": 0,
        "buy_signals": 0,
        "sell_signals": 0,
        "hold_signals": 0,
        "orders_executed": 0,
        "orders_blocked": 0,
        "errors": [],
    }

    # Default position size in USD (can be configured)
    default_position_size_usd = 100.0

    try:
        # Get the cached Council graph
        council_graph = get_council_graph()

        # Get async session
        session_maker = get_session_maker()
        async with session_maker() as session:
            # Get active assets
            assets = await load_active_assets(session)
            stats["total_assets"] = len(assets)

            if not assets:
                council_logger.warning("[Cycle] No active assets found in database")
                return stats

            council_logger.info(f"[Cycle] Processing {len(assets)} active assets")

            for asset in assets:
                council_logger.info(f"\n[Cycle] Processing {asset.symbol}...")

                try:
                    # Load data for asset
                    candles = await load_candles_for_asset(
                        asset.id, limit=200, session=session
                    )
                    sentiment = await load_sentiment_for_asset(
                        asset.symbol, hours=24, session=session
                    )

                    # Check for sufficient data
                    if len(candles) < 50:
                        council_logger.warning(
                            f"[Cycle] Skipping {asset.symbol} - insufficient candle data "
                            f"({len(candles)} candles, need 50+)"
                        )
                        stats["skipped"] += 1
                        continue

                    # Build initial state
                    initial_state = create_initial_state(
                        asset_symbol=asset.symbol,
                        candles_data=candles,
                        sentiment_data=sentiment,
                    )

                    # Run council graph
                    council_logger.info(f"[Cycle] Running council for {asset.symbol}...")
                    final_state = council_graph.invoke(initial_state)

                    # Log session to database
                    await log_council_session(final_state, asset.id, session=session)

                    # Extract decision for stats
                    decision = final_state.get("final_decision", {})
                    action = decision.get("action", "HOLD")

                    council_logger.info(
                        f"[Cycle] {asset.symbol} Decision: {action} "
                        f"(Confidence: {decision.get('confidence', 0)}%)"
                    )

                    # Update stats
                    stats["processed"] += 1

                    if action == "BUY":
                        stats["buy_signals"] += 1

                        # Story 3.1: Check for existing position before executing
                        if await has_open_position(asset.id, session):
                            council_logger.info(
                                f"[Cycle] BUY blocked for {asset.symbol} - "
                                f"open position already exists"
                            )
                            stats["orders_blocked"] += 1
                        else:
                            # Extract stop loss from decision if available
                            stop_loss_price = decision.get("stop_loss_price")

                            # Execute buy order via execution service
                            council_logger.info(
                                f"[Cycle] Executing BUY for {asset.symbol} "
                                f"(${default_position_size_usd:.2f} USD)..."
                            )

                            success, error, trade = await execute_buy(
                                symbol=asset.symbol,
                                amount_usd=default_position_size_usd,
                                stop_loss_price=stop_loss_price,
                                client=exec_client,
                                session=session,
                            )

                            if success:
                                stats["orders_executed"] += 1
                                council_logger.info(
                                    f"[Cycle] [{exec_mode}] BUY order executed: "
                                    f"Trade ID {trade.id if trade else 'N/A'}"
                                )
                            else:
                                stats["orders_blocked"] += 1
                                council_logger.warning(
                                    f"[Cycle] BUY order failed for {asset.symbol}: {error}"
                                )

                    elif action == "SELL":
                        stats["sell_signals"] += 1
                        council_logger.info(
                            f"[Cycle] SELL signal logged for {asset.symbol} - "
                            f"position management handled by Story 3.3"
                        )
                    else:
                        stats["hold_signals"] += 1

                except Exception as e:
                    error_msg = f"Error processing {asset.symbol}: {str(e)}"
                    council_logger.error(f"[Cycle] {error_msg}")
                    stats["errors"].append(error_msg)
                    continue

    except Exception as e:
        error_msg = f"Council cycle error: {str(e)}"
        council_logger.error(f"[Cycle] {error_msg}")
        stats["errors"].append(error_msg)

    # Calculate duration
    end_time = datetime.now(timezone.utc)
    duration = (end_time - start_time).total_seconds()
    stats["end_time"] = end_time.isoformat()
    stats["duration_seconds"] = duration

    council_logger.info(f"\n[Cycle] Council cycle complete")
    council_logger.info(
        f"[Cycle] Processed: {stats['processed']}/{stats['total_assets']}, "
        f"Skipped: {stats['skipped']}, "
        f"BUY: {stats['buy_signals']}, SELL: {stats['sell_signals']}, "
        f"HOLD: {stats['hold_signals']}"
    )
    council_logger.info(
        f"[Cycle] Orders: Executed={stats['orders_executed']}, "
        f"Blocked={stats['orders_blocked']}, "
        f"Duration: {duration:.2f}s"
    )
    council_logger.info(f"{'='*60}\n")

    return stats


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

    Job Execution Order (Story 3.3 - CRITICAL):
    1. :00, :15, :30, :45 - Data ingestion (Kraken + Sentiment)
    2. :03, :18, :33, :48 - Position check (stops/breakeven/trailing)
    3. :05, :20, :35, :50 - Council cycle (analysis + new entries)

    Position check runs BEFORE Council to protect capital first.

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

    # Add the Position check job (Story 3.3)
    # Runs 3 minutes after ingestion to allow data to be available
    # MUST run BEFORE Council cycle to protect capital first
    # e.g., runs at :03, :18, :33, :48
    scheduler.add_job(
        run_position_check,
        CronTrigger(minute="3,18,33,48"),
        id="position_check",
        name="Position Manager Check",
        replace_existing=True,
        max_instances=1,  # Prevent overlapping executions
    )

    position_logger.info(
        "Scheduler configured with Position check at minutes: 3,18,33,48 "
        "(runs BEFORE Council cycle)"
    )

    # Add the Council cycle job (Story 2.4)
    # Runs at 15-minute intervals, offset by 5 minutes to allow data ingestion first
    # e.g., if ingestion runs at :00, :15, :30, :45, council runs at :05, :20, :35, :50
    scheduler.add_job(
        run_council_cycle,
        CronTrigger(minute="5,20,35,50"),
        id="council_cycle",
        name="Council Decision Cycle (Paper Trading)",
        replace_existing=True,
        max_instances=1,  # Prevent overlapping executions
    )

    council_logger.info(
        "Scheduler configured with Council cycle at minutes: 5,20,35,50 (Paper Trading mode)"
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
