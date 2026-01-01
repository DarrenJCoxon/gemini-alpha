"""
Position Manager Service for managing open positions.

Story 3.3: Position Manager (Trailing Stops & Exits)
Story 5.4: Scale In/Out Position Management Integration

This module provides position lifecycle management:
- Monitor open positions every 15 minutes
- Check and execute stop loss hits
- Move stops to breakeven after 2*ATR profit
- Trail stops upward as price rises
- Close positions on Council SELL signals
- Calculate and log P&L on position close
- Check and execute scale-in triggers (Story 5.4)
- Check and execute scale-out profit targets (Story 5.4)

Position Check Priority Order (CRITICAL):
1. Stop Loss - Protect capital first
2. Council SELL - Take profits on reversal signals
3. Scale-out Profit Targets - Lock in profits (Story 5.4)
4. Breakeven Trigger - Lock in entry price
5. Trailing Stop - Maximize profits
6. Scale-in Triggers - Build position on dips (Story 5.4)

Reference: docs/core/prd.md Section 2.1 FR10
"""

import logging
from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from database import get_session_maker
from models import Trade, TradeStatus, Asset
from services.kraken import get_kraken_client, KrakenClient
from services.risk import calculate_atr
from services.execution import execute_sell
from services.scale_in_manager import (
    check_pending_scale_orders,
    execute_scale_order,
    cancel_pending_scales,
)
from services.scale_out_manager import (
    check_scale_out_triggers,
    execute_partial_exit,
    get_scale_out_position_for_trade,
    cancel_scale_out_plan,
)

# Configure logging
logger = logging.getLogger("position_manager")


class ExitReason(str, Enum):
    """
    Enumeration of reasons for closing a position.

    Used for audit trail and analytics.
    """
    STOP_LOSS = "STOP_LOSS"
    TRAILING_STOP = "TRAILING_STOP"
    COUNCIL_SELL = "COUNCIL_SELL"
    TAKE_PROFIT = "TAKE_PROFIT"
    MANUAL = "MANUAL"
    EMERGENCY = "EMERGENCY"
    MAX_DRAWDOWN = "MAX_DRAWDOWN"


# =============================================================================
# Position Fetching Functions
# =============================================================================

async def get_open_positions(
    session: Optional[AsyncSession] = None,
) -> List[Trade]:
    """
    Fetch all trades with status OPEN.

    Returns:
        List of Trade objects with OPEN status, ordered by entry_time
    """
    async def _get(s: AsyncSession) -> List[Trade]:
        statement = (
            select(Trade)
            .where(Trade.status == TradeStatus.OPEN)
            .order_by(Trade.entry_time)
        )
        result = await s.execute(statement)
        positions = result.scalars().all()

        logger.info(f"Found {len(positions)} open positions")

        # Log details for each position
        for pos in positions:
            entry = float(pos.entry_price) if pos.entry_price else 0
            stop = float(pos.stop_loss_price) if pos.stop_loss_price else 0
            age_hours = 0
            if pos.entry_time:
                age_hours = (datetime.now(timezone.utc) - pos.entry_time).total_seconds() / 3600

            logger.debug(
                f"Position {pos.id[:8]}...: Entry=${entry:.4f}, "
                f"Stop=${stop:.4f}, Age={age_hours:.1f}h"
            )

        return list(positions)

    if session:
        return await _get(session)
    else:
        session_maker = get_session_maker()
        async with session_maker() as new_session:
            return await _get(new_session)


async def get_symbol_for_trade(
    trade: Trade,
    session: Optional[AsyncSession] = None,
) -> Optional[str]:
    """
    Get the asset symbol for a trade.

    Args:
        trade: Trade object with asset_id
        session: Optional database session

    Returns:
        Asset symbol string (e.g., "SOLUSD") or None if not found
    """
    async def _get(s: AsyncSession) -> Optional[str]:
        statement = select(Asset).where(Asset.id == trade.asset_id)
        result = await s.execute(statement)
        asset = result.scalar_one_or_none()
        return asset.symbol if asset else None

    if session:
        return await _get(session)
    else:
        session_maker = get_session_maker()
        async with session_maker() as new_session:
            return await _get(new_session)


# =============================================================================
# Price Monitoring Functions
# =============================================================================

async def get_current_price(
    symbol: str,
    client: Optional[KrakenClient] = None,
) -> Optional[float]:
    """
    Fetch current market price for a single symbol.

    Args:
        symbol: Database format symbol (e.g., "SOLUSD")
        client: Optional Kraken client

    Returns:
        Current price as float, or None on error
    """
    kraken_client = client or get_kraken_client()

    try:
        await kraken_client.initialize()
        kraken_symbol = kraken_client.convert_symbol_to_kraken(symbol)

        if kraken_client.exchange is None:
            logger.error("Kraken exchange not initialized")
            return None

        ticker = await kraken_client.exchange.fetch_ticker(kraken_symbol)
        price = ticker['last']

        logger.debug(f"{symbol} current price: ${price:.4f}")
        return float(price)

    except Exception as e:
        logger.error(f"Failed to fetch price for {symbol}: {e}")
        return None


async def get_current_prices(
    symbols: List[str],
    client: Optional[KrakenClient] = None,
) -> Dict[str, Optional[float]]:
    """
    Fetch current prices for multiple symbols efficiently.

    Args:
        symbols: List of database format symbols
        client: Optional Kraken client

    Returns:
        Dict mapping symbol to price (None if fetch failed)
    """
    kraken_client = client or get_kraken_client()
    prices: Dict[str, Optional[float]] = {}

    try:
        await kraken_client.initialize()
    except Exception as e:
        logger.error(f"Failed to initialize Kraken client: {e}")
        return {symbol: None for symbol in symbols}

    for symbol in symbols:
        try:
            kraken_symbol = kraken_client.convert_symbol_to_kraken(symbol)

            if kraken_client.exchange is None:
                prices[symbol] = None
                continue

            ticker = await kraken_client.exchange.fetch_ticker(kraken_symbol)
            prices[symbol] = float(ticker['last'])

        except Exception as e:
            logger.error(f"Price fetch failed for {symbol}: {e}")
            prices[symbol] = None

    return prices


async def fetch_recent_candles(
    symbol: str,
    limit: int = 20,
    client: Optional[KrakenClient] = None,
) -> List[Dict[str, Any]]:
    """
    Fetch recent candle data for ATR calculation.

    Args:
        symbol: Database format symbol
        limit: Number of candles to fetch (default: 20 for ATR-14)
        client: Optional Kraken client

    Returns:
        List of candle dicts with high, low, close keys
    """
    kraken_client = client or get_kraken_client()

    try:
        candles = await kraken_client.fetch_ohlcv_for_asset(
            symbol,
            timeframe="15m",
            limit=limit,
        )

        # Convert to format expected by calculate_atr
        return [
            {
                "high": float(c["high"]),
                "low": float(c["low"]),
                "close": float(c["close"]),
            }
            for c in candles
        ]

    except Exception as e:
        logger.error(f"Failed to fetch candles for {symbol}: {e}")
        return []


# =============================================================================
# Stop Loss Check Functions
# =============================================================================

def check_stop_loss(
    trade: Trade,
    current_price: float,
) -> bool:
    """
    Check if stop loss has been hit.

    Returns True if position should be closed (price <= stop).

    Args:
        trade: Trade object with stop_loss_price
        current_price: Current market price

    Returns:
        True if stop loss triggered, False otherwise
    """
    if trade.stop_loss_price is None:
        logger.warning(f"Trade {trade.id} has no stop loss set!")
        return False

    stop_price = float(trade.stop_loss_price)

    if current_price <= stop_price:
        logger.warning(
            f"STOP LOSS HIT for trade {trade.id}: "
            f"Price ${current_price:.4f} <= Stop ${stop_price:.4f}"
        )
        return True

    # Log distance to stop for monitoring
    distance_pct = ((current_price - stop_price) / current_price) * 100
    logger.debug(
        f"Trade {trade.id}: Price ${current_price:.4f}, "
        f"Stop ${stop_price:.4f} ({distance_pct:.2f}% away)"
    )

    return False


# =============================================================================
# Breakeven Logic
# =============================================================================

async def check_breakeven_trigger(
    trade: Trade,
    current_price: float,
    atr: float,
    session: Optional[AsyncSession] = None,
) -> bool:
    """
    Check if price has moved enough to trigger breakeven stop.

    Trigger: Price > Entry + (2 * ATR)
    Action: Move stop loss to entry price

    Args:
        trade: Trade object
        current_price: Current market price
        atr: Current ATR value
        session: Optional database session

    Returns:
        True if breakeven was triggered, False otherwise
    """
    entry_price = float(trade.entry_price) if trade.entry_price else 0
    current_stop = float(trade.stop_loss_price) if trade.stop_loss_price else 0

    # Already at or above breakeven?
    if current_stop >= entry_price:
        return False

    # Calculate breakeven trigger level
    breakeven_trigger = entry_price + (2 * atr)

    if current_price >= breakeven_trigger:
        logger.info(
            f"BREAKEVEN TRIGGER for trade {trade.id}: "
            f"Price ${current_price:.4f} >= Trigger ${breakeven_trigger:.4f}"
        )

        # Update stop to entry price
        success = await update_stop_loss(trade.id, entry_price, session=session)
        if success:
            logger.info(
                f"Stop loss moved to breakeven for trade {trade.id}: "
                f"${current_stop:.4f} -> ${entry_price:.4f}"
            )
            return True

    return False


# =============================================================================
# Trailing Stop Implementation
# =============================================================================

async def update_trailing_stop(
    trade: Trade,
    current_price: float,
    atr: float,
    atr_multiplier: float = 2.0,
    session: Optional[AsyncSession] = None,
) -> bool:
    """
    Update trailing stop if price has moved higher.

    Trail Logic: New Stop = current_price - (ATR_Multiplier * ATR)
    Only updates if new stop > current stop.

    Args:
        trade: Trade object
        current_price: Current market price
        atr: Current ATR value
        atr_multiplier: Multiplier for ATR distance (default: 2.0)
        session: Optional database session

    Returns:
        True if stop was updated, False otherwise
    """
    entry_price = float(trade.entry_price) if trade.entry_price else 0
    current_stop = float(trade.stop_loss_price) if trade.stop_loss_price else 0

    # Only trail if we're in profit (stop is at or above entry)
    if current_stop < entry_price:
        return False

    # Calculate new potential stop
    new_stop = current_price - (atr_multiplier * atr)

    # Only update if new stop is higher than current
    if new_stop > current_stop:
        improvement = new_stop - current_stop
        logger.info(
            f"TRAILING STOP UPDATE for trade {trade.id}: "
            f"${current_stop:.4f} -> ${new_stop:.4f} (+${improvement:.4f})"
        )

        success = await update_stop_loss(trade.id, new_stop, session=session)
        return success

    return False


# =============================================================================
# Stop Loss Persistence
# =============================================================================

async def update_stop_loss(
    trade_id: str,
    new_stop: float,
    session: Optional[AsyncSession] = None,
) -> bool:
    """
    Update stop loss price in database.

    Args:
        trade_id: Trade ID to update
        new_stop: New stop loss price
        session: Optional database session

    Returns:
        True on success, False on failure
    """
    async def _update(s: AsyncSession) -> bool:
        try:
            statement = select(Trade).where(Trade.id == trade_id)
            result = await s.execute(statement)
            trade = result.scalar_one_or_none()

            if trade is None:
                logger.error(f"Trade {trade_id} not found")
                return False

            old_stop = trade.stop_loss_price
            trade.stop_loss_price = Decimal(str(new_stop))
            trade.updated_at = datetime.now(timezone.utc)

            s.add(trade)
            await s.commit()

            logger.info(
                f"Stop loss updated for {trade_id}: "
                f"${old_stop} -> ${new_stop:.4f}"
            )
            return True

        except Exception as e:
            logger.error(f"Failed to update stop loss: {e}")
            return False

    if session:
        return await _update(session)
    else:
        session_maker = get_session_maker()
        async with session_maker() as new_session:
            return await _update(new_session)


# =============================================================================
# Position Close Implementation
# =============================================================================

async def close_position(
    trade: Trade,
    reason: ExitReason,
    exit_price: Optional[float] = None,
    session: Optional[AsyncSession] = None,
) -> Tuple[bool, Optional[str]]:
    """
    Close a position by executing sell and updating Trade record.

    Args:
        trade: The Trade object to close
        reason: Why the position is being closed (ExitReason enum)
        exit_price: Optional override for exit price (for logging)
        session: Optional database session

    Returns:
        Tuple of (success, error_message)
    """
    logger.info(
        f"Closing position {trade.id} - Reason: {reason.value}"
    )

    async def _close(s: AsyncSession) -> Tuple[bool, Optional[str]]:
        # Get asset symbol
        symbol = await get_symbol_for_trade(trade, session=s)

        if symbol is None:
            error_msg = f"Asset not found for trade {trade.id}"
            logger.error(error_msg)
            return False, error_msg

        # Execute sell order via execution service
        success, error, order_details = await execute_sell(
            symbol=symbol,
            amount_token=float(trade.size),
            trade_id=trade.id,
            exit_reason=reason.value,
            session=s,
        )

        if not success:
            logger.error(f"Failed to close position {trade.id}: {error}")
            return False, error

        # Get actual exit price from order
        actual_exit_price = exit_price
        if order_details:
            actual_exit_price = order_details.get('average', order_details.get('price', exit_price))

        # Calculate P&L for logging (actual update done by execute_sell)
        if actual_exit_price:
            entry_value = float(trade.entry_price) * float(trade.size)
            exit_value = float(actual_exit_price) * float(trade.size)
            pnl = exit_value - entry_value
            pnl_percentage = (pnl / entry_value) * 100 if entry_value > 0 else 0

            logger.info(
                f"Position {trade.id} CLOSED: "
                f"P&L ${pnl:.2f} ({pnl_percentage:+.2f}%) - {reason.value}"
            )
        else:
            logger.info(f"Position {trade.id} CLOSED - {reason.value}")

        # Story 5.4: Cancel any pending scale orders for this position
        try:
            # Cancel pending scale-out orders
            scale_out_position = await get_scale_out_position_for_trade(trade.id, session=s)
            if scale_out_position:
                cancelled = await cancel_scale_out_plan(
                    scale_out_position.id,
                    reason=f"position_closed_{reason.value}",
                    session=s
                )
                if cancelled > 0:
                    logger.info(f"Cancelled {cancelled} pending scale-out orders")
        except Exception as e:
            logger.warning(f"Error cancelling scale orders: {e}")

        return True, None

    if session:
        return await _close(session)
    else:
        session_maker = get_session_maker()
        async with session_maker() as new_session:
            return await _close(new_session)


# =============================================================================
# Council Sell Signal Integration
# =============================================================================

def check_council_sell_signal(
    trade: Trade,
    council_decision: Optional[Dict[str, Any]],
) -> bool:
    """
    Check if Council has issued a SELL signal for this asset.

    A SELL signal is generated when:
    - Sentiment flips to Greed (score > 80)
    - Technical analysis shows bearish signal

    Args:
        trade: Trade object
        council_decision: Decision dict with 'action', 'asset_id', 'reasoning' keys

    Returns:
        True if should close position, False otherwise
    """
    if council_decision is None:
        return False

    action = council_decision.get('action')
    if action != 'SELL':
        return False

    # Verify this is for the same asset
    asset_id = council_decision.get('asset_id')
    if asset_id != trade.asset_id:
        return False

    reasoning = council_decision.get('reasoning', 'No reason provided')
    logger.info(
        f"COUNCIL SELL SIGNAL for trade {trade.id}: {reasoning}"
    )

    return True


# =============================================================================
# Main Position Check Loop
# =============================================================================

async def check_open_positions(
    council_decisions: Optional[Dict[str, Dict[str, Any]]] = None,
    session: Optional[AsyncSession] = None,
) -> Dict[str, Any]:
    """
    Main entry point: Check all open positions and take action.

    Called every 15 minutes by the scheduler.

    Priority Order:
    1. Stop Loss - Check first (protect capital)
    2. Council SELL - Close on reversal signal
    3. Breakeven Trigger - Lock in entry price
    4. Trailing Stop - Maximize profits

    Args:
        council_decisions: Dict of asset_id -> decision from latest Council run
        session: Optional database session

    Returns:
        Summary dict with actions taken
    """
    summary: Dict[str, Any] = {
        "positions_checked": 0,
        "stops_hit": 0,
        "breakevens_triggered": 0,
        "trailing_updates": 0,
        "council_closes": 0,
        "scale_ins_triggered": 0,  # Story 5.4
        "scale_outs_triggered": 0,  # Story 5.4
        "errors": 0,
    }

    logger.info("=" * 40)
    logger.info("Starting position check cycle")

    async def _check(s: AsyncSession) -> Dict[str, Any]:
        # Fetch all open positions
        positions = await get_open_positions(session=s)
        summary["positions_checked"] = len(positions)

        if len(positions) == 0:
            logger.info("No open positions to monitor")
            return summary

        # Get symbols for all positions
        symbols: List[str] = []
        symbol_map: Dict[str, str] = {}  # trade_id -> symbol

        for trade in positions:
            symbol = await get_symbol_for_trade(trade, session=s)
            if symbol:
                symbols.append(symbol)
                symbol_map[trade.id] = symbol
            else:
                logger.error(f"Could not find symbol for trade {trade.id}")
                summary["errors"] += 1

        # Fetch current prices (batch)
        prices = await get_current_prices(list(set(symbols)))

        # Process each position
        for trade in positions:
            symbol = symbol_map.get(trade.id)
            if symbol is None:
                continue

            current_price = prices.get(symbol)

            if current_price is None:
                logger.error(f"No price available for {symbol}")
                summary["errors"] += 1
                continue

            try:
                # PRIORITY 1: Check stop loss first (capital preservation)
                if check_stop_loss(trade, current_price):
                    success, _ = await close_position(
                        trade, ExitReason.STOP_LOSS, current_price, session=s
                    )
                    if success:
                        summary["stops_hit"] += 1
                    continue  # Position closed, move to next

                # Fetch recent candles for ATR calculation
                candles = await fetch_recent_candles(symbol, limit=20)
                atr = calculate_atr(candles)

                if atr is None:
                    logger.warning(
                        f"ATR unavailable for {symbol}, skipping trail logic"
                    )
                    continue

                # PRIORITY 2: Check for Council SELL signal
                council_decision = (council_decisions or {}).get(trade.asset_id)
                if check_council_sell_signal(trade, council_decision):
                    success, _ = await close_position(
                        trade, ExitReason.COUNCIL_SELL, current_price, session=s
                    )
                    if success:
                        summary["council_closes"] += 1
                    continue  # Position closed, move to next

                # PRIORITY 3: Check scale-out profit targets (Story 5.4)
                try:
                    scale_outs = await check_scale_out_triggers(symbol, current_price, session=s)
                    for pos_id, scale_num, parent_trade_id in scale_outs:
                        if parent_trade_id == trade.id:
                            error = await execute_partial_exit(
                                trade, pos_id, scale_num, symbol, current_price, session=s
                            )
                            if not error:
                                summary["scale_outs_triggered"] += 1
                                logger.info(
                                    f"Scale-out {scale_num} executed for {symbol} "
                                    f"at ${current_price:.4f}"
                                )
                except Exception as e:
                    logger.error(f"Error checking scale-outs for {symbol}: {e}")

                # PRIORITY 4: Check breakeven trigger
                if await check_breakeven_trigger(trade, current_price, atr, session=s):
                    summary["breakevens_triggered"] += 1

                # PRIORITY 5: Update trailing stop
                if await update_trailing_stop(trade, current_price, atr, session=s):
                    summary["trailing_updates"] += 1

            except Exception as e:
                logger.error(f"Error processing trade {trade.id}: {e}")
                summary["errors"] += 1

        # PRIORITY 6: Check scale-in opportunities for all symbols (Story 5.4)
        # This checks for pending scale orders that may be triggered by price drops
        unique_symbols = list(set(symbols))
        for symbol in unique_symbols:
            current_price = prices.get(symbol)
            if current_price is None:
                continue

            try:
                # Check for pending scale-in orders
                scale_in_orders = await check_pending_scale_orders(
                    symbol, current_price, session=s
                )

                for pos_id, scale_num in scale_in_orders:
                    # Fetch candles for this execution
                    candles = await fetch_recent_candles(symbol, limit=20)
                    if not candles:
                        logger.warning(f"No candles available for scale-in on {symbol}")
                        continue

                    error = await execute_scale_order(
                        pos_id, scale_num, symbol, candles, session=s
                    )
                    if not error:
                        summary["scale_ins_triggered"] += 1
                        logger.info(
                            f"Scale-in {scale_num} executed for {symbol} "
                            f"at ${current_price:.4f}"
                        )
                    else:
                        logger.error(f"Scale-in failed for {symbol}: {error}")
                        summary["errors"] += 1
            except Exception as e:
                logger.error(f"Error checking scale-ins for {symbol}: {e}")
                summary["errors"] += 1

        return summary

    try:
        if session:
            result = await _check(session)
        else:
            session_maker = get_session_maker()
            async with session_maker() as new_session:
                result = await _check(new_session)

        # Log summary
        logger.info(
            f"Position check complete: {result['positions_checked']} checked, "
            f"{result['stops_hit']} stops hit, "
            f"{result['breakevens_triggered']} breakevens, "
            f"{result['trailing_updates']} trailing updates, "
            f"{result['council_closes']} council sells, "
            f"{result['scale_ins_triggered']} scale-ins, "
            f"{result['scale_outs_triggered']} scale-outs"
        )
        logger.info("=" * 40)

        return result

    except Exception as e:
        logger.error(f"Position check cycle failed: {e}")
        summary["errors"] += 1
        return summary
