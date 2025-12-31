# Story 3.4: Global Safety Switch

**Status:** Draft
**Epic:** 3 - Execution & Risk Management
**Priority:** Critical (System safety & capital protection)

---

## Story

**As a** User,
**I want** a "Kill Switch" and a Max Drawdown protection,
**so that** the bot stops trading immediately if things go wrong.

---

## Acceptance Criteria

1. **Max Drawdown Guard:** If Portfolio Value drops > 20% from initial balance, the system MUST:
   - Close all open positions immediately.
   - Disable the "Buy" permission flag in the DB.
   - Send a notification (log error).

2. **Manual Kill Switch:** A database flag `system_status` (ACTIVE/PAUSED). If `PAUSED`, the Scheduler skips the "Council" and Execution steps.

---

## Tasks / Subtasks

### Phase 1: System Configuration Model

- [ ] **Create SystemConfig table/model**
  - [ ] Add to Prisma schema `packages/database/prisma/schema.prisma`:
    ```prisma
    enum SystemStatus {
      ACTIVE
      PAUSED
      EMERGENCY_STOP
    }

    model SystemConfig {
      id                String       @id @default("system")
      status            SystemStatus @default(ACTIVE)
      tradingEnabled    Boolean      @default(true)
      initialBalance    Decimal      @db.Decimal(18, 8)
      maxDrawdownPct    Decimal      @default(0.20) @db.Decimal(5, 4)
      lastDrawdownCheck DateTime?
      emergencyStopAt   DateTime?
      emergencyReason   String?
      updatedAt         DateTime     @updatedAt

      @@map("system_config")
    }
    ```
  - [ ] Run migration: `pnpm db:push` or `npx prisma migrate dev --name add_system_config`

- [ ] **Create SQLModel equivalent for Python**
  - [ ] Create/update `apps/bot/models/system_config.py`:
    ```python
    from sqlmodel import SQLModel, Field
    from typing import Optional
    from datetime import datetime
    from decimal import Decimal
    from enum import Enum

    class SystemStatus(str, Enum):
        ACTIVE = "ACTIVE"
        PAUSED = "PAUSED"
        EMERGENCY_STOP = "EMERGENCY_STOP"

    class SystemConfig(SQLModel, table=True):
        __tablename__ = "system_config"

        id: str = Field(default="system", primary_key=True)
        status: SystemStatus = Field(default=SystemStatus.ACTIVE)
        trading_enabled: bool = Field(default=True)
        initial_balance: Decimal = Field(default=Decimal("0"))
        max_drawdown_pct: Decimal = Field(default=Decimal("0.20"))
        last_drawdown_check: Optional[datetime] = None
        emergency_stop_at: Optional[datetime] = None
        emergency_reason: Optional[str] = None
        updated_at: datetime = Field(default_factory=datetime.utcnow)
    ```
  - [ ] Export from `apps/bot/models/__init__.py`

- [ ] **Create initialization script**
  - [ ] Create function to initialize SystemConfig:
    ```python
    async def initialize_system_config(initial_balance: float) -> SystemConfig:
        """Initialize or update system config with initial balance."""
        async with get_session() as session:
            config = await session.get(SystemConfig, "system")

            if config is None:
                config = SystemConfig(
                    id="system",
                    initial_balance=Decimal(str(initial_balance)),
                    status=SystemStatus.ACTIVE,
                    trading_enabled=True
                )
                session.add(config)
            else:
                # Update initial balance if needed
                config.initial_balance = Decimal(str(initial_balance))

            await session.commit()
            return config
    ```

### Phase 2: Safety Service Module

- [ ] **Create safety service**
  - [ ] Create `apps/bot/services/safety.py`
  - [ ] Add imports:
    ```python
    from decimal import Decimal
    from datetime import datetime, timezone
    from typing import Optional, Tuple
    import logging

    from database import get_session
    from models import SystemConfig, SystemStatus, Trade, TradeStatus
    from services.execution import execute_sell
    from services.kraken_client import KrakenClient

    logger = logging.getLogger(__name__)
    ```

### Phase 3: System Status Management

- [ ] **Implement status check functions**
  - [ ] Create function:
    ```python
    async def get_system_status() -> SystemStatus:
        """Get current system trading status."""
        async with get_session() as session:
            config = await session.get(SystemConfig, "system")

            if config is None:
                logger.error("SystemConfig not initialized!")
                return SystemStatus.PAUSED  # Fail safe

            return config.status


    async def is_trading_enabled() -> bool:
        """Check if trading is currently enabled."""
        async with get_session() as session:
            config = await session.get(SystemConfig, "system")

            if config is None:
                return False

            return (
                config.status == SystemStatus.ACTIVE
                and config.trading_enabled
            )
    ```

- [ ] **Implement status update functions**
  - [ ] Create function:
    ```python
    async def set_system_status(
        status: SystemStatus,
        reason: Optional[str] = None
    ) -> bool:
        """
        Update system trading status.

        Args:
            status: New system status
            reason: Optional reason for status change

        Returns:
            True on success
        """
        try:
            async with get_session() as session:
                config = await session.get(SystemConfig, "system")

                if config is None:
                    logger.error("SystemConfig not found")
                    return False

                old_status = config.status
                config.status = status
                config.updated_at = datetime.now(timezone.utc)

                if status == SystemStatus.EMERGENCY_STOP:
                    config.trading_enabled = False
                    config.emergency_stop_at = datetime.now(timezone.utc)
                    config.emergency_reason = reason

                await session.commit()

                logger.warning(
                    f"SYSTEM STATUS CHANGED: {old_status} -> {status}"
                    f"{f' ({reason})' if reason else ''}"
                )

                return True

        except Exception as e:
            logger.error(f"Failed to update system status: {e}")
            return False


    async def pause_trading(reason: str = "Manual pause") -> bool:
        """Pause trading (kill switch)."""
        return await set_system_status(SystemStatus.PAUSED, reason)


    async def resume_trading() -> bool:
        """Resume trading after pause."""
        async with get_session() as session:
            config = await session.get(SystemConfig, "system")

            if config is None:
                return False

            # Don't allow resume if in EMERGENCY_STOP
            if config.status == SystemStatus.EMERGENCY_STOP:
                logger.error(
                    "Cannot resume from EMERGENCY_STOP automatically. "
                    "Manual intervention required."
                )
                return False

            config.status = SystemStatus.ACTIVE
            config.trading_enabled = True
            config.updated_at = datetime.now(timezone.utc)

            await session.commit()

            logger.info("Trading resumed")
            return True
    ```

### Phase 4: Portfolio Balance Tracking

- [ ] **Implement balance fetching**
  - [ ] Create function:
    ```python
    async def get_portfolio_value() -> Tuple[float, dict]:
        """
        Calculate current total portfolio value.

        Returns:
            Tuple of (total_value_usd, breakdown_dict)
        """
        client = KrakenClient()

        try:
            # Fetch all balances
            balances = client.exchange.fetch_balance()

            total_usd = 0.0
            breakdown = {}

            for currency, balance_info in balances.items():
                if currency in ['info', 'free', 'used', 'total', 'debt']:
                    continue

                amount = balance_info.get('total', 0)
                if amount <= 0:
                    continue

                # Convert to USD
                if currency == 'USD':
                    value_usd = amount
                else:
                    # Fetch ticker for conversion
                    try:
                        symbol = f"{currency}/USD"
                        ticker = client.exchange.fetch_ticker(symbol)
                        price = ticker['last']
                        value_usd = amount * price
                    except Exception:
                        # Try USDT pair as fallback
                        try:
                            symbol = f"{currency}/USDT"
                            ticker = client.exchange.fetch_ticker(symbol)
                            price = ticker['last']
                            value_usd = amount * price
                        except Exception:
                            logger.warning(f"Cannot price {currency}, skipping")
                            continue

                total_usd += value_usd
                breakdown[currency] = {
                    'amount': amount,
                    'value_usd': value_usd
                }

            logger.info(f"Portfolio value: ${total_usd:.2f}")
            return total_usd, breakdown

        except Exception as e:
            logger.error(f"Failed to fetch portfolio value: {e}")
            return 0.0, {}
    ```

- [ ] **Track open position value**
  - [ ] Create function to include unrealized P&L:
    ```python
    async def get_open_positions_value() -> float:
        """Calculate total value of open positions."""
        async with get_session() as session:
            result = await session.execute(
                select(Trade).where(Trade.status == TradeStatus.OPEN)
            )
            trades = result.scalars().all()

        total_value = 0.0
        for trade in trades:
            symbol = await get_symbol_for_trade(trade)
            current_price = get_current_price(symbol)
            if current_price:
                position_value = float(trade.size) * current_price
                total_value += position_value

        return total_value
    ```

### Phase 5: Drawdown Calculation

- [ ] **Implement drawdown check**
  - [ ] Create function:
    ```python
    async def check_drawdown() -> Tuple[bool, float, float]:
        """
        Check if portfolio has exceeded maximum drawdown.

        Returns:
            Tuple of (exceeds_limit, current_drawdown_pct, current_value)
        """
        async with get_session() as session:
            config = await session.get(SystemConfig, "system")

            if config is None:
                logger.error("SystemConfig not initialized")
                return False, 0.0, 0.0

            initial_balance = float(config.initial_balance)
            max_drawdown = float(config.max_drawdown_pct)

        # Get current portfolio value
        current_value, _ = await get_portfolio_value()

        if current_value <= 0 or initial_balance <= 0:
            logger.error("Invalid balance values for drawdown calculation")
            return False, 0.0, current_value

        # Calculate drawdown percentage
        drawdown_amount = initial_balance - current_value
        drawdown_pct = drawdown_amount / initial_balance

        logger.info(
            f"Drawdown check: Initial ${initial_balance:.2f}, "
            f"Current ${current_value:.2f}, "
            f"Drawdown {drawdown_pct * 100:.2f}% (max {max_drawdown * 100:.0f}%)"
        )

        # Update last check timestamp
        async with get_session() as session:
            config = await session.get(SystemConfig, "system")
            config.last_drawdown_check = datetime.now(timezone.utc)
            await session.commit()

        exceeds_limit = drawdown_pct > max_drawdown

        if exceeds_limit:
            logger.critical(
                f"MAX DRAWDOWN EXCEEDED: {drawdown_pct * 100:.2f}% > {max_drawdown * 100:.0f}%"
            )

        return exceeds_limit, drawdown_pct, current_value
    ```

### Phase 6: Emergency Liquidation

- [ ] **Implement liquidate_all function**
  - [ ] Create function:
    ```python
    async def liquidate_all(reason: str = "Emergency liquidation") -> dict:
        """
        Emergency function to close ALL open positions immediately.

        This is the "nuclear option" - use with caution.

        Args:
            reason: Reason for liquidation (logged)

        Returns:
            Summary dict of liquidation results
        """
        logger.critical(f"LIQUIDATE_ALL TRIGGERED: {reason}")

        summary = {
            "positions_closed": 0,
            "positions_failed": 0,
            "total_pnl": 0.0,
            "reason": reason,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }

        # First, disable trading to prevent new positions
        await set_system_status(
            SystemStatus.EMERGENCY_STOP,
            reason=f"Emergency liquidation: {reason}"
        )

        # Fetch all open positions
        async with get_session() as session:
            result = await session.execute(
                select(Trade).where(Trade.status == TradeStatus.OPEN)
            )
            trades = result.scalars().all()

        if len(trades) == 0:
            logger.info("No open positions to liquidate")
            return summary

        logger.warning(f"Liquidating {len(trades)} positions...")

        # Close each position
        for trade in trades:
            try:
                symbol = await get_symbol_for_trade(trade)

                logger.info(f"Liquidating position {trade.id} ({symbol})")

                success, error = await close_position(
                    trade=trade,
                    reason=ExitReason.EMERGENCY,
                    exit_price=None  # Will use market price
                )

                if success:
                    summary["positions_closed"] += 1
                    # Get updated trade for P&L
                    async with get_session() as session:
                        updated_trade = await session.get(Trade, trade.id)
                        if updated_trade and updated_trade.pnl:
                            summary["total_pnl"] += float(updated_trade.pnl)
                else:
                    summary["positions_failed"] += 1
                    logger.error(f"Failed to liquidate {trade.id}: {error}")

                # Small delay to avoid rate limits
                await asyncio.sleep(0.5)

            except Exception as e:
                logger.error(f"Exception liquidating {trade.id}: {e}")
                summary["positions_failed"] += 1

        logger.critical(
            f"LIQUIDATION COMPLETE: "
            f"{summary['positions_closed']}/{len(trades)} closed, "
            f"P&L: ${summary['total_pnl']:.2f}"
        )

        return summary
    ```

### Phase 7: Max Drawdown Guard

- [ ] **Implement drawdown guard**
  - [ ] Create function:
    ```python
    async def enforce_max_drawdown() -> bool:
        """
        Check drawdown and trigger emergency stop if exceeded.

        Called every 15 minutes in scheduler.

        Returns:
            True if emergency stop was triggered
        """
        # Skip if already in emergency stop
        status = await get_system_status()
        if status == SystemStatus.EMERGENCY_STOP:
            logger.debug("Already in EMERGENCY_STOP, skipping drawdown check")
            return False

        # Check drawdown
        exceeds, drawdown_pct, current_value = await check_drawdown()

        if exceeds:
            reason = (
                f"Portfolio drawdown {drawdown_pct * 100:.2f}% "
                f"exceeded limit of 20%"
            )

            # Trigger liquidation
            await liquidate_all(reason=reason)

            # Send notification (placeholder - implement in Epic 4)
            await send_emergency_notification(
                title="MAX DRAWDOWN TRIGGERED",
                message=reason,
                current_value=current_value,
                drawdown_pct=drawdown_pct
            )

            return True

        return False


    async def send_emergency_notification(
        title: str,
        message: str,
        **context
    ) -> None:
        """
        Send emergency notification.

        TODO: Implement actual notification (email, Telegram, etc.)
        For now, logs as CRITICAL.
        """
        logger.critical(
            f"EMERGENCY NOTIFICATION: {title}\n"
            f"Message: {message}\n"
            f"Context: {context}"
        )

        # Future: Send to notification service
        # await notification_service.send_alert(title, message, context)
    ```

### Phase 8: Scheduler Integration

- [ ] **Add safety checks to scheduler**
  - [ ] Update `apps/bot/main.py`:
    ```python
    from services.safety import (
        is_trading_enabled,
        enforce_max_drawdown,
        get_system_status,
        SystemStatus
    )

    async def run_15min_cycle():
        """Main 15-minute cycle with safety checks."""

        # SAFETY CHECK 1: Is trading enabled?
        if not await is_trading_enabled():
            status = await get_system_status()
            logger.warning(
                f"Trading disabled (status: {status}). "
                "Skipping Council and Execution."
            )

            # Still run position monitoring for manual positions
            await check_open_positions()
            return

        # SAFETY CHECK 2: Drawdown guard
        if await enforce_max_drawdown():
            logger.critical(
                "Emergency stop triggered by drawdown guard. "
                "Cycle terminated."
            )
            return

        # Continue with normal cycle...
        logger.info("Safety checks passed. Proceeding with cycle.")

        # Step 1: Check positions
        await check_open_positions()

        # Step 2: Run Council (only if trading enabled)
        if await is_trading_enabled():  # Re-check after position management
            council_results = await run_council_session()

            # Step 3: Execute pending orders
            # ...
    ```

- [ ] **Add kill switch check before order execution**
  - [ ] In `execute_buy`:
    ```python
    async def execute_buy(...):
        # Check kill switch before any order
        if not await is_trading_enabled():
            logger.warning("Trading disabled - buy order blocked")
            return False, "Trading is currently disabled", None

        # ... rest of function
    ```

### Phase 9: API Endpoints (Optional - for Dashboard)

- [ ] **Create FastAPI endpoints for safety controls**
  - [ ] Add to `apps/bot/api/routes/safety.py`:
    ```python
    from fastapi import APIRouter, HTTPException
    from services.safety import (
        get_system_status,
        pause_trading,
        resume_trading,
        check_drawdown,
        get_portfolio_value,
        SystemStatus
    )

    router = APIRouter(prefix="/api/safety", tags=["safety"])


    @router.get("/status")
    async def get_status():
        """Get current system status."""
        status = await get_system_status()
        _, drawdown, current_value = await check_drawdown()

        return {
            "status": status.value,
            "current_value": current_value,
            "drawdown_pct": drawdown,
            "trading_enabled": status == SystemStatus.ACTIVE
        }


    @router.post("/pause")
    async def pause_system(reason: str = "Manual pause"):
        """Pause trading (kill switch)."""
        success = await pause_trading(reason)
        if not success:
            raise HTTPException(500, "Failed to pause trading")
        return {"status": "paused", "reason": reason}


    @router.post("/resume")
    async def resume_system():
        """Resume trading after pause."""
        success = await resume_trading()
        if not success:
            raise HTTPException(400, "Cannot resume - check system status")
        return {"status": "active"}


    @router.post("/liquidate")
    async def emergency_liquidate(reason: str = "Manual emergency"):
        """
        DANGER: Liquidate all positions immediately.

        This action cannot be undone.
        """
        summary = await liquidate_all(reason)
        return summary
    ```

- [ ] **Register routes in main app**
  - [ ] Add router to FastAPI app

### Phase 10: Testing & Verification

- [ ] **Create unit tests**
  - [ ] Create `apps/bot/tests/test_safety.py`:
    ```python
    import pytest
    from unittest.mock import Mock, patch, AsyncMock
    from decimal import Decimal
    from services.safety import (
        check_drawdown,
        enforce_max_drawdown,
        liquidate_all,
        is_trading_enabled,
        SystemStatus
    )

    @pytest.mark.asyncio
    async def test_drawdown_calculation():
        """Test drawdown percentage calculation."""
        # Mock config with $10,000 initial
        with patch('services.safety.get_session') as mock_session:
            mock_config = Mock(
                initial_balance=Decimal("10000"),
                max_drawdown_pct=Decimal("0.20")
            )
            # ... setup mocks

            # Current value $8,500 = 15% drawdown
            with patch('services.safety.get_portfolio_value', return_value=(8500.0, {})):
                exceeds, pct, value = await check_drawdown()

                assert exceeds is False  # 15% < 20%
                assert abs(pct - 0.15) < 0.01
                assert value == 8500.0


    @pytest.mark.asyncio
    async def test_drawdown_triggers_liquidation():
        """Test that exceeding drawdown triggers emergency stop."""
        with patch('services.safety.check_drawdown', return_value=(True, 0.25, 7500)):
            with patch('services.safety.liquidate_all') as mock_liquidate:
                mock_liquidate.return_value = {"positions_closed": 2}

                result = await enforce_max_drawdown()

                assert result is True
                mock_liquidate.assert_called_once()


    @pytest.mark.asyncio
    async def test_trading_disabled_blocks_execution():
        """Test that disabled trading blocks buy orders."""
        with patch('services.safety.is_trading_enabled', return_value=False):
            # execute_buy should return failure
            pass  # Implement test
    ```

- [ ] **Create simulation script**
  - [ ] Create `apps/bot/scripts/test_safety.py`:
    ```python
    """
    Safety switch simulation test.

    WARNING: This will actually pause trading and may affect live operations.
    Use only in development/staging environment.
    """
    import asyncio
    from services.safety import (
        get_system_status,
        pause_trading,
        resume_trading,
        check_drawdown,
        is_trading_enabled,
        SystemStatus
    )

    async def main():
        print("=" * 60)
        print("Safety Switch Simulation Test")
        print("=" * 60)

        # Check current status
        print("\n[1] Current Status:")
        status = await get_system_status()
        print(f"    Status: {status}")
        print(f"    Trading Enabled: {await is_trading_enabled()}")

        # Check drawdown
        print("\n[2] Drawdown Check:")
        exceeds, pct, value = await check_drawdown()
        print(f"    Portfolio Value: ${value:.2f}")
        print(f"    Drawdown: {pct * 100:.2f}%")
        print(f"    Exceeds Limit: {exceeds}")

        # Test pause/resume
        print("\n[3] Testing Kill Switch:")
        print("    Pausing trading...")
        await pause_trading("Test pause")

        print(f"    Status after pause: {await get_system_status()}")
        print(f"    Trading enabled: {await is_trading_enabled()}")

        print("    Resuming trading...")
        await resume_trading()

        print(f"    Status after resume: {await get_system_status()}")
        print(f"    Trading enabled: {await is_trading_enabled()}")

        print("\n" + "=" * 60)
        print("Test Complete")
        print("=" * 60)

    if __name__ == "__main__":
        asyncio.run(main())
    ```

---

## Dev Notes

### Architecture Context

**Reference:** `docs/core/prd.md` Section 1.1 Goals (Risk: Max 20% drawdown)

The Safety Switch is the ultimate protection mechanism. It provides:
1. **Automatic Protection:** Max drawdown guard triggers emergency liquidation
2. **Manual Control:** Kill switch for immediate human intervention

```
Safety Hierarchy:
1. is_trading_enabled() check on every cycle
2. enforce_max_drawdown() check every 15 minutes
3. liquidate_all() for emergency situations
```

**Critical Design Principle:** FAIL SAFE. When in doubt, stop trading.

### Technical Specifications

**SystemConfig Table:**
```sql
CREATE TABLE system_config (
    id              VARCHAR(255) PRIMARY KEY DEFAULT 'system',
    status          VARCHAR(50) DEFAULT 'ACTIVE',
    trading_enabled BOOLEAN DEFAULT true,
    initial_balance DECIMAL(18, 8),
    max_drawdown_pct DECIMAL(5, 4) DEFAULT 0.20,
    last_drawdown_check TIMESTAMP,
    emergency_stop_at TIMESTAMP,
    emergency_reason TEXT,
    updated_at      TIMESTAMP
);
```

**Drawdown Formula:**
```
Drawdown % = (Initial Balance - Current Value) / Initial Balance

If Drawdown % > 20%:
    TRIGGER EMERGENCY STOP
```

**Status State Machine:**
```
ACTIVE <--> PAUSED (via pause/resume)
   |
   v
EMERGENCY_STOP (no automatic return - manual intervention required)
```

### Security Considerations

**CRITICAL - API Security:**
- The `/api/safety/liquidate` endpoint MUST require authentication
- Consider requiring 2FA or confirmation code for liquidation
- Log ALL safety-related actions with full context
- Consider IP whitelisting for safety endpoints

**Environment Variables:**
```bash
# .env
INITIAL_BALANCE=10000.00  # Starting portfolio value
MAX_DRAWDOWN_PCT=0.20     # 20% max loss
SAFETY_CHECK_INTERVAL=900  # 15 minutes in seconds
```

### Implementation Guidance

**Order of Safety Checks:**
1. Check `is_trading_enabled()` FIRST in every cycle
2. Check drawdown BEFORE running Council
3. Re-check status before executing any orders

**Atomic Operations:**
- Status changes should be atomic (single DB transaction)
- Liquidation should complete all positions or log failures
- Never leave system in inconsistent state

**Recovery Procedure:**
After EMERGENCY_STOP, manual intervention is required:
1. Review portfolio state
2. Analyze what triggered the stop
3. Reset initial_balance if starting fresh
4. Manually set status back to ACTIVE in DB

### Dependencies & Prerequisites

**Required Completions:**
- Story 3.1: Execution service for selling positions
- Story 3.3: Position manager (close_position function)

**Environment Requirements:**
- Database with SystemConfig table
- Kraken API access for balance queries
- Environment variables for initial balance

### Downstream Dependencies

- **Epic 4:** Dashboard displays system status and provides kill switch UI
- **All trading operations:** Must check `is_trading_enabled()` before execution

---

## Testing Strategy

### Unit Tests

- [ ] `test_drawdown_calculation_accurate` - Verify % calculation
- [ ] `test_drawdown_exceeds_triggers_stop` - Returns True when > 20%
- [ ] `test_trading_disabled_by_default` - When config missing, fail safe
- [ ] `test_pause_disables_trading` - Verify status changes
- [ ] `test_resume_from_pause` - Verify can resume from PAUSED
- [ ] `test_cannot_resume_from_emergency` - Verify blocked
- [ ] `test_liquidate_all_closes_positions` - Verify all positions closed

### Integration Tests

- [ ] Test full drawdown scenario with mock portfolio
- [ ] Test kill switch pauses and resumes trading
- [ ] Test liquidation with multiple open positions
- [ ] Test scheduler respects disabled trading

### Manual Testing Scenarios

1. **Kill Switch Test:**
   - Set `status = 'PAUSED'` in database
   - Run scheduler cycle
   - Verify Council and Execution are skipped
   - Set `status = 'ACTIVE'`
   - Verify normal operation resumes

2. **Drawdown Simulation:**
   - Set `initial_balance = 10000`
   - Mock `get_portfolio_value()` to return $7500 (25% loss)
   - Run `enforce_max_drawdown()`
   - Verify liquidation triggered

3. **Emergency Recovery:**
   - Trigger EMERGENCY_STOP via drawdown
   - Verify cannot resume automatically
   - Manually reset in database
   - Verify trading can resume

### Acceptance Criteria Validation

- [ ] AC1a: When drawdown > 20%, all positions closed
- [ ] AC1b: When drawdown > 20%, trading_enabled set to false
- [ ] AC1c: When drawdown > 20%, notification logged
- [ ] AC2: When status = PAUSED, scheduler skips Council and Execution

---

## Technical Considerations

### Security

- Protect safety endpoints with strong authentication
- Log all status changes with timestamp and actor
- Consider rate limiting on pause/resume endpoints
- Implement audit trail for all safety actions

### Performance

- Drawdown check should complete quickly (< 5 seconds)
- Cache balance data briefly to avoid rate limits
- Liquidation should process positions sequentially to avoid API overload

### Reliability

- Safety checks must NEVER throw unhandled exceptions
- Default to safe state (trading disabled) on any error
- Implement health checks for safety service
- Consider redundant monitoring (external service watches bot)

### Edge Cases

- Exchange API down during drawdown check (fail safe - pause)
- Partial liquidation (some sells fail)
- Race condition between drawdown check and new order
- Clock skew affecting timestamp comparisons
- Initial balance set to zero (prevent division by zero)
