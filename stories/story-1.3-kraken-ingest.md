# Story 1.3: Kraken Data Ingestor (Python)

**Status:** Approved
**Epic:** 1 - Foundation & Data Pipeline
**Priority:** High

---

## Story

**As a** Data Engineer,
**I want** to build a Python service that polls Kraken API every 15 minutes,
**so that** we have a continuous stream of OHLCV data for our target assets.

---

## Acceptance Criteria

1. Python service uses `ccxt` or `httpx` to fetch OHLCV for the 30 active assets.
2. Scheduler (e.g., `APScheduler`) triggers job exactly at 00, 15, 30, 45 minutes past the hour.
3. Data is upserted into Supabase `Candle` table.
4. Error handling: Retry logic implemented if Kraken API times out (3 retries).

---

## Tasks / Subtasks

### Phase 1: Kraken Client Setup

- [ ] **Install required Python packages**
  - [ ] Add `ccxt>=4.2.0` to requirements.txt (preferred for exchange abstraction)
  - [ ] Add `httpx>=0.26.0` as fallback/alternative
  - [ ] Add `tenacity>=8.2.0` for retry logic
  - [ ] Run `pip install -r requirements.txt`

- [ ] **Create Kraken service module**
  - [ ] Create `apps/bot/services/kraken.py`
  - [ ] Import ccxt and configure Kraken exchange instance
  - [ ] Add type hints for all functions

- [ ] **Configure Kraken API credentials**
  - [ ] Add `KRAKEN_API_KEY` to `.env` (even if using public endpoints)
  - [ ] Add `KRAKEN_API_SECRET` to `.env`
  - [ ] Create config loader in `apps/bot/config.py`
  - [ ] Note: Public OHLCV endpoints don't require authentication

- [ ] **Implement basic connection test**
  - [ ] Create `test_connection()` function
  - [ ] Verify exchange status via `exchange.fetch_status()`
  - [ ] Log connection success/failure

### Phase 2: Database Connection (Python)

- [ ] **Configure async database session**
  - [ ] Update `apps/bot/database.py` with async engine
  - [ ] Create session factory using `async_sessionmaker`
  - [ ] Add connection pool configuration (max 10 connections)

- [ ] **Create database utility functions**
  - [ ] Create `get_active_assets()` - fetch all assets where `isActive=True`
  - [ ] Create `upsert_candle()` - insert or update candle data
  - [ ] Add proper error handling and logging

- [ ] **Test database connectivity**
  - [ ] Create `apps/bot/scripts/test_db.py`
  - [ ] Verify connection to PostgreSQL
  - [ ] Query asset count and log result

### Phase 3: OHLCV Fetching Logic

- [ ] **Implement core fetch function**
  ```python
  async def fetch_ohlcv(
      symbol: str,
      timeframe: str = "15m",
      limit: int = 1
  ) -> list[dict]:
      """
      Fetch OHLCV data from Kraken for a single symbol.

      Args:
          symbol: Trading pair (e.g., "SOL/USD")
          timeframe: Candle interval (default: "15m")
          limit: Number of candles to fetch (default: 1 = latest)

      Returns:
          List of OHLCV dicts with keys: timestamp, open, high, low, close, volume
      """
  ```

- [ ] **Implement symbol conversion**
  - [ ] Create `convert_symbol_to_kraken(db_symbol: str) -> str`
  - [ ] Map "SOLUSD" -> "SOL/USD" (ccxt format)
  - [ ] Handle edge cases (BTC -> XBT on Kraken)
  - [ ] Create mapping table for known conversions

- [ ] **Implement batch fetching**
  ```python
  async def fetch_all_active_assets() -> dict[str, list]:
      """
      Fetch OHLCV for all active assets from database.
      Returns dict mapping asset_id to candle data.
      """
  ```

- [ ] **Add rate limiting**
  - [ ] Implement `asyncio.sleep(0.5)` between API calls
  - [ ] Kraken rate limit: ~15 calls per second (public)
  - [ ] Calculate safe batch size (30 assets = 15 seconds minimum)

### Phase 4: Upsert Logic

- [ ] **Implement candle upsert function**
  ```python
  async def upsert_candles(
      session: AsyncSession,
      asset_id: str,
      candles: list[dict]
  ) -> int:
      """
      Upsert candles into database.
      Uses ON CONFLICT to update existing candles.
      Returns number of candles upserted.
      """
  ```

- [ ] **Handle duplicate prevention**
  - [ ] Use unique constraint `[assetId, timestamp, timeframe]`
  - [ ] Implement PostgreSQL `ON CONFLICT DO UPDATE`
  - [ ] Update only if new data has higher volume (data correction)

- [ ] **Implement batch processing**
  - [ ] Process 30 assets in batches of 5
  - [ ] Commit after each batch to prevent memory issues
  - [ ] Log progress: "Processed 10/30 assets..."

### Phase 5: Retry Logic

- [ ] **Implement retry decorator**
  ```python
  from tenacity import (
      retry,
      stop_after_attempt,
      wait_exponential,
      retry_if_exception_type
  )

  @retry(
      stop=stop_after_attempt(3),
      wait=wait_exponential(multiplier=1, min=2, max=10),
      retry=retry_if_exception_type((httpx.TimeoutException, ccxt.NetworkError))
  )
  async def fetch_ohlcv_with_retry(symbol: str) -> list[dict]:
      ...
  ```

- [ ] **Handle specific error cases**
  - [ ] Timeout: Retry with exponential backoff
  - [ ] Rate limit (429): Back off for 60 seconds
  - [ ] Invalid symbol: Log error, skip asset, continue
  - [ ] Network error: Retry up to 3 times

- [ ] **Implement circuit breaker pattern**
  - [ ] If 5 consecutive failures, pause for 5 minutes
  - [ ] Log alert for monitoring
  - [ ] Resume automatically after cooldown

### Phase 6: Scheduler Implementation

- [ ] **Install and configure APScheduler**
  - [ ] Add `apscheduler>=3.10.0` to requirements.txt
  - [ ] Import `AsyncIOScheduler` for async support
  - [ ] Configure timezone to UTC

- [ ] **Create scheduler configuration**
  ```python
  from apscheduler.schedulers.asyncio import AsyncIOScheduler
  from apscheduler.triggers.cron import CronTrigger

  scheduler = AsyncIOScheduler(timezone="UTC")

  scheduler.add_job(
      ingest_kraken_data,
      CronTrigger(minute="0,15,30,45"),
      id="kraken_ingest",
      name="Kraken OHLCV Ingestion",
      replace_existing=True
  )
  ```

- [ ] **Implement main ingestion job**
  ```python
  async def ingest_kraken_data():
      """
      Main job function called by scheduler.
      Fetches OHLCV for all active assets and upserts to DB.
      """
      start_time = datetime.utcnow()
      logger.info(f"Starting Kraken ingestion at {start_time}")

      # Fetch active assets
      # Fetch OHLCV for each
      # Upsert to database
      # Log completion time and stats
  ```

- [ ] **Handle scheduler lifecycle**
  - [ ] Start scheduler in `main.py` on application startup
  - [ ] Graceful shutdown on SIGTERM/SIGINT
  - [ ] Prevent overlapping job executions

### Phase 7: Main Entry Point Integration

- [ ] **Update `apps/bot/main.py`**
  ```python
  from fastapi import FastAPI
  from contextlib import asynccontextmanager
  from .services.kraken import scheduler, ingest_kraken_data

  @asynccontextmanager
  async def lifespan(app: FastAPI):
      # Startup
      scheduler.start()
      logger.info("Scheduler started")

      # Optional: Run immediate ingestion on startup
      await ingest_kraken_data()

      yield

      # Shutdown
      scheduler.shutdown()
      logger.info("Scheduler stopped")

  app = FastAPI(lifespan=lifespan)

  @app.get("/health")
  async def health_check():
      return {"status": "healthy", "scheduler_running": scheduler.running}
  ```

- [ ] **Add manual trigger endpoint**
  - [ ] Create `POST /api/ingest/kraken` for manual triggering
  - [ ] Useful for testing and backfilling
  - [ ] Return ingestion stats in response

- [ ] **Configure logging**
  - [ ] Setup structured logging with timestamps
  - [ ] Log to stdout for Railway compatibility
  - [ ] Include asset symbol, candle count, and duration

### Phase 8: Testing & Validation

- [ ] **Create unit tests**
  - [ ] Test symbol conversion function
  - [ ] Test candle data parsing
  - [ ] Test retry logic with mocked failures

- [ ] **Create integration tests**
  - [ ] Test end-to-end ingestion with test database
  - [ ] Verify candles appear in database after ingestion
  - [ ] Verify upsert doesn't create duplicates

- [ ] **Manual testing**
  - [ ] Run service locally with `uvicorn main:app --reload`
  - [ ] Trigger manual ingestion via API
  - [ ] Verify candles in Prisma Studio
  - [ ] Wait for scheduled run at next 15-minute mark

---

## Dev Notes

### Architecture Context

**Service Location:**
- `apps/bot/services/kraken.py` - Kraken API client
- `apps/bot/services/scheduler.py` - APScheduler configuration
- `apps/bot/main.py` - FastAPI entry point with scheduler lifecycle

**Data Flow:**
```
Kraken API -> fetch_ohlcv() -> parse_candles() -> upsert_candles() -> PostgreSQL
                                                                          |
                                                                    Candle table
```

### Technical Specifications

**Kraken API Details:**
- Base URL: `https://api.kraken.com`
- OHLCV Endpoint: `/0/public/OHLC`
- Rate Limit: 15 requests/second (public endpoints)
- Timeframe parameter: `15` (15 minutes in Kraken API)

**ccxt Configuration:**
```python
import ccxt.async_support as ccxt

exchange = ccxt.kraken({
    'enableRateLimit': True,  # Built-in rate limiting
    'rateLimit': 3000,        # 3 seconds between calls (conservative)
    'options': {
        'adjustForTimeDifference': True,
    }
})
```

**Symbol Mapping (Kraken Peculiarities):**
```python
SYMBOL_MAP = {
    "BTCUSD": "XBT/USD",   # Kraken uses XBT for Bitcoin
    "DOTUSD": "DOT/USD",
    "SOLUSD": "SOL/USD",
    # ... add all 30 assets
}
```

**Candle Data Structure (from ccxt):**
```python
# ccxt returns: [timestamp, open, high, low, close, volume]
# Convert to dict:
{
    "timestamp": datetime.fromtimestamp(ohlcv[0] / 1000, tz=timezone.utc),
    "open": Decimal(str(ohlcv[1])),
    "high": Decimal(str(ohlcv[2])),
    "low": Decimal(str(ohlcv[3])),
    "close": Decimal(str(ohlcv[4])),
    "volume": Decimal(str(ohlcv[5])),
    "timeframe": "15m"
}
```

### Implementation Guidance

**Upsert Query (PostgreSQL):**
```python
from sqlalchemy.dialects.postgresql import insert

stmt = insert(Candle).values(candle_data)
stmt = stmt.on_conflict_do_update(
    index_elements=['assetId', 'timestamp', 'timeframe'],
    set_={
        'open': stmt.excluded.open,
        'high': stmt.excluded.high,
        'low': stmt.excluded.low,
        'close': stmt.excluded.close,
        'volume': stmt.excluded.volume,
    }
)
await session.execute(stmt)
await session.commit()
```

**Logging Configuration:**
```python
import logging
import sys

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("kraken_ingestor")
```

**Environment Variables Required:**
```
DATABASE_URL=postgresql+asyncpg://user:pass@host:5432/db
KRAKEN_API_KEY=optional_for_public_endpoints
KRAKEN_API_SECRET=optional_for_public_endpoints
```

### Rate Limit Considerations

Per PRD NFR4: System must adhere to Kraken's API rate limits to avoid IP bans.

**Recommended Strategy:**
1. Use ccxt's built-in rate limiter (`enableRateLimit: True`)
2. Add 500ms delay between asset requests as safety margin
3. Total time for 30 assets: ~15 seconds (well within 15-minute window)
4. If rate limited (429 response), back off for 60 seconds

### Error Handling Requirements

Per PRD NFR1: The 15-minute polling loop must be robust; if a cycle is missed, an alert must be logged.

**Error Categories:**
| Error Type | Action | Log Level |
|------------|--------|-----------|
| API Timeout | Retry 3x with backoff | WARNING |
| Rate Limited | Wait 60s, retry | WARNING |
| Invalid Symbol | Skip asset, continue | ERROR |
| Network Error | Retry 3x with backoff | WARNING |
| Database Error | Retry once, then fail | ERROR |
| Full Cycle Failure | Log alert, notify | CRITICAL |

### Dependencies & Prerequisites

- **Story 1.1:** Monorepo structure and Python environment
- **Story 1.2:** Database schema with Candle model and seeded assets

### Downstream Dependencies

- **Story 1.4:** Shares scheduler with sentiment ingestion
- **Epic 2:** Technical Agent reads candles for analysis
- **Epic 4:** Dashboard displays candle data for charts

---

## Testing Strategy

### Unit Tests

- [ ] `test_symbol_conversion.py`
  - Test all 30 symbol mappings
  - Test edge cases (BTC -> XBT)
  - Test invalid symbol handling

- [ ] `test_candle_parsing.py`
  - Test ccxt OHLCV array to dict conversion
  - Test Decimal precision handling
  - Test timestamp UTC conversion

- [ ] `test_retry_logic.py`
  - Mock timeout exceptions
  - Verify 3 retry attempts
  - Verify exponential backoff timing

### Integration Tests

- [ ] `test_kraken_integration.py`
  - Live API call to fetch single symbol
  - Verify response structure
  - Test rate limiting behavior

- [ ] `test_database_upsert.py`
  - Insert new candle
  - Upsert existing candle (same timestamp)
  - Verify unique constraint prevents duplicates

### Manual Testing Scenarios

1. **Fresh Start Test:**
   - Start service with empty Candle table
   - Wait for scheduled run
   - Verify 30 candles created (1 per asset)

2. **Upsert Test:**
   - Run ingestion twice in a row
   - Verify candle count doesn't double
   - Verify latest data overwrites old data

3. **Error Recovery Test:**
   - Disconnect network mid-ingestion
   - Verify retries occur
   - Verify partial success is logged

4. **Scheduler Precision Test:**
   - Start service at XX:14
   - Verify job runs at XX:15
   - Verify job runs at XX:30

### Acceptance Criteria Validation

- [x] AC1: ccxt fetches OHLCV for 30 assets successfully
- [x] AC2: APScheduler triggers at 00, 15, 30, 45 minutes
- [x] AC3: Candles appear in database after ingestion
- [x] AC4: Retry logic handles 3 attempts on timeout

---

## Technical Considerations

### Security
- API keys stored in environment variables only
- No credentials logged in output
- HTTPS required for all API calls

### Performance
- 30 assets at 500ms each = 15 seconds per cycle
- Well within 15-minute window
- Database upsert uses bulk operations when possible

### Reliability
- Retry logic prevents transient failures from breaking pipeline
- Circuit breaker prevents cascading failures
- Scheduler runs independently of API endpoints

### Monitoring
- Log ingestion start/end times
- Log asset count and success/failure rates
- Log candle counts per cycle
- Consider adding metrics endpoint for Railway

### Edge Cases
- Handle Kraken maintenance windows gracefully
- Handle new asset listings (requires seed update)
- Handle delisted assets (mark as inactive)
- Handle partial data (some assets fail, others succeed)
