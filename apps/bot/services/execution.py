"""
Execution service for trade management.

Story 3.1: Kraken Order Execution Service

This module provides high-level trade execution functions:
- execute_buy(): Place market buy orders and create Trade records
- execute_sell(): Place market sell orders and update Trade records
- has_open_position(): Check for existing open positions
- Duplicate position prevention (one position per asset)
- Database integration with Trade model
"""

import logging
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional, Tuple, Any

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)

from database import get_session_maker
from models import Trade, TradeStatus, Asset
from .kraken_execution import (
    KrakenExecutionClient,
    get_kraken_execution_client,
)
from .exceptions import (
    DuplicatePositionError,
    InsufficientFundsError,
    RateLimitError,
    OrderRejectedError,
    PositionNotFoundError,
    InvalidSymbolError,
)

# Configure logging
logger = logging.getLogger("execution_service")


async def has_open_position(
    asset_id: str,
    session: Optional[AsyncSession] = None,
) -> bool:
    """
    Check if an OPEN trade exists for this asset.

    The system enforces ONE open position per asset. This function
    checks the database for any existing open trades.

    Args:
        asset_id: The asset ID to check
        session: Optional database session (creates one if not provided)

    Returns:
        True if an open position exists, False otherwise
    """
    async def _check(s: AsyncSession) -> bool:
        statement = select(Trade).where(
            Trade.asset_id == asset_id,
            Trade.status == TradeStatus.OPEN,
        )
        result = await s.execute(statement)
        return result.scalar_one_or_none() is not None

    if session:
        return await _check(session)
    else:
        session_maker = get_session_maker()
        async with session_maker() as new_session:
            return await _check(new_session)


async def get_open_position(
    asset_id: str,
    session: Optional[AsyncSession] = None,
) -> Optional[Trade]:
    """
    Get the open trade for an asset if it exists.

    Args:
        asset_id: The asset ID to check
        session: Optional database session

    Returns:
        Trade object if exists, None otherwise
    """
    async def _get(s: AsyncSession) -> Optional[Trade]:
        statement = select(Trade).where(
            Trade.asset_id == asset_id,
            Trade.status == TradeStatus.OPEN,
        )
        result = await s.execute(statement)
        return result.scalar_one_or_none()

    if session:
        return await _get(session)
    else:
        session_maker = get_session_maker()
        async with session_maker() as new_session:
            return await _get(new_session)


async def get_asset_by_symbol(
    symbol: str,
    session: AsyncSession,
) -> Optional[Asset]:
    """
    Get an asset by its symbol.

    Args:
        symbol: The asset symbol (e.g., "SOLUSD", "BTCUSD")
        session: Database session

    Returns:
        Asset object if found, None otherwise
    """
    statement = select(Asset).where(Asset.symbol == symbol)
    result = await session.execute(statement)
    return result.scalar_one_or_none()


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=10),
    retry=retry_if_exception_type(RateLimitError),
)
async def execute_buy(
    symbol: str,
    amount_usd: float,
    stop_loss_price: Optional[float] = None,
    client: Optional[KrakenExecutionClient] = None,
    session: Optional[AsyncSession] = None,
) -> Tuple[bool, Optional[str], Optional[Trade]]:
    """
    Execute a market buy order.

    Places a market buy order on Kraken and creates a Trade record
    in the database with status OPEN. Prevents duplicate positions.

    Args:
        symbol: Trading pair in database format (e.g., "SOLUSD")
        amount_usd: Amount in USD to spend
        stop_loss_price: Initial stop loss price (from ATR calculation)
        client: Optional Kraken client (uses global if not provided)
        session: Optional database session

    Returns:
        Tuple of (success, error_message, trade_record)

    Raises:
        DuplicatePositionError: If an open position already exists
        InsufficientFundsError: If balance is too low
        RateLimitError: If rate limit exceeded (will be retried)
    """
    execution_client = client or get_kraken_execution_client()

    async def _execute(s: AsyncSession) -> Tuple[bool, Optional[str], Optional[Trade]]:
        # Get asset from database
        asset = await get_asset_by_symbol(symbol, s)
        if not asset:
            return False, f"Asset not found: {symbol}", None

        # Check for existing position
        if await has_open_position(asset.id, s):
            logger.warning(f"Duplicate position blocked for {symbol}")
            raise DuplicatePositionError(
                f"An open position already exists for {symbol}",
                asset_id=asset.id,
                asset_symbol=symbol,
            )

        # Convert symbol to Kraken format
        try:
            kraken_symbol = execution_client.convert_symbol_to_kraken(symbol)
        except ValueError as e:
            return False, f"Invalid symbol format: {e}", None

        # Get current price to calculate quantity
        try:
            current_price = await execution_client.get_current_price(kraken_symbol)
            quantity = float(Decimal(str(amount_usd)) / current_price)
        except Exception as e:
            logger.error(f"Error fetching price for {symbol}: {e}")
            return False, f"Could not fetch current price: {e}", None

        # Check balance (in sandbox, this returns mock balance)
        try:
            usd_balance = await execution_client.get_balance("USD")
            if usd_balance < Decimal(str(amount_usd)):
                raise InsufficientFundsError(
                    f"Insufficient USD balance: ${usd_balance:.2f} < ${amount_usd:.2f}",
                    required_amount=amount_usd,
                    available_amount=float(usd_balance),
                    currency="USD",
                )
        except InsufficientFundsError:
            raise
        except Exception as e:
            logger.error(f"Error checking balance: {e}")
            # Continue in sandbox mode, fail in live mode
            if not execution_client.is_sandbox:
                return False, f"Could not verify balance: {e}", None

        # Execute order
        try:
            order = await execution_client.create_market_buy_order(
                kraken_symbol, quantity
            )
        except (InsufficientFundsError, RateLimitError, OrderRejectedError):
            raise
        except Exception as e:
            logger.error(f"Order execution failed: {e}")
            return False, f"Order execution failed: {e}", None

        # Extract fill price from order
        fill_price = Decimal(str(order.get('average', order.get('price', current_price))))
        filled_quantity = Decimal(str(order.get('filled', quantity)))

        # Create Trade record
        trade = Trade(
            id=str(uuid.uuid4()),
            asset_id=asset.id,
            status=TradeStatus.OPEN,
            side="BUY",
            entry_price=fill_price,
            size=filled_quantity,
            entry_time=datetime.now(timezone.utc),
            stop_loss_price=Decimal(str(stop_loss_price)) if stop_loss_price else fill_price * Decimal("0.95"),
            kraken_order_id=order.get('id'),
        )

        s.add(trade)
        await s.commit()
        await s.refresh(trade)

        mode = "[SANDBOX]" if execution_client.is_sandbox else "[LIVE]"
        logger.info(
            f"{mode} BUY executed for {symbol}: "
            f"{filled_quantity} @ ${fill_price:.4f}, "
            f"Trade ID: {trade.id}"
        )

        return True, None, trade

    try:
        if session:
            return await _execute(session)
        else:
            session_maker = get_session_maker()
            async with session_maker() as new_session:
                return await _execute(new_session)
    except DuplicatePositionError as e:
        return False, str(e), None
    except InsufficientFundsError as e:
        return False, str(e), None
    except RateLimitError:
        raise  # Let retry handle it
    except Exception as e:
        logger.error(f"Unexpected error in execute_buy: {e}")
        return False, f"Unexpected error: {e}", None


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=10),
    retry=retry_if_exception_type(RateLimitError),
)
async def execute_sell(
    symbol: str,
    amount_token: float,
    trade_id: Optional[str] = None,
    exit_reason: Optional[str] = None,
    client: Optional[KrakenExecutionClient] = None,
    session: Optional[AsyncSession] = None,
) -> Tuple[bool, Optional[str], Optional[dict]]:
    """
    Execute a market sell order.

    Places a market sell order on Kraken. Optionally updates the
    associated Trade record to CLOSED status.

    Args:
        symbol: Trading pair in database format (e.g., "SOLUSD")
        amount_token: Amount of token to sell
        trade_id: Optional trade ID to close
        exit_reason: Reason for closing (e.g., "stop_loss", "take_profit")
        client: Optional Kraken client
        session: Optional database session

    Returns:
        Tuple of (success, error_message, order_details)

    Raises:
        InsufficientFundsError: If token balance is too low
        RateLimitError: If rate limit exceeded (will be retried)
    """
    execution_client = client or get_kraken_execution_client()

    async def _execute(s: AsyncSession) -> Tuple[bool, Optional[str], Optional[dict]]:
        # Convert symbol to Kraken format
        try:
            kraken_symbol = execution_client.convert_symbol_to_kraken(symbol)
        except ValueError as e:
            return False, f"Invalid symbol format: {e}", None

        # Execute order
        try:
            order = await execution_client.create_market_sell_order(
                kraken_symbol, amount_token
            )
        except (InsufficientFundsError, RateLimitError, OrderRejectedError):
            raise
        except Exception as e:
            logger.error(f"Sell order execution failed: {e}")
            return False, f"Order execution failed: {e}", None

        # If trade_id provided, update the Trade record
        if trade_id:
            statement = select(Trade).where(Trade.id == trade_id)
            result = await s.execute(statement)
            trade = result.scalar_one_or_none()

            if trade:
                exit_price = Decimal(str(order.get('average', order.get('price', 0))))
                trade.status = TradeStatus.CLOSED
                trade.exit_price = exit_price
                trade.exit_time = datetime.now(timezone.utc)
                trade.exit_reason = exit_reason or "manual_sell"

                # Calculate P&L
                if trade.entry_price and exit_price:
                    pnl = (exit_price - trade.entry_price) * trade.size
                    pnl_percent = ((exit_price - trade.entry_price) / trade.entry_price) * Decimal("100")
                    trade.pnl = pnl
                    trade.pnl_percent = pnl_percent

                s.add(trade)
                await s.commit()

                mode = "[SANDBOX]" if execution_client.is_sandbox else "[LIVE]"
                logger.info(
                    f"{mode} SELL executed for {symbol}: "
                    f"{amount_token} @ ${exit_price:.4f}, "
                    f"P&L: ${trade.pnl:.2f} ({trade.pnl_percent:.2f}%)"
                )
            else:
                logger.warning(f"Trade not found for update: {trade_id}")
        else:
            await s.commit()
            mode = "[SANDBOX]" if execution_client.is_sandbox else "[LIVE]"
            logger.info(
                f"{mode} SELL executed for {symbol}: "
                f"{amount_token} tokens"
            )

        return True, None, order

    try:
        if session:
            return await _execute(session)
        else:
            session_maker = get_session_maker()
            async with session_maker() as new_session:
                return await _execute(new_session)
    except InsufficientFundsError as e:
        return False, str(e), None
    except RateLimitError:
        raise  # Let retry handle it
    except Exception as e:
        logger.error(f"Unexpected error in execute_sell: {e}")
        return False, f"Unexpected error: {e}", None


async def close_position(
    trade_id: str,
    exit_reason: str = "manual_close",
    client: Optional[KrakenExecutionClient] = None,
    session: Optional[AsyncSession] = None,
) -> Tuple[bool, Optional[str], Optional[dict]]:
    """
    Close an existing open position by trade ID.

    Fetches the trade details and executes a sell order for
    the full position size.

    Args:
        trade_id: The trade ID to close
        exit_reason: Reason for closing
        client: Optional Kraken client
        session: Optional database session

    Returns:
        Tuple of (success, error_message, order_details)

    Raises:
        PositionNotFoundError: If trade doesn't exist or isn't open
    """
    async def _close(s: AsyncSession) -> Tuple[bool, Optional[str], Optional[dict]]:
        # Get the trade
        statement = select(Trade).where(Trade.id == trade_id)
        result = await s.execute(statement)
        trade = result.scalar_one_or_none()

        if not trade:
            raise PositionNotFoundError(
                f"Trade not found: {trade_id}",
                trade_id=trade_id,
            )

        if trade.status != TradeStatus.OPEN:
            raise PositionNotFoundError(
                f"Trade is not open (status: {trade.status})",
                trade_id=trade_id,
            )

        # Get asset symbol
        asset_statement = select(Asset).where(Asset.id == trade.asset_id)
        asset_result = await s.execute(asset_statement)
        asset = asset_result.scalar_one_or_none()

        if not asset:
            return False, f"Asset not found for trade: {trade_id}", None

        # Execute sell for full position
        return await execute_sell(
            symbol=asset.symbol,
            amount_token=float(trade.size),
            trade_id=trade_id,
            exit_reason=exit_reason,
            client=client,
            session=s,
        )

    try:
        if session:
            return await _close(session)
        else:
            session_maker = get_session_maker()
            async with session_maker() as new_session:
                return await _close(new_session)
    except PositionNotFoundError as e:
        return False, str(e), None
    except Exception as e:
        logger.error(f"Unexpected error closing position: {e}")
        return False, f"Unexpected error: {e}", None


async def get_all_open_positions(
    session: Optional[AsyncSession] = None,
) -> list[Trade]:
    """
    Get all open positions across all assets.

    Returns:
        List of Trade objects with OPEN status
    """
    async def _get(s: AsyncSession) -> list[Trade]:
        statement = select(Trade).where(Trade.status == TradeStatus.OPEN)
        result = await s.execute(statement)
        return list(result.scalars().all())

    if session:
        return await _get(session)
    else:
        session_maker = get_session_maker()
        async with session_maker() as new_session:
            return await _get(new_session)
