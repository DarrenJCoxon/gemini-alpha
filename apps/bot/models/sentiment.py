"""
SentimentLog model for the trading bot.

This model mirrors the Prisma SentimentLog model with proper
camelCase to snake_case mapping using sa_column.
"""

from datetime import datetime
from typing import Optional, TYPE_CHECKING

from sqlalchemy import Column, String, DateTime, Integer, Text, ForeignKey, Index
from sqlmodel import Field, SQLModel, Relationship

from .base import generate_cuid

if TYPE_CHECKING:
    from .asset import Asset


class SentimentLog(SQLModel, table=True):
    """
    Sentiment data from various sources.

    Stores sentiment metrics from LunarCrush, social media scraping,
    and other sentiment data providers.
    """

    __tablename__ = "SentimentLog"
    __table_args__ = (
        Index("SentimentLog_assetId_timestamp_idx", "assetId", "timestamp"),
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
    source: str = Field(
        sa_column=Column(String, nullable=False),
    )
    galaxy_score: Optional[int] = Field(
        default=None,
        sa_column=Column("galaxyScore", Integer, nullable=True),
    )
    alt_rank: Optional[int] = Field(
        default=None,
        sa_column=Column("altRank", Integer, nullable=True),
    )
    social_volume: Optional[int] = Field(
        default=None,
        sa_column=Column("socialVolume", Integer, nullable=True),
    )
    raw_text: Optional[str] = Field(
        default=None,
        sa_column=Column("rawText", Text, nullable=True),
    )
    sentiment_score: Optional[int] = Field(
        default=None,
        sa_column=Column("sentimentScore", Integer, nullable=True),
    )
    created_at: datetime = Field(
        default_factory=datetime.utcnow,
        sa_column=Column("createdAt", DateTime, nullable=False),
    )

    # Relationships
    asset: Optional["Asset"] = Relationship(back_populates="sentiment_logs")
