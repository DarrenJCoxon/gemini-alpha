"""
Safety API endpoints for the Contrarian AI Trading Bot.

Story 3.4: Global Safety Switch

This module provides REST API endpoints for:
- GET /api/safety/status - Get current system status
- POST /api/safety/pause - Pause trading (kill switch)
- POST /api/safety/resume - Resume trading after pause
- POST /api/safety/liquidate - Emergency liquidation (DANGER!)

SECURITY NOTE: These endpoints should be protected with authentication
in production. The /liquidate endpoint is particularly dangerous and
should require additional confirmation.
"""

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from services.safety import (
    get_system_status,
    get_system_config,
    is_trading_enabled,
    pause_trading,
    resume_trading,
    check_drawdown,
    get_portfolio_value,
    get_open_positions_value,
    liquidate_all,
    initialize_system_config,
)
from models import SystemStatus

# Configure logging
logger = logging.getLogger("safety_api")

# Create router
router = APIRouter(prefix="/api/safety", tags=["safety"])


# =============================================================================
# Response Models
# =============================================================================


class SystemStatusResponse(BaseModel):
    """Response model for system status."""
    status: str
    trading_enabled: bool
    current_value: float
    initial_balance: float
    drawdown_pct: float
    max_drawdown_pct: float
    open_positions: int


class PauseResponse(BaseModel):
    """Response model for pause action."""
    status: str
    reason: str


class ResumeResponse(BaseModel):
    """Response model for resume action."""
    status: str


class LiquidationResponse(BaseModel):
    """Response model for liquidation action."""
    positions_closed: int
    positions_failed: int
    total_pnl: float
    reason: str
    timestamp: str


class InitConfigRequest(BaseModel):
    """Request model for initializing system config."""
    initial_balance: float
    max_drawdown_pct: float = 0.20


class InitConfigResponse(BaseModel):
    """Response model for system config initialization."""
    status: str
    initial_balance: float
    max_drawdown_pct: float


# =============================================================================
# Endpoints
# =============================================================================


@router.get("/status", response_model=SystemStatusResponse)
async def get_status():
    """
    Get current system status.

    Returns comprehensive safety status including:
    - Current system status (ACTIVE/PAUSED/EMERGENCY_STOP)
    - Whether trading is currently enabled
    - Current portfolio value
    - Current drawdown percentage
    - Number of open positions
    """
    try:
        status = await get_system_status()
        config = await get_system_config()
        trading_enabled = await is_trading_enabled()

        # Get drawdown info
        _, drawdown_pct, current_value = await check_drawdown()

        # Get open positions count
        _, position_count = await get_open_positions_value()

        initial_balance = float(config.initial_balance) if config else 0.0
        max_drawdown_pct = float(config.max_drawdown_pct) if config else 0.20

        return SystemStatusResponse(
            status=status.value,
            trading_enabled=trading_enabled,
            current_value=current_value,
            initial_balance=initial_balance,
            drawdown_pct=drawdown_pct,
            max_drawdown_pct=max_drawdown_pct,
            open_positions=position_count,
        )

    except Exception as e:
        logger.error(f"Failed to get system status: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get system status: {str(e)}"
        )


@router.post("/pause", response_model=PauseResponse)
async def pause_system(
    reason: str = Query(default="Manual pause", description="Reason for pausing")
):
    """
    Pause trading (kill switch).

    Sets system status to PAUSED which prevents:
    - Council decision cycles from executing orders
    - New buy orders from being placed

    Position monitoring (stop loss checks) will still run.

    Args:
        reason: Reason for pausing (logged for audit trail)
    """
    try:
        success = await pause_trading(reason)
        if not success:
            raise HTTPException(
                status_code=500,
                detail="Failed to pause trading"
            )

        logger.warning(f"Trading PAUSED via API: {reason}")

        return PauseResponse(
            status="paused",
            reason=reason,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to pause trading: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to pause trading: {str(e)}"
        )


@router.post("/resume", response_model=ResumeResponse)
async def resume_system():
    """
    Resume trading after pause.

    Sets system status back to ACTIVE.

    NOTE: Cannot resume from EMERGENCY_STOP status.
    EMERGENCY_STOP requires manual database intervention to clear.
    """
    try:
        success = await resume_trading()
        if not success:
            # Check if it's because we're in EMERGENCY_STOP
            status = await get_system_status()
            if status == SystemStatus.EMERGENCY_STOP:
                raise HTTPException(
                    status_code=400,
                    detail=(
                        "Cannot resume from EMERGENCY_STOP. "
                        "Manual database intervention required."
                    )
                )
            raise HTTPException(
                status_code=500,
                detail="Failed to resume trading"
            )

        logger.info("Trading RESUMED via API")

        return ResumeResponse(status="active")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to resume trading: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to resume trading: {str(e)}"
        )


@router.post("/liquidate", response_model=LiquidationResponse)
async def emergency_liquidate(
    reason: str = Query(default="Manual emergency", description="Reason for liquidation"),
    confirm: bool = Query(default=False, description="Confirm liquidation"),
):
    """
    DANGER: Liquidate all positions immediately.

    This action cannot be undone. It will:
    1. Set system status to EMERGENCY_STOP
    2. Close ALL open positions at market price
    3. Disable trading until manual intervention

    WARNING: This should only be used in emergency situations.

    Args:
        reason: Reason for liquidation (logged for audit trail)
        confirm: Must be True to confirm the action
    """
    if not confirm:
        raise HTTPException(
            status_code=400,
            detail=(
                "Liquidation requires confirmation. "
                "Set confirm=true to proceed. "
                "WARNING: This will close ALL positions immediately!"
            )
        )

    try:
        logger.critical(f"EMERGENCY LIQUIDATION triggered via API: {reason}")

        summary = await liquidate_all(reason=reason)

        return LiquidationResponse(
            positions_closed=summary["positions_closed"],
            positions_failed=summary["positions_failed"],
            total_pnl=summary["total_pnl"],
            reason=summary["reason"],
            timestamp=summary["timestamp"],
        )

    except Exception as e:
        logger.error(f"Liquidation failed: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Liquidation failed: {str(e)}"
        )


@router.post("/init", response_model=InitConfigResponse)
async def init_config(request: InitConfigRequest):
    """
    Initialize system configuration.

    Sets the initial balance for drawdown calculations.
    Should be called when starting the bot with a new portfolio.

    Args:
        initial_balance: Starting portfolio value in USD
        max_drawdown_pct: Maximum allowed drawdown (default: 0.20 = 20%)
    """
    try:
        await initialize_system_config(
            initial_balance=request.initial_balance,
            max_drawdown_pct=request.max_drawdown_pct,
        )

        logger.info(
            f"System config initialized: "
            f"${request.initial_balance:.2f}, "
            f"max drawdown {request.max_drawdown_pct * 100:.0f}%"
        )

        return InitConfigResponse(
            status="initialized",
            initial_balance=request.initial_balance,
            max_drawdown_pct=request.max_drawdown_pct,
        )

    except Exception as e:
        logger.error(f"Failed to initialize config: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to initialize config: {str(e)}"
        )


@router.get("/portfolio")
async def get_portfolio():
    """
    Get current portfolio breakdown.

    Returns detailed breakdown of portfolio value by asset.
    """
    try:
        total_value, breakdown = await get_portfolio_value()

        return {
            "total_value_usd": total_value,
            "breakdown": breakdown,
        }

    except Exception as e:
        logger.error(f"Failed to get portfolio: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get portfolio: {str(e)}"
        )
