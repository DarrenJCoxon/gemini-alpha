"""
APScheduler configuration for the Contrarian AI Trading Bot.

This module provides the scheduler setup and the main ingestion jobs:

EVERY 15 MINUTES (capital protection):
- Kraken OHLCV at :00, :15, :30, :45 (fresh prices for stop checks)
- Position Manager at :03, :18, :33, :48 (stop-loss, trailing stops)

HOURLY (Council decisions - Basket Trading mode):
- Opportunity Scanner at :10 (find top opportunities)
- Sentiment + On-Chain at :14 (prep for Council)
- Council Cycle at :15 (AI analysis + trade execution)

Story References:
- Story 1.3: Kraken Data Ingestor
- Story 1.4: Sentiment Ingestor
- Story 3.3: Position Manager
- Story 3.4: Global Safety Switch
- Story 5.2: Asset Universe Reduction
- Story 5.6: On-Chain Data Integration
- Story 5.8: Dynamic Opportunity Scanner
- Story 5.9: Basket Trading System (optimized schedule)
"""

import asyncio
import logging
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, List

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
from services.asset_universe import (
    get_full_asset_universe,
    get_asset_tier,
    AssetTier,
)
from services.opportunity_scanner import run_opportunity_scan, get_dynamic_trading_universe

# Configure logging
logger = logging.getLogger("kraken_ingestor")


async def get_active_assets(session: AsyncSession) -> list[Asset]:
    """
    Fetch all active assets from the database.

    Story 5.2: Now filters to quality asset universe only.

    Args:
        session: Database session

    Returns:
        List of active Asset objects in quality universe
    """
    from sqlmodel import select

    statement = select(Asset).where(Asset.is_active == True)  # noqa: E712
    result = await session.execute(statement)
    assets = result.scalars().all()
    return list(assets)


async def get_quality_assets(session: AsyncSession) -> List[Asset]:
    """
    Fetch quality assets for council processing.

    Story 5.8: Now uses dynamic scanner universe when available.
    Falls back to static configuration (Story 5.2) if scanner disabled.

    Args:
        session: Database session

    Returns:
        List of Asset objects for council processing
    """
    from sqlmodel import select

    # Get dynamic universe (or fallback to static)
    quality_symbols = get_dynamic_trading_universe()

    # Query only assets in the quality universe
    statement = select(Asset).where(
        Asset.is_active == True,  # noqa: E712
        Asset.symbol.in_(quality_symbols),
    )
    result = await session.execute(statement)
    assets = list(result.scalars().all())

    logger.info(
        f"Trading universe: {len(assets)} assets "
        f"(requested: {len(quality_symbols)})"
    )

    return assets


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
    from models.base import generate_cuid

    try:
        stmt = insert(Candle).values(
            id=generate_cuid(),  # Must provide ID for Prisma schema
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
            # Use naive datetime for Prisma compatibility (data is always UTC)
            asset.last_updated = datetime.now(timezone.utc).replace(tzinfo=None)
            session.add(asset)

    except Exception as e:
        logger.error(f"Failed to update asset price for {asset_id}: {e}")


async def ingest_single_asset(
    kraken_client: KrakenClient,
    session: AsyncSession,
    asset: Asset,
    limit: int = 1,
) -> tuple[bool, int]:
    """
    Fetch and upsert candle data for a single asset.

    Args:
        kraken_client: Kraken API client
        session: Database session
        asset: Asset to fetch data for
        limit: Number of candles to fetch (default: 1 for regular ingestion)

    Returns:
        Tuple of (success: bool, candle_count: int)
    """
    try:
        # Fetch OHLCV data
        candles = await kraken_client.fetch_ohlcv_for_asset(
            asset.symbol,
            timeframe="15m",
            limit=limit,
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


async def backfill_kraken_data(limit: int = 200) -> dict[str, Any]:
    """
    Backfill historical OHLCV data from Kraken.

    Fetches multiple candles per asset to build up historical data.
    Use limit=200 for ~50 hours of 15-minute candles (enough for Council).
    Use limit=720 for ~1 week of 15-minute candles.

    Args:
        limit: Number of candles to fetch per asset (default: 200)

    Returns:
        Dict with backfill statistics
    """
    start_time = datetime.now(timezone.utc)
    logger.info(f"Starting Kraken BACKFILL at {start_time.isoformat()} (limit={limit})")

    config = get_config()
    kraken_client = get_kraken_client()

    # Initialize client
    await kraken_client.initialize()

    stats = {
        "start_time": start_time.isoformat(),
        "limit_per_asset": limit,
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

            logger.info(f"Backfilling {len(assets)} active assets with {limit} candles each")

            # Process assets one at a time with longer delays for backfill
            for i, asset in enumerate(assets):
                logger.info(f"Backfilling {asset.symbol} ({i+1}/{len(assets)})...")

                success, count = await ingest_single_asset(
                    kraken_client,
                    session,
                    asset,
                    limit=limit,
                )

                if success:
                    stats["successful"] += 1
                    stats["candles_upserted"] += count
                    logger.info(f"  -> {asset.symbol}: {count} candles upserted")
                else:
                    stats["failed"] += 1
                    logger.warning(f"  -> {asset.symbol}: FAILED")

                # Longer rate limiting delay for backfill to avoid rate limits
                await asyncio.sleep(max(config.kraken.rate_limit_ms / 500, 2.0))

                # Commit after each asset for backfill
                await session.commit()

    except Exception as e:
        error_msg = f"Backfill error: {str(e)}"
        logger.error(error_msg)
        stats["errors"].append(error_msg)

    # Calculate duration
    end_time = datetime.now(timezone.utc)
    duration = (end_time - start_time).total_seconds()
    stats["end_time"] = end_time.isoformat()
    stats["duration_seconds"] = duration

    # Log summary
    logger.info(
        f"Kraken BACKFILL complete. "
        f"Success: {stats['successful']}/{stats['total_assets']}, "
        f"Candles: {stats['candles_upserted']}, "
        f"Duration: {duration:.2f}s"
    )

    return stats


# Sentiment ingestion logger
sentiment_logger = logging.getLogger("sentiment_ingestor")

# Council cycle logger
council_logger = logging.getLogger("council_cycle")

# Position manager logger
position_logger = logging.getLogger("position_manager")

# Safety service logger
safety_logger = logging.getLogger("safety_service")

# On-chain ingestion logger (Story 5.6)
onchain_logger = logging.getLogger("onchain_ingestor")

# Scanner logger (Story 5.8)
scanner_logger = logging.getLogger("opportunity_scanner")


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
    Story 3.4: Global Safety Switch Integration
    Story 5.9: Basket Trading System Integration

    Called every 15 minutes (or hourly if basket.hourly_council_enabled).
    Processes each active asset through the Council of AI Agents.

    BASKET CHECKS (Story 5.9):
    1. Check if basket has room for new positions (max 10)
    2. Check correlation with existing positions
    3. Require reversal confirmation before BUY
    4. Consider position rotation if basket full

    SAFETY CHECKS (Story 3.4):
    1. Check is_trading_enabled() FIRST - skip if disabled
    2. Check enforce_max_drawdown() BEFORE Council
    3. If either check fails, skip Council and Execution

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
    from services.safety import (
        is_trading_enabled,
        get_system_status,
        enforce_max_drawdown,
    )
    from services.basket_manager import (
        can_open_new_position,
        get_position_count,
        initialize_basket_manager,
        calculate_dynamic_position_size,
    )
    from services.reversal_detector import (
        detect_bullish_reversal,
        detect_volume_exhaustion,
    )
    from models import SystemStatus

    start_time = datetime.now(timezone.utc)
    council_logger.info(f"\n{'='*60}")
    council_logger.info(f"[Cycle] Starting council cycle at {start_time.isoformat()}")
    council_logger.info(f"{'='*60}")

    # Initialize basket manager
    await initialize_basket_manager()

    # Check execution mode
    exec_client = get_kraken_execution_client()
    exec_mode = "SANDBOX" if exec_client.is_sandbox else "LIVE"
    council_logger.info(f"[Cycle] Execution mode: {exec_mode}")

    # Story 5.9: Log basket status
    config = get_config()
    basket_count = await get_position_count()
    council_logger.info(
        f"[Cycle] Basket: {basket_count}/{config.basket.max_positions} positions "
        f"(Fear threshold: <{config.basket.fear_threshold_buy}, "
        f"Greed threshold: >{config.basket.greed_threshold_sell})"
    )

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
        "basket_full_blocks": 0,
        "reversal_not_confirmed": 0,
        "insufficient_funds": 0,
        "errors": [],
    }

    # Story 5.10: Calculate dynamic position size based on portfolio value
    position_size_usd, size_reasoning = await calculate_dynamic_position_size(
        execution_client=exec_client,
    )

    if position_size_usd <= 0:
        council_logger.warning(f"[Cycle] {size_reasoning}")
        stats["skipped_reason"] = size_reasoning
        end_time = datetime.now(timezone.utc)
        stats["end_time"] = end_time.isoformat()
        stats["duration_seconds"] = (end_time - start_time).total_seconds()
        return stats

    council_logger.info(f"[Cycle] Position size: {size_reasoning}")

    # SAFETY CHECK 1 (Story 3.4): Is trading enabled?
    try:
        if not await is_trading_enabled():
            status = await get_system_status()
            council_logger.warning(
                f"[Cycle] Trading disabled (status: {status.value}). "
                "Skipping Council and Execution."
            )
            stats["skipped_reason"] = f"Trading disabled: {status.value}"

            # Calculate duration
            end_time = datetime.now(timezone.utc)
            duration = (end_time - start_time).total_seconds()
            stats["end_time"] = end_time.isoformat()
            stats["duration_seconds"] = duration

            return stats
    except Exception as e:
        council_logger.error(f"[Cycle] Safety check error: {e}")
        # Continue anyway - fail open for initial setup without DB

    # SAFETY CHECK 2 (Story 3.4): Drawdown guard
    try:
        if await enforce_max_drawdown():
            council_logger.critical(
                "[Cycle] Emergency stop triggered by drawdown guard. "
                "Cycle terminated."
            )
            stats["skipped_reason"] = "Emergency stop - max drawdown exceeded"

            # Calculate duration
            end_time = datetime.now(timezone.utc)
            duration = (end_time - start_time).total_seconds()
            stats["end_time"] = end_time.isoformat()
            stats["duration_seconds"] = duration

            return stats
    except Exception as e:
        council_logger.error(f"[Cycle] Drawdown check error: {e}")
        # Continue anyway - fail open for initial setup without DB

    council_logger.info("[Cycle] Safety checks passed. Proceeding with cycle.")

    try:
        # Get the cached Council graph
        council_graph = get_council_graph()

        # Get async session
        session_maker = get_session_maker()
        async with session_maker() as session:
            # Story 5.2: Get quality assets only (not all active assets)
            assets = await get_quality_assets(session)
            stats["total_assets"] = len(assets)

            if not assets:
                council_logger.warning("[Cycle] No quality assets found in database")
                return stats

            council_logger.info(f"[Cycle] Processing {len(assets)} quality assets")

            for asset in assets:
                # Story 5.2: Log tier information
                tier = get_asset_tier(asset.symbol)
                council_logger.info(f"\n[Cycle] Processing {asset.symbol} ({tier.value})...")

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

                        # Story 3.4: Re-check trading enabled before execution
                        try:
                            if not await is_trading_enabled():
                                council_logger.warning(
                                    f"[Cycle] BUY blocked for {asset.symbol} - "
                                    "trading disabled during cycle"
                                )
                                stats["orders_blocked"] += 1
                                continue
                        except Exception:
                            pass  # Continue if check fails

                        # Story 3.1: Check for existing position before executing
                        if await has_open_position(asset.id, session):
                            council_logger.info(
                                f"[Cycle] BUY blocked for {asset.symbol} - "
                                f"open position already exists"
                            )
                            stats["orders_blocked"] += 1
                            continue

                        # Story 5.9: Check basket capacity
                        can_open, basket_reason = await can_open_new_position(session)
                        if not can_open:
                            council_logger.info(
                                f"[Cycle] BUY blocked for {asset.symbol} - "
                                f"basket full ({basket_reason})"
                            )
                            stats["basket_full_blocks"] += 1
                            stats["orders_blocked"] += 1
                            continue

                        # Story 5.9: Require reversal confirmation
                        reversal = detect_bullish_reversal(candles)
                        if not reversal.is_confirmed:
                            council_logger.info(
                                f"[Cycle] BUY blocked for {asset.symbol} - "
                                f"reversal not confirmed: {reversal.reasoning}"
                            )
                            stats["reversal_not_confirmed"] += 1
                            stats["orders_blocked"] += 1
                            continue

                        council_logger.info(
                            f"[Cycle] Reversal confirmed for {asset.symbol}: "
                            f"{reversal.reasoning}"
                        )

                        # Extract stop loss from decision if available
                        stop_loss_price = decision.get("stop_loss_price")

                        # Execute buy order via execution service
                        # Story 5.10: Use dynamic position size
                        council_logger.info(
                            f"[Cycle] Executing BUY for {asset.symbol} "
                            f"(${position_size_usd:.2f} USD)..."
                        )

                        success, error, trade = await execute_buy(
                            symbol=asset.symbol,
                            amount_usd=position_size_usd,
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

            # Fetch Fear & Greed Index ONCE (market-wide, not per-asset)
            fear_greed_data = await sentiment_service.fetch_fear_greed_data()
            if fear_greed_data:
                sentiment_logger.info(
                    f"Fear & Greed Index: {fear_greed_data.value} "
                    f"({fear_greed_data.classification})"
                )
            else:
                sentiment_logger.warning("Fear & Greed data unavailable")

            # Process all assets for social data, but only current group for LunarCrush
            for asset in assets:
                try:
                    # Determine if this asset should fetch LunarCrush data
                    fetch_lunarcrush = asset in current_group

                    # Fetch sentiment from all sources (with Fear & Greed fallback)
                    sentiment = await sentiment_service.fetch_all_sentiment(
                        asset.symbol,
                        fetch_lunarcrush=fetch_lunarcrush,
                        fetch_socials=True,
                        fear_greed_data=fear_greed_data,
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


async def run_onchain_ingestion() -> dict[str, Any]:
    """
    Run on-chain data ingestion.

    Story 5.6: On-Chain Data Integration

    Called every 15 minutes (aligned with council cycle).
    Ingests:
    - Exchange flows (accumulation/distribution)
    - Whale activity
    - Funding rates
    - Stablecoin reserves

    Returns:
        Dict with ingestion statistics
    """
    from services.onchain_ingestor import OnChainIngestor

    start_time = datetime.now(timezone.utc)
    onchain_logger.info(f"\n{'='*60}")
    onchain_logger.info(f"[OnChain] Starting on-chain data ingestion at {start_time.isoformat()}")
    onchain_logger.info(f"{'='*60}")

    config = get_config()

    # Check if on-chain is configured
    if not config.onchain.is_configured():
        onchain_logger.warning("[OnChain] On-chain data not configured - skipping ingestion")
        return {
            "start_time": start_time.isoformat(),
            "skipped": True,
            "reason": "Not configured"
        }

    stats = {
        "start_time": start_time.isoformat(),
        "exchange_flows": 0,
        "whale_activity": 0,
        "funding_rates": 0,
        "stablecoin_reserves": 0,
        "errors": [],
    }

    ingestor = OnChainIngestor()

    try:
        initialized = await ingestor.initialize()

        if not initialized:
            onchain_logger.warning("[OnChain] Failed to initialize ingestor")
            stats["errors"].append("Failed to initialize")
            return stats

        # Get active asset symbols
        session_maker = get_session_maker()
        async with session_maker() as session:
            assets = await get_active_assets(session)
            symbols = [asset.symbol for asset in assets]

        if not symbols:
            onchain_logger.warning("[OnChain] No active assets to ingest")
            return stats

        onchain_logger.info(f"[OnChain] Ingesting on-chain data for {len(symbols)} assets")

        # Run full ingestion
        results = await ingestor.run_full_ingestion(symbols)
        stats.update(results)

    except Exception as e:
        error_msg = f"On-chain ingestion error: {str(e)}"
        onchain_logger.error(f"[OnChain] {error_msg}")
        stats["errors"].append(error_msg)

    finally:
        await ingestor.close()

    # Calculate duration
    end_time = datetime.now(timezone.utc)
    duration = (end_time - start_time).total_seconds()
    stats["end_time"] = end_time.isoformat()
    stats["duration_seconds"] = duration

    total_records = (
        stats["exchange_flows"] +
        stats["whale_activity"] +
        stats["funding_rates"] +
        stats["stablecoin_reserves"]
    )

    onchain_logger.info(f"[OnChain] On-chain ingestion complete")
    onchain_logger.info(
        f"[OnChain] Records: {total_records} total "
        f"(Flows: {stats['exchange_flows']}, Whales: {stats['whale_activity']}, "
        f"Funding: {stats['funding_rates']}, Stables: {stats['stablecoin_reserves']})"
    )
    onchain_logger.info(f"[OnChain] Duration: {duration:.2f}s")
    onchain_logger.info(f"{'='*60}\n")

    return stats


def create_scheduler() -> AsyncIOScheduler:
    """
    Create and configure the APScheduler instance.

    Job Execution Order (Story 3.3, 3.4, 5.6, 5.9 - CRITICAL):

    EVERY 15 MINUTES (for Position Manager stop-loss protection):
    1. :00, :15, :30, :45 - Kraken OHLCV (fresh prices for stop checks)
    2. :03, :18, :33, :48 - Position check (stops/breakeven/trailing)

    HOURLY (for Council decisions - Basket Trading mode):
    3. :10 - Opportunity Scanner (find top opportunities)
    4. :14 - Sentiment + On-Chain ingestion (prep for Council)
    5. :15 - Council cycle (analysis + new entries)

    Benefits of optimized schedule:
    - Stop-losses checked every 15 min with fresh prices (capital protection)
    - Sentiment/On-Chain API calls reduced 75% (4x → 1x per hour)
    - Council gets all fresh data right before it runs

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

    # Add the Sentiment ingestion job (Story 1.4, Story 5.9)
    # Story 5.9: Optimized to run hourly at minute 14 (just before Council at :15)
    # Only needed for Council decisions, not for Position Manager
    scheduler.add_job(
        ingest_sentiment_data,
        CronTrigger(minute="14"),
        id="sentiment_ingest",
        name="Sentiment Data Ingestion (Hourly)",
        replace_existing=True,
        max_instances=1,  # Prevent overlapping executions
    )

    sentiment_logger.info(
        "Scheduler configured with Sentiment ingestion at minute: 14 (hourly - before Council)"
    )

    # Add the On-Chain ingestion job (Story 5.6, Story 5.9)
    # Story 5.9: Optimized to run hourly at minute 14 (just before Council at :15)
    # Only needed for Council decisions, not for Position Manager
    scheduler.add_job(
        run_onchain_ingestion,
        CronTrigger(minute="14"),
        id="onchain_ingest",
        name="On-Chain Data Ingestion (Hourly)",
        replace_existing=True,
        max_instances=1,  # Prevent overlapping executions
    )

    onchain_logger.info(
        "Scheduler configured with On-Chain ingestion at minute: 14 (hourly - before Council)"
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

    # Add the Council cycle job (Story 2.4, Story 5.9)
    # Story 5.9: Optionally run hourly (aligned with scanner) instead of every 15 min
    # Hourly: Runs at minute 15 each hour (after scanner at minute 10)
    # 15-min: Runs at :05, :20, :35, :50 (after data ingestion)
    if config.basket.hourly_council_enabled:
        council_schedule = "15"
        council_name = "Council Decision Cycle (Hourly - Basket Mode)"
        council_logger.info(
            "Scheduler configured with Council cycle at minute: 15 "
            "(Hourly - aligned with scanner for Basket Trading)"
        )
    else:
        council_schedule = "5,20,35,50"
        council_name = "Council Decision Cycle (Paper Trading)"
        council_logger.info(
            "Scheduler configured with Council cycle at minutes: 5,20,35,50 (Paper Trading mode)"
        )

    scheduler.add_job(
        run_council_cycle,
        CronTrigger(minute=council_schedule),
        id="council_cycle",
        name=council_name,
        replace_existing=True,
        max_instances=1,  # Prevent overlapping executions
    )

    # Add the Opportunity Scanner job (Story 5.8)
    # Runs at minute 10 each hour (after data ingestion, before council)
    scheduler.add_job(
        run_opportunity_scan,
        CronTrigger(minute="10"),
        id="opportunity_scanner",
        name="Dynamic Opportunity Scanner",
        replace_existing=True,
        max_instances=1,  # Prevent overlapping executions
    )

    scanner_logger.info(
        "Scheduler configured with Opportunity Scanner at minute: 10 (hourly)"
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
