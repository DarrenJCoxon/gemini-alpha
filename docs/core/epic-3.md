### **File 1: `docs/stories/story-3.1.kraken-execution.md`**

```markdown
# Story 3.1: Kraken Order Execution Service

**Status:** Draft

## Story
**As a** Trading Engine,
**I want** to execute "Market Buy" and "Market Sell" orders on Kraken via the Private API,
**so that** we can enter and exit positions based on the Council's decisions.

## Acceptance Criteria
1.  Python service authenticates with Kraken Private API using API Key/Secret (from Environment Variables).
2.  `execute_buy(symbol, amount_usd)` function places a Market Buy order.
3.  `execute_sell(symbol, amount_token)` function places a Market Sell order.
4.  Trade details (Entry Price, Size, Timestamp, Order ID) are saved to the `Trade` database table with status `OPEN`.
5.  Safety Check: Service prevents opening a new trade if an `OPEN` trade already exists for that asset.

## Tasks / Subtasks
- [ ] Secure Configuration
    - [ ] Add `KRAKEN_API_KEY` and `KRAKEN_PRIVATE_KEY` to `.env`.
    - [ ] Update `ccxt` client initialization to use private keys.
- [ ] Execution Service
    - [ ] Create `apps/bot/services/execution.py`.
    - [ ] Implement `place_market_order(side, symbol, quantity)`.
    - [ ] Implement `get_balance(currency)` to check available funds.
- [ ] Database Integration
    - [ ] Update `MasterNode` logic to call `execution_service` when Decision = BUY.
    - [ ] Create new `Trade` record on successful API response.

## Dev Notes
- **Testing:** Use Kraken's **Demo/Sandbox** API if available, or use `validate=True` flag in `ccxt` to test API connectivity without executing real trades first.
- **Error Handling:** Handle `InsufficientFunds` and `RateLimit` errors gracefully.
```

---

### **File 2: `docs/stories/story-3.2.dynamic-risk-atr.md`**

```markdown
# Story 3.2: Dynamic Risk Engine (ATR Stop Loss)

**Status:** Draft

## Story
**As a** Risk Manager,
**I want** to calculate the Stop Loss price dynamically using the Average True Range (ATR),
**so that** our risk adapts to the current market volatility rather than using a fixed percentage.

## Acceptance Criteria
1.  System calculates ATR (14-period) for the target asset at the moment of entry.
2.  Stop Loss is calculated as `Entry Price - (2 * ATR)`.
3.  The calculated `stop_loss_price` is saved to the `Trade` record in the database.
4.  (Optional) A "Stop Loss" order is placed on Kraken immediately after entry (OSSO - One Sends Other), OR the bot monitors this internally (Soft Stop). *Decision: Internal Soft Stop for V1 to avoid complex order management.*

## Tasks / Subtasks
- [ ] ATR Calculation
    - [ ] Update `TechnicalAgent` or create `RiskService` to calculate ATR from OHLCV data using `pandas-ta`.
- [ ] Stop Loss Logic
    - [ ] Implement `calculate_stop_loss(entry_price, ohlcv_data)`.
    - [ ] Update `execute_buy` flow to call this calculation immediately before/after ordering.
- [ ] Database Update
    - [ ] Ensure `Trade` model stores the initial `stop_loss_price`.

## Dev Notes
- **Volatility Protection:** This logic ensures that if the market is wild, we give the trade more room to breathe. If the market is calm, the stop is tighter.
- **Soft Stop:** For V1, the bot will check price vs. DB Stop Price every 15m. We are NOT placing limit orders on the exchange yet to keep logic simple.
```

---

### **File 3: `docs/stories/story-3.3.position-manager.md`**

```markdown
# Story 3.3: Position Manager (Trailing Stops & Exits)

**Status:** Draft

## Story
**As a** Portfolio Manager,
**I want** to monitor open positions every 15 minutes and update stops or trigger exits,
**so that** we protect profits and limit losses automatically.

## Acceptance Criteria
1.  **Stop Loss Hit:** If Current Price <= `stop_loss_price`, execute Market Sell and close `Trade` record.
2.  **Breakeven Trigger:** If Price > Entry + (2 * ATR), move `stop_loss_price` to `entry_price` (Breakeven).
3.  **Trailing Stop:** If Price continues to rise, trail the stop loss upwards (e.g., keep it at 2 * ATR below the new High).
4.  **Take Profit (Council):** If the "Council" generates a **SELL** signal (Sentiment flips to Greed + Tech Bearish), close the trade regardless of stops.

## Tasks / Subtasks
- [ ] Position Monitor Service
    - [ ] Create `apps/bot/services/position_manager.py`.
    - [ ] Create `check_open_positions()` function.
    - [ ] Add to the 15-minute Scheduler loop.
- [ ] Exit Logic
    - [ ] Implement `close_position(trade_id, reason)`.
    - [ ] Call `execution_service.execute_sell`.
    - [ ] Update `Trade` record with `exit_price`, `exit_time`, and `pnl`.
- [ ] Trailing Logic
    - [ ] Implement logic to update `stop_loss_price` in the DB if the price moves favorably.

## Dev Notes
- **Priority:** The "Stop Loss" check must happen *before* the "Council" analysis in the scheduler loop to prevent holding a losing bag while the agents debate.
```

---

### **File 4: `docs/stories/story-3.4.safety-switch.md`**

```markdown
# Story 3.4: Global Safety Switch

**Status:** Draft

## Story
**As a** User,
**I want** a "Kill Switch" and a Max Drawdown protection,
**so that** the bot stops trading immediately if things go wrong.

## Acceptance Criteria
1.  **Max Drawdown Guard:** If Portfolio Value drops > 20% from initial balance, the system MUST:
    *   Close all open positions immediately.
    *   Disable the "Buy" permission flag in the DB.
    *   Send a notification (log error).
2.  **Manual Kill Switch:** A database flag `system_status` (ACTIVE/PAUSED). If `PAUSED`, the Scheduler skips the "Council" and Execution steps.

## Tasks / Subtasks
- [ ] Global Config
    - [ ] Create `SystemConfig` table (or simple ENV var check/DB flag) for `is_trading_active`.
- [ ] Portfolio Monitoring
    - [ ] Implement `check_drawdown()` in the scheduler.
    - [ ] Fetch total balance from Kraken.
    - [ ] Compare vs `INITIAL_BALANCE` (env var).
- [ ] Emergency Exit
    - [ ] Implement `liquidate_all()` function.

## Dev Notes
- **Safety First:** This is the "Eject Button." Test this logic thoroughly with mock data before live deployment.
```

---

**Epic 3 is mapped.** This completes the backend logic. The bot can now trade, protect itself, and manage profits.

**Next Step:** Epic 4 will build the UI so you can actually *see* all this happening.

**Ready for the Epic 4 tickets?**