"""
Data Loader Utilities for the Trading Bot.

Story 2.2: Sentiment & Technical Agents

This module provides utilities for loading candle and sentiment data
from the database for use by the Council of AI Agents.
"""

from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
import logging

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from models.candle import Candle
from models.sentiment import SentimentLog
from models.asset import Asset

logger = logging.getLogger(__name__)


async def load_candles_for_asset(
    asset_id: str,
    limit: int = 200,
    session: Optional[AsyncSession] = None
) -> List[Dict[str, Any]]:
    """
    Load recent candles for an asset from the database.

    Retrieves OHLCV candle data sorted by timestamp for technical analysis.
    Returns data in the format expected by candles_to_dataframe().

    Args:
        asset_id: The asset ID to load candles for
        limit: Maximum number of candles to load (default: 200)
        session: Optional database session. If not provided, creates one.

    Returns:
        List of candle dicts with keys: timestamp, open, high, low, close, volume
        Sorted oldest-first for technical analysis
    """
    from database import get_session_maker

    own_session = session is None
    if own_session:
        session_maker = get_session_maker()
        session = session_maker()

    try:
        # Query candles ordered by timestamp descending, then reverse for TA
        statement = (
            select(Candle)
            .where(Candle.asset_id == asset_id)
            .order_by(Candle.timestamp.desc())
            .limit(limit)
        )
        result = await session.execute(statement)
        candles = result.scalars().all()

        # Convert to dict format and reverse for oldest-first ordering
        candle_list = [
            {
                "timestamp": c.timestamp,
                "open": float(c.open),
                "high": float(c.high),
                "low": float(c.low),
                "close": float(c.close),
                "volume": float(c.volume)
            }
            for c in reversed(candles)  # Oldest first for TA
        ]

        logger.debug(f"Loaded {len(candle_list)} candles for asset {asset_id}")
        return candle_list

    except Exception as e:
        logger.error(f"Error loading candles for asset {asset_id}: {e}")
        return []

    finally:
        if own_session:
            await session.close()


async def load_sentiment_for_asset(
    asset_symbol: str,
    hours: int = 24,
    session: Optional[AsyncSession] = None
) -> List[Dict[str, Any]]:
    """
    Load recent sentiment logs for an asset from the database.

    Retrieves sentiment data from the specified time window for analysis.
    Returns data in the format expected by the sentiment utilities.

    Args:
        asset_symbol: The asset symbol (e.g., "BTCUSD") to load sentiment for
        hours: Number of hours of history to load (default: 24)
        session: Optional database session. If not provided, creates one.

    Returns:
        List of sentiment dicts with keys: text, source, timestamp
        Sorted newest-first
    """
    from database import get_session_maker

    own_session = session is None
    if own_session:
        session_maker = get_session_maker()
        session = session_maker()

    try:
        # Calculate time window
        since = datetime.utcnow() - timedelta(hours=hours)

        # First, find the asset by symbol
        asset_statement = select(Asset).where(Asset.symbol == asset_symbol)
        asset_result = await session.execute(asset_statement)
        asset = asset_result.scalar_one_or_none()

        if not asset:
            logger.warning(f"Asset not found for symbol: {asset_symbol}")
            return []

        # Query sentiment logs
        statement = (
            select(SentimentLog)
            .where(
                SentimentLog.asset_id == asset.id,
                SentimentLog.timestamp >= since
            )
            .order_by(SentimentLog.timestamp.desc())
            .limit(50)
        )
        result = await session.execute(statement)
        logs = result.scalars().all()

        # Convert to dict format
        sentiment_list = [
            {
                "text": log.raw_text or "",
                "source": log.source,
                "timestamp": log.timestamp,
                "galaxy_score": log.galaxy_score,
                "sentiment_score": log.sentiment_score,
            }
            for log in logs
            if log.raw_text  # Only include logs with text content
        ]

        logger.debug(f"Loaded {len(sentiment_list)} sentiment logs for {asset_symbol}")
        return sentiment_list

    except Exception as e:
        logger.error(f"Error loading sentiment for {asset_symbol}: {e}")
        return []

    finally:
        if own_session:
            await session.close()


async def load_asset_by_symbol(
    symbol: str,
    session: Optional[AsyncSession] = None
) -> Optional[Asset]:
    """
    Load an asset by its symbol.

    Args:
        symbol: The asset symbol (e.g., "BTCUSD")
        session: Optional database session

    Returns:
        Asset object if found, None otherwise
    """
    from database import get_session_maker

    own_session = session is None
    if own_session:
        session_maker = get_session_maker()
        session = session_maker()

    try:
        statement = select(Asset).where(Asset.symbol == symbol)
        result = await session.execute(statement)
        return result.scalar_one_or_none()

    except Exception as e:
        logger.error(f"Error loading asset {symbol}: {e}")
        return None

    finally:
        if own_session:
            await session.close()


async def get_active_assets(
    session: Optional[AsyncSession] = None
) -> List[Asset]:
    """
    Get all active assets for analysis.

    Args:
        session: Optional database session

    Returns:
        List of active Asset objects
    """
    from database import get_session_maker

    own_session = session is None
    if own_session:
        session_maker = get_session_maker()
        session = session_maker()

    try:
        statement = select(Asset).where(Asset.is_active == True)
        result = await session.execute(statement)
        assets = result.scalars().all()
        return list(assets)

    except Exception as e:
        logger.error(f"Error loading active assets: {e}")
        return []

    finally:
        if own_session:
            await session.close()
