"""
SystemConfig model for the trading bot.

Story 3.4: Global Safety Switch

This model provides system-wide configuration for:
- Trading status (ACTIVE, PAUSED, EMERGENCY_STOP)
- Max drawdown protection settings
- Emergency stop tracking and logging
"""

from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Optional

from sqlalchemy import Column, String, DateTime, Numeric, Boolean, Enum as SAEnum
from sqlmodel import Field, SQLModel


class SystemStatus(str, Enum):
    """
    System trading status enum matching Prisma schema.

    ACTIVE: Normal trading operations enabled
    PAUSED: Trading temporarily paused (manual kill switch)
    EMERGENCY_STOP: Emergency stop triggered (requires manual intervention to resume)
    """
    ACTIVE = "ACTIVE"
    PAUSED = "PAUSED"
    EMERGENCY_STOP = "EMERGENCY_STOP"


class SystemConfig(SQLModel, table=True):
    """
    System-wide configuration for trading controls and safety mechanisms.

    This is a singleton table with a fixed ID of "system".
    Only one row should exist in this table.

    Story 3.4: Global Safety Switch

    Features:
    - Trading status control (kill switch)
    - Max drawdown percentage configuration
    - Emergency stop tracking with timestamp and reason
    - Initial balance tracking for drawdown calculation
    """

    __tablename__ = "system_config"

    id: str = Field(
        default="system",
        sa_column=Column(String, primary_key=True),
    )
    status: SystemStatus = Field(
        default=SystemStatus.ACTIVE,
        sa_column=Column(
            SAEnum(SystemStatus, name="SystemStatus", create_type=False),
            nullable=False,
            default="ACTIVE",
        ),
    )
    trading_enabled: bool = Field(
        default=True,
        sa_column=Column("tradingEnabled", Boolean, nullable=False, default=True),
    )
    initial_balance: Decimal = Field(
        default=Decimal("0"),
        sa_column=Column("initialBalance", Numeric(18, 8), nullable=False),
    )
    max_drawdown_pct: Decimal = Field(
        default=Decimal("0.20"),
        sa_column=Column("maxDrawdownPct", Numeric(5, 4), nullable=False, default=0.20),
    )
    last_drawdown_check: Optional[datetime] = Field(
        default=None,
        sa_column=Column("lastDrawdownCheck", DateTime, nullable=True),
    )
    emergency_stop_at: Optional[datetime] = Field(
        default=None,
        sa_column=Column("emergencyStopAt", DateTime, nullable=True),
    )
    emergency_reason: Optional[str] = Field(
        default=None,
        sa_column=Column("emergencyReason", String, nullable=True),
    )
    updated_at: datetime = Field(
        default_factory=datetime.utcnow,
        sa_column=Column("updatedAt", DateTime, nullable=False),
    )
