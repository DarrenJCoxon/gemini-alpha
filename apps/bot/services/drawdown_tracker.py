"""
Drawdown tracking service for portfolio risk management.

Story 5.5: Risk Parameter Optimization

This module tracks portfolio drawdown from peak equity:
- Updates portfolio value and calculates drawdown
- Stores snapshots in the database
- Provides current drawdown percentage
"""

from decimal import Decimal
from datetime import datetime, timezone
from typing import Optional, Dict, Any
import logging

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from database import get_session_maker
from models.portfolio import PortfolioSnapshot

logger = logging.getLogger(__name__)


class DrawdownTracker:
    """
    Track portfolio drawdown from peak equity.

    The drawdown is calculated as:
    Drawdown = (Peak Value - Current Value) / Peak Value * 100%

    Peak value is the highest portfolio value ever recorded.
    It only resets when a new high is made.
    """

    def __init__(self):
        self.peak_value: Optional[Decimal] = None
        self.current_value: Optional[Decimal] = None
        self._loaded: bool = False

    async def update_portfolio_value(
        self,
        new_value: Decimal,
        open_positions_count: Optional[int] = None,
        realized_pnl_today: Optional[Decimal] = None,
        session: Optional[AsyncSession] = None,
    ) -> Dict[str, Any]:
        """
        Update portfolio value and calculate drawdown.

        Args:
            new_value: Current portfolio value in USD
            open_positions_count: Optional count of open positions
            realized_pnl_today: Optional realized P&L for today
            session: Optional database session

        Returns:
            Dict with drawdown metrics
        """
        self.current_value = new_value

        async def _update(s: AsyncSession) -> Dict[str, Any]:
            # Get historical peak
            result = await s.execute(
                select(PortfolioSnapshot)
                .order_by(PortfolioSnapshot.peak_value.desc())
                .limit(1)
            )
            peak_record = result.scalar_one_or_none()

            if peak_record:
                self.peak_value = peak_record.peak_value
            else:
                # First snapshot - peak is current value
                self.peak_value = new_value

            # Update peak if we have new high
            if new_value > self.peak_value:
                self.peak_value = new_value
                logger.info(f"New portfolio peak: ${new_value:.2f}")

            # Calculate drawdown
            if self.peak_value > 0:
                drawdown = (self.peak_value - new_value) / self.peak_value * 100
            else:
                drawdown = Decimal("0")

            # Save snapshot
            snapshot = PortfolioSnapshot(
                timestamp=datetime.now(timezone.utc),
                portfolio_value=new_value,
                peak_value=self.peak_value,
                drawdown_pct=drawdown,
                open_positions_count=open_positions_count,
                realized_pnl_today=realized_pnl_today,
            )
            s.add(snapshot)
            await s.commit()

            logger.info(
                f"Portfolio snapshot: ${new_value:.2f} "
                f"(peak: ${self.peak_value:.2f}, drawdown: {drawdown:.2f}%)"
            )

            return {
                "current_value": float(new_value),
                "peak_value": float(self.peak_value),
                "drawdown_pct": float(drawdown),
                "is_at_peak": new_value >= self.peak_value,
            }

        if session:
            return await _update(session)
        else:
            session_maker = get_session_maker()
            async with session_maker() as new_session:
                return await _update(new_session)

    async def get_current_drawdown(
        self,
        session: Optional[AsyncSession] = None,
    ) -> float:
        """
        Get current drawdown percentage.

        Returns:
            Current drawdown as percentage (0.0 to 100.0+)
        """
        if self.peak_value is None or self.current_value is None:
            await self._load_latest(session)

        if self.peak_value and self.peak_value > 0 and self.current_value is not None:
            return float((self.peak_value - self.current_value) / self.peak_value * 100)
        return 0.0

    async def get_peak_value(
        self,
        session: Optional[AsyncSession] = None,
    ) -> Decimal:
        """
        Get the current peak portfolio value.

        Returns:
            Peak value in USD
        """
        if self.peak_value is None:
            await self._load_latest(session)

        return self.peak_value or Decimal("0")

    async def _load_latest(
        self,
        session: Optional[AsyncSession] = None,
    ) -> None:
        """Load latest values from database."""
        async def _load(s: AsyncSession) -> None:
            result = await s.execute(
                select(PortfolioSnapshot)
                .order_by(PortfolioSnapshot.timestamp.desc())
                .limit(1)
            )
            snapshot = result.scalar_one_or_none()
            if snapshot:
                self.current_value = snapshot.portfolio_value
                self.peak_value = snapshot.peak_value
                logger.debug(
                    f"Loaded portfolio state: value=${self.current_value}, "
                    f"peak=${self.peak_value}"
                )
            else:
                logger.debug("No portfolio snapshots found")
                self.current_value = Decimal("0")
                self.peak_value = Decimal("0")

        if session:
            await _load(session)
        else:
            session_maker = get_session_maker()
            async with session_maker() as new_session:
                await _load(new_session)

        self._loaded = True

    async def get_recent_snapshots(
        self,
        limit: int = 100,
        session: Optional[AsyncSession] = None,
    ) -> list:
        """
        Get recent portfolio snapshots.

        Args:
            limit: Maximum number of snapshots to return
            session: Optional database session

        Returns:
            List of PortfolioSnapshot objects
        """
        async def _get(s: AsyncSession) -> list:
            result = await s.execute(
                select(PortfolioSnapshot)
                .order_by(PortfolioSnapshot.timestamp.desc())
                .limit(limit)
            )
            return list(result.scalars().all())

        if session:
            return await _get(session)
        else:
            session_maker = get_session_maker()
            async with session_maker() as new_session:
                return await _get(new_session)


# Global instance for convenience
_drawdown_tracker: Optional[DrawdownTracker] = None


def get_drawdown_tracker() -> DrawdownTracker:
    """Get or create the global drawdown tracker instance."""
    global _drawdown_tracker
    if _drawdown_tracker is None:
        _drawdown_tracker = DrawdownTracker()
    return _drawdown_tracker
