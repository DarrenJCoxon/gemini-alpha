"""
Portfolio snapshot model for drawdown tracking.

Story 5.5: Risk Parameter Optimization

This model stores point-in-time portfolio value snapshots
for calculating drawdown from peak equity.
"""

from datetime import datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import Column, String, DateTime, Numeric, Integer, Index
from sqlmodel import Field, SQLModel

from .base import generate_cuid


class PortfolioSnapshot(SQLModel, table=True):
    """
    Point-in-time portfolio value snapshot for drawdown tracking.

    Stores the portfolio value, peak value, and calculated drawdown
    percentage at each snapshot point.
    """

    __tablename__ = "PortfolioSnapshot"
    __table_args__ = (
        Index("PortfolioSnapshot_timestamp_idx", "timestamp"),
    )

    id: str = Field(
        default_factory=generate_cuid,
        sa_column=Column(String, primary_key=True),
    )
    timestamp: datetime = Field(
        default_factory=datetime.utcnow,
        sa_column=Column(DateTime, nullable=False, index=True),
    )
    portfolio_value: Decimal = Field(
        sa_column=Column("portfolioValue", Numeric(18, 2), nullable=False),
    )
    peak_value: Decimal = Field(
        sa_column=Column("peakValue", Numeric(18, 2), nullable=False),
    )
    drawdown_pct: Decimal = Field(
        sa_column=Column("drawdownPct", Numeric(5, 2), nullable=False),
    )

    # Additional metrics
    open_positions_count: Optional[int] = Field(
        default=None,
        sa_column=Column("openPositionsCount", Integer, nullable=True),
    )
    realized_pnl_today: Optional[Decimal] = Field(
        default=None,
        sa_column=Column("realizedPnlToday", Numeric(18, 2), nullable=True),
    )

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "id": self.id,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "portfolio_value": float(self.portfolio_value),
            "peak_value": float(self.peak_value),
            "drawdown_pct": float(self.drawdown_pct),
            "open_positions_count": self.open_positions_count,
            "realized_pnl_today": float(self.realized_pnl_today) if self.realized_pnl_today else None,
        }
