"""
Pre-trade risk validation service.

Story 5.5: Risk Parameter Optimization

This module validates trades against all risk limits before execution:
- Daily loss limit
- Maximum drawdown
- Maximum single position size
- Correlated exposure
- Per-trade risk
"""

from decimal import Decimal
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
import logging

from sqlmodel.ext.asyncio.session import AsyncSession

from services.risk_status import RiskStatus, RiskLevel, PositionRisk, determine_risk_level
from services.drawdown_tracker import DrawdownTracker, get_drawdown_tracker
from services.correlation_tracker import (
    calculate_correlated_exposure,
    get_correlated_assets,
    get_correlation_group,
)
from config import get_config

logger = logging.getLogger(__name__)


@dataclass
class TradeRiskCheck:
    """Result of pre-trade risk validation."""
    approved: bool
    max_allowed_size: Decimal  # May be reduced from requested
    rejection_reasons: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    risk_adjustments: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "approved": self.approved,
            "max_allowed_size": float(self.max_allowed_size),
            "rejection_reasons": self.rejection_reasons,
            "warnings": self.warnings,
            "risk_adjustments": self.risk_adjustments,
        }


class RiskValidator:
    """
    Validates trades against risk limits before execution.

    Performs the following checks:
    1. Daily loss limit (stop trading for day if reached)
    2. Maximum drawdown (stop new positions until recovery)
    3. Maximum single position size (concentration limit)
    4. Correlated exposure (diversification requirement)
    5. Per-trade risk (position sizing input)
    """

    def __init__(self, drawdown_tracker: Optional[DrawdownTracker] = None):
        """
        Initialize risk validator.

        Args:
            drawdown_tracker: Optional drawdown tracker instance
        """
        self.drawdown_tracker = drawdown_tracker or get_drawdown_tracker()
        self.risk_config = get_config().enhanced_risk

    async def validate_trade(
        self,
        symbol: str,
        requested_size_usd: float,
        portfolio_value: float,
        current_positions: List[Dict],
        daily_pnl: float = 0.0,
        session: Optional[AsyncSession] = None,
    ) -> TradeRiskCheck:
        """
        Validate a trade against all risk limits.

        Args:
            symbol: Asset to trade
            requested_size_usd: Requested position size in USD
            portfolio_value: Total portfolio value in USD
            current_positions: List of current open positions
            daily_pnl: Today's realized + unrealized P&L
            session: Optional database session

        Returns:
            TradeRiskCheck with approval status and adjustments
        """
        rejection_reasons: List[str] = []
        warnings: List[str] = []
        adjustments: Dict[str, Any] = {}
        max_allowed = Decimal(str(requested_size_usd))

        portfolio = Decimal(str(portfolio_value))

        # Prevent division by zero
        if portfolio <= 0:
            return TradeRiskCheck(
                approved=False,
                max_allowed_size=Decimal("0"),
                rejection_reasons=["Portfolio value is zero or negative"],
            )

        # CHECK 1: Daily Loss Limit
        daily_loss_pct = abs(daily_pnl / portfolio_value * 100) if portfolio_value > 0 else 0
        if daily_pnl < 0 and daily_loss_pct >= self.risk_config.daily_loss_limit_pct:
            rejection_reasons.append(
                f"Daily loss limit reached: {daily_loss_pct:.1f}% >= {self.risk_config.daily_loss_limit_pct}%"
            )
        elif daily_pnl < 0 and daily_loss_pct >= self.risk_config.daily_loss_limit_pct * 0.8:
            warnings.append(
                f"Approaching daily loss limit: {daily_loss_pct:.1f}% (limit: {self.risk_config.daily_loss_limit_pct}%)"
            )

        # CHECK 2: Maximum Drawdown
        current_drawdown = await self.drawdown_tracker.get_current_drawdown(session)
        if current_drawdown >= self.risk_config.max_drawdown_pct:
            rejection_reasons.append(
                f"Max drawdown reached: {current_drawdown:.1f}% >= {self.risk_config.max_drawdown_pct}%"
            )
        elif current_drawdown >= self.risk_config.max_drawdown_pct * 0.8:
            warnings.append(
                f"Approaching max drawdown: {current_drawdown:.1f}% (limit: {self.risk_config.max_drawdown_pct}%)"
            )

        # CHECK 3: Maximum Single Position Size
        max_position_usd = portfolio * Decimal(str(self.risk_config.max_single_position_pct)) / 100
        if max_allowed > max_position_usd:
            adjustments["position_size_reduced"] = True
            adjustments["original_size"] = float(max_allowed)
            max_allowed = max_position_usd
            warnings.append(
                f"Position size reduced to {self.risk_config.max_single_position_pct}% limit: ${max_allowed:.2f}"
            )

        # CHECK 4: Correlated Exposure
        # First calculate current correlated exposure
        current_correlated = await calculate_correlated_exposure(
            current_positions,
            portfolio,
            session=session,
        )
        current_corr_pct = current_correlated["correlated_exposure_pct"]

        # Then check if adding this position would exceed limit
        test_positions = current_positions + [{"symbol": symbol, "value": float(max_allowed)}]
        projected_correlated = await calculate_correlated_exposure(
            test_positions,
            portfolio,
            session=session,
        )
        projected_corr_pct = projected_correlated["correlated_exposure_pct"]

        if projected_corr_pct > self.risk_config.max_correlated_exposure_pct:
            # Calculate how much we can add without exceeding limit
            available_pct = self.risk_config.max_correlated_exposure_pct - current_corr_pct

            if available_pct <= 0:
                rejection_reasons.append(
                    f"Correlated exposure at limit: {current_corr_pct:.1f}% >= {self.risk_config.max_correlated_exposure_pct}%"
                )
            else:
                available_usd = portfolio * Decimal(str(available_pct)) / 100
                if max_allowed > available_usd:
                    adjustments["correlation_reduced"] = True
                    adjustments["correlation_available_pct"] = available_pct
                    max_allowed = available_usd
                    warnings.append(
                        f"Position reduced due to correlation limit: ${max_allowed:.2f}"
                    )

        # CHECK 5: Per-Trade Risk
        # This is primarily used for position sizing, but we validate here
        max_risk_usd = portfolio * Decimal(str(self.risk_config.per_trade_risk_pct)) / 100
        adjustments["max_risk_usd"] = float(max_risk_usd)
        adjustments["per_trade_risk_pct"] = self.risk_config.per_trade_risk_pct

        # Ensure max_allowed is positive
        if max_allowed <= 0:
            if not rejection_reasons:
                rejection_reasons.append("Calculated position size is zero or negative")

        # FINAL DECISION
        approved = len(rejection_reasons) == 0 and max_allowed > 0

        if not approved:
            logger.warning(
                f"Trade REJECTED for {symbol}: {', '.join(rejection_reasons)}"
            )
        elif warnings:
            logger.info(
                f"Trade APPROVED with warnings for {symbol}: {', '.join(warnings)}"
            )
        else:
            logger.info(f"Trade APPROVED for {symbol}: ${max_allowed:.2f}")

        return TradeRiskCheck(
            approved=approved,
            max_allowed_size=max_allowed,
            rejection_reasons=rejection_reasons,
            warnings=warnings,
            risk_adjustments=adjustments,
        )

    async def get_risk_status(
        self,
        portfolio_value: float,
        current_positions: List[Dict],
        daily_pnl: float = 0.0,
        session: Optional[AsyncSession] = None,
    ) -> RiskStatus:
        """
        Get comprehensive risk status across all parameters.

        Args:
            portfolio_value: Total portfolio value in USD
            current_positions: List of current open positions
            daily_pnl: Today's realized + unrealized P&L
            session: Optional database session

        Returns:
            RiskStatus with all risk metrics
        """
        portfolio = Decimal(str(portfolio_value))

        # Calculate all risk metrics
        current_drawdown = await self.drawdown_tracker.get_current_drawdown(session)

        # Position concentration
        if current_positions and portfolio > 0:
            largest_position = max(
                (Decimal(str(p.get("value", 0))) for p in current_positions),
                default=Decimal("0")
            )
            largest_position_pct = float(largest_position / portfolio * 100)
        else:
            largest_position_pct = 0.0

        # Correlation exposure
        correlation_metrics = await calculate_correlated_exposure(
            current_positions,
            portfolio,
            session=session,
        )
        correlated_pct = correlation_metrics["correlated_exposure_pct"]

        # Daily loss
        if daily_pnl < 0 and portfolio_value > 0:
            daily_loss_pct = abs(daily_pnl / portfolio_value * 100)
        else:
            daily_loss_pct = 0.0

        # Calculate utilizations
        drawdown_util = (
            current_drawdown / self.risk_config.max_drawdown_pct * 100
            if self.risk_config.max_drawdown_pct > 0 else 0
        )
        position_util = (
            largest_position_pct / self.risk_config.max_single_position_pct * 100
            if self.risk_config.max_single_position_pct > 0 else 0
        )
        correlation_util = (
            correlated_pct / self.risk_config.max_correlated_exposure_pct * 100
            if self.risk_config.max_correlated_exposure_pct > 0 else 0
        )
        daily_loss_util = (
            daily_loss_pct / self.risk_config.daily_loss_limit_pct * 100
            if self.risk_config.daily_loss_limit_pct > 0 else 0
        )

        # Determine overall risk level
        max_utilization = max(drawdown_util, position_util, correlation_util, daily_loss_util)
        risk_level = determine_risk_level(max_utilization)

        # Generate alerts and recommendations
        alerts: List[str] = []
        recommendations: List[str] = []

        if drawdown_util >= 80:
            alerts.append(
                f"Drawdown at {current_drawdown:.1f}% - approaching {self.risk_config.max_drawdown_pct}% limit"
            )
            recommendations.append("Consider reducing position sizes or hedging")

        if position_util >= 80:
            alerts.append(
                f"Position concentration at {largest_position_pct:.1f}% - approaching {self.risk_config.max_single_position_pct}% limit"
            )
            recommendations.append("Consider diversifying into other assets")

        if correlation_util >= 80:
            alerts.append(
                f"Correlated exposure at {correlated_pct:.1f}% - approaching {self.risk_config.max_correlated_exposure_pct}% limit"
            )
            recommendations.append("Diversify into uncorrelated assets")

        if daily_loss_util >= 80:
            alerts.append(
                f"Daily loss at {daily_loss_pct:.1f}% - approaching {self.risk_config.daily_loss_limit_pct}% limit"
            )
            recommendations.append("Consider pausing trading for the day")

        can_trade = risk_level != RiskLevel.CRITICAL and daily_loss_util < 100

        return RiskStatus(
            current_drawdown_pct=current_drawdown,
            max_drawdown_pct=self.risk_config.max_drawdown_pct,
            drawdown_utilization=drawdown_util,
            per_trade_risk_pct=self.risk_config.per_trade_risk_pct,
            max_per_trade_risk_pct=self.risk_config.per_trade_risk_pct,
            largest_position_pct=largest_position_pct,
            max_single_position_pct=self.risk_config.max_single_position_pct,
            position_concentration_utilization=position_util,
            correlated_exposure_pct=correlated_pct,
            max_correlated_exposure_pct=self.risk_config.max_correlated_exposure_pct,
            correlation_utilization=correlation_util,
            daily_loss_pct=daily_loss_pct,
            daily_loss_limit_pct=self.risk_config.daily_loss_limit_pct,
            daily_loss_utilization=daily_loss_util,
            overall_risk_level=risk_level,
            can_trade=can_trade,
            alerts=alerts,
            recommendations=recommendations,
        )

    async def get_position_risks(
        self,
        current_positions: List[Dict],
        portfolio_value: float,
        session: Optional[AsyncSession] = None,
    ) -> List[PositionRisk]:
        """
        Get risk metrics for each position.

        Args:
            current_positions: List of current open positions
            portfolio_value: Total portfolio value in USD
            session: Optional database session

        Returns:
            List of PositionRisk objects
        """
        portfolio = Decimal(str(portfolio_value))
        position_risks: List[PositionRisk] = []

        for position in current_positions:
            symbol = position.get("symbol", "")
            value = Decimal(str(position.get("value", 0)))
            position_pct = float(value / portfolio * 100) if portfolio > 0 else 0

            # Get correlation info
            correlation_group = get_correlation_group(symbol)
            correlated = await get_correlated_assets(
                symbol,
                current_positions,
                session=session,
            )

            position_risks.append(
                PositionRisk(
                    symbol=symbol,
                    position_value=value,
                    position_pct=position_pct,
                    correlation_group=correlation_group,
                    correlated_with=[c[0] for c in correlated],
                    risk_contribution=position_pct,  # Simplified
                )
            )

        return position_risks


# Global instance for convenience
_risk_validator: Optional[RiskValidator] = None


def get_risk_validator() -> RiskValidator:
    """Get or create the global risk validator instance."""
    global _risk_validator
    if _risk_validator is None:
        _risk_validator = RiskValidator()
    return _risk_validator
