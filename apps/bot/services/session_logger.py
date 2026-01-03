"""
Session Logger Service for Council Sessions.

Story 2.4: Master Node & Signal Logging
Story 5.3: Multi-Factor Confirmation System

This module provides functions to log council sessions to the database
for audit, performance tracking, and UI display in the "Council Feed".

Paper Trading Mode:
    This story logs decisions but does NOT execute trades.
    The Trade table is untouched. Trade execution is in Epic 3.

Multi-Factor Logging (Story 5.3):
    Council sessions now include multi-factor analysis results:
    - buy_factors_met: Number of BUY factors triggered
    - sell_factors_met: Number of SELL factors triggered
    - factors_triggered: JSON with lists of triggered factor names
"""

import json
import logging
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from core.state import GraphState
from models.base import Decision
from models.council import CouncilSession
from models.asset import Asset

logger = logging.getLogger(__name__)


async def log_council_session(
    state: GraphState,
    asset_id: str,
    session: AsyncSession
) -> CouncilSession:
    """
    Log a council session to the database.

    Creates a CouncilSession record with all agent analyses and the
    final decision for audit and performance tracking.

    Args:
        state: Final GraphState after all nodes executed
        asset_id: Database ID of the asset
        session: AsyncSession for database operations

    Returns:
        Created CouncilSession record

    Note:
        This is Paper Trading mode - NO trade execution.
        The executed_trade_id field remains null.

    Story 5.3:
        Multi-factor analysis is now logged including:
        - buy_factors_met: count of triggered buy factors
        - sell_factors_met: count of triggered sell factors
        - factors_triggered: JSON with factor names
    """
    sentiment = state.get("sentiment_analysis") or {}
    technical = state.get("technical_analysis") or {}
    vision = state.get("vision_analysis") or {}
    decision = state.get("final_decision") or {}
    mf_analysis = state.get("multi_factor_analysis") or {}

    # Build technical details JSON
    # Story 5.11: Include ADX and trend data for debugging
    adx_data = technical.get("adx", {})
    technical_details = {
        "rsi": technical.get("rsi"),
        "sma_50": technical.get("sma_50"),
        "sma_200": technical.get("sma_200"),
        "volume_delta": technical.get("volume_delta"),
        "reasoning": technical.get("reasoning"),
        "strength": technical.get("strength"),
        # Story 5.11: ADX and trend data
        "adx": adx_data.get("value") if isinstance(adx_data, dict) else None,
        "trend_direction": adx_data.get("trend_direction") if isinstance(adx_data, dict) else None,
        "is_trending": adx_data.get("is_trending") if isinstance(adx_data, dict) else None,
    }

    # Get decision timestamp or use current time (naive UTC for Prisma)
    decision_timestamp = decision.get("timestamp")
    if decision_timestamp is None:
        decision_timestamp = datetime.now(timezone.utc).replace(tzinfo=None)
    elif hasattr(decision_timestamp, 'tzinfo') and decision_timestamp.tzinfo is not None:
        decision_timestamp = decision_timestamp.replace(tzinfo=None)

    # Map action string to Decision enum
    action_str = decision.get("action", "HOLD").upper()
    final_decision_enum = Decision.HOLD
    if action_str == "BUY":
        final_decision_enum = Decision.BUY
    elif action_str == "SELL":
        final_decision_enum = Decision.SELL

    # Convert vision confidence to Decimal for database
    vision_confidence_value = vision.get("confidence_score", 0)
    if vision_confidence_value is not None:
        # Store as decimal percentage (0.00 to 1.00)
        vision_confidence_decimal = Decimal(str(vision_confidence_value)) / 100
    else:
        vision_confidence_decimal = None

    # Story 5.3: Build multi-factor data
    buy_factors_met = mf_analysis.get("buy_factors_met")
    sell_factors_met = mf_analysis.get("sell_factors_met")
    factors_triggered_json = json.dumps({
        "buy": mf_analysis.get("buy_factors_triggered", []),
        "sell": mf_analysis.get("sell_factors_triggered", [])
    }) if mf_analysis else None

    # Create session record
    council_session = CouncilSession(
        asset_id=asset_id,
        timestamp=decision_timestamp,
        sentiment_score=sentiment.get("fear_score", 50),
        technical_signal=technical.get("signal", "NEUTRAL"),
        technical_details=technical_details,
        vision_analysis=vision.get("description", ""),
        vision_confidence=vision_confidence_decimal,
        final_decision=final_decision_enum,
        reasoning_log=decision.get("reasoning", "No reasoning provided"),
        executed_trade_id=None,  # Paper Trading - no trade execution
        # Story 5.3: Multi-factor fields
        buy_factors_met=buy_factors_met,
        sell_factors_met=sell_factors_met,
        factors_triggered=factors_triggered_json,
    )

    session.add(council_session)
    await session.commit()
    await session.refresh(council_session)

    logger.info(
        f"[SessionLogger] Logged session #{council_session.id} for asset {asset_id}: "
        f"{final_decision_enum.value} (buy_factors: {buy_factors_met}, sell_factors: {sell_factors_met})"
    )

    return council_session


async def get_recent_sessions(
    asset_id: str,
    limit: int = 10,
    session: AsyncSession = None
) -> List[CouncilSession]:
    """
    Get recent council sessions for an asset.

    Retrieves the most recent council sessions ordered by timestamp
    for performance analysis and UI display.

    Args:
        asset_id: Database ID of the asset
        limit: Maximum number of sessions to retrieve (default: 10)
        session: AsyncSession for database operations

    Returns:
        List of CouncilSession records, newest first
    """
    statement = (
        select(CouncilSession)
        .where(CouncilSession.asset_id == asset_id)
        .order_by(CouncilSession.timestamp.desc())
        .limit(limit)
    )

    result = await session.execute(statement)
    sessions = result.scalars().all()

    logger.debug(f"[SessionLogger] Retrieved {len(sessions)} sessions for asset {asset_id}")

    return list(sessions)


async def get_sessions_by_decision(
    decision_type: Decision,
    limit: int = 50,
    session: AsyncSession = None
) -> List[CouncilSession]:
    """
    Get recent council sessions filtered by decision type.

    Useful for analyzing BUY or SELL signal patterns.

    Args:
        decision_type: Decision enum value (BUY, SELL, HOLD)
        limit: Maximum number of sessions to retrieve (default: 50)
        session: AsyncSession for database operations

    Returns:
        List of CouncilSession records matching the decision type
    """
    statement = (
        select(CouncilSession)
        .where(CouncilSession.final_decision == decision_type)
        .order_by(CouncilSession.timestamp.desc())
        .limit(limit)
    )

    result = await session.execute(statement)
    sessions = result.scalars().all()

    logger.debug(
        f"[SessionLogger] Retrieved {len(sessions)} {decision_type.value} sessions"
    )

    return list(sessions)


async def get_session_stats(
    asset_id: str,
    hours: int = 24,
    session: AsyncSession = None
) -> Dict[str, Any]:
    """
    Get statistics for council sessions over a time period.

    Calculates decision distribution and average confidence
    for performance tracking.

    Args:
        asset_id: Database ID of the asset
        hours: Number of hours to look back (default: 24)
        session: AsyncSession for database operations

    Returns:
        Dict with session statistics
    """
    from datetime import timedelta

    since = datetime.now(timezone.utc) - timedelta(hours=hours)

    statement = (
        select(CouncilSession)
        .where(
            CouncilSession.asset_id == asset_id,
            CouncilSession.timestamp >= since
        )
        .order_by(CouncilSession.timestamp.desc())
    )

    result = await session.execute(statement)
    sessions = result.scalars().all()

    # Calculate stats
    total = len(sessions)
    if total == 0:
        return {
            "total_sessions": 0,
            "buy_count": 0,
            "sell_count": 0,
            "hold_count": 0,
            "period_hours": hours,
        }

    buy_count = sum(1 for s in sessions if s.final_decision == Decision.BUY)
    sell_count = sum(1 for s in sessions if s.final_decision == Decision.SELL)
    hold_count = sum(1 for s in sessions if s.final_decision == Decision.HOLD)

    return {
        "total_sessions": total,
        "buy_count": buy_count,
        "sell_count": sell_count,
        "hold_count": hold_count,
        "buy_percentage": round(buy_count / total * 100, 1),
        "sell_percentage": round(sell_count / total * 100, 1),
        "hold_percentage": round(hold_count / total * 100, 1),
        "period_hours": hours,
    }
