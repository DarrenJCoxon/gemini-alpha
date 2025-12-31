# Story 3.2: Dynamic Risk Engine (ATR Stop Loss)

**Status:** Draft
**Epic:** 3 - Execution & Risk Management
**Priority:** High (Required for safe trade execution)

---

## Story

**As a** Risk Manager,
**I want** to calculate the Stop Loss price dynamically using the Average True Range (ATR),
**so that** our risk adapts to the current market volatility rather than using a fixed percentage.

---

## Acceptance Criteria

1. System calculates ATR (14-period) for the target asset at the moment of entry.
2. Stop Loss is calculated as `Entry Price - (2 * ATR)`.
3. The calculated `stop_loss_price` is saved to the `Trade` record in the database.
4. (Optional) A "Stop Loss" order is placed on Kraken immediately after entry (OSSO - One Sends Other), OR the bot monitors this internally (Soft Stop). *Decision: Internal Soft Stop for V1 to avoid complex order management.*

---

## Tasks / Subtasks

### Phase 1: Dependency Setup

- [ ] **Install/verify pandas-ta library**
  - [ ] Add to `apps/bot/requirements.txt`:
    ```
    pandas-ta>=0.3.14b0
    pandas>=2.0.0
    numpy>=1.24.0
    ```
  - [ ] Install: `pip install -r requirements.txt`
  - [ ] Verify: `python -c "import pandas_ta; print(pandas_ta.version)"`

### Phase 2: ATR Calculation Service

- [ ] **Create risk service module**
  - [ ] Create `apps/bot/services/risk.py`
  - [ ] Add imports:
    ```python
    from decimal import Decimal
    from typing import List, Optional, Tuple
    import pandas as pd
    import pandas_ta as ta
    import logging
    from datetime import datetime, timezone

    logger = logging.getLogger(__name__)
    ```

- [ ] **Implement ATR calculation function**
  - [ ] Create function:
    ```python
    def calculate_atr(
        candles: List[dict],
        period: int = 14
    ) -> Optional[float]:
        """
        Calculate Average True Range (ATR) from OHLCV candle data.

        Args:
            candles: List of candle dicts with 'high', 'low', 'close' keys
            period: ATR period (default: 14)

        Returns:
            Current ATR value or None if insufficient data
        """
        if len(candles) < period + 1:
            logger.warning(
                f"Insufficient candles for ATR calculation. "
                f"Need {period + 1}, got {len(candles)}"
            )
            return None

        # Convert to DataFrame
        df = pd.DataFrame(candles)

        # Ensure required columns exist
        required_cols = ['high', 'low', 'close']
        if not all(col in df.columns for col in required_cols):
            logger.error(f"Missing required columns. Have: {df.columns.tolist()}")
            return None

        # Calculate ATR using pandas-ta
        atr_series = ta.atr(
            high=df['high'],
            low=df['low'],
            close=df['close'],
            length=period
        )

        if atr_series is None or atr_series.empty:
            logger.error("ATR calculation returned empty result")
            return None

        # Return the most recent ATR value
        current_atr = atr_series.iloc[-1]

        if pd.isna(current_atr):
            logger.warning("ATR is NaN - likely insufficient data")
            return None

        logger.info(f"Calculated ATR({period}): {current_atr:.6f}")
        return float(current_atr)
    ```

- [ ] **Add ATR logging for audit trail**
  - [ ] Log ATR calculation inputs (candle count, period)
  - [ ] Log resulting ATR value
  - [ ] Store historical ATR values for analysis (optional)

### Phase 3: Stop Loss Calculation

- [ ] **Implement stop loss calculator**
  - [ ] Create function:
    ```python
    def calculate_stop_loss(
        entry_price: float,
        candles: List[dict],
        atr_multiplier: float = 2.0,
        atr_period: int = 14
    ) -> Tuple[Optional[float], Optional[float]]:
        """
        Calculate dynamic stop loss based on ATR.

        Formula: Stop Loss = Entry Price - (ATR_Multiplier * ATR)

        Args:
            entry_price: The trade entry price
            candles: Recent OHLCV candle data
            atr_multiplier: Multiplier for ATR (default: 2.0)
            atr_period: ATR calculation period (default: 14)

        Returns:
            Tuple of (stop_loss_price, atr_value) or (None, None) on error
        """
        atr = calculate_atr(candles, period=atr_period)

        if atr is None:
            logger.error("Cannot calculate stop loss - ATR calculation failed")
            return None, None

        # Calculate stop loss
        stop_distance = atr_multiplier * atr
        stop_loss_price = entry_price - stop_distance

        # Ensure stop loss is positive (sanity check)
        if stop_loss_price <= 0:
            logger.warning(
                f"Calculated stop loss is negative or zero: {stop_loss_price}. "
                f"Entry: {entry_price}, ATR: {atr}, Multiplier: {atr_multiplier}"
            )
            # Fall back to percentage-based stop (emergency)
            stop_loss_price = entry_price * 0.85  # 15% max loss
            logger.warning(f"Using fallback 15% stop loss: {stop_loss_price}")

        # Calculate percentage from entry for logging
        stop_percentage = ((entry_price - stop_loss_price) / entry_price) * 100

        logger.info(
            f"Stop Loss calculated: ${stop_loss_price:.4f} "
            f"({stop_percentage:.2f}% below entry of ${entry_price:.4f})"
        )

        return stop_loss_price, atr
    ```

- [ ] **Add configuration for ATR parameters**
  - [ ] Update `apps/bot/config.py`:
    ```python
    class RiskSettings(BaseSettings):
        atr_period: int = 14
        atr_multiplier: float = 2.0
        max_stop_loss_percentage: float = 0.20  # 20% max
        min_stop_loss_percentage: float = 0.02  # 2% min

        class Config:
            env_prefix = "RISK_"

    risk_settings = RiskSettings()
    ```
  - [ ] Add to `.env.example`:
    ```
    RISK_ATR_PERIOD=14
    RISK_ATR_MULTIPLIER=2.0
    RISK_MAX_STOP_LOSS_PERCENTAGE=0.20
    RISK_MIN_STOP_LOSS_PERCENTAGE=0.02
    ```

### Phase 4: Integration with Execution Flow

- [ ] **Modify execute_buy to include stop loss calculation**
  - [ ] Update `apps/bot/services/execution.py`:
    ```python
    from services.risk import calculate_stop_loss

    async def execute_buy(
        symbol: str,
        amount_usd: float,
        candles: List[dict]  # Add this parameter
    ) -> Tuple[bool, Optional[str], Optional[Trade]]:
        """
        Execute a market buy order with dynamic stop loss.
        """
        # ... existing duplicate check ...

        # Calculate stop loss BEFORE execution
        # Use estimated entry price (current market price)
        ticker = client.exchange.fetch_ticker(symbol)
        estimated_entry = ticker['last']

        stop_loss_price, atr_value = calculate_stop_loss(
            entry_price=estimated_entry,
            candles=candles
        )

        if stop_loss_price is None:
            return False, "Failed to calculate stop loss - insufficient data", None

        logger.info(
            f"Executing BUY with dynamic stop loss: "
            f"Entry ~${estimated_entry:.4f}, Stop ${stop_loss_price:.4f}"
        )

        # ... existing order execution ...

        # Create Trade record with stop loss
        trade = Trade(
            # ... existing fields ...
            stop_loss_price=Decimal(str(stop_loss_price)),
            # Store ATR for position manager reference
        )
    ```

- [ ] **Fetch candles before execution**
  - [ ] In scheduler or MasterNode integration:
    ```python
    # Ensure we have candles available for ATR
    candles = await fetch_recent_candles(
        symbol=state["asset_symbol"],
        limit=50  # Need at least 15 for ATR(14)
    )
    state["candles_for_risk"] = candles
    ```

### Phase 5: Database Updates

- [ ] **Add ATR tracking to Trade model (optional)**
  - [ ] Consider adding field to track the ATR at entry:
    ```python
    class Trade(SQLModel, table=True):
        # ... existing fields ...
        entry_atr: Optional[Decimal] = None  # ATR at time of entry
    ```
  - [ ] This allows position manager to use same ATR for trailing

- [ ] **Verify stop_loss_price is persisted**
  - [ ] Query database after test trade
  - [ ] Confirm stop_loss_price is populated
  - [ ] Verify value matches expected calculation

### Phase 6: Position Sizing Integration (Optional Enhancement)

- [ ] **Calculate position size based on risk**
  - [ ] Create function:
    ```python
    def calculate_position_size(
        account_balance: float,
        entry_price: float,
        stop_loss_price: float,
        risk_percentage: float = 0.02  # Risk 2% of account per trade
    ) -> float:
        """
        Calculate position size based on risk per trade.

        Formula: Position Size = (Account * Risk%) / (Entry - Stop)
        """
        risk_amount = account_balance * risk_percentage
        risk_per_unit = entry_price - stop_loss_price

        if risk_per_unit <= 0:
            raise ValueError("Stop loss must be below entry price")

        position_size = risk_amount / risk_per_unit

        logger.info(
            f"Position size: {position_size:.4f} units "
            f"(risking ${risk_amount:.2f} of ${account_balance:.2f} account)"
        )

        return position_size
    ```
  - [ ] Document that this is V2 enhancement (not required for MVP)

### Phase 7: Testing & Verification

- [ ] **Create unit tests for ATR calculation**
  - [ ] Create `apps/bot/tests/test_risk.py`:
    ```python
    import pytest
    from services.risk import calculate_atr, calculate_stop_loss

    # Sample candle data for testing
    SAMPLE_CANDLES = [
        {"high": 105.0, "low": 95.0, "close": 100.0},
        {"high": 108.0, "low": 98.0, "close": 105.0},
        # ... add at least 15 candles
    ]

    def test_calculate_atr_with_valid_data():
        atr = calculate_atr(SAMPLE_CANDLES, period=14)
        assert atr is not None
        assert atr > 0

    def test_calculate_atr_insufficient_data():
        atr = calculate_atr(SAMPLE_CANDLES[:5], period=14)
        assert atr is None

    def test_calculate_stop_loss_valid():
        entry_price = 100.0
        stop_loss, atr = calculate_stop_loss(
            entry_price=entry_price,
            candles=SAMPLE_CANDLES
        )
        assert stop_loss is not None
        assert stop_loss < entry_price
        assert atr is not None

    def test_calculate_stop_loss_respects_multiplier():
        entry = 100.0
        sl_2x, atr = calculate_stop_loss(entry, SAMPLE_CANDLES, atr_multiplier=2.0)
        sl_3x, _ = calculate_stop_loss(entry, SAMPLE_CANDLES, atr_multiplier=3.0)

        # 3x ATR should give lower stop loss
        assert sl_3x < sl_2x

    def test_calculate_stop_loss_fallback():
        # Test with data that would give negative stop
        extreme_candles = [{"high": 1000, "low": 1, "close": 100} for _ in range(20)]
        stop_loss, _ = calculate_stop_loss(10.0, extreme_candles)

        # Should use fallback (15% below entry)
        assert stop_loss > 0
        assert stop_loss == 10.0 * 0.85
    ```

- [ ] **Create verification script**
  - [ ] Create `apps/bot/scripts/test_atr.py`:
    ```python
    """
    Verification script for ATR-based stop loss calculation.
    Uses real market data to validate calculations.
    """
    import asyncio
    from services.risk import calculate_atr, calculate_stop_loss
    from services.kraken_client import KrakenClient

    async def main():
        client = KrakenClient()

        print("=" * 60)
        print("ATR Stop Loss Calculation Test")
        print("=" * 60)

        # Fetch real candles
        symbol = "SOL/USD"
        print(f"\n[1] Fetching candles for {symbol}...")
        ohlcv = client.exchange.fetch_ohlcv(symbol, '15m', limit=50)

        candles = [
            {
                "timestamp": c[0],
                "open": c[1],
                "high": c[2],
                "low": c[3],
                "close": c[4],
                "volume": c[5]
            }
            for c in ohlcv
        ]
        print(f"    Fetched {len(candles)} candles")

        # Calculate ATR
        print("\n[2] Calculating ATR(14)...")
        atr = calculate_atr(candles, period=14)
        print(f"    ATR: ${atr:.4f}")

        # Calculate stop loss at current price
        current_price = candles[-1]['close']
        print(f"\n[3] Calculating stop loss...")
        print(f"    Current price: ${current_price:.4f}")

        stop_loss, _ = calculate_stop_loss(current_price, candles)
        print(f"    Stop Loss (2x ATR): ${stop_loss:.4f}")

        stop_pct = ((current_price - stop_loss) / current_price) * 100
        print(f"    Distance: {stop_pct:.2f}%")

        # Show different ATR scenarios
        print("\n[4] ATR Multiplier Scenarios:")
        for mult in [1.0, 1.5, 2.0, 2.5, 3.0]:
            sl, _ = calculate_stop_loss(current_price, candles, atr_multiplier=mult)
            pct = ((current_price - sl) / current_price) * 100
            print(f"    {mult}x ATR: ${sl:.4f} ({pct:.2f}% below entry)")

        print("\n" + "=" * 60)
        print("Test Complete")
        print("=" * 60)

    if __name__ == "__main__":
        asyncio.run(main())
    ```

---

## Dev Notes

### Architecture Context

**Reference:** `docs/core/prd.md` Section 2.1 FR9

The Dynamic Risk Engine adapts position risk to market volatility. During calm markets, stops are tighter; during volatile periods, stops are wider to avoid premature stop-outs.

```
Risk Calculation Flow:
Candle Data -> ATR(14) Calculation -> Stop Loss = Entry - (2 * ATR) -> Trade Record
```

**Key Design Decisions:**

1. **Soft Stop (Internal Monitoring):** For V1, we do NOT place stop-loss orders on the exchange. The Position Manager (Story 3.3) monitors prices every 15 minutes and executes market sells when stops are hit. This simplifies order management and avoids exchange-specific stop order complexities.

2. **ATR Period = 14:** Industry standard for crypto. Provides good balance between responsiveness and stability.

3. **ATR Multiplier = 2.0:** Gives reasonable "breathing room" while limiting risk. Can be adjusted via environment variable.

### Technical Specifications

**Average True Range (ATR) Formula:**
```
True Range = max(
    High - Low,
    abs(High - Previous Close),
    abs(Low - Previous Close)
)

ATR = EMA(True Range, period=14)
```

**Stop Loss Visualization:**
```
Price:  $100.00 (Entry)
ATR:    $5.00
Stop:   $100.00 - (2 * $5.00) = $90.00

Risk per unit: $10.00 (10%)
```

**pandas-ta Usage:**
```python
import pandas_ta as ta

# ATR calculation
atr_series = ta.atr(high=df['high'], low=df['low'], close=df['close'], length=14)

# Returns pandas Series with NaN for first 'length' rows
# Use .iloc[-1] for most recent value
```

### Volatility Protection Rationale

**Why ATR-based stops instead of fixed percentage?**

| Market Condition | ATR | Fixed 5% Stop | ATR 2x Stop |
|-----------------|-----|---------------|-------------|
| Low volatility (BTC in range) | $500 | $47,500 | $49,000 |
| High volatility (altcoin pump) | $5.00 | $95.00 | $90.00 |

In calm markets, a 5% fixed stop might be too wide, leaving money on the table when the trade goes wrong. In volatile markets, a 5% fixed stop might get triggered by normal price noise, stopping out a trade that would have been profitable.

ATR adapts to the current regime automatically.

### Implementation Guidance

**Order of Operations:**
1. Fetch recent candles (at least 15 for ATR-14)
2. Calculate ATR using pandas-ta
3. Calculate stop loss = entry - (2 * ATR)
4. Validate stop is reasonable (2% to 20% from entry)
5. Execute buy order
6. Store entry_price and stop_loss_price in Trade record

**Edge Cases to Handle:**
- Insufficient candle data (need period + 1 candles minimum)
- Extreme ATR values giving unreasonable stops
- Zero or negative ATR (data quality issue)
- Very low-priced assets where stops become tiny fractions

### Dependencies & Prerequisites

**Required Completions:**
- Story 1.2: Database schema with Trade model
- Story 1.3: Kraken candle data ingestion (for OHLCV data)
- Story 3.1: Execution service (this integrates with execute_buy)

**Environment Requirements:**
- Python 3.11+
- pandas-ta library
- Recent candle data in database (at least 15 periods)

### Downstream Dependencies

- **Story 3.3:** Uses stop_loss_price from Trade record for monitoring
- **Story 3.3:** May recalculate ATR for trailing stop adjustments

---

## Testing Strategy

### Unit Tests

- [ ] `test_calculate_atr_valid_data` - Returns positive float
- [ ] `test_calculate_atr_insufficient_data` - Returns None
- [ ] `test_calculate_atr_missing_columns` - Returns None with error
- [ ] `test_calculate_stop_loss_basic` - Returns price below entry
- [ ] `test_calculate_stop_loss_multiplier_effect` - Higher multiplier = lower stop
- [ ] `test_calculate_stop_loss_fallback` - Uses fallback when ATR unreasonable
- [ ] `test_calculate_stop_loss_with_config` - Uses settings from environment

### Integration Tests

- [ ] Test with real Kraken candle data (historical)
- [ ] Test stop loss calculation integrates with execute_buy
- [ ] Test Trade record contains correct stop_loss_price

### Manual Testing Scenarios

1. **Normal Market Conditions:**
   - Fetch real candles for BTC/USD
   - Calculate ATR and stop loss
   - Verify stop is reasonable (typically 3-8% for BTC)

2. **High Volatility Asset:**
   - Use a volatile altcoin (e.g., SHIB)
   - Verify ATR is proportionally higher
   - Verify stop gives adequate room

3. **Low Data Scenario:**
   - Test with only 10 candles (should fail gracefully)
   - Verify clear error message logged

### Acceptance Criteria Validation

- [ ] AC1: ATR(14) calculated correctly using pandas-ta
- [ ] AC2: Stop Loss = Entry - (2 * ATR) formula applied
- [ ] AC3: stop_loss_price saved to Trade record in database
- [ ] AC4: Soft Stop strategy documented (no exchange orders)

---

## Technical Considerations

### Security

- No additional security concerns (calculations are local)
- Ensure candle data integrity (could be attack vector if spoofed)

### Performance

- ATR calculation is O(n) where n = candle count
- Cache ATR if multiple calculations needed per cycle
- pandas-ta is optimized with numpy vectorization

### Reliability

- Always validate ATR output is reasonable
- Implement fallback to percentage-based stop if ATR fails
- Log all calculations for audit/debugging

### Edge Cases

- Very new assets with < 14 periods of history
- Assets with gaps in trading (weekends for some)
- Extreme flash crashes affecting ATR calculation
- Currency conversion for non-USD pairs
