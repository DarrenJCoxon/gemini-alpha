"""
Contrarian AI Trading Bot - Main Entry Point

This module initializes the FastAPI application and sets up the scheduler
for automated trading operations.

Story 1.3: Added Kraken ingestion scheduler and manual trigger endpoint.
Story 2.1: Added LangGraph Council integration for AI-powered trading decisions.
Story 2.4: Added 15-minute Council cycle for automated decision-making (Paper Trading).
"""

import logging
import os
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Any, AsyncGenerator, Dict, List, Optional

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from config import get_config
from core.graph import get_council_graph
from core.state import create_initial_state
from database import init_db, get_session_maker
from services.kraken import close_kraken_client, get_kraken_client
from services.socials.telegram import close_telegram_fetcher
from services.cryptopanic import close_cryptopanic_client
from services.scheduler import get_scheduler, ingest_kraken_data, ingest_sentiment_data, run_council_cycle, backfill_kraken_data
from services.data_loader import (
    load_candles_for_asset,
    load_sentiment_for_asset,
    get_active_assets,
    load_asset_by_symbol,
)
from services.session_logger import log_council_session, get_recent_sessions
from services.risk_validator import get_risk_validator
from services.execution import get_all_open_positions
from api.routes import safety_router

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
)
logger = logging.getLogger("contrarian_bot")

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    Application lifespan manager.
    Handles startup and shutdown events including scheduler lifecycle.
    """
    config = get_config()
    scheduler = get_scheduler()

    # Startup
    await init_db()
    scheduler.start()
    logger.info("Scheduler started")

    # Optional: Run immediate ingestion on startup
    if config.scheduler.run_on_startup:
        logger.info("Running initial Kraken ingestion on startup...")
        try:
            await ingest_kraken_data()
        except Exception as e:
            logger.error(f"Initial ingestion failed: {e}")

    logger.info("Contrarian AI Bot started successfully")
    logger.info("Mode: Paper Trading (no actual trade execution)")

    yield

    # Shutdown
    logger.info("Shutting down...")
    scheduler.shutdown(wait=False)
    await close_kraken_client()
    await close_telegram_fetcher()
    await close_cryptopanic_client()
    logger.info("Contrarian AI Bot stopped")


# Initialize FastAPI app
app = FastAPI(
    title="Contrarian AI Trading Bot",
    description="AI-powered cryptocurrency trading bot with contrarian sentiment analysis",
    version="0.2.0",
    lifespan=lifespan,
)

# Configure CORS for development
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",  # Next.js development
        os.getenv("WEB_URL", ""),  # Production web URL
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register API routers (Story 3.4: Safety endpoints)
app.include_router(safety_router)


@app.get("/")
async def root() -> dict[str, str]:
    """Root endpoint returning API status."""
    return {
        "status": "ok",
        "service": "contrarian-ai-bot",
        "mode": "Paper Trading"
    }


@app.get("/health")
async def health_check() -> dict[str, Any]:
    """
    Health check endpoint for container orchestration.

    Returns scheduler status and basic health info.
    """
    scheduler = get_scheduler()
    return {
        "status": "healthy",
        "scheduler_running": scheduler.running,
        "scheduled_jobs": len(scheduler.get_jobs()),
        "mode": "Paper Trading",
    }


@app.post("/api/ingest/kraken")
async def trigger_kraken_ingestion() -> dict[str, Any]:
    """
    Manually trigger Kraken OHLCV data ingestion.

    Useful for testing and backfilling data.
    This endpoint bypasses the scheduler and runs ingestion immediately.

    Returns:
        Dict with ingestion statistics including success/failure counts.
    """
    logger.info("Manual Kraken ingestion triggered via API")
    try:
        stats = await ingest_kraken_data()
        return {
            "status": "completed",
            "stats": stats,
        }
    except Exception as e:
        logger.error(f"Manual ingestion failed: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Ingestion failed: {str(e)}",
        )


@app.post("/api/ingest/kraken/backfill")
async def trigger_kraken_backfill(limit: int = 200) -> dict[str, Any]:
    """
    Backfill historical OHLCV data from Kraken.

    Fetches multiple candles per asset to build up historical data.
    This is useful for initial setup or after database reset.

    Args:
        limit: Number of candles to fetch per asset (default: 200)
               - 200 = ~50 hours of 15-minute candles (enough for Council)
               - 720 = ~1 week of 15-minute candles

    Returns:
        Dict with backfill statistics including success/failure counts.
    """
    logger.info(f"Manual Kraken BACKFILL triggered via API (limit={limit})")
    try:
        stats = await backfill_kraken_data(limit=limit)
        return {
            "status": "completed",
            "stats": stats,
        }
    except Exception as e:
        logger.error(f"Manual backfill failed: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Backfill failed: {str(e)}",
        )


@app.post("/api/ingest/sentiment")
async def trigger_sentiment_ingestion() -> dict[str, Any]:
    """
    Manually trigger sentiment data ingestion.

    Fetches Fear & Greed Index and social sentiment data.
    This endpoint bypasses the scheduler and runs ingestion immediately.

    Returns:
        Dict with ingestion statistics.
    """
    logger.info("Manual sentiment ingestion triggered via API")
    try:
        stats = await ingest_sentiment_data()
        return {
            "status": "completed",
            "stats": stats,
        }
    except Exception as e:
        logger.error(f"Manual sentiment ingestion failed: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Sentiment ingestion failed: {str(e)}",
        )


@app.get("/api/ingest/status")
async def get_ingestion_status() -> dict[str, Any]:
    """
    Get the status of scheduled ingestion jobs.

    Returns information about the scheduler and next run times.
    """
    scheduler = get_scheduler()
    jobs = scheduler.get_jobs()

    job_info = []
    for job in jobs:
        job_info.append({
            "id": job.id,
            "name": job.name,
            "next_run_time": job.next_run_time.isoformat() if job.next_run_time else None,
        })

    return {
        "scheduler_running": scheduler.running,
        "jobs": job_info,
    }


@app.get("/api/kraken/test")
async def test_kraken_connection() -> dict[str, Any]:
    """
    Test connectivity to Kraken exchange.

    Returns connection status and exchange info.
    """
    try:
        client = get_kraken_client()
        is_connected = await client.test_connection()

        return {
            "status": "connected" if is_connected else "disconnected",
            "exchange": "kraken",
        }
    except Exception as e:
        logger.error(f"Kraken connection test failed: {e}")
        raise HTTPException(
            status_code=503,
            detail=f"Connection test failed: {str(e)}",
        )


# =============================================================================
# Story 2.1: LangGraph Council Endpoints
# =============================================================================


class CouncilSessionRequest(BaseModel):
    """Request model for running a Council session."""

    asset_symbol: str
    # TODO: In future stories, these will be loaded from the database
    # For now, we accept optional test data
    candles_data: Optional[List[Dict[str, Any]]] = None
    sentiment_data: Optional[List[Dict[str, Any]]] = None


class CouncilSessionResponse(BaseModel):
    """Response model for Council session results."""

    asset_symbol: str
    technical_analysis: Optional[Dict[str, Any]] = None
    sentiment_analysis: Optional[Dict[str, Any]] = None
    vision_analysis: Optional[Dict[str, Any]] = None
    final_decision: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


@app.post("/api/council/session", response_model=CouncilSessionResponse)
async def run_council_session(request: CouncilSessionRequest) -> CouncilSessionResponse:
    """
    Run a Council of AI Agents session for trading decision.

    Story 2.1: LangGraph State Machine Setup

    This endpoint invokes the LangGraph state machine with the provided
    asset data and returns the synthesized trading decision.

    Args:
        request: CouncilSessionRequest containing asset_symbol and optional data

    Returns:
        CouncilSessionResponse with all agent analyses and final decision

    Note:
        Currently uses stub agent implementations (Story 2.1).
        Full agent logic will be implemented in Stories 2.2-2.4.

    Future Enhancement:
        - Load candles_data from database (Kraken OHLCV)
        - Load sentiment_data from database (LunarCrush/Social)
        - Add async execution for better performance
    """
    logger.info(f"Council session requested for {request.asset_symbol}")

    try:
        # Get the cached Council graph
        council_graph = get_council_graph()

        # Create initial state
        # TODO: In future stories, load data from database instead of request
        initial_state = create_initial_state(
            asset_symbol=request.asset_symbol,
            candles_data=request.candles_data,  # type: ignore
            sentiment_data=request.sentiment_data,
        )

        # Run the graph (synchronous for now)
        # TODO: Consider async execution in future stories
        final_state = council_graph.invoke(initial_state)

        logger.info(
            f"Council session completed for {request.asset_symbol}: "
            f"{final_state.get('final_decision', {}).get('action', 'N/A')}"
        )

        # Convert datetime to ISO string for JSON serialization
        final_decision = final_state.get("final_decision")
        if final_decision and "timestamp" in final_decision:
            final_decision = dict(final_decision)
            final_decision["timestamp"] = final_decision["timestamp"].isoformat()

        return CouncilSessionResponse(
            asset_symbol=final_state["asset_symbol"],
            technical_analysis=final_state.get("technical_analysis"),
            sentiment_analysis=final_state.get("sentiment_analysis"),
            vision_analysis=final_state.get("vision_analysis"),
            final_decision=final_decision,
            error=final_state.get("error"),
        )

    except Exception as e:
        logger.error(f"Council session failed for {request.asset_symbol}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Council session failed: {str(e)}",
        )


@app.get("/api/council/test")
async def test_council_graph() -> dict[str, Any]:
    """
    Test the Council graph with dummy data.

    Story 2.1: LangGraph State Machine Setup

    This endpoint is for development testing of the graph flow.
    It creates a test state with sample data and runs the graph.

    Returns:
        Dict containing test results and graph status.
    """
    logger.info("Council graph test initiated")

    try:
        # Get the cached graph
        council_graph = get_council_graph()

        # Create test state
        test_state = create_initial_state(
            asset_symbol="SOLUSD",
            candles_data=[
                {
                    "timestamp": datetime.now(timezone.utc),
                    "open": 100.0,
                    "high": 105.0,
                    "low": 98.0,
                    "close": 103.0,
                    "volume": 10000.0
                }
            ],
            sentiment_data=[
                {"text": "Test sentiment", "source": "test", "score": 0.5}
            ],
        )

        # Run graph
        result = council_graph.invoke(test_state)

        # Extract decision for response
        decision = result.get("final_decision", {})

        return {
            "status": "success",
            "graph_compiled": True,
            "test_asset": result["asset_symbol"],
            "decision_action": decision.get("action"),
            "decision_confidence": decision.get("confidence"),
            "all_nodes_executed": all([
                result.get("technical_analysis") is not None,
                result.get("sentiment_analysis") is not None,
                result.get("vision_analysis") is not None,
                result.get("final_decision") is not None,
            ]),
        }

    except Exception as e:
        logger.error(f"Council graph test failed: {e}")
        return {
            "status": "error",
            "graph_compiled": False,
            "error": str(e),
        }


# =============================================================================
# Story 2.4: Council Cycle Endpoints (Paper Trading)
# =============================================================================


@app.post("/api/council/cycle")
async def trigger_council_cycle() -> dict[str, Any]:
    """
    Manually trigger a council cycle for all active assets.

    Story 2.4: Master Node & Signal Logging

    This endpoint bypasses the scheduler and runs a full council
    cycle immediately. Useful for testing and on-demand analysis.

    Note: Paper Trading mode - NO actual trade execution.

    Returns:
        Dict with cycle statistics
    """
    logger.info("Manual council cycle triggered via API")
    try:
        stats = await run_council_cycle()
        return {
            "status": "completed",
            "mode": "Paper Trading",
            "stats": stats,
        }
    except Exception as e:
        logger.error(f"Manual council cycle failed: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Council cycle failed: {str(e)}",
        )


@app.post("/api/council/run/{asset_symbol}")
async def manual_council_run(asset_symbol: str) -> dict[str, Any]:
    """
    Manually trigger council session for a single asset.

    Story 2.4: Master Node & Signal Logging

    Runs the council for a specific asset and logs the decision
    to the database. Useful for testing individual assets.

    Note: Paper Trading mode - NO actual trade execution.

    Args:
        asset_symbol: Trading pair symbol (e.g., "SOLUSD")

    Returns:
        Dict with session result and decision
    """
    logger.info(f"Manual council run triggered for {asset_symbol}")

    try:
        # Get the cached Council graph
        council_graph = get_council_graph()

        # Get async session
        session_maker = get_session_maker()
        async with session_maker() as session:
            # Load asset
            asset = await load_asset_by_symbol(asset_symbol, session)
            if not asset:
                raise HTTPException(
                    status_code=404,
                    detail=f"Asset not found: {asset_symbol}"
                )

            # Load data
            candles = await load_candles_for_asset(asset.id, limit=200, session=session)
            sentiment = await load_sentiment_for_asset(asset_symbol, hours=24, session=session)

            if len(candles) < 50:
                return {
                    "status": "skipped",
                    "reason": f"Insufficient candle data ({len(candles)} candles, need 50+)",
                    "asset": asset_symbol,
                }

            # Build initial state
            initial_state = create_initial_state(
                asset_symbol=asset_symbol,
                candles_data=candles,
                sentiment_data=sentiment,
            )

            # Run council
            final_state = council_graph.invoke(initial_state)

            # Log session (Paper Trading)
            council_session = await log_council_session(final_state, asset.id, session=session)

            # Extract decision
            decision = final_state.get("final_decision", {})

            return {
                "status": "completed",
                "mode": "Paper Trading",
                "asset": asset_symbol,
                "session_id": council_session.id,
                "decision": {
                    "action": decision.get("action"),
                    "confidence": decision.get("confidence"),
                    "reasoning": decision.get("reasoning"),
                },
                "analyses": {
                    "sentiment": final_state.get("sentiment_analysis"),
                    "technical": final_state.get("technical_analysis"),
                    "vision": final_state.get("vision_analysis"),
                }
            }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Manual council run failed for {asset_symbol}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Council run failed: {str(e)}",
        )


@app.get("/api/council/sessions/{asset_symbol}")
async def get_asset_sessions(
    asset_symbol: str,
    limit: int = 10
) -> dict[str, Any]:
    """
    Get recent council sessions for an asset.

    Story 2.4: Master Node & Signal Logging

    Returns the most recent council decisions for UI display
    and performance analysis.

    Args:
        asset_symbol: Trading pair symbol (e.g., "SOLUSD")
        limit: Maximum number of sessions to return (default: 10)

    Returns:
        Dict with list of recent sessions
    """
    try:
        session_maker = get_session_maker()
        async with session_maker() as session:
            # Load asset
            asset = await load_asset_by_symbol(asset_symbol, session)
            if not asset:
                raise HTTPException(
                    status_code=404,
                    detail=f"Asset not found: {asset_symbol}"
                )

            # Get recent sessions
            sessions = await get_recent_sessions(asset.id, limit=limit, session=session)

            # Format for response
            session_list = []
            for s in sessions:
                session_list.append({
                    "id": s.id,
                    "timestamp": s.timestamp.isoformat() if s.timestamp else None,
                    "sentiment_score": s.sentiment_score,
                    "technical_signal": s.technical_signal,
                    "final_decision": s.final_decision.value if s.final_decision else None,
                    "reasoning_log": s.reasoning_log,
                })

            return {
                "asset": asset_symbol,
                "sessions": session_list,
                "count": len(session_list),
            }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get sessions for {asset_symbol}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get sessions: {str(e)}",
        )


# =============================================================================
# Story 5.5: Risk Parameter Optimization - Risk Status API
# =============================================================================


@app.get("/api/risk/status")
async def get_risk_status() -> dict[str, Any]:
    """
    Get current risk status across all parameters.

    Story 5.5: Risk Parameter Optimization

    Returns comprehensive risk metrics including:
    - Drawdown utilization
    - Position concentration
    - Correlation exposure
    - Daily loss tracking
    - Overall risk level
    - Alerts and recommendations

    Returns:
        Dict with risk status, metrics, alerts, and recommendations
    """
    logger.info("Risk status requested via API")

    try:
        validator = get_risk_validator()

        # Get current portfolio state
        session_maker = get_session_maker()
        async with session_maker() as session:
            # Get open positions
            open_trades = await get_all_open_positions(session)

            # Calculate portfolio value and positions list
            positions = []
            total_value = 0.0

            for trade in open_trades:
                # Get current price for position value
                # For simplicity, use entry_price * size as position value
                position_value = float(trade.entry_price * trade.size)
                total_value += position_value

                # Get asset symbol
                from models import Asset
                from sqlmodel import select
                asset_result = await session.execute(
                    select(Asset).where(Asset.id == trade.asset_id)
                )
                asset = asset_result.scalar_one_or_none()

                if asset:
                    positions.append({
                        "symbol": asset.symbol,
                        "value": position_value,
                        "trade_id": trade.id,
                    })

            # Estimate portfolio value (positions + assumed cash)
            # In production, this would come from exchange balance
            estimated_portfolio = max(total_value * 2, 10000.0)  # Assume 50% deployed

            # Calculate daily P&L (simplified - would need trade history)
            daily_pnl = 0.0

            # Get risk status
            status = await validator.get_risk_status(
                portfolio_value=estimated_portfolio,
                current_positions=positions,
                daily_pnl=daily_pnl,
                session=session,
            )

            return {
                "status": status.overall_risk_level.value,
                "can_trade": status.can_trade,
                "metrics": {
                    "drawdown": {
                        "current": status.current_drawdown_pct,
                        "limit": status.max_drawdown_pct,
                        "utilization": status.drawdown_utilization,
                    },
                    "position_concentration": {
                        "largest_pct": status.largest_position_pct,
                        "limit": status.max_single_position_pct,
                        "utilization": status.position_concentration_utilization,
                    },
                    "correlation": {
                        "exposure_pct": status.correlated_exposure_pct,
                        "limit": status.max_correlated_exposure_pct,
                        "utilization": status.correlation_utilization,
                    },
                    "daily_loss": {
                        "current_pct": status.daily_loss_pct,
                        "limit": status.daily_loss_limit_pct,
                        "utilization": status.daily_loss_utilization,
                    },
                },
                "alerts": status.alerts,
                "recommendations": status.recommendations,
                "open_positions": len(positions),
                "estimated_portfolio_value": estimated_portfolio,
            }

    except Exception as e:
        logger.error(f"Failed to get risk status: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get risk status: {str(e)}",
        )


@app.post("/api/risk/validate")
async def validate_trade_risk(
    symbol: str,
    requested_size_usd: float,
    portfolio_value: Optional[float] = None,
) -> dict[str, Any]:
    """
    Validate a potential trade against risk limits.

    Story 5.5: Risk Parameter Optimization

    Args:
        symbol: Trading pair symbol (e.g., "SOLUSD")
        requested_size_usd: Requested position size in USD
        portfolio_value: Optional portfolio value (estimated if not provided)

    Returns:
        Dict with validation result and any adjustments
    """
    logger.info(f"Trade risk validation requested for {symbol}: ${requested_size_usd}")

    try:
        validator = get_risk_validator()

        session_maker = get_session_maker()
        async with session_maker() as session:
            # Get open positions
            open_trades = await get_all_open_positions(session)

            # Calculate positions list
            positions = []
            total_value = 0.0

            for trade in open_trades:
                position_value = float(trade.entry_price * trade.size)
                total_value += position_value

                from models import Asset
                from sqlmodel import select
                asset_result = await session.execute(
                    select(Asset).where(Asset.id == trade.asset_id)
                )
                asset = asset_result.scalar_one_or_none()

                if asset:
                    positions.append({
                        "symbol": asset.symbol,
                        "value": position_value,
                    })

            # Use provided portfolio value or estimate
            pv = portfolio_value or max(total_value * 2, 10000.0)

            # Validate the trade
            result = await validator.validate_trade(
                symbol=symbol,
                requested_size_usd=requested_size_usd,
                portfolio_value=pv,
                current_positions=positions,
                daily_pnl=0.0,
                session=session,
            )

            return {
                "approved": result.approved,
                "max_allowed_size": float(result.max_allowed_size),
                "rejection_reasons": result.rejection_reasons,
                "warnings": result.warnings,
                "adjustments": result.risk_adjustments,
            }

    except Exception as e:
        logger.error(f"Failed to validate trade risk: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to validate trade risk: {str(e)}",
        )
