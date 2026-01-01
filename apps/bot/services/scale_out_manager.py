"""
Scale-Out Manager for gradual position exit.

Story 5.4: Scale In/Out Position Management

This module provides functions for scaling out of positions:
- Create scaled exit plans with profit targets
- Execute partial exits when targets are hit
- Check pending scale-out orders for trigger conditions
- Manage position reduction lifecycle

Scale-out Strategy (default):
- Exit 1: 33% of position at +10% profit (lock in gains)
- Exit 2: 33% of position at +20% profit (more gains)
- Exit 3: 33% at trailing stop or extended target (ride the trend)

This locks in profits progressively while keeping exposure
for potential larger moves.
"""

import logging
from datetime import datetime, timezone
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
from services.execution import execute_sell

# Configure logging
logger = logging.getLogger("scale_out_manager")


async def create_scaled_exit(
    trade: Trade,
    average_entry_price: float,
    session: Optional[AsyncSession] = None,
) -> Optional[ScaledPosition]:
    """
    Create a scaled exit plan for an existing position.

    Creates a parent ScaledPosition and child ScaleOrders for
    taking profits at multiple levels.

    Args:
        trade: The trade to scale out of
        average_entry_price: Average entry price for profit calculations

    Returns:
        ScaledPosition for exits, or None on error
    """
    config = get_config()
    scale_config = config.scale
    scale_pcts = scale_config.get_scale_out_percentages()
    profit_triggers = scale_config.get_scale_out_profit_triggers()

    async def _create(s: AsyncSession) -> Optional[ScaledPosition]:
        # Create parent scaled position
        scaled_position = ScaledPosition(
            asset_id=trade.asset_id,
            direction=ScaleDirection.SCALE_OUT.value,
            is_active=True,
            target_size=trade.size,
            filled_size=Decimal("0"),
            remaining_size=trade.size,
            average_price=Decimal(str(average_entry_price)),
            num_scales=len(scale_pcts),
            scales_executed=0,
            parent_trade_id=trade.id,
        )
        s.add(scaled_position)
        await s.flush()

        entry_price = Decimal(str(average_entry_price))

        logger.info(
            f"Creating scaled exit for trade {trade.id}: "
            f"size={trade.size:.8f}, avg entry=${average_entry_price:.4f}"
        )

        # Create scale-out orders
        for i, pct in enumerate(scale_pcts, 1):
            scale_size = trade.size * Decimal(str(pct)) / Decimal("100")
            profit_pct = profit_triggers[i - 1]

            if profit_pct > 0:
                # Profit target trigger
                trigger_type = ScaleTriggerType.PROFIT_TARGET.value
                trigger_pct = Decimal(str(profit_pct))
                trigger_price = entry_price * (1 + trigger_pct / 100)
            else:
                # Trailing stop (managed by position_manager)
                trigger_type = ScaleTriggerType.TRAILING_STOP.value
                trigger_price = None
                trigger_pct = None

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
                f"Scale-out {i}: {pct}% = {scale_size:.8f} tokens, "
                f"trigger={trigger_type} @ ${trigger_price or 'trailing'}"
            )

        await s.commit()
        await s.refresh(scaled_position)

        logger.info(
            f"Created scale-out plan {scaled_position.id} with {len(scale_pcts)} exits "
            f"for trade {trade.id}"
        )

        return scaled_position

    try:
        if session:
            return await _create(session)
        else:
            session_maker = get_session_maker()
            async with session_maker() as new_session:
                return await _create(new_session)
    except Exception as e:
        logger.error(f"Error creating scaled exit: {e}")
        return None


async def check_scale_out_triggers(
    symbol: str,
    current_price: float,
    session: Optional[AsyncSession] = None,
) -> List[Tuple[str, int, str]]:
    """
    Check if any scale-out orders should be triggered.

    Scans all active scale-out positions for the given symbol and
    checks if the current price has reached profit targets.

    Args:
        symbol: Trading pair symbol
        current_price: Current market price

    Returns:
        List of (scaled_position_id, scale_number, parent_trade_id) tuples
    """
    orders_to_execute: List[Tuple[str, int, str]] = []

    async def _check(s: AsyncSession) -> List[Tuple[str, int, str]]:
        # Get asset for symbol
        asset_result = await s.execute(
            select(Asset).where(Asset.symbol == symbol)
        )
        asset = asset_result.scalar_one_or_none()

        if not asset:
            return []

        # Find pending scale-out orders with profit targets
        result = await s.execute(
            select(ScaleOrder, ScaledPosition)
            .join(ScaledPosition)
            .where(ScaledPosition.asset_id == asset.id)
            .where(ScaledPosition.is_active == True)
            .where(ScaledPosition.direction == ScaleDirection.SCALE_OUT.value)
            .where(ScaleOrder.status == ScaleStatus.PENDING.value)
            .where(ScaleOrder.trigger_type == ScaleTriggerType.PROFIT_TARGET.value)
        )

        for scale_order, position in result.all():
            if scale_order.trigger_price is None:
                continue

            trigger_price = float(scale_order.trigger_price)

            # Check if price reached profit target
            if current_price >= trigger_price:
                logger.info(
                    f"Scale-out {scale_order.scale_number} triggered for {symbol}: "
                    f"price ${current_price:.4f} >= target ${trigger_price:.4f}"
                )
                orders_to_execute.append(
                    (position.id, scale_order.scale_number, position.parent_trade_id or "")
                )

        return orders_to_execute

    try:
        if session:
            return await _check(session)
        else:
            session_maker = get_session_maker()
            async with session_maker() as new_session:
                return await _check(new_session)
    except Exception as e:
        logger.error(f"Error checking scale-out triggers: {e}")
        return []


async def execute_partial_exit(
    trade: Trade,
    scaled_position_id: str,
    scale_number: int,
    symbol: str,
    exit_price: float,
    session: Optional[AsyncSession] = None,
) -> Optional[str]:
    """
    Execute a partial exit (scale-out).

    Sells the scale amount and updates both the ScaleOrder and
    parent Trade with execution details.

    Args:
        trade: The trade to partially exit
        scaled_position_id: Parent scaled position ID
        scale_number: Which scale to execute (1, 2, or 3)
        symbol: Trading pair symbol
        exit_price: Current exit price

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

        logger.info(
            f"Executing scale-out {scale_number}: {scale_order.target_size:.8f} tokens "
            f"at ~${exit_price:.4f}"
        )

        # Execute partial sell
        success, error, order_details = await execute_sell(
            symbol=symbol,
            amount_token=float(scale_order.target_size),
            trade_id=None,  # Don't close the trade yet
            exit_reason=f"scale_out_{scale_number}",
            session=s,
        )

        if not success:
            logger.error(f"Scale-out {scale_number} failed: {error}")
            return error

        # Get actual exit price from order
        actual_exit_price = exit_price
        if order_details:
            actual_exit_price = float(
                order_details.get('average', order_details.get('price', exit_price))
            )

        # Update scale order
        scale_order.status = ScaleStatus.EXECUTED.value
        scale_order.executed_size = scale_order.target_size
        scale_order.executed_price = Decimal(str(actual_exit_price))
        scale_order.executed_at = datetime.now(timezone.utc)
        s.add(scale_order)

        # Update parent scaled position
        position = await s.get(ScaledPosition, scaled_position_id)
        if position:
            position.filled_size += scale_order.executed_size
            position.remaining_size -= scale_order.executed_size
            position.scales_executed += 1

            # Calculate total cost for this exit (for P&L tracking)
            exit_value = scale_order.executed_size * scale_order.executed_price
            position.total_cost += exit_value

            # Check if fully exited
            if position.remaining_size <= Decimal("0"):
                position.is_active = False
                position.completed_at = datetime.now(timezone.utc)
                logger.info(f"Scale-out plan {position.id} COMPLETE")

            s.add(position)

        # Update the parent trade's size (partial reduction)
        trade_to_update = await s.get(Trade, trade.id)
        if trade_to_update:
            trade_to_update.size -= scale_order.executed_size
            trade_to_update.updated_at = datetime.now(timezone.utc)

            # If position fully closed, mark trade as closed
            if trade_to_update.size <= Decimal("0"):
                trade_to_update.status = TradeStatus.CLOSED
                trade_to_update.exit_time = datetime.now(timezone.utc)
                trade_to_update.exit_price = Decimal(str(actual_exit_price))
                trade_to_update.exit_reason = "scaled_exit_complete"

                # Calculate P&L
                if trade_to_update.entry_price:
                    # Use original size for P&L calculation
                    original_size = trade.size  # Original before reduction
                    pnl = (trade_to_update.exit_price - trade_to_update.entry_price) * original_size
                    pnl_pct = (pnl / (trade_to_update.entry_price * original_size)) * 100
                    trade_to_update.pnl = pnl
                    trade_to_update.pnl_percent = pnl_pct

            s.add(trade_to_update)

        await s.commit()

        logger.info(
            f"Scale-out {scale_number} executed: sold {scale_order.executed_size:.8f} @ "
            f"${actual_exit_price:.4f}. "
            f"Remaining: {position.remaining_size:.8f if position else 'N/A'}"
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
        logger.error(f"Error executing partial exit: {e}")
        return str(e)


async def get_scale_out_position_for_trade(
    trade_id: str,
    session: Optional[AsyncSession] = None,
) -> Optional[ScaledPosition]:
    """
    Get the active scale-out position for a trade.

    Args:
        trade_id: Parent trade ID
        session: Optional database session

    Returns:
        ScaledPosition if exists, None otherwise
    """
    async def _get(s: AsyncSession) -> Optional[ScaledPosition]:
        result = await s.execute(
            select(ScaledPosition)
            .where(ScaledPosition.parent_trade_id == trade_id)
            .where(ScaledPosition.direction == ScaleDirection.SCALE_OUT.value)
            .where(ScaledPosition.is_active == True)
        )
        return result.scalar_one_or_none()

    try:
        if session:
            return await _get(session)
        else:
            session_maker = get_session_maker()
            async with session_maker() as new_session:
                return await _get(new_session)
    except Exception as e:
        logger.error(f"Error getting scale-out position: {e}")
        return None


async def cancel_scale_out_plan(
    scaled_position_id: str,
    reason: str = "position_closed",
    session: Optional[AsyncSession] = None,
) -> int:
    """
    Cancel all pending scale-out orders for a position.

    Called when a position is closed early (e.g., stop loss hit).

    Args:
        scaled_position_id: Parent scaled position ID
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
                f"Cancelled scale-out order {scale_order.id} "
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
        logger.error(f"Error cancelling scale-out orders: {e}")
        return 0


async def get_pending_trailing_stop_orders(
    symbol: str,
    session: Optional[AsyncSession] = None,
) -> List[Tuple[ScaleOrder, ScaledPosition]]:
    """
    Get all pending trailing stop scale-out orders for a symbol.

    These are handled specially by the position manager.

    Args:
        symbol: Trading pair symbol
        session: Optional database session

    Returns:
        List of (ScaleOrder, ScaledPosition) tuples
    """
    async def _get(s: AsyncSession) -> List[Tuple[ScaleOrder, ScaledPosition]]:
        # Get asset for symbol
        asset_result = await s.execute(
            select(Asset).where(Asset.symbol == symbol)
        )
        asset = asset_result.scalar_one_or_none()

        if not asset:
            return []

        result = await s.execute(
            select(ScaleOrder, ScaledPosition)
            .join(ScaledPosition)
            .where(ScaledPosition.asset_id == asset.id)
            .where(ScaledPosition.is_active == True)
            .where(ScaledPosition.direction == ScaleDirection.SCALE_OUT.value)
            .where(ScaleOrder.status == ScaleStatus.PENDING.value)
            .where(ScaleOrder.trigger_type == ScaleTriggerType.TRAILING_STOP.value)
        )

        return [(order, position) for order, position in result.all()]

    try:
        if session:
            return await _get(session)
        else:
            session_maker = get_session_maker()
            async with session_maker() as new_session:
                return await _get(new_session)
    except Exception as e:
        logger.error(f"Error getting trailing stop orders: {e}")
        return []
