"""
Candle model for the trading bot.

This model mirrors the Prisma Candle model with proper
camelCase to snake_case mapping using sa_column.
"""

from datetime import datetime
from decimal import Decimal
from typing import Optional, TYPE_CHECKING

from sqlalchemy import Column, String, DateTime, Numeric, ForeignKey, Index, UniqueConstraint
from sqlmodel import Field, SQLModel, Relationship

from .base import generate_cuid

if TYPE_CHECKING:
    from .asset import Asset


class Candle(SQLModel, table=True):
    """
    OHLCV candle data.

    Stores price and volume data for each time period (default: 15 minutes).
    Indexed for fast lookups by asset and timestamp.
    """

    __tablename__ = "Candle"
    __table_args__ = (
        UniqueConstraint("assetId", "timestamp", "timeframe", name="Candle_assetId_timestamp_timeframe_key"),
        Index("Candle_assetId_timestamp_idx", "assetId", "timestamp"),
    )

    id: str = Field(
        default_factory=generate_cuid,
        sa_column=Column(String, primary_key=True),
    )
    asset_id: str = Field(
        sa_column=Column("assetId", String, ForeignKey("Asset.id"), nullable=False),
    )
    timestamp: datetime = Field(
        sa_column=Column(DateTime, nullable=False),
    )
    timeframe: str = Field(
        default="15m",
        sa_column=Column(String, nullable=False, default="15m"),
    )
    open: Decimal = Field(
        sa_column=Column(Numeric(18, 8), nullable=False),
    )
    high: Decimal = Field(
        sa_column=Column(Numeric(18, 8), nullable=False),
    )
    low: Decimal = Field(
        sa_column=Column(Numeric(18, 8), nullable=False),
    )
    close: Decimal = Field(
        sa_column=Column(Numeric(18, 8), nullable=False),
    )
    volume: Decimal = Field(
        sa_column=Column(Numeric(24, 8), nullable=False),
    )

    # Relationships
    asset: Optional["Asset"] = Relationship(back_populates="candles")
