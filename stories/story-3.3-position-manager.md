# Story 3.3: Position Manager (Trailing Stops & Exits)

**Status:** Draft
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

- [ ] **Create position manager module**
  - [ ] Create `apps/bot/services/position_manager.py`
  - [ ] Add imports:
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

- [ ] **Define exit reason enum**
  - [ ] Create enumeration:
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

- [ ] **Implement position fetching**
  - [ ] Create function:
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

- [ ] **Add position details logging**
  - [ ] Log each position's entry price, current stop, age

### Phase 3: Price Monitoring

- [ ] **Implement current price fetching**
  - [ ] Create function:
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

- [ ] **Batch price fetching for efficiency**
  - [ ] If multiple positions exist, fetch all prices in single call:
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

- [ ] **Implement stop loss check**
  - [ ] Create function:
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

- [ ] **Implement breakeven trigger**
  - [ ] Create function:
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

- [ ] **Add breakeven flag to Trade model (optional)**
  - [ ] Consider adding `breakeven_triggered: bool` field
  - [ ] Useful for analytics/logging

### Phase 6: Trailing Stop Implementation

- [ ] **Implement trailing stop logic**
  - [ ] Create function:
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

- [ ] **Track highest price seen (high water mark)**
  - [ ] Consider adding `highest_price: Decimal` to Trade model
  - [ ] Alternative: Calculate from candle data

### Phase 7: Stop Loss Update Persistence

- [ ] **Implement stop loss update function**
  - [ ] Create function:
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

- [ ] **Implement position close function**
  - [ ] Create function:
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

- [ ] **Implement Council sell signal check**
  - [ ] Create function:
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

- [ ] **Implement main check function**
  - [ ] Create function:
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

- [ ] **Update scheduler to call position manager**
  - [ ] Modify `apps/bot/main.py` or scheduler module:
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

- [ ] **Ensure correct priority order**
  - [ ] Document that stop check MUST happen before Council analysis
  - [ ] Add comment in scheduler explaining priority

### Phase 12: Testing & Verification

- [ ] **Create unit tests**
  - [ ] Create `apps/bot/tests/test_position_manager.py`:
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

- [ ] **Create integration test script**
  - [ ] Create `apps/bot/scripts/test_position_manager.py`:
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

- [ ] `test_check_stop_loss_triggered` - Returns True when price <= stop
- [ ] `test_check_stop_loss_not_triggered` - Returns False when price > stop
- [ ] `test_breakeven_trigger_hit` - Updates stop to entry price
- [ ] `test_breakeven_already_triggered` - Skips if stop >= entry
- [ ] `test_trailing_stop_updates` - Increases stop when in profit
- [ ] `test_trailing_stop_no_decrease` - Never lowers stop
- [ ] `test_close_position_success` - Executes sell and updates DB
- [ ] `test_council_sell_signal` - Closes on SELL signal

### Integration Tests

- [ ] Create test trade, simulate price drop, verify stop closes position
- [ ] Create test trade, simulate price rise, verify breakeven triggers
- [ ] Create test trade, simulate continued rise, verify trailing works
- [ ] Create test trade, mock Council SELL, verify close

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

- [ ] AC1: Stop loss triggers sell when price <= stop_loss_price
- [ ] AC2: Breakeven triggers when price > entry + (2 * ATR)
- [ ] AC3: Trailing stop updates when price rises (never decreases)
- [ ] AC4: Council SELL signal closes position regardless of stops

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
