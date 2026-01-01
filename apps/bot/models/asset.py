"""
Asset model for the trading bot.

This model mirrors the Prisma Asset model with proper
camelCase to snake_case mapping using sa_column_kwargs.

Story 5.2: Added tier system fields for asset universe reduction.
"""

from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Optional, TYPE_CHECKING, List

from sqlalchemy import Column, String, Boolean, DateTime, Numeric
from sqlmodel import Field, SQLModel, Relationship

from .base import generate_cuid

if TYPE_CHECKING:
    from .candle import Candle
    from .sentiment import SentimentLog
    from .council import CouncilSession
    from .trade import Trade


class AssetTier(str, Enum):
    """
    Asset tier classification for allocation limits.

    Story 5.2: Asset Universe Reduction

    Tier 1: BTC, ETH - 60% max allocation (highest liquidity)
    Tier 2: SOL, AVAX, LINK - 30% max allocation (strong fundamentals)
    Tier 3: High conviction picks - 10% max allocation (configurable)
    Excluded: Meme coins, micro-caps, risky assets - not tradeable
    """

    TIER_1 = "TIER_1"
    TIER_2 = "TIER_2"
    TIER_3 = "TIER_3"
    EXCLUDED = "EXCLUDED"


class Asset(SQLModel, table=True):
    """
    Crypto asset definition.

    Represents a tradable cryptocurrency asset (e.g., BTCUSD, ETHUSD).
    This is the source of truth for all assets monitored by the system.

    Story 5.2: Added tier system for asset universe management.
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

    # Story 5.2: Asset Tier System
    tier: Optional[str] = Field(
        default=None,
        sa_column=Column("tier", String(20), nullable=True),
    )
    max_allocation_percent: Optional[Decimal] = Field(
        default=None,
        sa_column=Column("maxAllocationPercent", Numeric(5, 2), nullable=True),
    )
    min_volume_24h: Optional[Decimal] = Field(
        default=None,
        sa_column=Column("minVolume24h", Numeric(18, 2), nullable=True),
    )
    min_market_cap: Optional[Decimal] = Field(
        default=None,
        sa_column=Column("minMarketCap", Numeric(18, 2), nullable=True),
    )
    is_meme_coin: bool = Field(
        default=False,
        sa_column=Column("isMemeCoin", Boolean, default=False),
    )
    exclusion_reason: Optional[str] = Field(
        default=None,
        sa_column=Column("exclusionReason", String(255), nullable=True),
    )

    # Relationships
    candles: List["Candle"] = Relationship(back_populates="asset")
    sentiment_logs: List["SentimentLog"] = Relationship(back_populates="asset")
    council_sessions: List["CouncilSession"] = Relationship(back_populates="asset")
    trades: List["Trade"] = Relationship(back_populates="asset")
