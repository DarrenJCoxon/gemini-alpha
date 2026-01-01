"""
CouncilSession model for the trading bot.

This model mirrors the Prisma CouncilSession model with proper
camelCase to snake_case mapping using sa_column.

Story 5.1: Added market regime fields for audit trail:
- market_regime: Current regime (BULL/BEAR/CHOP)
- regime_confidence: Detection confidence
- price_vs_200dma: Price position relative to 200 DMA
"""

from datetime import datetime
from decimal import Decimal
from typing import Optional, Any, Dict, TYPE_CHECKING

from sqlalchemy import Column, String, DateTime, Integer, Numeric, Text, ForeignKey, Index, Enum as SAEnum
from sqlalchemy.dialects.postgresql import JSON
from sqlmodel import Field, SQLModel, Relationship

from .base import generate_cuid, Decision

if TYPE_CHECKING:
    from .asset import Asset
    from .trade import Trade


class CouncilSession(SQLModel, table=True):
    """
    AI council deliberation session.

    Records the full context and reasoning of each trading decision,
    including sentiment analysis, technical signals, and AI synthesis.
    This is critical for the UI to display the "AI Thinking" experience.
    """

    __tablename__ = "CouncilSession"
    __table_args__ = (
        Index("CouncilSession_assetId_timestamp_idx", "assetId", "timestamp"),
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
    sentiment_score: int = Field(
        sa_column=Column("sentimentScore", Integer, nullable=False),
    )
    technical_signal: str = Field(
        sa_column=Column("technicalSignal", String, nullable=False),
    )
    technical_details: Optional[Dict[str, Any]] = Field(
        default=None,
        sa_column=Column("technicalDetails", JSON, nullable=True),
    )
    vision_analysis: Optional[str] = Field(
        default=None,
        sa_column=Column("visionAnalysis", Text, nullable=True),
    )
    vision_confidence: Optional[Decimal] = Field(
        default=None,
        sa_column=Column("visionConfidence", Numeric(3, 2), nullable=True),
    )
    final_decision: Decision = Field(
        sa_column=Column(
            "finalDecision",
            SAEnum(Decision, name="Decision", create_type=False),
            nullable=False,
        ),
    )
    reasoning_log: str = Field(
        sa_column=Column("reasoningLog", Text, nullable=False),
    )
    executed_trade_id: Optional[str] = Field(
        default=None,
        sa_column=Column("executedTradeId", String, ForeignKey("Trade.id"), nullable=True),
    )
    created_at: datetime = Field(
        default_factory=datetime.utcnow,
        sa_column=Column("createdAt", DateTime, nullable=False),
    )

    # Market Regime fields (Story 5.1)
    market_regime: Optional[str] = Field(
        default=None,
        sa_column=Column("marketRegime", String(10), nullable=True),
    )
    regime_confidence: Optional[int] = Field(
        default=None,
        sa_column=Column("regimeConfidence", Integer, nullable=True),
    )
    price_vs_200dma: Optional[Decimal] = Field(
        default=None,
        sa_column=Column("priceVs200Dma", Numeric(10, 4), nullable=True),
    )

    # Relationships
    asset: Optional["Asset"] = Relationship(back_populates="council_sessions")
    trade: Optional["Trade"] = Relationship(back_populates="council_sessions")
