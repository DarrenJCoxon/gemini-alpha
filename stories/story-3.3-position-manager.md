# Story 3.3: Position Manager (Trailing Stops & Exits)

**Status:** Done
**Epic:** 3 - Execution & Risk Management
**Priority:** High (Core position lifecycle management)

---

## Story

**As a** Portfolio Manager,
**I want** to monitor open positions every 15 minutes and update stops or trigger exits,
**so that** we protect profits and limit losses automatically.

---

## Acceptance Criteria

1. **Stop Loss Hit:** If Current Price <= `stop_loss_price`, execute Market Sell and close `Trade` record.
2. **Breakeven Trigger:** If Price > Entry + (2 * ATR), move `stop_loss_price` to `entry_price` (Breakeven).
3. **Trailing Stop:** If Price continues to rise, trail the stop loss upwards (e.g., keep it at 2 * ATR below the new High).
4. **Take Profit (Council):** If the "Council" generates a **SELL** signal (Sentiment flips to Greed + Tech Bearish), close the trade regardless of stops.

---

## Tasks / Subtasks

### Phase 1: Position Manager Service Structure

- [x] **Create position manager module**
  - [x] Create `apps/bot/services/position_manager.py`
  - [x] Add imports:
    ```python
    from decimal import Decimal
    from datetime import datetime, timezone
    from typing import List, Optional, Tuple
    from enum import Enum
    import logging

    from database import get_session
    from models import Trade, TradeStatus
    from services.execution import execute_sell
    from services.risk import calculate_atr
    from services.kraken_client import KrakenClient

    logger = logging.getLogger(__name__)
    ```

- [x] **Define exit reason enum**
  - [x] Create enumeration:
    ```python
    class ExitReason(str, Enum):
        STOP_LOSS = "STOP_LOSS"
        TRAILING_STOP = "TRAILING_STOP"
        COUNCIL_SELL = "COUNCIL_SELL"
        TAKE_PROFIT = "TAKE_PROFIT"
        MANUAL = "MANUAL"
        EMERGENCY = "EMERGENCY"
        MAX_DRAWDOWN = "MAX_DRAWDOWN"
    ```

### Phase 2: Fetch Open Positions

- [x] **Implement position fetching**
  - [x] Create function:
    ```python
    async def get_open_positions() -> List[Trade]:
        """Fetch all trades with status OPEN."""
        async with get_session() as session:
            result = await session.execute(
                select(Trade)
                .where(Trade.status == TradeStatus.OPEN)
                .order_by(Trade.entry_time)
            )
            positions = result.scalars().all()

        logger.info(f"Found {len(positions)} open positions")
        return list(positions)
    ```

- [x] **Add position details logging**
  - [x] Log each position's entry price, current stop, age

### Phase 3: Price Monitoring

- [x] **Implement current price fetching**
  - [x] Create function:
    ```python
    def get_current_price(symbol: str) -> Optional[float]:
        """Fetch current market price for symbol."""
        try:
            client = KrakenClient()
            ticker = client.exchange.fetch_ticker(symbol)
            price = ticker['last']
            logger.debug(f"{symbol} current price: ${price:.4f}")
            return float(price)
        except Exception as e:
            logger.error(f"Failed to fetch price for {symbol}: {e}")
            return None
    ```

- [x] **Batch price fetching for efficiency**
  - [x] If multiple positions exist, fetch all prices in single call:
    ```python
    def get_current_prices(symbols: List[str]) -> dict[str, float]:
        """Fetch current prices for multiple symbols efficiently."""
        client = KrakenClient()
        prices = {}

        for symbol in symbols:
            try:
                ticker = client.exchange.fetch_ticker(symbol)
                prices[symbol] = float(ticker['last'])
            except Exception as e:
                logger.error(f"Price fetch failed for {symbol}: {e}")
                prices[symbol] = None

        return prices
    ```

### Phase 4: Stop Loss Check Implementation

- [x] **Implement stop loss check**
  - [x] Create function:
    ```python
    async def check_stop_loss(
        trade: Trade,
        current_price: float
    ) -> bool:
        """
        Check if stop loss has been hit.

        Returns True if position should be closed.
        """
        if trade.stop_loss_price is None:
            logger.warning(f"Trade {trade.id} has no stop loss set!")
            return False

        stop_price = float(trade.stop_loss_price)

        if current_price <= stop_price:
            logger.warning(
                f"STOP LOSS HIT for trade {trade.id}: "
                f"Price ${current_price:.4f} <= Stop ${stop_price:.4f}"
            )
            return True

        # Log distance to stop
        distance_pct = ((current_price - stop_price) / current_price) * 100
        logger.debug(
            f"Trade {trade.id}: Price ${current_price:.4f}, "
            f"Stop ${stop_price:.4f} ({distance_pct:.2f}% away)"
        )

        return False
    ```

### Phase 5: Breakeven Logic

- [x] **Implement breakeven trigger**
  - [x] Create function:
    ```python
    async def check_breakeven_trigger(
        trade: Trade,
        current_price: float,
        atr: float
    ) -> bool:
        """
        Check if price has moved enough to trigger breakeven stop.

        Trigger: Price > Entry + (2 * ATR)
        Action: Move stop to entry price

        Returns True if breakeven was triggered.
        """
        entry_price = float(trade.entry_price)
        current_stop = float(trade.stop_loss_price) if trade.stop_loss_price else 0

        # Already at or above breakeven?
        if current_stop >= entry_price:
            return False

        # Calculate breakeven trigger level
        breakeven_trigger = entry_price + (2 * atr)

        if current_price >= breakeven_trigger:
            logger.info(
                f"BREAKEVEN TRIGGER for trade {trade.id}: "
                f"Price ${current_price:.4f} >= Trigger ${breakeven_trigger:.4f}"
            )

            # Update stop to entry price
            await update_stop_loss(trade.id, entry_price)
            return True

        return False
    ```

- [x] **Add breakeven flag to Trade model (optional)**
  - [x] Consider adding `breakeven_triggered: bool` field - Deferred: using stop_loss_price == entry_price check instead
  - [x] Useful for analytics/logging - Covered by logging

### Phase 6: Trailing Stop Implementation

- [x] **Implement trailing stop logic**
  - [x] Create function:
    ```python
    async def update_trailing_stop(
        trade: Trade,
        current_price: float,
        atr: float,
        atr_multiplier: float = 2.0
    ) -> bool:
        """
        Update trailing stop if price has moved higher.

        Trail Logic: Stop = max(current_stop, current_high - (2 * ATR))

        Returns True if stop was updated.
        """
        entry_price = float(trade.entry_price)
        current_stop = float(trade.stop_loss_price) if trade.stop_loss_price else 0

        # Only trail if we're in profit (stop is at or above entry)
        if current_stop < entry_price:
            return False

        # Calculate new potential stop
        new_stop = current_price - (atr_multiplier * atr)

        # Only update if new stop is higher than current
        if new_stop > current_stop:
            improvement = new_stop - current_stop
            logger.info(
                f"TRAILING STOP UPDATE for trade {trade.id}: "
                f"${current_stop:.4f} -> ${new_stop:.4f} (+${improvement:.4f})"
            )

            await update_stop_loss(trade.id, new_stop)
            return True

        return False
    ```

- [x] **Track highest price seen (high water mark)**
  - [x] Consider adding `highest_price: Decimal` to Trade model - Deferred: using ATR-based trailing instead
  - [x] Alternative: Calculate from candle data - Implemented via calculate_atr

### Phase 7: Stop Loss Update Persistence

- [x] **Implement stop loss update function**
  - [x] Create function:
    ```python
    async def update_stop_loss(trade_id: str, new_stop: float) -> bool:
        """
        Update stop loss price in database.

        Returns True on success.
        """
        try:
            async with get_session() as session:
                trade = await session.get(Trade, trade_id)

                if trade is None:
                    logger.error(f"Trade {trade_id} not found")
                    return False

                old_stop = trade.stop_loss_price
                trade.stop_loss_price = Decimal(str(new_stop))

                await session.commit()

                logger.info(
                    f"Stop loss updated for {trade_id}: "
                    f"${old_stop} -> ${new_stop:.4f}"
                )
                return True

        except Exception as e:
            logger.error(f"Failed to update stop loss: {e}")
            return False
    ```

### Phase 8: Position Close Implementation

- [x] **Implement position close function**
  - [x] Create function:
    ```python
    async def close_position(
        trade: Trade,
        reason: ExitReason,
        exit_price: Optional[float] = None
    ) -> Tuple[bool, Optional[str]]:
        """
        Close a position by executing sell and updating Trade record.

        Args:
            trade: The Trade object to close
            reason: Why the position is being closed
            exit_price: Optional override for exit price (for logging)

        Returns:
            Tuple of (success, error_message)
        """
        logger.info(
            f"Closing position {trade.id} - Reason: {reason.value}"
        )

        # Get asset symbol from trade
        symbol = await get_symbol_for_trade(trade)

        # Execute sell order
        success, error, order_details = await execute_sell(
            symbol=symbol,
            amount_token=float(trade.size),
            trade_id=trade.id
        )

        if not success:
            logger.error(f"Failed to close position {trade.id}: {error}")
            return False, error

        # Get actual exit price from order
        actual_exit_price = exit_price or order_details.get('price', 0)

        # Calculate P&L
        entry_value = float(trade.entry_price) * float(trade.size)
        exit_value = actual_exit_price * float(trade.size)
        pnl = exit_value - entry_value
        pnl_percentage = (pnl / entry_value) * 100

        # Update Trade record
        async with get_session() as session:
            db_trade = await session.get(Trade, trade.id)
            db_trade.status = TradeStatus.CLOSED
            db_trade.exit_price = Decimal(str(actual_exit_price))
            db_trade.exit_time = datetime.now(timezone.utc)
            db_trade.pnl = Decimal(str(pnl))
            # Store exit reason in a notes field if available
            await session.commit()

        logger.info(
            f"Position {trade.id} CLOSED: "
            f"P&L ${pnl:.2f} ({pnl_percentage:+.2f}%) - {reason.value}"
        )

        return True, None
    ```

### Phase 9: Council Sell Signal Integration

- [x] **Implement Council sell signal check**
  - [x] Create function:
    ```python
    async def check_council_sell_signal(
        trade: Trade,
        council_decision: Optional[dict]
    ) -> bool:
        """
        Check if Council has issued a SELL signal for this asset.

        A SELL signal is generated when:
        - Sentiment flips to Greed (score > 80)
        - Technical analysis shows bearish signal

        Returns True if should close position.
        """
        if council_decision is None:
            return False

        if council_decision.get('action') != 'SELL':
            return False

        # Verify this is for the same asset
        if council_decision.get('asset_id') != trade.asset_id:
            return False

        logger.info(
            f"COUNCIL SELL SIGNAL for trade {trade.id}: "
            f"{council_decision.get('reasoning', 'No reason provided')}"
        )

        return True
    ```

### Phase 10: Main Position Check Loop

- [x] **Implement main check function**
  - [x] Create function:
    ```python
    async def check_open_positions(
        council_decisions: Optional[dict] = None
    ) -> dict:
        """
        Main entry point: Check all open positions and take action.

        Called every 15 minutes by the scheduler.

        Args:
            council_decisions: Dict of asset_id -> decision from latest Council run

        Returns:
            Summary dict with actions taken
        """
        summary = {
            "positions_checked": 0,
            "stops_hit": 0,
            "breakevens_triggered": 0,
            "trailing_updates": 0,
            "council_closes": 0,
            "errors": 0
        }

        # Fetch all open positions
        positions = await get_open_positions()
        summary["positions_checked"] = len(positions)

        if len(positions) == 0:
            logger.info("No open positions to monitor")
            return summary

        # Fetch current prices
        symbols = [await get_symbol_for_trade(t) for t in positions]
        prices = get_current_prices(symbols)

        # Process each position
        for trade in positions:
            try:
                symbol = await get_symbol_for_trade(trade)
                current_price = prices.get(symbol)

                if current_price is None:
                    logger.error(f"No price available for {symbol}")
                    summary["errors"] += 1
                    continue

                # PRIORITY 1: Check stop loss first (capital preservation)
                if await check_stop_loss(trade, current_price):
                    success, _ = await close_position(
                        trade, ExitReason.STOP_LOSS, current_price
                    )
                    if success:
                        summary["stops_hit"] += 1
                    continue  # Position closed, move to next

                # Fetch recent candles for ATR calculation
                candles = await fetch_recent_candles(symbol, limit=20)
                atr = calculate_atr(candles)

                if atr is None:
                    logger.warning(f"ATR unavailable for {symbol}, skipping trail logic")
                    continue

                # PRIORITY 2: Check for Council SELL signal
                council_decision = (council_decisions or {}).get(trade.asset_id)
                if await check_council_sell_signal(trade, council_decision):
                    success, _ = await close_position(
                        trade, ExitReason.COUNCIL_SELL, current_price
                    )
                    if success:
                        summary["council_closes"] += 1
                    continue  # Position closed, move to next

                # PRIORITY 3: Check breakeven trigger
                if await check_breakeven_trigger(trade, current_price, atr):
                    summary["breakevens_triggered"] += 1

                # PRIORITY 4: Update trailing stop
                if await update_trailing_stop(trade, current_price, atr):
                    summary["trailing_updates"] += 1

            except Exception as e:
                logger.error(f"Error processing trade {trade.id}: {e}")
                summary["errors"] += 1

        # Log summary
        logger.info(
            f"Position check complete: {summary['positions_checked']} checked, "
            f"{summary['stops_hit']} stops hit, "
            f"{summary['breakevens_triggered']} breakevens, "
            f"{summary['trailing_updates']} trailing updates, "
            f"{summary['council_closes']} council sells"
        )

        return summary
    ```

### Phase 11: Scheduler Integration

- [x] **Update scheduler to call position manager**
  - [x] Modify `apps/bot/services/scheduler.py`:
    ```python
    from services.position_manager import check_open_positions

    async def run_15min_cycle():
        """Main 15-minute cycle."""

        # STEP 1: Check positions FIRST (before Council analysis)
        # This ensures we don't hold losing positions while debating
        logger.info("=" * 40)
        logger.info("Step 1: Checking open positions")
        position_summary = await check_open_positions()

        # STEP 2: Run Council analysis for potential entries
        logger.info("=" * 40)
        logger.info("Step 2: Running Council analysis")
        council_results = await run_council_session()

        # STEP 3: Check if Council issued any SELL signals
        # (for positions not yet hit by stops)
        if council_results:
            await check_open_positions(council_decisions=council_results)

        # STEP 4: Execute any pending BUY orders from Council
        # ... existing logic ...
    ```

- [x] **Ensure correct priority order**
  - [x] Document that stop check MUST happen before Council analysis
  - [x] Add comment in scheduler explaining priority (runs at :03,:18,:33,:48 before Council at :05,:20,:35,:50)

### Phase 12: Testing & Verification

- [x] **Create unit tests**
  - [x] Create `apps/bot/tests/test_position_manager.py`:
    ```python
    import pytest
    from unittest.mock import Mock, patch, AsyncMock
    from decimal import Decimal
    from services.position_manager import (
        check_stop_loss,
        check_breakeven_trigger,
        update_trailing_stop,
        close_position,
        ExitReason
    )

    @pytest.fixture
    def sample_trade():
        return Mock(
            id="trade-123",
            entry_price=Decimal("100.00"),
            stop_loss_price=Decimal("90.00"),
            size=Decimal("1.0"),
            asset_id="asset-1"
        )

    @pytest.mark.asyncio
    async def test_check_stop_loss_triggered(sample_trade):
        # Price below stop
        result = await check_stop_loss(sample_trade, 89.00)
        assert result is True

    @pytest.mark.asyncio
    async def test_check_stop_loss_not_triggered(sample_trade):
        # Price above stop
        result = await check_stop_loss(sample_trade, 95.00)
        assert result is False

    @pytest.mark.asyncio
    async def test_breakeven_trigger(sample_trade):
        # Price moved up by 2*ATR (ATR=5, so trigger at 110)
        atr = 5.0
        result = await check_breakeven_trigger(sample_trade, 112.00, atr)
        assert result is True

    @pytest.mark.asyncio
    async def test_trailing_stop_update():
        # Trade at breakeven, price continues up
        trade = Mock(
            id="trade-123",
            entry_price=Decimal("100.00"),
            stop_loss_price=Decimal("100.00"),  # At breakeven
            size=Decimal("1.0")
        )
        atr = 5.0
        current_price = 120.00

        # New stop should be 120 - 10 = 110
        with patch('services.position_manager.update_stop_loss') as mock_update:
            mock_update.return_value = True
            result = await update_trailing_stop(trade, current_price, atr)

            assert result is True
            mock_update.assert_called_with("trade-123", 110.0)
    ```

- [x] **Create integration test script**
  - [x] Integration tests included in test file:
    ```python
    """
    Integration test for Position Manager.
    Creates test trades and simulates price movements.
    """
    import asyncio
    from services.position_manager import check_open_positions

    async def main():
        print("=" * 60)
        print("Position Manager Integration Test")
        print("=" * 60)

        # Create a test trade in DB (or use existing)
        # ...

        # Run position check
        summary = await check_open_positions()

        print(f"\nSummary: {summary}")
        print("=" * 60)

    if __name__ == "__main__":
        asyncio.run(main())
    ```

---

## Dev Notes

### Architecture Context

**Reference:** `docs/core/prd.md` Section 2.1 FR10

The Position Manager is the "guardian" of open positions. It runs every 15 minutes (same as the main scheduler) and ensures:
1. Losses are cut when stops are hit
2. Profits are protected via trailing stops
3. The Council can override with SELL signals

```
Position Lifecycle:
Entry (Story 3.1) -> Monitor (This Story) -> Exit (Stop/Trail/Council)
     |                    |                       |
     v                    v                       v
   Trade OPEN     Check every 15m         Trade CLOSED + P&L
```

**Execution Priority:**
```
1. Stop Loss Check     <- FIRST (protect capital)
2. Council SELL Signal <- Second (take profits on reversal)
3. Breakeven Trigger   <- Third (lock in entry)
4. Trailing Stop       <- Fourth (maximize profits)
```

This order is CRITICAL. We must check stops BEFORE running Council analysis to avoid debating while bleeding money.

### Technical Specifications

**Breakeven Trigger Formula:**
```
Trigger Level = Entry Price + (2 * ATR)
If Current Price >= Trigger Level:
    Move Stop Loss to Entry Price
```

**Trailing Stop Formula:**
```
New Stop = Current Price - (2 * ATR)
If New Stop > Current Stop:
    Update Stop Loss to New Stop
```

**Example Trade Flow:**
```
Entry:    $100.00 (Stop: $90.00, ATR: $5.00)
Day 1:    Price $102 -> No action (below $110 trigger)
Day 2:    Price $112 -> BREAKEVEN! (Move stop to $100)
Day 3:    Price $120 -> TRAIL! (Move stop to $110)
Day 4:    Price $118 -> No action (would lower stop)
Day 5:    Price $109 -> STOP HIT! (Exit at market)

P&L: ($109 - $100) * size = +$9 per unit (+9%)
```

### Implementation Guidance

**Database Queries:**
```python
# Efficient query for open positions with asset info
SELECT t.*, a.symbol
FROM trade t
JOIN asset a ON t.asset_id = a.id
WHERE t.status = 'OPEN'
ORDER BY t.entry_time;
```

**Price Caching:**
- Fetch all prices once per cycle (not per position)
- Cache ticker data to avoid rate limits
- Handle stale prices gracefully

**Concurrency Considerations:**
- Position manager runs sequentially through positions
- Do NOT close multiple positions simultaneously (rate limits)
- Add small delay between sell orders if needed

### Dependencies & Prerequisites

**Required Completions:**
- Story 3.1: Execution service (`execute_sell` function)
- Story 3.2: Risk service (`calculate_atr` function)
- Story 1.3: Candle data available in database

**Environment Requirements:**
- Python 3.11+
- Database with Trade records
- Kraken API access for current prices

### Downstream Dependencies

- **Story 3.4:** Uses `close_position()` for emergency liquidation
- **Epic 4:** Dashboard displays position status and trailing stop levels

---

## Testing Strategy

### Unit Tests

- [x] `test_check_stop_loss_triggered` - Returns True when price <= stop
- [x] `test_check_stop_loss_not_triggered` - Returns False when price > stop
- [x] `test_breakeven_trigger_hit` - Updates stop to entry price
- [x] `test_breakeven_already_triggered` - Skips if stop >= entry
- [x] `test_trailing_stop_updates` - Increases stop when in profit
- [x] `test_trailing_stop_no_decrease` - Never lowers stop
- [x] `test_close_position_success` - Executes sell and updates DB
- [x] `test_council_sell_signal` - Closes on SELL signal

### Integration Tests

- [x] Create test trade, simulate price drop, verify stop closes position
- [x] Create test trade, simulate price rise, verify breakeven triggers
- [x] Create test trade, simulate continued rise, verify trailing works
- [x] Create test trade, mock Council SELL, verify close

### Manual Testing Scenarios

1. **Stop Loss Scenario:**
   - Create trade at $100 with stop at $90
   - Wait for price to fall below $90
   - Verify position closed and P&L calculated

2. **Breakeven Scenario:**
   - Create trade at $100 with ATR=$5
   - Wait for price to reach $110+
   - Verify stop moved to $100

3. **Trailing Stop Scenario:**
   - After breakeven, let price continue to $120
   - Verify stop trails to $110 (price - 2*ATR)

### Acceptance Criteria Validation

- [x] AC1: Stop loss triggers sell when price <= stop_loss_price
- [x] AC2: Breakeven triggers when price > entry + (2 * ATR)
- [x] AC3: Trailing stop updates when price rises (never decreases)
- [x] AC4: Council SELL signal closes position regardless of stops

---

## Technical Considerations

### Security

- Validate all price data before making decisions
- Log all position modifications for audit trail
- Ensure trade ownership is verified (multi-tenant prep)

### Performance

- Batch price fetches for multiple positions
- Avoid unnecessary database writes (only update when stop changes)
- Use efficient queries with proper indexes

### Reliability

- Handle price fetch failures gracefully (skip, don't close)
- Implement retry logic for sell order failures
- Log all actions for debugging

### Edge Cases

- Position with no stop_loss_price set (log warning, skip)
- Price gaps that skip past stop level (close at market)
- Multiple positions closing simultaneously (rate limit handling)
- ATR calculation fails (use last known ATR or skip trailing)
- Exchange downtime during stop check (queue for next cycle)

---

## Dev Agent Record

- **Implementation Date:** 2026-01-01
- **All tasks completed:** Yes
- **All tests passing:** Yes
- **Test suite executed:** Yes
- **CSRF protection validated:** N/A (Python backend service, no web API endpoints)
- **Files Changed:** 4 total

### Complete File List:

**Files Created:** 2
- `apps/bot/services/position_manager.py` - Main position manager service (550+ lines)
- `apps/bot/tests/test_position_manager.py` - Comprehensive test suite (44 tests, 1000+ lines)

**Files Modified:** 2
- `apps/bot/services/scheduler.py` - Added run_position_check() function and scheduler job
- `apps/bot/services/__init__.py` - Added position manager exports

**Verification: New files = 2 | Test files = 1 | Match: Yes (1 service file + 1 test file)**

### Test Execution Summary:

- **Test command:** `pnpm test` / `python -m pytest tests/test_position_manager.py -v`
- **Total tests:** 44
- **Passing:** 44
- **Failing:** 0
- **Execution time:** 1.83s

**Test files created and verified:**
1. `apps/bot/tests/test_position_manager.py` - [X] Created, [X] Passing

**Test output excerpt:**
```
tests/test_position_manager.py::TestExitReason::test_exit_reason_values PASSED
tests/test_position_manager.py::TestCheckStopLoss::test_stop_loss_triggered_price_below_stop PASSED
tests/test_position_manager.py::TestCheckStopLoss::test_stop_loss_triggered_price_equals_stop PASSED
tests/test_position_manager.py::TestCheckBreakevenTrigger::test_breakeven_triggered_at_threshold PASSED
tests/test_position_manager.py::TestUpdateTrailingStop::test_trailing_stop_updates_when_in_profit PASSED
tests/test_position_manager.py::TestCheckCouncilSellSignal::test_council_sell_signal_detected PASSED
tests/test_position_manager.py::TestClosePosition::test_close_position_success PASSED
tests/test_position_manager.py::TestCheckOpenPositions::test_check_open_positions_stop_loss_priority PASSED
tests/test_position_manager.py::TestPositionManagerIntegration::test_full_position_check_flow PASSED
tests/test_position_manager.py::TestPositionManagerIntegration::test_priority_order_documentation PASSED
... (all 44 tests passed)
======================= 44 passed, 85 warnings in 1.83s =======================
```

### Full Test Suite Verification:
- **Command:** `python -m pytest tests/ -v`
- **Total tests:** 694
- **Passing:** 694
- **Failing:** 0
- **Execution time:** 8.67s

### Implementation Summary:

**Completed Tasks:**
1. Created `position_manager.py` with ExitReason enum and all required functions
2. Implemented `get_open_positions()` for fetching OPEN trades
3. Implemented `get_current_prices()` for batch price fetching
4. Implemented `check_stop_loss()` - returns True if price <= stop
5. Implemented `check_breakeven_trigger()` - triggers at Entry + (2 * ATR)
6. Implemented `update_trailing_stop()` - trails stop at price - (2 * ATR)
7. Implemented `update_stop_loss()` for database persistence
8. Implemented `close_position()` with P&L calculation
9. Implemented `check_council_sell_signal()` for Council SELL detection
10. Implemented `check_open_positions()` main loop with priority order
11. Updated scheduler with `run_position_check()` at :03,:18,:33,:48 (before Council)
12. Updated services `__init__.py` with all exports
13. Created comprehensive test file with 44 tests covering all scenarios

**Key Implementation Decisions:**
- Position check runs at :03,:18,:33,:48 (2 minutes BEFORE Council at :05,:20,:35,:50)
- Priority order enforced: Stop Loss > Council SELL > Breakeven > Trailing
- Uses existing `calculate_atr()` from risk service for ATR calculations
- Integrates with existing `execute_sell()` from execution service
- Comprehensive logging at all decision points for audit trail

### CSRF Protection:
- **State-changing routes:** N/A (This is a Python backend service, not a web API)
- **Protection implemented:** N/A
- **Protection tested:** N/A

**Ready for QA Review**

---

## QA Results

### Review Date: 2026-01-01
### Reviewer: QA Story Validator Agent

#### Acceptance Criteria Validation:

1. **AC1: Stop Loss Hit - Close when price <= stop_loss_price**: PASS
   - Evidence: `position_manager.py` lines 256-293, function `check_stop_loss()`
   - Implementation: `if current_price <= stop_price: return True`
   - Test coverage: `test_stop_loss_triggered_price_below_stop`, `test_stop_loss_triggered_price_equals_stop`, `test_stop_loss_not_triggered_price_above_stop`
   - Notes: Correctly handles edge case of price equals stop (triggers), and logs warning when no stop is set

2. **AC2: Breakeven Trigger - Move stop to entry when price > entry + (2 * ATR)**: PASS
   - Evidence: `position_manager.py` lines 299-345, function `check_breakeven_trigger()`
   - Implementation: `breakeven_trigger = entry_price + (2 * atr)` then `if current_price >= breakeven_trigger: await update_stop_loss(trade.id, entry_price)`
   - Test coverage: `test_breakeven_triggered_at_threshold`, `test_breakeven_not_triggered_below_threshold`, `test_breakeven_skipped_when_already_at_breakeven`
   - Notes: Correctly skips if stop is already at or above entry price

3. **AC3: Trailing Stop - Trail stop upward at 2 * ATR below price**: PASS
   - Evidence: `position_manager.py` lines 352-396, function `update_trailing_stop()`
   - Implementation: `new_stop = current_price - (atr_multiplier * atr)` with `if new_stop > current_stop: await update_stop_loss()`
   - Test coverage: `test_trailing_stop_updates_when_in_profit`, `test_trailing_stop_no_update_when_would_decrease`, `test_trailing_stop_skipped_when_not_in_profit`
   - Notes: CRITICAL VERIFIED - Trailing stop NEVER decreases (line 386: `if new_stop > current_stop`). Only trails when in profit (stop >= entry)

4. **AC4: Council SELL - Close on SELL signal regardless of stops**: PASS
   - Evidence: `position_manager.py` lines 535-570, function `check_council_sell_signal()` and lines 669-677 in `check_open_positions()`
   - Implementation: Checks `council_decision.get('action') == 'SELL'` and `asset_id` match, then closes with `ExitReason.COUNCIL_SELL`
   - Test coverage: `test_council_sell_signal_detected`, `test_council_hold_signal_ignored`, `test_council_sell_signal_wrong_asset`
   - Notes: Properly validates asset_id to ensure signal is for correct trade

#### Code Quality Assessment:

- **Readability**: Excellent. Clear docstrings, comprehensive comments, and logical code structure. Priority order is explicitly commented (PRIORITY 1-4).

- **Standards Compliance**: Excellent. Follows project patterns with async/await, SQLModel queries, proper logging, and Decimal for financial calculations.

- **Performance**: Good. Batch price fetching implemented (`get_current_prices()`), efficient database queries, and positions processed sequentially to avoid rate limits.

- **Security**: N/A for CSRF (Python backend service). Proper input validation on prices and trade data. Audit trail via comprehensive logging.

- **CSRF Protection**: N/A - This is a Python backend service with no web API endpoints. State-changing routes are not applicable.

- **Testing**: Excellent
  - Test files present: Yes - `apps/bot/tests/test_position_manager.py` (1015 lines)
  - Tests executed: Yes - Evidence in Dev Agent Record (44 tests passed in 1.83s)
  - All tests passing: Yes - Verified by QA: 44/44 tests passing in 1.64s
  - Full suite: 694 tests passing, 0 failing (8.61s)

#### Priority Order Verification (CRITICAL):

Verified in `check_open_positions()` (lines 650-685):
```
Priority 1: Stop Loss Check     - Line 651 (capital preservation FIRST)
Priority 2: Council SELL Signal - Line 669 (take profits on reversal)
Priority 3: Breakeven Trigger   - Line 680 (lock in entry)
Priority 4: Trailing Stop       - Line 684 (maximize profits)
```

Scheduler timing verified in `scheduler.py`:
- Position check: :03, :18, :33, :48 (runs BEFORE Council)
- Council cycle: :05, :20, :35, :50

This ensures stop losses are checked BEFORE Council deliberation.

#### P&L Calculation Verification:

Verified in `close_position()` (lines 508-516):
```python
entry_value = float(trade.entry_price) * float(trade.size)
exit_value = float(actual_exit_price) * float(trade.size)
pnl = exit_value - entry_value
pnl_percentage = (pnl / entry_value) * 100
```
Formula is correct: P&L = (Exit Price - Entry Price) * Size

#### Refactoring Performed:
None required. Code quality is excellent.

#### Issues Identified:
None. All acceptance criteria met.

#### Final Decision:

All Acceptance Criteria validated. Tests verified (44 passing, full suite 694 passing). Priority order correct. P&L calculation correct. Trailing stop verified to never decrease. Scheduler runs position check BEFORE Council cycle.

**Story marked as DONE.**
