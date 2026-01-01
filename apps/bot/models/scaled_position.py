"""
Scaled Position models for gradual position entry/exit.

Story 5.4: Scale In/Out Position Management

This module provides models for managing scaled positions:
- ScaledPosition: Parent position tracking overall scaling strategy
- ScaleOrder: Individual scale orders within a scaled position

Scale-in: Build position gradually (33% immediate, 33% at -5%, 33% at -10%)
Scale-out: Exit position gradually (33% at +10%, 33% at +20%, 33% trailing)
"""

from datetime import datetime
from decimal import Decimal
from typing import Optional, List, TYPE_CHECKING
from enum import Enum

from sqlalchemy import Column, String, Integer, Boolean, DateTime, Numeric, ForeignKey
from sqlmodel import Field, SQLModel, Relationship

from .base import generate_cuid

if TYPE_CHECKING:
    from .asset import Asset


class ScaleDirection(str, Enum):
    """Direction of scaling operation."""
    SCALE_IN = "SCALE_IN"    # Building position
    SCALE_OUT = "SCALE_OUT"  # Reducing position


class ScaleStatus(str, Enum):
    """Status of a scale order."""
    PENDING = "PENDING"      # Waiting for trigger
    EXECUTED = "EXECUTED"    # Order filled
    CANCELLED = "CANCELLED"  # Cancelled (position closed)
    EXPIRED = "EXPIRED"      # Timeout reached


class ScaleTriggerType(str, Enum):
    """Types of scale order triggers."""
    IMMEDIATE = "IMMEDIATE"           # Execute immediately
    PRICE_DROP = "PRICE_DROP"        # Trigger on price drop (scale-in)
    CAPITULATION = "CAPITULATION"    # Extreme drop trigger (scale-in)
    PROFIT_TARGET = "PROFIT_TARGET"  # Profit target reached (scale-out)
    TRAILING_STOP = "TRAILING_STOP"  # Trailing stop (scale-out)


class ScaledPosition(SQLModel, table=True):
    """
    Parent position that tracks overall scaling strategy.

    A ScaledPosition represents the full intended position,
    while individual ScaleOrders represent the partial entries/exits.
    """
    __tablename__ = "ScaledPosition"

    id: str = Field(
        default_factory=generate_cuid,
        sa_column=Column(String, primary_key=True),
    )
    asset_id: str = Field(
        sa_column=Column("assetId", String, ForeignKey("Asset.id"), nullable=False),
    )

    # Position status
    direction: str = Field(
        sa_column=Column(String(20), nullable=False),
    )  # SCALE_IN or SCALE_OUT
    is_active: bool = Field(
        default=True,
        sa_column=Column("isActive", Boolean, default=True),
    )

    # Target sizing
    target_size: Decimal = Field(
        sa_column=Column("targetSize", Numeric(18, 8), nullable=False),
    )  # Total position size targeted
    filled_size: Decimal = Field(
        default=Decimal("0"),
        sa_column=Column("filledSize", Numeric(18, 8), default=0),
    )  # Amount filled so far
    remaining_size: Decimal = Field(
        sa_column=Column("remainingSize", Numeric(18, 8), nullable=False),
    )

    # Average price tracking
    average_price: Optional[Decimal] = Field(
        default=None,
        sa_column=Column("averagePrice", Numeric(18, 8), nullable=True),
    )
    total_cost: Decimal = Field(
        default=Decimal("0"),
        sa_column=Column("totalCost", Numeric(18, 2), default=0),
    )  # For calculating average (size * price sum)

    # Scale configuration
    num_scales: int = Field(
        default=3,
        sa_column=Column("numScales", Integer, default=3),
    )
    scales_executed: int = Field(
        default=0,
        sa_column=Column("scalesExecuted", Integer, default=0),
    )

    # Timestamps
    created_at: datetime = Field(
        default_factory=datetime.utcnow,
        sa_column=Column("createdAt", DateTime, nullable=False),
    )
    completed_at: Optional[datetime] = Field(
        default=None,
        sa_column=Column("completedAt", DateTime, nullable=True),
    )

    # Council session reference (for audit trail)
    council_session_id: Optional[str] = Field(
        default=None,
        sa_column=Column("councilSessionId", String, nullable=True),
    )

    # Reference to parent trade (for scale-out operations)
    parent_trade_id: Optional[str] = Field(
        default=None,
        sa_column=Column("parentTradeId", String, nullable=True),
    )

    # Relationships
    scale_orders: List["ScaleOrder"] = Relationship(back_populates="scaled_position")

    def calculate_average_price(self) -> Optional[Decimal]:
        """Calculate weighted average price from total cost and filled size."""
        if self.filled_size > Decimal("0"):
            return self.total_cost / self.filled_size
        return None

    def is_complete(self) -> bool:
        """Check if all scales have been executed."""
        return self.scales_executed >= self.num_scales

    def get_fill_percentage(self) -> float:
        """Get percentage of position filled."""
        if self.target_size > Decimal("0"):
            return float(self.filled_size / self.target_size * 100)
        return 0.0


class ScaleOrder(SQLModel, table=True):
    """
    Individual scale order within a scaled position.

    Each ScaleOrder represents one leg of a scaled entry or exit,
    with its own trigger conditions and execution details.
    """
    __tablename__ = "ScaleOrder"

    id: str = Field(
        default_factory=generate_cuid,
        sa_column=Column(String, primary_key=True),
    )
    scaled_position_id: str = Field(
        sa_column=Column("scaledPositionId", String, ForeignKey("ScaledPosition.id"), nullable=False),
    )

    # Order details
    scale_number: int = Field(
        sa_column=Column("scaleNumber", Integer, nullable=False),
    )  # 1, 2, or 3
    status: str = Field(
        default=ScaleStatus.PENDING.value,
        sa_column=Column(String(20), default="PENDING"),
    )

    # Trigger conditions
    trigger_type: str = Field(
        sa_column=Column("triggerType", String(50), nullable=False),
    )  # IMMEDIATE, PRICE_DROP, CAPITULATION, PROFIT_TARGET, TRAILING_STOP
    trigger_price: Optional[Decimal] = Field(
        default=None,
        sa_column=Column("triggerPrice", Numeric(18, 8), nullable=True),
    )
    trigger_pct: Optional[Decimal] = Field(
        default=None,
        sa_column=Column("triggerPct", Numeric(5, 2), nullable=True),
    )  # Percentage from first entry

    # Execution details
    target_size: Decimal = Field(
        sa_column=Column("targetSize", Numeric(18, 8), nullable=False),
    )
    executed_size: Optional[Decimal] = Field(
        default=None,
        sa_column=Column("executedSize", Numeric(18, 8), nullable=True),
    )
    executed_price: Optional[Decimal] = Field(
        default=None,
        sa_column=Column("executedPrice", Numeric(18, 8), nullable=True),
    )

    # Trade reference (when executed)
    trade_id: Optional[str] = Field(
        default=None,
        sa_column=Column("tradeId", String, nullable=True),
    )

    # Timestamps
    created_at: datetime = Field(
        default_factory=datetime.utcnow,
        sa_column=Column("createdAt", DateTime, nullable=False),
    )
    triggered_at: Optional[datetime] = Field(
        default=None,
        sa_column=Column("triggeredAt", DateTime, nullable=True),
    )
    executed_at: Optional[datetime] = Field(
        default=None,
        sa_column=Column("executedAt", DateTime, nullable=True),
    )

    # Relationship
    scaled_position: "ScaledPosition" = Relationship(back_populates="scale_orders")

    def is_triggered(self, current_price: float, direction: str) -> bool:
        """
        Check if this scale order should be triggered based on current price.

        Args:
            current_price: Current market price
            direction: SCALE_IN or SCALE_OUT

        Returns:
            True if order should be triggered, False otherwise
        """
        if self.status != ScaleStatus.PENDING.value:
            return False

        if self.trigger_type == ScaleTriggerType.IMMEDIATE.value:
            return True

        if self.trigger_price is None:
            return False

        trigger = float(self.trigger_price)

        if direction == ScaleDirection.SCALE_IN.value:
            # Scale-in triggers when price drops to or below trigger
            return current_price <= trigger
        else:
            # Scale-out triggers when price rises to or above trigger
            return current_price >= trigger

    def get_execution_value(self) -> Decimal:
        """Get the value of this execution (size * price)."""
        if self.executed_size and self.executed_price:
            return self.executed_size * self.executed_price
        return Decimal("0")
