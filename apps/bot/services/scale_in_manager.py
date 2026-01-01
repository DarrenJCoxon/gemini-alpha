"""
Scale-In Manager for gradual position entry.

Story 5.4: Scale In/Out Position Management

This module provides functions for scaling into positions:
- Create scaled entry plans with multiple trigger levels
- Execute scale orders when triggers are hit
- Check pending scale orders for trigger conditions
- Manage position building lifecycle

Scale-in Strategy (default):
- Entry 1: 33% of position at initial signal (IMMEDIATE)
- Entry 2: 33% if price drops 5% from first entry (PRICE_DROP)
- Entry 3: 33% if price drops 10% from first entry (CAPITULATION)

This achieves better average entry prices when the market dips after
our initial entry, reducing the impact of timing errors.
"""

import logging
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from typing import Optional, List, Tuple

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from database import get_session_maker
from models import (
    Asset,
    Trade,
    TradeStatus,
    ScaledPosition,
    ScaleOrder,
    ScaleDirection,
    ScaleStatus,
    ScaleTriggerType,
)
from config import get_config
from services.execution import execute_buy_with_risk

# Configure logging
logger = logging.getLogger("scale_in_manager")


async def create_scaled_entry(
    asset_id: str,
    symbol: str,
    total_amount_usd: float,
    first_entry_price: float,
    candles: List[dict],
    council_session_id: Optional[str] = None,
    session: Optional[AsyncSession] = None,
) -> Tuple[Optional[ScaledPosition], Optional[str]]:
    """
    Create a scaled entry position with multiple scale orders.

    Creates a parent ScaledPosition and child ScaleOrders based on
    the configured scale percentages and trigger levels. The first
    scale order is executed immediately.

    Args:
        asset_id: Database asset ID
        symbol: Trading pair symbol (e.g., "SOLUSD")
        total_amount_usd: Total position size in USD
        first_entry_price: Current price for first entry
        candles: Price candles for ATR calculation
        council_session_id: Council session that triggered entry
        session: Optional database session

    Returns:
        Tuple of (ScaledPosition, error_message)
        If successful, error_message is None
    """
    config = get_config()
    scale_config = config.scale
    scale_pcts = scale_config.get_scale_in_percentages()
    drop_triggers = scale_config.get_scale_in_drop_triggers()

    # Calculate total tokens at current price
    total_tokens = Decimal(str(total_amount_usd)) / Decimal(str(first_entry_price))

    async def _create(s: AsyncSession) -> Tuple[Optional[ScaledPosition], Optional[str]]:
        # Create parent scaled position
        scaled_position = ScaledPosition(
            asset_id=asset_id,
            direction=ScaleDirection.SCALE_IN.value,
            is_active=True,
            target_size=total_tokens,
            filled_size=Decimal("0"),
            remaining_size=total_tokens,
            num_scales=len(scale_pcts),
            scales_executed=0,
            council_session_id=council_session_id,
        )
        s.add(scaled_position)
        await s.flush()  # Get the ID

        logger.info(
            f"Creating scaled entry for {symbol}: "
            f"target={total_tokens:.8f} tokens, {len(scale_pcts)} scales"
        )

        # Create scale orders
        for i, pct in enumerate(scale_pcts, 1):
            scale_size = total_tokens * Decimal(str(pct)) / Decimal("100")
            drop_pct = drop_triggers[i - 1]

            if i == 1:
                # First scale - execute immediately
                trigger_type = ScaleTriggerType.IMMEDIATE.value
                trigger_price = None
                trigger_pct = None
            elif i == 2:
                # Second scale - trigger on price drop
                trigger_type = ScaleTriggerType.PRICE_DROP.value
                trigger_pct = Decimal(str(drop_pct))
                trigger_price = Decimal(str(first_entry_price)) * (1 - trigger_pct / 100)
            else:
                # Third scale - capitulation level
                trigger_type = ScaleTriggerType.CAPITULATION.value
                trigger_pct = Decimal(str(drop_pct))
                trigger_price = Decimal(str(first_entry_price)) * (1 - trigger_pct / 100)

            scale_order = ScaleOrder(
                scaled_position_id=scaled_position.id,
                scale_number=i,
                status=ScaleStatus.PENDING.value,
                trigger_type=trigger_type,
                trigger_price=trigger_price,
                trigger_pct=trigger_pct,
                target_size=scale_size,
            )
            s.add(scale_order)

            logger.debug(
                f"Scale {i}: {pct}% = {scale_size:.8f} tokens, "
                f"trigger={trigger_type} @ ${trigger_price or 'immediate'}"
            )

        await s.commit()
        await s.refresh(scaled_position)

        logger.info(
            f"Created scaled position {scaled_position.id} with {len(scale_pcts)} scales "
            f"for {symbol}, total size: {total_tokens:.8f}"
        )

        # Execute first scale immediately
        error = await execute_scale_order(
            scaled_position.id,
            1,
            symbol,
            candles,
            session=s,
        )

        if error:
            logger.error(f"First scale execution failed: {error}")
            # Mark position as failed but keep for retry
            return scaled_position, error

        return scaled_position, None

    try:
        if session:
            return await _create(session)
        else:
            session_maker = get_session_maker()
            async with session_maker() as new_session:
                return await _create(new_session)
    except Exception as e:
        logger.error(f"Error creating scaled entry: {e}")
        return None, str(e)


async def execute_scale_order(
    scaled_position_id: str,
    scale_number: int,
    symbol: str,
    candles: List[dict],
    session: Optional[AsyncSession] = None,
) -> Optional[str]:
    """
    Execute a specific scale order.

    Places a buy order for the scale amount and updates both the
    ScaleOrder and parent ScaledPosition with execution details.

    Args:
        scaled_position_id: Parent position ID
        scale_number: Which scale to execute (1, 2, or 3)
        symbol: Trading pair symbol
        candles: Recent candles for ATR calculation

    Returns:
        Error message if failed, None on success
    """
    async def _execute(s: AsyncSession) -> Optional[str]:
        # Get scale order
        result = await s.execute(
            select(ScaleOrder)
            .where(ScaleOrder.scaled_position_id == scaled_position_id)
            .where(ScaleOrder.scale_number == scale_number)
        )
        scale_order = result.scalar_one_or_none()

        if not scale_order:
            return f"Scale order {scale_number} not found"

        if scale_order.status != ScaleStatus.PENDING.value:
            return f"Scale order already {scale_order.status}"

        # Mark as triggered
        scale_order.triggered_at = datetime.now(timezone.utc)

        # Calculate USD amount for this scale
        current_price = candles[-1]['close'] if candles else 0
        if current_price == 0:
            return "Cannot execute: no price data available"

        amount_usd = float(scale_order.target_size) * current_price

        logger.info(
            f"Executing scale {scale_number}: {scale_order.target_size:.8f} tokens "
            f"(~${amount_usd:.2f}) at ~${current_price:.4f}"
        )

        # Execute buy with risk management
        success, error, trade = await execute_buy_with_risk(
            symbol=symbol,
            amount_usd=amount_usd,
            candles=candles,
            session=s,
        )

        if not success:
            logger.error(f"Scale {scale_number} execution failed: {error}")
            return error

        if not trade:
            return "Trade execution returned no trade object"

        # Update scale order
        scale_order.status = ScaleStatus.EXECUTED.value
        scale_order.executed_size = trade.size
        scale_order.executed_price = trade.entry_price
        scale_order.trade_id = trade.id
        scale_order.executed_at = datetime.now(timezone.utc)

        # Update parent position
        position = await s.get(ScaledPosition, scaled_position_id)
        if position:
            position.filled_size += scale_order.executed_size
            position.remaining_size = position.target_size - position.filled_size
            position.scales_executed += 1

            # Recalculate average price (weighted average)
            executed_value = scale_order.executed_size * scale_order.executed_price
            position.total_cost += executed_value
            position.average_price = position.total_cost / position.filled_size

            # Check if all scales complete
            if position.scales_executed >= position.num_scales:
                position.is_active = False
                position.completed_at = datetime.now(timezone.utc)
                logger.info(
                    f"Scaled position {position.id} COMPLETE: "
                    f"avg entry ${position.average_price:.4f}"
                )

            s.add(position)

        s.add(scale_order)
        await s.commit()

        logger.info(
            f"Scale {scale_number} executed: {scale_order.executed_size:.8f} @ "
            f"${scale_order.executed_price:.4f}. "
            f"Position avg: ${position.average_price:.4f if position else 'N/A'}"
        )

        return None

    try:
        if session:
            return await _execute(session)
        else:
            session_maker = get_session_maker()
            async with session_maker() as new_session:
                return await _execute(new_session)
    except Exception as e:
        logger.error(f"Error executing scale order: {e}")
        return str(e)


async def check_pending_scale_orders(
    symbol: str,
    current_price: float,
    session: Optional[AsyncSession] = None,
) -> List[Tuple[str, int]]:
    """
    Check if any pending scale orders should be triggered.

    Scans all active scaled positions for the given symbol and
    checks if the current price has dropped to trigger levels.

    Args:
        symbol: Trading pair symbol
        current_price: Current market price

    Returns:
        List of (scaled_position_id, scale_number) tuples to execute
    """
    orders_to_execute: List[Tuple[str, int]] = []

    async def _check(s: AsyncSession) -> List[Tuple[str, int]]:
        # Get asset for symbol
        asset_result = await s.execute(
            select(Asset).where(Asset.symbol == symbol)
        )
        asset = asset_result.scalar_one_or_none()

        if not asset:
            return []

        # Find pending scale-in orders for this asset
        result = await s.execute(
            select(ScaleOrder, ScaledPosition)
            .join(ScaledPosition)
            .where(ScaledPosition.asset_id == asset.id)
            .where(ScaledPosition.is_active == True)
            .where(ScaledPosition.direction == ScaleDirection.SCALE_IN.value)
            .where(ScaleOrder.status == ScaleStatus.PENDING.value)
            .where(ScaleOrder.trigger_price != None)
        )

        for scale_order, position in result.all():
            trigger_price = float(scale_order.trigger_price)

            # Check if price dropped to trigger level
            if current_price <= trigger_price:
                logger.info(
                    f"Scale {scale_order.scale_number} triggered for {symbol}: "
                    f"price ${current_price:.4f} <= trigger ${trigger_price:.4f}"
                )
                orders_to_execute.append((position.id, scale_order.scale_number))

        return orders_to_execute

    try:
        if session:
            return await _check(session)
        else:
            session_maker = get_session_maker()
            async with session_maker() as new_session:
                return await _check(new_session)
    except Exception as e:
        logger.error(f"Error checking pending scale orders: {e}")
        return []


async def expire_old_scale_orders(
    session: Optional[AsyncSession] = None,
) -> int:
    """
    Expire scale orders that have exceeded the timeout period.

    Called periodically to clean up stale pending orders.

    Returns:
        Number of orders expired
    """
    config = get_config()
    timeout_hours = config.scale.scale_timeout_hours
    cutoff_time = datetime.now(timezone.utc) - timedelta(hours=timeout_hours)

    expired_count = 0

    async def _expire(s: AsyncSession) -> int:
        nonlocal expired_count

        # Find old pending scale orders
        result = await s.execute(
            select(ScaleOrder)
            .where(ScaleOrder.status == ScaleStatus.PENDING.value)
            .where(ScaleOrder.created_at < cutoff_time)
        )

        for scale_order in result.scalars().all():
            scale_order.status = ScaleStatus.EXPIRED.value
            s.add(scale_order)
            expired_count += 1

            logger.info(
                f"Expired scale order {scale_order.id} "
                f"(created {scale_order.created_at})"
            )

        if expired_count > 0:
            await s.commit()

        return expired_count

    try:
        if session:
            return await _expire(session)
        else:
            session_maker = get_session_maker()
            async with session_maker() as new_session:
                return await _expire(new_session)
    except Exception as e:
        logger.error(f"Error expiring scale orders: {e}")
        return 0


async def cancel_pending_scales(
    scaled_position_id: str,
    reason: str = "position_closed",
    session: Optional[AsyncSession] = None,
) -> int:
    """
    Cancel all pending scale orders for a position.

    Called when a position is closed early (e.g., stop loss hit).

    Args:
        scaled_position_id: Parent position ID
        reason: Reason for cancellation

    Returns:
        Number of orders cancelled
    """
    cancelled_count = 0

    async def _cancel(s: AsyncSession) -> int:
        nonlocal cancelled_count

        # Find pending scale orders
        result = await s.execute(
            select(ScaleOrder)
            .where(ScaleOrder.scaled_position_id == scaled_position_id)
            .where(ScaleOrder.status == ScaleStatus.PENDING.value)
        )

        for scale_order in result.scalars().all():
            scale_order.status = ScaleStatus.CANCELLED.value
            s.add(scale_order)
            cancelled_count += 1

            logger.info(
                f"Cancelled scale order {scale_order.id} "
                f"(scale {scale_order.scale_number}): {reason}"
            )

        # Mark parent position as inactive
        position = await s.get(ScaledPosition, scaled_position_id)
        if position:
            position.is_active = False
            position.completed_at = datetime.now(timezone.utc)
            s.add(position)

        if cancelled_count > 0:
            await s.commit()

        return cancelled_count

    try:
        if session:
            return await _cancel(session)
        else:
            session_maker = get_session_maker()
            async with session_maker() as new_session:
                return await _cancel(new_session)
    except Exception as e:
        logger.error(f"Error cancelling scale orders: {e}")
        return 0


async def get_active_scaled_positions(
    asset_id: Optional[str] = None,
    session: Optional[AsyncSession] = None,
) -> List[ScaledPosition]:
    """
    Get all active scaled positions, optionally filtered by asset.

    Args:
        asset_id: Optional asset ID to filter by
        session: Optional database session

    Returns:
        List of active ScaledPosition objects
    """
    async def _get(s: AsyncSession) -> List[ScaledPosition]:
        query = select(ScaledPosition).where(ScaledPosition.is_active == True)

        if asset_id:
            query = query.where(ScaledPosition.asset_id == asset_id)

        result = await s.execute(query)
        return list(result.scalars().all())

    try:
        if session:
            return await _get(session)
        else:
            session_maker = get_session_maker()
            async with session_maker() as new_session:
                return await _get(new_session)
    except Exception as e:
        logger.error(f"Error getting active scaled positions: {e}")
        return []
