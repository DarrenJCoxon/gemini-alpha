# Story 3.1: Kraken Order Execution Service

**Status:** Draft
**Epic:** 3 - Execution & Risk Management
**Priority:** Critical (Foundation for all Epic 3 trading functionality)

---

## Story

**As a** Trading Engine,
**I want** to execute "Market Buy" and "Market Sell" orders on Kraken via the Private API,
**so that** we can enter and exit positions based on the Council's decisions.

---

## Acceptance Criteria

1. Python service authenticates with Kraken Private API using API Key/Secret (from Environment Variables).
2. `execute_buy(symbol, amount_usd)` function places a Market Buy order.
3. `execute_sell(symbol, amount_token)` function places a Market Sell order.
4. Trade details (Entry Price, Size, Timestamp, Order ID) are saved to the `Trade` database table with status `OPEN`.
5. Safety Check: Service prevents opening a new trade if an `OPEN` trade already exists for that asset.

---

## Tasks / Subtasks

### Phase 1: Secure Configuration

- [ ] **Configure Kraken API credentials**
  - [ ] Add `KRAKEN_API_KEY` to `.env.example` with placeholder
  - [ ] Add `KRAKEN_PRIVATE_KEY` to `.env.example` with placeholder
  - [ ] Add `KRAKEN_SANDBOX_MODE=true` to `.env.example` for test environment
  - [ ] Document in `.env.example` that keys should have "Create & Modify Orders" permission
  - [ ] Verify `.gitignore` includes `.env` files

- [ ] **Create configuration loader**
  - [ ] Create/update `apps/bot/config.py` if not exists
  - [ ] Add Kraken credential loading:
    ```python
    import os
    from pydantic_settings import BaseSettings

    class KrakenSettings(BaseSettings):
        api_key: str = ""
        private_key: str = ""
        sandbox_mode: bool = True

        class Config:
            env_prefix = "KRAKEN_"

    kraken_settings = KrakenSettings()
    ```
  - [ ] Add validation that raises clear error if credentials missing when sandbox_mode=False

### Phase 2: CCXT Client Setup

- [ ] **Install/verify ccxt dependency**
  - [ ] Confirm `ccxt>=4.0.0` is in `apps/bot/requirements.txt`
  - [ ] Install: `pip install -r requirements.txt`
  - [ ] Verify: `python -c "import ccxt; print(ccxt.__version__)"`

- [ ] **Create Kraken client wrapper**
  - [ ] Create `apps/bot/services/__init__.py` if not exists
  - [ ] Create `apps/bot/services/kraken_client.py`:
    ```python
    import ccxt
    from config import kraken_settings

    class KrakenClient:
        def __init__(self):
            self.exchange = ccxt.kraken({
                'apiKey': kraken_settings.api_key,
                'secret': kraken_settings.private_key,
                'enableRateLimit': True,
                'options': {
                    'defaultType': 'spot',
                }
            })
            self._sandbox_mode = kraken_settings.sandbox_mode

        @property
        def is_sandbox(self) -> bool:
            return self._sandbox_mode
    ```
  - [ ] Add method `test_connection()` to verify API authentication
  - [ ] Add method `get_balance(currency: str) -> float` to check available funds
  - [ ] Export client instance from module

### Phase 3: Execution Service Implementation

- [ ] **Create execution service module**
  - [ ] Create `apps/bot/services/execution.py`
  - [ ] Import dependencies:
    ```python
    from decimal import Decimal
    from datetime import datetime, timezone
    from typing import Optional, Tuple
    import logging
    from .kraken_client import KrakenClient
    from database import get_session
    from models import Trade, Asset, TradeStatus

    logger = logging.getLogger(__name__)
    ```

- [ ] **Implement duplicate position check**
  - [ ] Create function `has_open_position(asset_id: str) -> bool`:
    ```python
    async def has_open_position(asset_id: str) -> bool:
        """Check if an OPEN trade exists for this asset."""
        async with get_session() as session:
            result = await session.execute(
                select(Trade).where(
                    Trade.asset_id == asset_id,
                    Trade.status == TradeStatus.OPEN
                )
            )
            return result.scalar_one_or_none() is not None
    ```

- [ ] **Implement execute_buy function**
  - [ ] Create function signature:
    ```python
    async def execute_buy(
        symbol: str,
        amount_usd: float,
        stop_loss_price: Optional[float] = None
    ) -> Tuple[bool, Optional[str], Optional[Trade]]:
        """
        Execute a market buy order.

        Args:
            symbol: Trading pair (e.g., "SOL/USD")
            amount_usd: Amount in USD to spend
            stop_loss_price: Initial stop loss price (from ATR calculation)

        Returns:
            Tuple of (success, error_message, trade_record)
        """
    ```
  - [ ] Add duplicate position check at start
  - [ ] Fetch current price to calculate quantity
  - [ ] If sandbox mode, log order but don't execute:
    ```python
    if client.is_sandbox:
        logger.info(f"[SANDBOX] Would execute BUY {quantity} {symbol} @ market")
        # Create mock order response for testing
        order = {
            'id': f'sandbox_{datetime.now().timestamp()}',
            'price': current_price,
            'amount': quantity,
            'timestamp': datetime.now(timezone.utc).isoformat()
        }
    else:
        order = client.exchange.create_market_buy_order(symbol, quantity)
    ```
  - [ ] Extract fill price from order response
  - [ ] Create Trade record with status OPEN
  - [ ] Return success tuple with Trade object

- [ ] **Implement execute_sell function**
  - [ ] Create function signature:
    ```python
    async def execute_sell(
        symbol: str,
        amount_token: float,
        trade_id: Optional[str] = None
    ) -> Tuple[bool, Optional[str], Optional[dict]]:
        """
        Execute a market sell order.

        Args:
            symbol: Trading pair (e.g., "SOL/USD")
            amount_token: Amount of token to sell
            trade_id: Optional trade ID to close

        Returns:
            Tuple of (success, error_message, order_details)
        """
    ```
  - [ ] If sandbox mode, log order but don't execute
  - [ ] Execute real order if not sandbox
  - [ ] If trade_id provided, update Trade record (handled by position manager)
  - [ ] Return success tuple with order details

### Phase 4: Database Integration

- [ ] **Verify Trade model compatibility**
  - [ ] Confirm `apps/bot/models/trade.py` has SQLModel definition:
    ```python
    from sqlmodel import SQLModel, Field
    from typing import Optional
    from datetime import datetime
    from decimal import Decimal
    from enum import Enum

    class TradeStatus(str, Enum):
        OPEN = "OPEN"
        CLOSED = "CLOSED"

    class Trade(SQLModel, table=True):
        id: Optional[str] = Field(default=None, primary_key=True)
        asset_id: str = Field(foreign_key="asset.id")
        status: TradeStatus = Field(default=TradeStatus.OPEN)
        entry_price: Decimal
        size: Decimal
        entry_time: datetime
        stop_loss_price: Optional[Decimal] = None
        take_profit_price: Optional[Decimal] = None
        exit_price: Optional[Decimal] = None
        exit_time: Optional[datetime] = None
        pnl: Optional[Decimal] = None
        order_id: Optional[str] = None  # Kraken order ID
    ```
  - [ ] Add `order_id` field if missing (for exchange reference)

- [ ] **Create Trade record on buy execution**
  - [ ] In `execute_buy`, after successful order:
    ```python
    trade = Trade(
        id=str(uuid.uuid4()),
        asset_id=asset_id,
        status=TradeStatus.OPEN,
        entry_price=Decimal(str(fill_price)),
        size=Decimal(str(quantity)),
        entry_time=datetime.now(timezone.utc),
        stop_loss_price=Decimal(str(stop_loss_price)) if stop_loss_price else None,
        order_id=order['id']
    )
    async with get_session() as session:
        session.add(trade)
        await session.commit()
        await session.refresh(trade)
    ```

### Phase 5: Error Handling

- [ ] **Create custom exceptions**
  - [ ] Create `apps/bot/services/exceptions.py`:
    ```python
    class ExecutionError(Exception):
        """Base exception for execution errors."""
        pass

    class InsufficientFundsError(ExecutionError):
        """Raised when account has insufficient funds."""
        pass

    class DuplicatePositionError(ExecutionError):
        """Raised when trying to open duplicate position."""
        pass

    class RateLimitError(ExecutionError):
        """Raised when API rate limit exceeded."""
        pass

    class OrderRejectedError(ExecutionError):
        """Raised when exchange rejects order."""
        pass
    ```

- [ ] **Add error handling to execute_buy**
  - [ ] Catch `ccxt.InsufficientFunds` and raise `InsufficientFundsError`
  - [ ] Catch `ccxt.RateLimitExceeded` and raise `RateLimitError`
  - [ ] Catch `ccxt.ExchangeError` for general failures
  - [ ] Log all errors with full context
  - [ ] Implement retry logic for transient errors (max 3 attempts)

- [ ] **Add error handling to execute_sell**
  - [ ] Same error handling pattern as execute_buy
  - [ ] Handle case where position doesn't exist

### Phase 6: Integration with Master Node

- [ ] **Update Master Node to call execution service**
  - [ ] Modify `apps/bot/nodes/master.py`:
    ```python
    from services.execution import execute_buy, has_open_position

    async def master_node(state: GraphState) -> GraphState:
        # ... existing synthesis logic ...

        if state["final_decision"]["action"] == "BUY":
            # Check for existing position
            if await has_open_position(state["asset_id"]):
                logger.info(f"Skipping BUY - open position exists for {state['asset_symbol']}")
                state["final_decision"]["action"] = "HOLD"
                state["final_decision"]["reasoning"] += " [Blocked: Existing position]"
            else:
                # Calculate position size (from config or risk rules)
                position_size_usd = calculate_position_size()

                # Execute will be called by scheduler after graph completes
                state["pending_order"] = {
                    "action": "BUY",
                    "symbol": state["asset_symbol"],
                    "amount_usd": position_size_usd
                }

        return state
    ```

- [ ] **Update scheduler to process pending orders**
  - [ ] After graph invocation, check for `pending_order` in result
  - [ ] Call `execute_buy()` with order details
  - [ ] Log execution result

### Phase 7: Testing & Verification

- [ ] **Create unit tests**
  - [ ] Create `apps/bot/tests/test_execution.py`:
    ```python
    import pytest
    from unittest.mock import Mock, patch
    from services.execution import execute_buy, execute_sell, has_open_position

    @pytest.mark.asyncio
    async def test_has_open_position_returns_true_when_exists():
        # Mock database with existing open trade
        pass

    @pytest.mark.asyncio
    async def test_has_open_position_returns_false_when_none():
        # Mock empty database
        pass

    @pytest.mark.asyncio
    async def test_execute_buy_prevents_duplicate_position():
        # Should return error if position exists
        pass

    @pytest.mark.asyncio
    async def test_execute_buy_sandbox_mode():
        # Should log but not execute real order
        pass

    @pytest.mark.asyncio
    async def test_execute_buy_creates_trade_record():
        # Should create Trade with status OPEN
        pass
    ```

- [ ] **Create integration test script**
  - [ ] Create `apps/bot/scripts/test_execution.py`:
    ```python
    """
    Integration test for Kraken execution service.
    Run with KRAKEN_SANDBOX_MODE=true for safety.
    """
    import asyncio
    from services.execution import execute_buy, execute_sell
    from services.kraken_client import KrakenClient

    async def main():
        client = KrakenClient()

        print("=" * 60)
        print("Execution Service Integration Test")
        print(f"Sandbox Mode: {client.is_sandbox}")
        print("=" * 60)

        # Test connection
        print("\n[1] Testing API connection...")
        balance = client.get_balance("USD")
        print(f"    USD Balance: ${balance:.2f}")

        # Test buy execution (sandbox)
        print("\n[2] Testing execute_buy (sandbox)...")
        success, error, trade = await execute_buy(
            symbol="SOL/USD",
            amount_usd=100.0,
            stop_loss_price=95.0
        )
        if success:
            print(f"    Trade created: {trade.id}")
            print(f"    Entry price: ${trade.entry_price}")
        else:
            print(f"    Error: {error}")

        print("\n" + "=" * 60)
        print("Test Complete")
        print("=" * 60)

    if __name__ == "__main__":
        asyncio.run(main())
    ```

- [ ] **Manual testing checklist**
  - [ ] Run with `KRAKEN_SANDBOX_MODE=true` - verify no real orders
  - [ ] Verify Trade record created in database
  - [ ] Attempt duplicate buy - verify rejection
  - [ ] Test with invalid credentials - verify clear error message
  - [ ] Test rate limit handling by rapid requests

---

## Dev Notes

### Architecture Context

**Reference:** `docs/core/architecture.md` Section 6.1 (Backend Components)

The Execution Service is the bridge between the Council's decisions and real market orders. It wraps the Kraken Private API via `ccxt` library.

```
Decision Flow:
MasterNode (BUY decision) -> Scheduler -> ExecutionService -> Kraken API
                                      |
                                      v
                               Trade Record (DB)
```

**Key Design Decisions:**

1. **Soft Stop Strategy:** We do NOT place stop-loss orders on the exchange. The bot monitors prices internally and executes market sells when stops are triggered. This avoids complex order management and exchange-specific stop order quirks.

2. **Sandbox Mode:** Critical for development. The `KRAKEN_SANDBOX_MODE` flag allows full testing without real money.

3. **Duplicate Prevention:** Only ONE open position per asset. This is a hard rule enforced at the service layer.

### Technical Specifications

**Kraken API Authentication:**
- Uses HMAC-SHA512 signature
- ccxt handles this automatically with API key/secret
- Rate limits: 15 calls per 3 seconds (private endpoints)

**Market Order Specifics:**
```python
# ccxt market buy - specify amount in base currency (e.g., SOL)
order = exchange.create_market_buy_order('SOL/USD', 1.5)  # Buy 1.5 SOL

# To buy with USD amount, first calculate quantity:
ticker = exchange.fetch_ticker('SOL/USD')
price = ticker['last']
quantity = amount_usd / price
```

**Trade Record Schema (from Prisma):**
```prisma
model Trade {
  id             String    @id @default(uuid())
  assetId        String
  status         TradeStatus @default(OPEN)
  entryPrice     Decimal
  size           Decimal
  entryTime      DateTime
  stopLossPrice  Decimal?
  takeProfitPrice Decimal?
  exitPrice      Decimal?
  exitTime       DateTime?
  pnl            Decimal?
  orderId        String?   // Kraken order reference

  asset          Asset     @relation(fields: [assetId], references: [id])
}
```

### Security Considerations

**CRITICAL - API Key Permissions:**
- Kraken API keys should have ONLY: "Query Funds" + "Create & Modify Orders"
- NEVER enable "Withdraw Funds" permission
- Use separate keys for development (sandbox) vs production

**Environment Variable Security:**
```bash
# .env (NEVER commit)
KRAKEN_API_KEY=your-api-key-here
KRAKEN_PRIVATE_KEY=your-private-key-here
KRAKEN_SANDBOX_MODE=true
```

### Error Handling Patterns

```python
# Retry pattern for transient errors
from tenacity import retry, stop_after_attempt, wait_exponential

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=10),
    retry=retry_if_exception_type(RateLimitError)
)
async def execute_with_retry(order_fn, *args, **kwargs):
    return await order_fn(*args, **kwargs)
```

### Dependencies & Prerequisites

**Required Completions:**
- Story 1.1: Monorepo setup
- Story 1.2: Database schema with Trade model
- Story 1.3: Kraken API client (read-only portions)
- Story 2.4: Master Node decision output

**Environment Requirements:**
- Python 3.11+
- ccxt library installed
- Kraken API keys with trading permissions
- Supabase database accessible

### Downstream Dependencies

- **Story 3.2:** Calls `execute_buy` with calculated stop_loss_price
- **Story 3.3:** Calls `execute_sell` to close positions
- **Story 3.4:** Calls `execute_sell` for emergency liquidation

---

## Testing Strategy

### Unit Tests

- [ ] `test_kraken_client_initialization` - Verify client creates with credentials
- [ ] `test_kraken_client_sandbox_mode` - Verify sandbox flag respected
- [ ] `test_has_open_position_true` - Mock DB with open trade
- [ ] `test_has_open_position_false` - Mock empty DB
- [ ] `test_execute_buy_duplicate_blocked` - Verify duplicate prevention
- [ ] `test_execute_buy_success` - Mock successful order, verify Trade created
- [ ] `test_execute_buy_insufficient_funds` - Mock ccxt exception
- [ ] `test_execute_sell_success` - Mock successful sell order

### Integration Tests

- [ ] Test full flow: buy -> verify Trade in DB -> sell -> verify Trade updated
- [ ] Test with real Kraken sandbox/testnet if available
- [ ] Test concurrent buy attempts for same asset (race condition)

### Manual Testing Scenarios

1. **Sandbox Buy Test:**
   - Set `KRAKEN_SANDBOX_MODE=true`
   - Run test script with $100 buy
   - Verify Trade record created with OPEN status
   - Verify no real order on Kraken

2. **Duplicate Position Test:**
   - Create an OPEN trade in DB manually
   - Attempt to buy same asset
   - Verify rejection with clear error message

3. **Error Recovery Test:**
   - Simulate network timeout mid-order
   - Verify system state is consistent
   - Verify appropriate error logged

### Acceptance Criteria Validation

- [ ] AC1: Service loads credentials from environment variables
- [ ] AC2: `execute_buy` places market order (verified in sandbox)
- [ ] AC3: `execute_sell` places market order (verified in sandbox)
- [ ] AC4: Trade record created with all required fields
- [ ] AC5: Duplicate position prevented with clear error

---

## Technical Considerations

### Security

- API keys stored ONLY in environment variables
- Never log API keys or secrets
- Use read-only keys for development where possible
- Production keys should have minimal permissions

### Performance

- Use connection pooling for database operations
- Cache exchange instance (don't recreate per request)
- Implement rate limiting to stay within Kraken limits
- Async operations for non-blocking execution

### Reliability

- Implement idempotency for order placement
- Store Kraken order ID for reconciliation
- Log all order attempts with full context
- Handle network timeouts gracefully

### Edge Cases

- Partial fills (rare for market orders, but possible)
- Price moved significantly between quote and execution
- Exchange maintenance windows
- Invalid trading pair symbols
- Minimum order size not met
