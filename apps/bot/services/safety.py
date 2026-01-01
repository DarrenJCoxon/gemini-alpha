"""
Safety Service for the Contrarian AI Trading Bot.

Story 3.4: Global Safety Switch

This module provides system-wide safety controls:
- Trading status management (ACTIVE, PAUSED, EMERGENCY_STOP)
- Max drawdown protection with automatic liquidation
- Portfolio value tracking
- Emergency liquidation functionality
- Kill switch (manual pause/resume)

Safety Hierarchy (FAIL SAFE principle):
1. is_trading_enabled() check on every cycle
2. enforce_max_drawdown() check every 15 minutes
3. liquidate_all() for emergency situations

When in doubt, STOP TRADING.

Reference: docs/core/prd.md Section 1.1 Goals (Risk: Max 20% drawdown)
"""

import asyncio
import logging
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional, Tuple

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from database import get_session_maker
from models import SystemConfig, SystemStatus, Trade, TradeStatus
from services.position_manager import ExitReason, close_position, get_symbol_for_trade
from services.kraken import get_kraken_client

# Configure logging
logger = logging.getLogger("safety_service")


# =============================================================================
# System Configuration Initialization
# =============================================================================


async def initialize_system_config(
    initial_balance: float,
    max_drawdown_pct: float = 0.20,
    session: Optional[AsyncSession] = None,
) -> SystemConfig:
    """
    Initialize or update system config with initial balance.

    This should be called on system startup to set the reference
    point for drawdown calculations.

    Args:
        initial_balance: Starting portfolio value in USD
        max_drawdown_pct: Maximum allowed drawdown (default: 0.20 = 20%)
        session: Optional database session

    Returns:
        SystemConfig object
    """
    async def _initialize(s: AsyncSession) -> SystemConfig:
        result = await s.execute(
            select(SystemConfig).where(SystemConfig.id == "system")
        )
        config = result.scalar_one_or_none()

        if config is None:
            config = SystemConfig(
                id="system",
                initial_balance=Decimal(str(initial_balance)),
                max_drawdown_pct=Decimal(str(max_drawdown_pct)),
                status=SystemStatus.ACTIVE,
                trading_enabled=True,
                updated_at=datetime.now(timezone.utc),
            )
            s.add(config)
            logger.info(
                f"SystemConfig created: Initial balance ${initial_balance:.2f}, "
                f"Max drawdown {max_drawdown_pct * 100:.0f}%"
            )
        else:
            # Update initial balance if needed
            config.initial_balance = Decimal(str(initial_balance))
            config.max_drawdown_pct = Decimal(str(max_drawdown_pct))
            config.updated_at = datetime.now(timezone.utc)
            s.add(config)
            logger.info(
                f"SystemConfig updated: Initial balance ${initial_balance:.2f}"
            )

        await s.commit()
        await s.refresh(config)
        return config

    if session:
        return await _initialize(session)
    else:
        session_maker = get_session_maker()
        async with session_maker() as new_session:
            return await _initialize(new_session)


async def get_system_config(
    session: Optional[AsyncSession] = None,
) -> Optional[SystemConfig]:
    """
    Get the current system configuration.

    Returns:
        SystemConfig object or None if not initialized
    """
    async def _get(s: AsyncSession) -> Optional[SystemConfig]:
        result = await s.execute(
            select(SystemConfig).where(SystemConfig.id == "system")
        )
        return result.scalar_one_or_none()

    if session:
        return await _get(session)
    else:
        session_maker = get_session_maker()
        async with session_maker() as new_session:
            return await _get(new_session)


# =============================================================================
# Status Check Functions
# =============================================================================


async def get_system_status(
    session: Optional[AsyncSession] = None,
) -> SystemStatus:
    """
    Get current system trading status.

    Returns:
        SystemStatus enum value (ACTIVE, PAUSED, or EMERGENCY_STOP)
        Returns PAUSED if config not initialized (fail safe)
    """
    async def _get(s: AsyncSession) -> SystemStatus:
        result = await s.execute(
            select(SystemConfig).where(SystemConfig.id == "system")
        )
        config = result.scalar_one_or_none()

        if config is None:
            logger.error("SystemConfig not initialized! Returning PAUSED (fail safe)")
            return SystemStatus.PAUSED  # Fail safe

        return config.status

    if session:
        return await _get(session)
    else:
        session_maker = get_session_maker()
        async with session_maker() as new_session:
            return await _get(new_session)


async def is_trading_enabled(
    session: Optional[AsyncSession] = None,
) -> bool:
    """
    Check if trading is currently enabled.

    Trading is enabled only when:
    - SystemConfig exists
    - status is ACTIVE
    - trading_enabled flag is True

    Returns:
        True if trading is enabled, False otherwise
    """
    async def _check(s: AsyncSession) -> bool:
        result = await s.execute(
            select(SystemConfig).where(SystemConfig.id == "system")
        )
        config = result.scalar_one_or_none()

        if config is None:
            logger.warning("SystemConfig not initialized - trading disabled (fail safe)")
            return False

        return (
            config.status == SystemStatus.ACTIVE
            and config.trading_enabled
        )

    if session:
        return await _check(session)
    else:
        session_maker = get_session_maker()
        async with session_maker() as new_session:
            return await _check(new_session)


# =============================================================================
# Status Update Functions
# =============================================================================


async def set_system_status(
    status: SystemStatus,
    reason: Optional[str] = None,
    session: Optional[AsyncSession] = None,
) -> bool:
    """
    Update system trading status.

    Args:
        status: New system status
        reason: Optional reason for status change

    Returns:
        True on success, False on failure
    """
    async def _update(s: AsyncSession) -> bool:
        try:
            result = await s.execute(
                select(SystemConfig).where(SystemConfig.id == "system")
            )
            config = result.scalar_one_or_none()

            if config is None:
                logger.error("SystemConfig not found")
                return False

            old_status = config.status
            config.status = status
            config.updated_at = datetime.now(timezone.utc)

            if status == SystemStatus.EMERGENCY_STOP:
                config.trading_enabled = False
                config.emergency_stop_at = datetime.now(timezone.utc)
                config.emergency_reason = reason

            s.add(config)
            await s.commit()

            logger.warning(
                f"SYSTEM STATUS CHANGED: {old_status.value} -> {status.value}"
                f"{f' ({reason})' if reason else ''}"
            )

            return True

        except Exception as e:
            logger.error(f"Failed to update system status: {e}")
            return False

    if session:
        return await _update(session)
    else:
        session_maker = get_session_maker()
        async with session_maker() as new_session:
            return await _update(new_session)


async def pause_trading(
    reason: str = "Manual pause",
    session: Optional[AsyncSession] = None,
) -> bool:
    """
    Pause trading (kill switch).

    Sets system status to PAUSED which prevents Council and Execution.

    Args:
        reason: Reason for pausing (logged for audit trail)
        session: Optional database session

    Returns:
        True on success, False on failure
    """
    logger.warning(f"PAUSE TRADING requested: {reason}")
    return await set_system_status(SystemStatus.PAUSED, reason, session=session)


async def resume_trading(
    session: Optional[AsyncSession] = None,
) -> bool:
    """
    Resume trading after pause.

    Cannot resume from EMERGENCY_STOP - requires manual intervention.

    Args:
        session: Optional database session

    Returns:
        True on success, False if blocked
    """
    async def _resume(s: AsyncSession) -> bool:
        result = await s.execute(
            select(SystemConfig).where(SystemConfig.id == "system")
        )
        config = result.scalar_one_or_none()

        if config is None:
            logger.error("SystemConfig not found - cannot resume")
            return False

        # Don't allow resume if in EMERGENCY_STOP
        if config.status == SystemStatus.EMERGENCY_STOP:
            logger.error(
                "Cannot resume from EMERGENCY_STOP automatically. "
                "Manual intervention required - reset status in database."
            )
            return False

        config.status = SystemStatus.ACTIVE
        config.trading_enabled = True
        config.updated_at = datetime.now(timezone.utc)

        s.add(config)
        await s.commit()

        logger.info("Trading RESUMED")
        return True

    if session:
        return await _resume(session)
    else:
        session_maker = get_session_maker()
        async with session_maker() as new_session:
            return await _resume(new_session)


# =============================================================================
# Portfolio Balance Tracking
# =============================================================================


async def get_portfolio_value(
    session: Optional[AsyncSession] = None,
) -> Tuple[float, dict]:
    """
    Calculate current total portfolio value.

    Fetches all balances from Kraken and converts to USD.

    Returns:
        Tuple of (total_value_usd, breakdown_dict)
    """
    client = get_kraken_client()

    try:
        await client.initialize()

        if client.exchange is None:
            logger.error("Kraken exchange not initialized")
            return 0.0, {}

        # Fetch all balances
        balances = await client.exchange.fetch_balance()

        total_usd = 0.0
        breakdown = {}

        for currency, balance_info in balances.items():
            if currency in ['info', 'free', 'used', 'total', 'debt', 'timestamp', 'datetime']:
                continue

            if not isinstance(balance_info, dict):
                continue

            amount = balance_info.get('total', 0)
            if amount is None or amount <= 0:
                continue

            # Convert to USD
            if currency in ('USD', 'ZUSD'):
                value_usd = float(amount)
            else:
                # Fetch ticker for conversion
                try:
                    # Handle Kraken's currency naming (e.g., XXBT for BTC)
                    base = currency
                    if base.startswith('X') and len(base) == 4:
                        base = base[1:]
                    if base.startswith('Z') and len(base) == 4:
                        base = base[1:]
                    if base == 'XBT':
                        base = 'BTC'

                    symbol = f"{base}/USD"
                    ticker = await client.exchange.fetch_ticker(symbol)
                    price = ticker['last']
                    value_usd = float(amount) * price
                except Exception:
                    # Try USDT pair as fallback
                    try:
                        symbol = f"{base}/USDT"
                        ticker = await client.exchange.fetch_ticker(symbol)
                        price = ticker['last']
                        value_usd = float(amount) * price
                    except Exception:
                        logger.debug(f"Cannot price {currency}, skipping")
                        continue

            total_usd += value_usd
            breakdown[currency] = {
                'amount': float(amount),
                'value_usd': value_usd
            }

        logger.info(f"Portfolio value: ${total_usd:.2f}")
        return total_usd, breakdown

    except Exception as e:
        logger.error(f"Failed to fetch portfolio value: {e}")
        return 0.0, {}


async def get_open_positions_value(
    session: Optional[AsyncSession] = None,
) -> Tuple[float, int]:
    """
    Calculate total value of open positions.

    Returns:
        Tuple of (total_value_usd, position_count)
    """
    from services.position_manager import get_current_prices

    async def _get(s: AsyncSession) -> Tuple[float, int]:
        result = await s.execute(
            select(Trade).where(Trade.status == TradeStatus.OPEN)
        )
        trades = result.scalars().all()

        if not trades:
            return 0.0, 0

        # Get symbols for all trades
        symbols = []
        for trade in trades:
            symbol = await get_symbol_for_trade(trade, session=s)
            if symbol:
                symbols.append(symbol)

        # Get current prices
        prices = await get_current_prices(list(set(symbols)))

        total_value = 0.0
        for trade in trades:
            symbol = await get_symbol_for_trade(trade, session=s)
            if symbol and prices.get(symbol):
                position_value = float(trade.size) * prices[symbol]
                total_value += position_value

        return total_value, len(trades)

    if session:
        return await _get(session)
    else:
        session_maker = get_session_maker()
        async with session_maker() as new_session:
            return await _get(new_session)


# =============================================================================
# Drawdown Calculation
# =============================================================================


async def check_drawdown(
    session: Optional[AsyncSession] = None,
) -> Tuple[bool, float, float]:
    """
    Check if portfolio has exceeded maximum drawdown.

    Drawdown Formula:
    Drawdown % = (Initial Balance - Current Value) / Initial Balance

    Returns:
        Tuple of (exceeds_limit, current_drawdown_pct, current_value)
    """
    async def _check(s: AsyncSession) -> Tuple[bool, float, float]:
        # Get system config
        result = await s.execute(
            select(SystemConfig).where(SystemConfig.id == "system")
        )
        config = result.scalar_one_or_none()

        if config is None:
            logger.error("SystemConfig not initialized")
            return False, 0.0, 0.0

        initial_balance = float(config.initial_balance)
        max_drawdown = float(config.max_drawdown_pct)

        if initial_balance <= 0:
            logger.error("Invalid initial balance for drawdown calculation")
            return False, 0.0, 0.0

        # Get current portfolio value
        current_value, _ = await get_portfolio_value()

        if current_value <= 0:
            logger.warning("Current portfolio value is zero or unavailable")
            # In case of API failure, don't trigger false emergency
            return False, 0.0, current_value

        # Calculate drawdown percentage
        drawdown_amount = initial_balance - current_value
        drawdown_pct = drawdown_amount / initial_balance

        logger.info(
            f"Drawdown check: Initial ${initial_balance:.2f}, "
            f"Current ${current_value:.2f}, "
            f"Drawdown {drawdown_pct * 100:.2f}% (max {max_drawdown * 100:.0f}%)"
        )

        # Update last check timestamp
        config.last_drawdown_check = datetime.now(timezone.utc)
        s.add(config)
        await s.commit()

        exceeds_limit = drawdown_pct > max_drawdown

        if exceeds_limit:
            logger.critical(
                f"MAX DRAWDOWN EXCEEDED: {drawdown_pct * 100:.2f}% > {max_drawdown * 100:.0f}%"
            )

        return exceeds_limit, drawdown_pct, current_value

    if session:
        return await _check(session)
    else:
        session_maker = get_session_maker()
        async with session_maker() as new_session:
            return await _check(new_session)


# =============================================================================
# Emergency Liquidation
# =============================================================================


async def liquidate_all(
    reason: str = "Emergency liquidation",
    session: Optional[AsyncSession] = None,
) -> dict:
    """
    Emergency function to close ALL open positions immediately.

    This is the "nuclear option" - use with caution.

    Steps:
    1. Set system status to EMERGENCY_STOP
    2. Fetch all open positions
    3. Close each position with EMERGENCY exit reason
    4. Log results

    Args:
        reason: Reason for liquidation (logged)
        session: Optional database session

    Returns:
        Summary dict of liquidation results
    """
    logger.critical(f"LIQUIDATE_ALL TRIGGERED: {reason}")

    summary = {
        "positions_closed": 0,
        "positions_failed": 0,
        "total_pnl": 0.0,
        "reason": reason,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }

    async def _liquidate(s: AsyncSession) -> dict:
        # First, disable trading to prevent new positions
        await set_system_status(
            SystemStatus.EMERGENCY_STOP,
            reason=f"Emergency liquidation: {reason}",
            session=s,
        )

        # Fetch all open positions
        result = await s.execute(
            select(Trade).where(Trade.status == TradeStatus.OPEN)
        )
        trades = list(result.scalars().all())

        if len(trades) == 0:
            logger.info("No open positions to liquidate")
            return summary

        logger.warning(f"Liquidating {len(trades)} positions...")

        # Close each position
        for trade in trades:
            try:
                symbol = await get_symbol_for_trade(trade, session=s)

                logger.info(f"Liquidating position {trade.id} ({symbol})")

                success, error = await close_position(
                    trade=trade,
                    reason=ExitReason.MAX_DRAWDOWN,
                    exit_price=None,  # Will use market price
                    session=s,
                )

                if success:
                    summary["positions_closed"] += 1
                    # Get updated trade for P&L
                    await s.refresh(trade)
                    if trade.pnl:
                        summary["total_pnl"] += float(trade.pnl)
                else:
                    summary["positions_failed"] += 1
                    logger.error(f"Failed to liquidate {trade.id}: {error}")

                # Small delay to avoid rate limits
                await asyncio.sleep(0.5)

            except Exception as e:
                logger.error(f"Exception liquidating {trade.id}: {e}")
                summary["positions_failed"] += 1

        logger.critical(
            f"LIQUIDATION COMPLETE: "
            f"{summary['positions_closed']}/{len(trades)} closed, "
            f"P&L: ${summary['total_pnl']:.2f}"
        )

        return summary

    if session:
        return await _liquidate(session)
    else:
        session_maker = get_session_maker()
        async with session_maker() as new_session:
            return await _liquidate(new_session)


# =============================================================================
# Max Drawdown Guard
# =============================================================================


async def send_emergency_notification(
    title: str,
    message: str,
    **context
) -> None:
    """
    Send emergency notification.

    TODO: Implement actual notification (email, Telegram, etc.)
    For now, logs as CRITICAL.

    Args:
        title: Notification title
        message: Notification message
        **context: Additional context data
    """
    logger.critical(
        f"EMERGENCY NOTIFICATION: {title}\n"
        f"Message: {message}\n"
        f"Context: {context}"
    )

    # Future: Send to notification service
    # await notification_service.send_alert(title, message, context)


async def enforce_max_drawdown(
    session: Optional[AsyncSession] = None,
) -> bool:
    """
    Check drawdown and trigger emergency stop if exceeded.

    Called every 15 minutes in scheduler.

    Returns:
        True if emergency stop was triggered, False otherwise
    """
    # Skip if already in emergency stop
    status = await get_system_status(session=session)
    if status == SystemStatus.EMERGENCY_STOP:
        logger.debug("Already in EMERGENCY_STOP, skipping drawdown check")
        return False

    # Skip if trading is paused (user paused manually)
    if status == SystemStatus.PAUSED:
        logger.debug("System is PAUSED, skipping drawdown check")
        return False

    # Check drawdown
    exceeds, drawdown_pct, current_value = await check_drawdown(session=session)

    if exceeds:
        reason = (
            f"Portfolio drawdown {drawdown_pct * 100:.2f}% "
            f"exceeded limit of 20%"
        )

        # Trigger liquidation
        await liquidate_all(reason=reason, session=session)

        # Send notification
        await send_emergency_notification(
            title="MAX DRAWDOWN TRIGGERED",
            message=reason,
            current_value=current_value,
            drawdown_pct=drawdown_pct,
        )

        return True

    return False
