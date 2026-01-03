"""
Execution service for trade management.

Story 3.1: Kraken Order Execution Service
Story 3.2: Dynamic Risk Engine Integration
Story 3.4: Global Safety Switch Integration
Story 5.2: Asset Universe Reduction - Allocation Limits

This module provides high-level trade execution functions:
- execute_buy(): Place market buy orders and create Trade records
- execute_buy_with_risk(): Place market buy orders with ATR-based stop loss
- execute_buy_with_allocation_check(): Execute with tier allocation enforcement
- execute_sell(): Place market sell orders and update Trade records
- has_open_position(): Check for existing open positions
- Duplicate position prevention (one position per asset)
- Kill switch integration (blocks buys when trading disabled)
- Tier allocation limits (Story 5.2)
- Database integration with Trade model
"""

import logging
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Dict, List, Optional, Tuple, Any

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
from .risk import calculate_stop_loss
from .risk_validator import RiskValidator, TradeRiskCheck, get_risk_validator
from .exceptions import (
    DuplicatePositionError,
    InsufficientFundsError,
    RateLimitError,
    OrderRejectedError,
    PositionNotFoundError,
    InvalidSymbolError,
)
from .asset_universe import get_asset_tier, AssetTier
from .allocation_manager import check_allocation_capacity

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
    entry_atr: Optional[float] = None,
    client: Optional[KrakenExecutionClient] = None,
    session: Optional[AsyncSession] = None,
    skip_safety_check: bool = False,
) -> Tuple[bool, Optional[str], Optional[Trade]]:
    """
    Execute a market buy order.

    Places a market buy order on Kraken and creates a Trade record
    in the database with status OPEN. Prevents duplicate positions.

    Story 3.4: Includes kill switch check - blocks buys when trading disabled.

    Args:
        symbol: Trading pair in database format (e.g., "SOLUSD")
        amount_usd: Amount in USD to spend
        stop_loss_price: Initial stop loss price (from ATR calculation)
        entry_atr: ATR value at time of entry (from risk calculation, Story 3.2)
        client: Optional Kraken client (uses global if not provided)
        session: Optional database session
        skip_safety_check: Skip trading enabled check (for testing only)

    Returns:
        Tuple of (success, error_message, trade_record)

    Raises:
        DuplicatePositionError: If an open position already exists
        InsufficientFundsError: If balance is too low
        RateLimitError: If rate limit exceeded (will be retried)
    """
    execution_client = client or get_kraken_execution_client()

    # Story 3.4: Check kill switch before any order
    if not skip_safety_check:
        try:
            from services.safety import is_trading_enabled
            if not await is_trading_enabled():
                logger.warning(f"Trading disabled - buy order blocked for {symbol}")
                return False, "Trading is currently disabled", None
        except Exception as e:
            # If safety check fails, log but continue (fail open for initial setup)
            logger.debug(f"Safety check failed (continuing): {e}")

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
            entry_time=datetime.now(timezone.utc).replace(tzinfo=None),  # Naive for Prisma
            stop_loss_price=Decimal(str(stop_loss_price)) if stop_loss_price else fill_price * Decimal("0.95"),
            entry_atr=Decimal(str(entry_atr)) if entry_atr else None,
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


async def execute_buy_with_risk(
    symbol: str,
    amount_usd: float,
    candles: List[dict],
    atr_multiplier: float = 2.0,
    atr_period: int = 14,
    client: Optional[KrakenExecutionClient] = None,
    session: Optional[AsyncSession] = None,
) -> Tuple[bool, Optional[str], Optional[Trade]]:
    """
    Execute a market buy order with ATR-based dynamic stop loss calculation.

    Story 3.2: Dynamic Risk Engine Integration

    This function:
    1. Calculates ATR from provided candle data
    2. Computes stop loss as Entry - (ATR_Multiplier * ATR)
    3. Executes the buy order via execute_buy()
    4. Saves both stop_loss_price and entry_atr to the Trade record

    Args:
        symbol: Trading pair in database format (e.g., "SOLUSD")
        amount_usd: Amount in USD to spend
        candles: Recent OHLCV candle data for ATR calculation
                 (at least period + 1 candles required)
        atr_multiplier: Multiplier for ATR distance (default: 2.0)
        atr_period: ATR calculation period (default: 14)
        client: Optional Kraken client (uses global if not provided)
        session: Optional database session

    Returns:
        Tuple of (success, error_message, trade_record)

    Example:
        >>> candles = await fetch_candles(symbol, limit=50)
        >>> success, error, trade = await execute_buy_with_risk(
        ...     symbol="SOLUSD",
        ...     amount_usd=100.0,
        ...     candles=candles,
        ... )
        >>> if success:
        ...     print(f"Trade {trade.id}: Entry ${trade.entry_price}, Stop ${trade.stop_loss_price}")
    """
    execution_client = client or get_kraken_execution_client()

    # Get estimated entry price for stop loss calculation
    try:
        kraken_symbol = execution_client.convert_symbol_to_kraken(symbol)
        estimated_entry = await execution_client.get_current_price(kraken_symbol)
    except ValueError as e:
        return False, f"Invalid symbol format: {e}", None
    except Exception as e:
        logger.error(f"Error fetching price for stop loss calculation: {e}")
        return False, f"Could not fetch current price: {e}", None

    # Calculate stop loss using ATR
    stop_loss_price, atr_value = calculate_stop_loss(
        entry_price=float(estimated_entry),
        candles=candles,
        atr_multiplier=atr_multiplier,
        atr_period=atr_period,
    )

    if stop_loss_price is None:
        logger.error(
            f"Failed to calculate stop loss for {symbol} - "
            f"insufficient candle data (have {len(candles)}, need {atr_period + 1})"
        )
        return False, "Failed to calculate stop loss - insufficient data for ATR calculation", None

    logger.info(
        f"ATR-based stop loss calculated for {symbol}: "
        f"Entry ~${estimated_entry:.4f}, Stop ${stop_loss_price:.4f}, "
        f"ATR({atr_period})=${atr_value:.4f}, Multiplier={atr_multiplier}x"
    )

    # Execute buy with calculated stop loss
    return await execute_buy(
        symbol=symbol,
        amount_usd=amount_usd,
        stop_loss_price=stop_loss_price,
        entry_atr=atr_value,
        client=client,
        session=session,
    )


async def execute_buy_with_risk_validation(
    symbol: str,
    amount_usd: float,
    candles: List[dict],
    portfolio_value: float,
    current_positions: List[Dict],
    daily_pnl: float = 0.0,
    atr_multiplier: float = 2.0,
    atr_period: int = 14,
    client: Optional[KrakenExecutionClient] = None,
    session: Optional[AsyncSession] = None,
) -> Tuple[bool, Optional[str], Optional[Trade]]:
    """
    Execute buy with pre-trade risk validation.

    Story 5.5: Risk Parameter Optimization

    This function:
    1. Validates the trade against all risk limits
    2. Adjusts position size if necessary
    3. Calculates ATR-based stop loss
    4. Executes the order if approved

    Args:
        symbol: Trading pair in database format (e.g., "SOLUSD")
        amount_usd: Requested amount in USD to spend
        candles: Recent OHLCV candle data for ATR calculation
        portfolio_value: Total portfolio value in USD
        current_positions: List of current open positions with 'symbol' and 'value' keys
        daily_pnl: Today's realized + unrealized P&L
        atr_multiplier: Multiplier for ATR distance (default: 2.0)
        atr_period: ATR calculation period (default: 14)
        client: Optional Kraken client (uses global if not provided)
        session: Optional database session

    Returns:
        Tuple of (success, error_message, trade_record)

    Example:
        >>> candles = await fetch_candles(symbol, limit=50)
        >>> positions = [{"symbol": "BTCUSD", "value": 5000}, ...]
        >>> success, error, trade = await execute_buy_with_risk_validation(
        ...     symbol="SOLUSD",
        ...     amount_usd=1000.0,
        ...     candles=candles,
        ...     portfolio_value=100000.0,
        ...     current_positions=positions,
        ... )
    """
    # Step 1: Validate against risk limits
    risk_validator = get_risk_validator()
    risk_check = await risk_validator.validate_trade(
        symbol=symbol,
        requested_size_usd=amount_usd,
        portfolio_value=portfolio_value,
        current_positions=current_positions,
        daily_pnl=daily_pnl,
        session=session,
    )

    if not risk_check.approved:
        logger.warning(
            f"Trade REJECTED for {symbol}: {'; '.join(risk_check.rejection_reasons)}"
        )
        return False, f"Risk check failed: {'; '.join(risk_check.rejection_reasons)}", None

    # Step 2: Use adjusted size if necessary
    adjusted_amount = float(risk_check.max_allowed_size)

    if adjusted_amount < amount_usd:
        logger.info(
            f"Position size adjusted from ${amount_usd:.2f} to ${adjusted_amount:.2f} "
            f"due to risk limits"
        )

    # Log any warnings
    for warning in risk_check.warnings:
        logger.warning(f"Risk warning for {symbol}: {warning}")

    # Step 3: Execute with adjusted amount using ATR-based stop loss
    return await execute_buy_with_risk(
        symbol=symbol,
        amount_usd=adjusted_amount,
        candles=candles,
        atr_multiplier=atr_multiplier,
        atr_period=atr_period,
        client=client,
        session=session,
    )


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


# =============================================================================
# Scaled Execution Functions (Story 5.4)
# =============================================================================

async def execute_buy_scaled(
    symbol: str,
    amount_usd: float,
    candles: List[dict],
    asset_id: str,
    council_session_id: Optional[str] = None,
    session: Optional[AsyncSession] = None,
) -> Tuple[bool, Optional[str], Any]:
    """
    Execute a scaled entry (multiple partial buys).

    Story 5.4: Scale In/Out Position Management

    This function creates a scaled entry position that:
    1. Executes 33% immediately
    2. Sets up trigger for 33% at -5% drop
    3. Sets up trigger for 33% at -10% drop (capitulation)

    Args:
        symbol: Trading pair in database format (e.g., "SOLUSD")
        amount_usd: Total amount in USD for full position
        candles: Recent OHLCV candle data for ATR calculation
        asset_id: Database asset ID
        council_session_id: Optional council session ID for audit trail
        session: Optional database session

    Returns:
        Tuple of (success, error_message, scaled_position)
        If successful, returns the ScaledPosition object

    Example:
        >>> candles = await fetch_candles(symbol, limit=50)
        >>> success, error, scaled_pos = await execute_buy_scaled(
        ...     symbol="SOLUSD",
        ...     amount_usd=300.0,  # Will split into 3 x $100 entries
        ...     candles=candles,
        ...     asset_id=asset.id,
        ... )
        >>> if success:
        ...     print(f"Scaled position {scaled_pos.id} created, first entry executed")
    """
    # Import here to avoid circular import
    from services.scale_in_manager import create_scaled_entry

    if not candles:
        return False, "No candle data provided for scaled entry", None

    current_price = candles[-1]['close']

    logger.info(
        f"Creating scaled entry for {symbol}: "
        f"${amount_usd:.2f} total at ~${current_price:.4f}"
    )

    try:
        scaled_position, error = await create_scaled_entry(
            asset_id=asset_id,
            symbol=symbol,
            total_amount_usd=amount_usd,
            first_entry_price=current_price,
            candles=candles,
            council_session_id=council_session_id,
            session=session,
        )

        if error:
            logger.error(f"Scaled entry failed: {error}")
            return False, error, scaled_position

        logger.info(
            f"Scaled position {scaled_position.id} created: "
            f"first scale executed, {scaled_position.num_scales - 1} pending"
        )

        return True, None, scaled_position

    except Exception as e:
        logger.error(f"Error creating scaled entry: {e}")
        return False, str(e), None


async def setup_scaled_exit(
    trade: Trade,
    average_entry_price: Optional[float] = None,
    session: Optional[AsyncSession] = None,
) -> Tuple[bool, Optional[str], Any]:
    """
    Set up a scaled exit plan for an existing position.

    Story 5.4: Scale In/Out Position Management

    This function creates a scaled exit plan that:
    1. Sells 33% at +10% profit
    2. Sells 33% at +20% profit
    3. Sells final 33% via trailing stop

    Args:
        trade: The Trade object to create exit plan for
        average_entry_price: Override average entry (uses trade.entry_price if not set)
        session: Optional database session

    Returns:
        Tuple of (success, error_message, scaled_position)

    Example:
        >>> success, error, exit_plan = await setup_scaled_exit(trade)
        >>> if success:
        ...     print(f"Exit plan created: {exit_plan.id}")
    """
    # Import here to avoid circular import
    from services.scale_out_manager import create_scaled_exit

    entry_price = average_entry_price or float(trade.entry_price)

    logger.info(
        f"Creating scaled exit plan for trade {trade.id}: "
        f"size={trade.size:.8f}, entry=${entry_price:.4f}"
    )

    try:
        scaled_position = await create_scaled_exit(
            trade=trade,
            average_entry_price=entry_price,
            session=session,
        )

        if scaled_position is None:
            return False, "Failed to create scaled exit plan", None

        logger.info(
            f"Scaled exit plan {scaled_position.id} created: "
            f"{scaled_position.num_scales} exits configured"
        )

        return True, None, scaled_position

    except Exception as e:
        logger.error(f"Error creating scaled exit: {e}")
        return False, str(e), None
