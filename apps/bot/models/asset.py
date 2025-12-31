"""
Asset model for the trading bot.

This model mirrors the Prisma Asset model with proper
camelCase to snake_case mapping using sa_column_kwargs.
"""

from datetime import datetime
from decimal import Decimal
from typing import Optional, TYPE_CHECKING, List

from sqlalchemy import Column, String, Boolean, DateTime, Numeric
from sqlmodel import Field, SQLModel, Relationship

from .base import generate_cuid

if TYPE_CHECKING:
    from .candle import Candle
    from .sentiment import SentimentLog
    from .council import CouncilSession
    from .trade import Trade


class Asset(SQLModel, table=True):
    """
    Crypto asset definition.

    Represents a tradable cryptocurrency asset (e.g., BTCUSD, ETHUSD).
    This is the source of truth for all assets monitored by the system.
    """

    __tablename__ = "Asset"

    id: str = Field(
        default_factory=generate_cuid,
        sa_column=Column(String, primary_key=True),
    )
    symbol: str = Field(
        sa_column=Column(String, unique=True, index=True, nullable=False),
    )
    name: Optional[str] = Field(
        default=None,
        sa_column=Column(String, nullable=True),
    )
    is_active: bool = Field(
        default=True,
        sa_column=Column("isActive", Boolean, nullable=False, default=True),
    )
    last_price: Optional[Decimal] = Field(
        default=None,
        sa_column=Column("lastPrice", Numeric(18, 8), nullable=True),
    )
    last_updated: Optional[datetime] = Field(
        default=None,
        sa_column=Column("lastUpdated", DateTime, nullable=True),
    )
    created_at: datetime = Field(
        default_factory=datetime.utcnow,
        sa_column=Column("createdAt", DateTime, nullable=False),
    )

    # Relationships
    candles: List["Candle"] = Relationship(back_populates="asset")
    sentiment_logs: List["SentimentLog"] = Relationship(back_populates="asset")
    council_sessions: List["CouncilSession"] = Relationship(back_populates="asset")
    trades: List["Trade"] = Relationship(back_populates="asset")
