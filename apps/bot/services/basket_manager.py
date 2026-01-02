"""
Basket Manager Service for Portfolio-Level Position Management.

Story 5.9: Basket Trading System

This module manages the trading basket:
- Maximum 10 concurrent positions
- Correlation checks between assets
- Position rotation (exit weakest for new opportunity)
- Dynamic position sizing based on conviction

Key Functions:
- can_open_new_position(): Check if basket has room
- get_position_count(): Current basket size
- calculate_correlation(): Check correlation between assets
- get_weakest_position(): Find candidate for rotation
- calculate_position_score(): Score position strength/weakness
"""

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from config import get_config
from database import get_session_maker
from models import Trade, TradeStatus, Asset

logger = logging.getLogger(__name__)


@dataclass
class PositionStrength:
    """Score and metadata for a position's strength."""

    trade_id: str
    symbol: str
    score: float  # 0-100, lower = weaker
    pnl_pct: float
    age_hours: float
    momentum_score: float
    reasoning: str


@dataclass
class CorrelationResult:
    """Result of correlation check between assets."""

    symbol_a: str
    symbol_b: str
    correlation: float
    lookback_days: int
    is_highly_correlated: bool
    reasoning: str


@dataclass
class BasketStatus:
    """Current status of the trading basket."""

    position_count: int
    max_positions: int
    can_open_new: bool
    total_value_usd: float
    positions: List[Dict[str, Any]]
    correlated_exposure_pct: float
    weakest_position: Optional[PositionStrength]


async def get_open_positions(
    session: Optional[AsyncSession] = None
) -> List[Trade]:
    """
    Get all currently open positions.

    Returns:
        List of Trade objects with OPEN status
    """
    async def _get(s: AsyncSession) -> List[Trade]:
        statement = (
            select(Trade)
            .where(Trade.status == TradeStatus.OPEN)
            .order_by(Trade.entry_time)
        )
        result = await s.execute(statement)
        return list(result.scalars().all())

    if session:
        return await _get(session)
    else:
        session_maker = get_session_maker()
        async with session_maker() as new_session:
            return await _get(new_session)


async def get_position_count(
    session: Optional[AsyncSession] = None
) -> int:
    """
    Get current number of open positions.

    Returns:
        Integer count of open positions
    """
    positions = await get_open_positions(session)
    return len(positions)


async def can_open_new_position(
    session: Optional[AsyncSession] = None
) -> Tuple[bool, str]:
    """
    Check if basket has room for a new position.

    Returns:
        Tuple of (can_open, reason)
    """
    config = get_config().basket
    count = await get_position_count(session)

    if count >= config.max_positions:
        return False, f"At max positions ({count}/{config.max_positions})"

    return True, f"Room available ({count}/{config.max_positions})"


async def get_symbols_for_positions(
    trades: List[Trade],
    session: AsyncSession
) -> Dict[str, str]:
    """
    Get asset symbols for a list of trades.

    Returns:
        Dict mapping trade_id -> symbol
    """
    symbol_map = {}

    # Get all unique asset IDs
    asset_ids = list(set(t.asset_id for t in trades))

    if not asset_ids:
        return symbol_map

    # Fetch all assets in one query
    statement = select(Asset).where(Asset.id.in_(asset_ids))
    result = await session.execute(statement)
    assets = {a.id: a.symbol for a in result.scalars().all()}

    # Map trades to symbols
    for trade in trades:
        if trade.asset_id in assets:
            symbol_map[trade.id] = assets[trade.asset_id]

    return symbol_map


def calculate_price_correlation(
    prices_a: List[float],
    prices_b: List[float]
) -> float:
    """
    Calculate Pearson correlation between two price series.

    Args:
        prices_a: Price series for asset A
        prices_b: Price series for asset B

    Returns:
        Correlation coefficient (-1 to 1)
    """
    if len(prices_a) != len(prices_b) or len(prices_a) < 10:
        return 0.0

    try:
        # Calculate returns
        returns_a = np.diff(prices_a) / prices_a[:-1]
        returns_b = np.diff(prices_b) / prices_b[:-1]

        # Calculate correlation
        correlation = np.corrcoef(returns_a, returns_b)[0, 1]

        if np.isnan(correlation):
            return 0.0

        return float(correlation)

    except Exception as e:
        logger.debug(f"Correlation calculation error: {e}")
        return 0.0


async def check_correlation(
    symbol_new: str,
    existing_symbols: List[str],
    price_data: Dict[str, List[float]],
    session: Optional[AsyncSession] = None
) -> List[CorrelationResult]:
    """
    Check correlation between new symbol and existing positions.

    Args:
        symbol_new: Symbol we want to add
        existing_symbols: Symbols already in basket
        price_data: Dict of symbol -> list of closing prices

    Returns:
        List of CorrelationResult for each existing symbol
    """
    config = get_config().basket
    results = []

    new_prices = price_data.get(symbol_new, [])
    if not new_prices:
        return results

    for symbol in existing_symbols:
        existing_prices = price_data.get(symbol, [])

        if not existing_prices:
            continue

        # Ensure same length
        min_len = min(len(new_prices), len(existing_prices))
        if min_len < 10:
            continue

        correlation = calculate_price_correlation(
            new_prices[-min_len:],
            existing_prices[-min_len:]
        )

        is_highly_correlated = abs(correlation) >= config.max_correlation

        results.append(CorrelationResult(
            symbol_a=symbol_new,
            symbol_b=symbol,
            correlation=correlation,
            lookback_days=config.correlation_lookback_days,
            is_highly_correlated=is_highly_correlated,
            reasoning=f"Correlation: {correlation:.2f} ({'HIGH' if is_highly_correlated else 'OK'})"
        ))

    return results


async def would_exceed_correlation_limit(
    symbol_new: str,
    price_data: Dict[str, List[float]],
    session: Optional[AsyncSession] = None
) -> Tuple[bool, List[str]]:
    """
    Check if adding a new position would create too much correlated exposure.

    Returns:
        Tuple of (would_exceed, list_of_correlated_symbols)
    """
    config = get_config().basket

    # Get existing position symbols
    positions = await get_open_positions(session)

    if not positions:
        return False, []

    session_maker = get_session_maker()
    async with session_maker() as s:
        symbol_map = await get_symbols_for_positions(positions, s)

    existing_symbols = list(symbol_map.values())

    # Check correlations
    correlations = await check_correlation(
        symbol_new,
        existing_symbols,
        price_data,
        session
    )

    highly_correlated = [
        c.symbol_b for c in correlations
        if c.is_highly_correlated
    ]

    # If more than 30% of basket would be highly correlated, block
    if len(highly_correlated) >= len(existing_symbols) * 0.3:
        return True, highly_correlated

    return False, highly_correlated


def calculate_position_score(
    trade: Trade,
    current_price: float,
    momentum_score: float = 50.0
) -> PositionStrength:
    """
    Calculate strength score for a position.

    Higher score = stronger position (keep)
    Lower score = weaker position (consider for rotation)

    Factors:
    - P&L percentage (40%)
    - Age (20%) - older positions get lower scores
    - Momentum (40%) - current technical momentum

    Args:
        trade: Trade object
        current_price: Current market price
        momentum_score: 0-100 momentum indicator

    Returns:
        PositionStrength with calculated score
    """
    config = get_config().basket

    entry_price = float(trade.entry_price) if trade.entry_price else current_price
    size = float(trade.size) if trade.size else 0

    # Calculate P&L
    pnl_pct = ((current_price - entry_price) / entry_price) * 100 if entry_price > 0 else 0

    # Calculate age in hours
    age_hours = 0
    if trade.entry_time:
        age_hours = (datetime.now(timezone.utc) - trade.entry_time).total_seconds() / 3600

    # Score components (all normalized to 0-100)

    # P&L component (40%): -50% = 0, 0% = 50, +50% = 100
    pnl_score = max(0, min(100, 50 + pnl_pct))

    # Age component (20%): newer = better, but penalize very new
    # <4h = 40, 4-24h = 70, 24-72h = 50, >72h = 30
    if age_hours < 4:
        age_score = 40  # Too new to judge
    elif age_hours < 24:
        age_score = 70  # Sweet spot
    elif age_hours < 72:
        age_score = 50  # Getting old
    else:
        age_score = 30  # Consider rotation

    # Momentum component (40%): direct use of momentum_score
    momentum_component = momentum_score

    # Calculate weighted total
    total_score = (
        pnl_score * 0.40 +
        age_score * 0.20 +
        momentum_component * 0.40
    )

    # Build reasoning
    reasons = []
    if pnl_pct >= 10:
        reasons.append(f"Profitable +{pnl_pct:.1f}%")
    elif pnl_pct <= -5:
        reasons.append(f"Losing {pnl_pct:.1f}%")

    if age_hours > config.max_position_age_hours:
        reasons.append(f"Aged out ({age_hours:.0f}h)")

    if momentum_score < 30:
        reasons.append("Weak momentum")
    elif momentum_score > 70:
        reasons.append("Strong momentum")

    return PositionStrength(
        trade_id=trade.id,
        symbol="",  # Filled by caller
        score=total_score,
        pnl_pct=pnl_pct,
        age_hours=age_hours,
        momentum_score=momentum_score,
        reasoning="; ".join(reasons) if reasons else "Average position"
    )


async def get_weakest_position(
    current_prices: Dict[str, float],
    momentum_scores: Dict[str, float],
    session: Optional[AsyncSession] = None
) -> Optional[PositionStrength]:
    """
    Find the weakest position in the basket for potential rotation.

    Args:
        current_prices: Dict of symbol -> current price
        momentum_scores: Dict of symbol -> momentum score (0-100)

    Returns:
        PositionStrength for weakest position, or None if no positions
    """
    config = get_config().basket

    positions = await get_open_positions(session)

    if not positions:
        return None

    session_maker = get_session_maker()
    async with session_maker() as s:
        symbol_map = await get_symbols_for_positions(positions, s)

    weakest: Optional[PositionStrength] = None
    lowest_score = float('inf')

    for trade in positions:
        symbol = symbol_map.get(trade.id)
        if not symbol:
            continue

        # Skip positions that haven't met minimum hold time
        if trade.entry_time:
            age_hours = (datetime.now(timezone.utc) - trade.entry_time).total_seconds() / 3600
            if age_hours < config.min_hold_hours:
                continue

        current_price = current_prices.get(symbol, 0)
        if current_price <= 0:
            continue

        momentum = momentum_scores.get(symbol, 50)

        strength = calculate_position_score(trade, current_price, momentum)
        strength.symbol = symbol

        if strength.score < lowest_score:
            lowest_score = strength.score
            weakest = strength

    return weakest


async def get_basket_status(
    current_prices: Dict[str, float],
    momentum_scores: Dict[str, float],
    session: Optional[AsyncSession] = None
) -> BasketStatus:
    """
    Get complete status of the trading basket.

    Args:
        current_prices: Dict of symbol -> current price
        momentum_scores: Dict of symbol -> momentum score

    Returns:
        BasketStatus with all metrics
    """
    config = get_config().basket

    positions = await get_open_positions(session)

    session_maker = get_session_maker()
    async with session_maker() as s:
        symbol_map = await get_symbols_for_positions(positions, s)

    # Calculate total value and positions list
    total_value = 0.0
    position_details = []

    for trade in positions:
        symbol = symbol_map.get(trade.id, "UNKNOWN")
        current_price = current_prices.get(symbol, 0)
        entry_price = float(trade.entry_price) if trade.entry_price else 0
        size = float(trade.size) if trade.size else 0

        value = current_price * size
        total_value += value

        pnl_pct = ((current_price - entry_price) / entry_price * 100) if entry_price > 0 else 0

        position_details.append({
            "trade_id": trade.id,
            "symbol": symbol,
            "entry_price": entry_price,
            "current_price": current_price,
            "size": size,
            "value_usd": value,
            "pnl_pct": pnl_pct,
            "entry_time": trade.entry_time.isoformat() if trade.entry_time else None
        })

    # Get weakest position
    weakest = await get_weakest_position(current_prices, momentum_scores, session)

    # Calculate correlated exposure (simplified - would need price data)
    correlated_exposure = 0.0  # TODO: Implement with price data

    can_open = len(positions) < config.max_positions

    return BasketStatus(
        position_count=len(positions),
        max_positions=config.max_positions,
        can_open_new=can_open,
        total_value_usd=total_value,
        positions=position_details,
        correlated_exposure_pct=correlated_exposure,
        weakest_position=weakest
    )


async def should_rotate_for_opportunity(
    new_symbol: str,
    new_opportunity_score: float,
    current_prices: Dict[str, float],
    momentum_scores: Dict[str, float],
    session: Optional[AsyncSession] = None
) -> Tuple[bool, Optional[str], str]:
    """
    Determine if we should rotate out a weak position for a new opportunity.

    Only rotate if:
    1. Basket is full
    2. New opportunity score is high (>60)
    3. Weakest position score is low (<40)
    4. New score significantly better than weakest (+20 points)

    Args:
        new_symbol: Symbol of new opportunity
        new_opportunity_score: Score of new opportunity (0-100)
        current_prices: Dict of symbol -> current price
        momentum_scores: Dict of symbol -> momentum score

    Returns:
        Tuple of (should_rotate, symbol_to_exit, reasoning)
    """
    config = get_config().basket

    count = await get_position_count(session)

    # If basket not full, no need to rotate
    if count < config.max_positions:
        return False, None, "Basket not full, no rotation needed"

    # Get weakest position
    weakest = await get_weakest_position(current_prices, momentum_scores, session)

    if not weakest:
        return False, None, "No positions available for rotation"

    # Check if rotation makes sense
    min_new_score = 60
    max_weak_score = 40
    min_improvement = 20

    if new_opportunity_score < min_new_score:
        return False, None, f"New opportunity score {new_opportunity_score:.0f} < min {min_new_score}"

    if weakest.score > max_weak_score:
        return False, None, f"Weakest position score {weakest.score:.0f} > max {max_weak_score}"

    improvement = new_opportunity_score - weakest.score
    if improvement < min_improvement:
        return False, None, f"Improvement {improvement:.0f} < min {min_improvement}"

    reasoning = (
        f"Rotate {weakest.symbol} (score: {weakest.score:.0f}) for "
        f"{new_symbol} (score: {new_opportunity_score:.0f}). "
        f"Improvement: +{improvement:.0f} points"
    )

    return True, weakest.symbol, reasoning


# Global basket manager instance
_basket_manager_initialized = False


async def initialize_basket_manager() -> None:
    """Initialize the basket manager on startup."""
    global _basket_manager_initialized

    if _basket_manager_initialized:
        return

    config = get_config().basket
    logger.info(
        f"Basket Manager initialized: max_positions={config.max_positions}, "
        f"max_correlation={config.max_correlation}, "
        f"hourly_council={config.hourly_council_enabled}"
    )

    # Log current basket status
    count = await get_position_count()
    logger.info(f"Current basket: {count}/{config.max_positions} positions")

    _basket_manager_initialized = True


async def get_basket_summary_for_tui() -> Dict[str, Any]:
    """
    Get basket summary formatted for TUI display.

    Returns:
        Dict with basket metrics for TUI
    """
    config = get_config().basket
    count = await get_position_count()

    return {
        "position_count": count,
        "max_positions": config.max_positions,
        "slots_available": config.max_positions - count,
        "hourly_council": config.hourly_council_enabled,
        "fear_threshold": config.fear_threshold_buy,
        "greed_threshold": config.greed_threshold_sell,
        "require_reversal": config.require_macd_confirmation or config.require_higher_low
    }


# =============================================================================
# DYNAMIC POSITION SIZING (Story 5.10)
# =============================================================================


async def get_portfolio_value(
    execution_client: Any = None,
    session: Optional[AsyncSession] = None,
) -> Tuple[float, float, float]:
    """
    Calculate total portfolio value (cash + open positions).

    Story 5.10: Dynamic Position Sizing

    Args:
        execution_client: Kraken execution client for fetching balance
        session: Optional database session

    Returns:
        Tuple of (total_value, cash_balance, positions_value)
    """
    config = get_config().basket

    # Get USD balance from Kraken
    cash_balance = 0.0
    if execution_client:
        try:
            balance = await execution_client.get_balance("USD")
            cash_balance = float(balance)
        except Exception as e:
            logger.warning(f"Could not fetch USD balance: {e}")
            # Use a default for sandbox mode
            cash_balance = 10000.0

    # Calculate value of open positions
    positions_value = 0.0
    if config.include_open_positions:
        try:
            close_session = False
            if session is None:
                session_maker = get_session_maker()
                session = session_maker()
                close_session = True

            try:
                # Get all open positions
                statement = select(Trade).where(Trade.status == TradeStatus.OPEN)
                result = await session.execute(statement)
                open_trades = list(result.scalars().all())

                for trade in open_trades:
                    # Use current market value (entry_price * quantity as approximation)
                    # In production, fetch current prices for accuracy
                    if trade.entry_price and trade.quantity:
                        trade_value = float(trade.entry_price) * float(trade.quantity)
                        positions_value += trade_value

            finally:
                if close_session:
                    await session.close()

        except Exception as e:
            logger.warning(f"Could not calculate positions value: {e}")

    total_value = cash_balance + positions_value

    logger.debug(
        f"Portfolio value: ${total_value:.2f} "
        f"(cash: ${cash_balance:.2f}, positions: ${positions_value:.2f})"
    )

    return total_value, cash_balance, positions_value


async def calculate_dynamic_position_size(
    execution_client: Any = None,
    session: Optional[AsyncSession] = None,
) -> Tuple[float, str]:
    """
    Calculate dynamic position size based on portfolio value.

    Story 5.10: Dynamic Position Sizing

    Position size = portfolio_value * position_size_pct
    Clamped to [min_position_usd, max_position_usd]

    Examples (8% position size):
        - $1,000 portfolio → $80 (but min $50) → $50
        - $10,000 portfolio → $800
        - $100,000 portfolio → $8,000 (but max $5,000) → $5,000

    Args:
        execution_client: Kraken execution client for fetching balance
        session: Optional database session

    Returns:
        Tuple of (position_size_usd, reasoning)
    """
    config = get_config().basket

    # Get portfolio value
    total_value, cash_balance, positions_value = await get_portfolio_value(
        execution_client=execution_client,
        session=session,
    )

    # Calculate base position size
    base_size = total_value * (config.position_size_pct / 100.0)

    # Apply min/max limits
    position_size = max(config.min_position_usd, min(base_size, config.max_position_usd))

    # Check if we have enough cash
    if position_size > cash_balance:
        if cash_balance >= config.min_position_usd:
            # Use available cash
            position_size = cash_balance
            reasoning = (
                f"${position_size:.2f} (limited by available cash ${cash_balance:.2f})"
            )
        else:
            # Not enough cash for minimum position
            reasoning = (
                f"Insufficient funds: ${cash_balance:.2f} available, "
                f"${config.min_position_usd:.2f} minimum required"
            )
            return 0.0, reasoning
    else:
        # Explain the calculation
        if position_size == config.min_position_usd:
            reasoning = (
                f"${position_size:.2f} (minimum, {config.position_size_pct}% of "
                f"${total_value:.2f} = ${base_size:.2f})"
            )
        elif position_size == config.max_position_usd:
            reasoning = (
                f"${position_size:.2f} (capped at max, {config.position_size_pct}% of "
                f"${total_value:.2f} = ${base_size:.2f})"
            )
        else:
            reasoning = (
                f"${position_size:.2f} ({config.position_size_pct}% of "
                f"${total_value:.2f} portfolio)"
            )

    logger.info(f"Dynamic position size: {reasoning}")

    return position_size, reasoning
