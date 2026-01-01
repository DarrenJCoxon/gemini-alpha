"""
Correlation tracking service for portfolio risk management.

Story 5.5: Risk Parameter Optimization

This module provides correlation analysis for crypto assets:
- Pre-defined correlation groups (crypto typically moves together)
- Dynamic correlation calculation from price history
- Correlated exposure calculation
"""

from decimal import Decimal
from typing import Any, Dict, List, Tuple, Optional
import logging

import pandas as pd
import numpy as np

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from database import get_session_maker
from models.candle import Candle
from models.asset import Asset
from config import get_config

logger = logging.getLogger(__name__)

# Pre-defined correlation groups (crypto typically moves together)
# These are fallback groups when historical data is insufficient
CORRELATION_GROUPS = {
    "BTC_CORRELATED": ["BTCUSD", "ETHUSD"],  # Major cryptos
    "ALT_LAYER1": ["SOLUSD", "AVAXUSD", "ADAUSD"],  # L1 alts
    "DEFI": ["LINKUSD", "AAVEUSD", "UNIUSD"],  # DeFi tokens
    "MEME": ["DOGEUSD", "SHIBUSD"],  # Meme coins (excluded anyway)
}


def get_correlation_group(symbol: str) -> str:
    """
    Get pre-defined correlation group for a symbol.

    Args:
        symbol: Trading pair symbol (e.g., "BTCUSD")

    Returns:
        Group name or "UNCORRELATED" if not in any group
    """
    for group_name, group_symbols in CORRELATION_GROUPS.items():
        if symbol in group_symbols:
            return group_name
    return "UNCORRELATED"


def get_group_members(group: str) -> List[str]:
    """
    Get all symbols in a correlation group.

    Args:
        group: Group name

    Returns:
        List of symbols in the group
    """
    return CORRELATION_GROUPS.get(group, [])


async def calculate_correlation_matrix(
    symbols: List[str],
    lookback_days: int = 30,
    session: Optional[AsyncSession] = None,
) -> pd.DataFrame:
    """
    Calculate price correlation matrix for given symbols.

    Uses daily returns to calculate correlation between assets.

    Args:
        symbols: List of trading pair symbols
        lookback_days: Days of price history to use
        session: Optional database session

    Returns:
        DataFrame with correlation matrix
    """
    if len(symbols) < 2:
        return pd.DataFrame()

    async def _calculate(s: AsyncSession) -> pd.DataFrame:
        price_data = {}

        for symbol in symbols:
            # Get asset ID
            asset_result = await s.execute(
                select(Asset).where(Asset.symbol == symbol)
            )
            asset = asset_result.scalar_one_or_none()

            if not asset:
                logger.warning(f"Asset not found: {symbol}")
                continue

            # Get daily closes for symbol
            result = await s.execute(
                select(Candle)
                .where(Candle.asset_id == asset.id)
                .where(Candle.timeframe == "1d")
                .order_by(Candle.timestamp.desc())
                .limit(lookback_days)
            )
            candles = result.scalars().all()

            if len(candles) >= lookback_days * 0.8:  # Need at least 80% of data
                prices = [float(c.close) for c in reversed(list(candles))]
                returns = pd.Series(prices).pct_change().dropna()
                price_data[symbol] = returns
            else:
                logger.debug(
                    f"Insufficient data for {symbol}: "
                    f"{len(candles)}/{lookback_days} candles"
                )

        if len(price_data) < 2:
            return pd.DataFrame()

        # Build DataFrame and calculate correlation
        df = pd.DataFrame(price_data)
        correlation_matrix = df.corr()

        return correlation_matrix

    if session:
        return await _calculate(session)
    else:
        session_maker = get_session_maker()
        async with session_maker() as new_session:
            return await _calculate(new_session)


async def get_correlated_assets(
    symbol: str,
    all_positions: List[Dict],
    threshold: Optional[float] = None,
    session: Optional[AsyncSession] = None,
) -> List[Tuple[str, float]]:
    """
    Find assets that are correlated with the given symbol.

    Args:
        symbol: The symbol to check
        all_positions: List of current positions (each with 'symbol' key)
        threshold: Correlation threshold (default from config)
        session: Optional database session

    Returns:
        List of (correlated_symbol, correlation_value) tuples
    """
    config = get_config()
    if threshold is None:
        threshold = config.enhanced_risk.correlation_threshold

    position_symbols = [p.get("symbol", "") for p in all_positions if p.get("symbol")]

    if symbol not in position_symbols:
        position_symbols.append(symbol)

    if len(position_symbols) < 2:
        return []

    # Try to calculate dynamic correlation
    correlation_matrix = await calculate_correlation_matrix(
        position_symbols,
        session=session,
    )

    if correlation_matrix.empty or symbol not in correlation_matrix.columns:
        # Fall back to pre-defined groups
        group = get_correlation_group(symbol)
        if group == "UNCORRELATED":
            return []

        correlated = []
        for s in position_symbols:
            if s != symbol and get_correlation_group(s) == group:
                # Assume high correlation within group
                correlated.append((s, 0.85))

        return correlated

    # Find correlated assets from matrix
    correlated = []
    for other_symbol in position_symbols:
        if other_symbol == symbol:
            continue

        if other_symbol not in correlation_matrix.columns:
            continue

        correlation = correlation_matrix.loc[symbol, other_symbol]
        if not pd.isna(correlation) and abs(correlation) >= threshold:
            correlated.append((other_symbol, float(correlation)))

    return correlated


async def calculate_correlated_exposure(
    positions: List[Dict],
    portfolio_value: Decimal,
    session: Optional[AsyncSession] = None,
) -> Dict[str, Any]:
    """
    Calculate total exposure to correlated assets.

    Groups positions by their correlation group and calculates
    the percentage exposure to each group.

    Args:
        positions: List of position dicts with 'symbol' and 'value' keys
        portfolio_value: Total portfolio value in USD
        session: Optional database session

    Returns:
        Dict with correlation metrics:
        - correlated_exposure_pct: Total exposure to correlated assets
        - largest_correlated_group_pct: Largest group exposure
        - correlation_groups: Dict of group -> percentage
    """
    if not positions or portfolio_value <= 0:
        return {
            "correlated_exposure_pct": 0.0,
            "largest_correlated_group_pct": 0.0,
            "correlation_groups": {},
        }

    # Group positions by correlation
    group_exposures: Dict[str, Decimal] = {}

    for position in positions:
        symbol = position.get("symbol", "")
        value = Decimal(str(position.get("value", 0)))
        group = get_correlation_group(symbol)

        if group not in group_exposures:
            group_exposures[group] = Decimal("0")
        group_exposures[group] += value

    # Calculate percentages
    group_percentages = {
        group: float(value / portfolio_value * 100)
        for group, value in group_exposures.items()
    }

    # Find largest correlated group (excluding UNCORRELATED)
    correlated_groups = {
        k: v for k, v in group_percentages.items()
        if k != "UNCORRELATED"
    }

    largest_group_pct = max(correlated_groups.values()) if correlated_groups else 0.0

    # Total correlated exposure (excluding uncorrelated)
    correlated_total = sum(correlated_groups.values())

    return {
        "correlated_exposure_pct": correlated_total,
        "largest_correlated_group_pct": largest_group_pct,
        "correlation_groups": group_percentages,
    }


def would_exceed_correlation_limit(
    new_symbol: str,
    new_value: Decimal,
    existing_positions: List[Dict],
    portfolio_value: Decimal,
    max_correlated_exposure_pct: float,
) -> Tuple[bool, float, float]:
    """
    Check if adding a new position would exceed correlation limits.

    Args:
        new_symbol: Symbol of the new position
        new_value: Value of the new position in USD
        existing_positions: Current positions
        portfolio_value: Total portfolio value
        max_correlated_exposure_pct: Maximum allowed correlated exposure

    Returns:
        Tuple of (would_exceed, current_pct, projected_pct)
    """
    # Get current exposure
    current_groups: Dict[str, Decimal] = {}
    for position in existing_positions:
        symbol = position.get("symbol", "")
        value = Decimal(str(position.get("value", 0)))
        group = get_correlation_group(symbol)
        if group not in current_groups:
            current_groups[group] = Decimal("0")
        current_groups[group] += value

    # Add new position to its group
    new_group = get_correlation_group(new_symbol)
    if new_group not in current_groups:
        current_groups[new_group] = Decimal("0")
    current_groups[new_group] += new_value

    # Calculate current and projected exposure
    current_correlated = sum(
        v for k, v in current_groups.items()
        if k != "UNCORRELATED" and k != new_group
    )
    current_pct = float(current_correlated / portfolio_value * 100) if portfolio_value > 0 else 0

    projected_correlated = sum(
        v for k, v in current_groups.items()
        if k != "UNCORRELATED"
    )
    projected_pct = float(projected_correlated / portfolio_value * 100) if portfolio_value > 0 else 0

    would_exceed = projected_pct > max_correlated_exposure_pct

    return would_exceed, current_pct, projected_pct


