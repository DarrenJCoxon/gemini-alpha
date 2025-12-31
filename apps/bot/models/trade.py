"""
Trade model for the trading bot.

This model mirrors the Prisma Trade model with proper
camelCase to snake_case mapping using sa_column.
"""

from datetime import datetime
from decimal import Decimal
from typing import Optional, List, TYPE_CHECKING

from sqlalchemy import Column, String, DateTime, Numeric, ForeignKey, Enum as SAEnum
from sqlmodel import Field, SQLModel, Relationship

from .base import generate_cuid, TradeStatus

if TYPE_CHECKING:
    from .asset import Asset
    from .council import CouncilSession


class Trade(SQLModel, table=True):
    """
    Trade execution records.

    Tracks all trades executed by the system, including entry/exit
    prices, P&L, and links to the council session that triggered them.
    """

    __tablename__ = "Trade"

    id: str = Field(
        default_factory=generate_cuid,
        sa_column=Column(String, primary_key=True),
    )
    asset_id: str = Field(
        sa_column=Column("assetId", String, ForeignKey("Asset.id"), nullable=False),
    )
    council_session_id: Optional[str] = Field(
        default=None,
        sa_column=Column("councilSessionId", String, nullable=True),
    )
    status: TradeStatus = Field(
        default=TradeStatus.PENDING,
        sa_column=Column(
            SAEnum(TradeStatus, name="TradeStatus", create_type=False),
            nullable=False,
            default="PENDING",
        ),
    )
    side: str = Field(
        default="BUY",
        sa_column=Column(String, nullable=False, default="BUY"),
    )
    entry_price: Decimal = Field(
        sa_column=Column("entryPrice", Numeric(18, 8), nullable=False),
    )
    size: Decimal = Field(
        sa_column=Column(Numeric(18, 8), nullable=False),
    )
    entry_time: datetime = Field(
        sa_column=Column("entryTime", DateTime, nullable=False),
    )
    stop_loss_price: Decimal = Field(
        sa_column=Column("stopLossPrice", Numeric(18, 8), nullable=False),
    )
    take_profit_price: Optional[Decimal] = Field(
        default=None,
        sa_column=Column("takeProfitPrice", Numeric(18, 8), nullable=True),
    )
    exit_price: Optional[Decimal] = Field(
        default=None,
        sa_column=Column("exitPrice", Numeric(18, 8), nullable=True),
    )
    exit_time: Optional[datetime] = Field(
        default=None,
        sa_column=Column("exitTime", DateTime, nullable=True),
    )
    pnl: Optional[Decimal] = Field(
        default=None,
        sa_column=Column(Numeric(18, 8), nullable=True),
    )
    pnl_percent: Optional[Decimal] = Field(
        default=None,
        sa_column=Column("pnlPercent", Numeric(8, 4), nullable=True),
    )
    exit_reason: Optional[str] = Field(
        default=None,
        sa_column=Column("exitReason", String, nullable=True),
    )
    kraken_order_id: Optional[str] = Field(
        default=None,
        sa_column=Column("krakenOrderId", String, nullable=True),
    )
    created_at: datetime = Field(
        default_factory=datetime.utcnow,
        sa_column=Column("createdAt", DateTime, nullable=False),
    )
    updated_at: datetime = Field(
        default_factory=datetime.utcnow,
        sa_column=Column("updatedAt", DateTime, nullable=False),
    )

    # Relationships
    asset: Optional["Asset"] = Relationship(back_populates="trades")
    council_sessions: List["CouncilSession"] = Relationship(back_populates="trade")
