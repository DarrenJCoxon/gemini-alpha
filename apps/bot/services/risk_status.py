"""
Risk status tracking for portfolio risk management.

Story 5.5: Risk Parameter Optimization

This module provides data structures for tracking risk status
across all parameters including drawdown, position concentration,
correlation exposure, and daily loss limits.
"""

from dataclasses import dataclass
from decimal import Decimal
from typing import Dict, List
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class RiskLevel(str, Enum):
    """Risk level classification based on limit utilization."""
    LOW = "LOW"           # < 50% of limits
    MODERATE = "MODERATE" # 50-80% of limits
    HIGH = "HIGH"         # 80-100% of limits
    CRITICAL = "CRITICAL" # At or exceeding limits


@dataclass
class RiskStatus:
    """Current risk status across all parameters."""

    # Drawdown
    current_drawdown_pct: float
    max_drawdown_pct: float
    drawdown_utilization: float  # Percentage of limit used

    # Per-trade risk
    per_trade_risk_pct: float
    max_per_trade_risk_pct: float

    # Position concentration
    largest_position_pct: float
    max_single_position_pct: float
    position_concentration_utilization: float

    # Correlation exposure
    correlated_exposure_pct: float
    max_correlated_exposure_pct: float
    correlation_utilization: float

    # Daily loss
    daily_loss_pct: float
    daily_loss_limit_pct: float
    daily_loss_utilization: float

    # Overall status
    overall_risk_level: RiskLevel
    can_trade: bool
    alerts: List[str]
    recommendations: List[str]

    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "drawdown": {
                "current": self.current_drawdown_pct,
                "limit": self.max_drawdown_pct,
                "utilization": self.drawdown_utilization,
            },
            "per_trade_risk": {
                "current": self.per_trade_risk_pct,
                "limit": self.max_per_trade_risk_pct,
            },
            "position_concentration": {
                "largest_pct": self.largest_position_pct,
                "limit": self.max_single_position_pct,
                "utilization": self.position_concentration_utilization,
            },
            "correlation": {
                "exposure_pct": self.correlated_exposure_pct,
                "limit": self.max_correlated_exposure_pct,
                "utilization": self.correlation_utilization,
            },
            "daily_loss": {
                "current_pct": self.daily_loss_pct,
                "limit": self.daily_loss_limit_pct,
                "utilization": self.daily_loss_utilization,
            },
            "overall": {
                "risk_level": self.overall_risk_level.value,
                "can_trade": self.can_trade,
            },
            "alerts": self.alerts,
            "recommendations": self.recommendations,
        }


@dataclass
class PositionRisk:
    """Risk metrics for a single position."""
    symbol: str
    position_value: Decimal
    position_pct: float
    correlation_group: str
    correlated_with: List[str]
    risk_contribution: float

    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "symbol": self.symbol,
            "position_value": float(self.position_value),
            "position_pct": self.position_pct,
            "correlation_group": self.correlation_group,
            "correlated_with": self.correlated_with,
            "risk_contribution": self.risk_contribution,
        }


def determine_risk_level(utilization: float) -> RiskLevel:
    """
    Determine risk level based on utilization percentage.

    Args:
        utilization: Percentage of limit used (0-100+)

    Returns:
        RiskLevel enum value
    """
    if utilization >= 100:
        return RiskLevel.CRITICAL
    elif utilization >= 80:
        return RiskLevel.HIGH
    elif utilization >= 50:
        return RiskLevel.MODERATE
    else:
        return RiskLevel.LOW
