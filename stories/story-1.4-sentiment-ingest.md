# Story 1.4: Sentiment Ingestor (LunarCrush/Socials)

**Status:** Approved
**Epic:** 1 - Foundation & Data Pipeline
**Priority:** High

---

## Story

**As a** Quant,
**I want** to fetch social sentiment metrics every 15 minutes,
**so that** the Sentiment Agent has raw data to analyze.

---

## Acceptance Criteria

1. Service fetches "Galaxy Score" or "AltRank" (or raw volume) from LunarCrush API.
2. Service scrapes/fetches latest messages from configured Telegram/Bluesky sources (stubbed/mocked if API access pending).
3. Data stored in `SentimentLog` table linked to the `Asset`.

---

## Tasks / Subtasks

### Phase 1: LunarCrush Integration

- [ ] **Obtain LunarCrush API access**
  - [ ] Sign up at https://lunarcrush.com/developers
  - [ ] Obtain API key (free tier available)
  - [ ] Review API documentation and rate limits
  - [ ] Add `LUNARCRUSH_API_KEY` to `.env`

- [ ] **Install required packages**
  - [ ] Add `httpx>=0.26.0` to requirements.txt (if not already)
  - [ ] Add `tenacity>=8.2.0` for retry logic (if not already)
  - [ ] Run `pip install -r requirements.txt`

- [ ] **Create LunarCrush service module**
  - [ ] Create `apps/bot/services/lunarcrush.py`
  - [ ] Add type hints and docstrings
  - [ ] Import httpx for async HTTP requests

- [ ] **Implement LunarCrush client class**
  ```python
  class LunarCrushClient:
      BASE_URL = "https://lunarcrush.com/api4/public"

      def __init__(self, api_key: str):
          self.api_key = api_key
          self.client = httpx.AsyncClient(
              headers={"Authorization": f"Bearer {api_key}"},
              timeout=30.0
          )

      async def get_coin_metrics(self, symbol: str) -> dict:
          """Fetch Galaxy Score, AltRank, and social volume for a coin."""
          ...

      async def close(self):
          await self.client.aclose()
  ```

- [ ] **Implement Galaxy Score fetching**
  ```python
  async def fetch_galaxy_score(self, symbol: str) -> dict:
      """
      Fetch sentiment metrics for a single symbol.

      Returns:
          {
              "galaxy_score": int (0-100),
              "alt_rank": int (1-5000+),
              "social_volume": int,
              "social_score": int (0-100),
              "bullish_sentiment": float (0.0-1.0),
              "bearish_sentiment": float (0.0-1.0)
          }
      """
  ```

- [ ] **Handle LunarCrush symbol mapping**
  - [ ] Map database symbols to LunarCrush format
  - [ ] "SOLUSD" -> "sol" (lowercase, USD suffix removed)
  - [ ] Create `convert_to_lunarcrush_symbol()` function

- [ ] **Implement mock fallback for development**
  - [ ] Create `MockLunarCrushClient` class
  - [ ] Generate realistic random scores (40-80 range)
  - [ ] Use mock when `LUNARCRUSH_API_KEY` not set

### Phase 2: Bluesky Integration

- [ ] **Research Bluesky API options**
  - [ ] AT Protocol (atproto) library for Python
  - [ ] Public feed endpoints (no auth required for public posts)
  - [ ] Install `atproto>=0.0.40` if available

- [ ] **Create Bluesky scraper module**
  - [ ] Create `apps/bot/services/socials/bluesky.py`
  - [ ] Define target accounts/hashtags to monitor

- [ ] **Implement Bluesky fetcher**
  ```python
  class BlueskyFetcher:
      TARGET_HASHTAGS = ["#crypto", "#bitcoin", "#altcoins"]
      TARGET_ACCOUNTS = [
          "cryptoanalyst.bsky.social",
          "tradingview.bsky.social"
      ]

      async def fetch_recent_posts(
          self,
          symbol: str,
          limit: int = 10
      ) -> list[dict]:
          """
          Fetch recent posts mentioning a crypto symbol.

          Returns:
              List of {
                  "text": str,
                  "author": str,
                  "timestamp": datetime,
                  "likes": int
              }
          """
  ```

- [ ] **Implement stub/mock for initial development**
  - [ ] Create `MockBlueskyFetcher` class
  - [ ] Return sample posts for testing pipeline
  - [ ] Include realistic timestamps and content

### Phase 3: Telegram Integration

- [ ] **Research Telegram access options**
  - [ ] Option A: Telethon (user account, requires phone auth)
  - [ ] Option B: pyrogram (user account)
  - [ ] Option C: Bot API (limited to bot-accessible channels)
  - [ ] **Recommended:** Start with mock, implement later

- [ ] **Create Telegram scraper module**
  - [ ] Create `apps/bot/services/socials/telegram.py`
  - [ ] Define target channels to monitor

- [ ] **Define target Telegram channels**
  ```python
  TARGET_CHANNELS = [
      "@CryptoNews",
      "@WhaleTrades",
      "@AltcoinDaily",
      # Add more as needed
  ]
  ```

- [ ] **Implement Telegram fetcher interface**
  ```python
  class TelegramFetcher:
      async def fetch_channel_messages(
          self,
          channel: str,
          symbol: str,
          limit: int = 10
      ) -> list[dict]:
          """
          Fetch recent messages from a Telegram channel.

          Returns:
              List of {
                  "text": str,
                  "channel": str,
                  "timestamp": datetime,
                  "views": int
              }
          """
  ```

- [ ] **Implement stub/mock for initial development**
  - [ ] Create `MockTelegramFetcher` class
  - [ ] Return sample messages for testing pipeline
  - [ ] Include realistic crypto-related content

### Phase 4: Sentiment Aggregation Service

- [ ] **Create unified sentiment service**
  - [ ] Create `apps/bot/services/sentiment.py`
  - [ ] Aggregate data from all sources

- [ ] **Implement aggregation logic**
  ```python
  class SentimentService:
      def __init__(
          self,
          lunarcrush: LunarCrushClient,
          bluesky: BlueskyFetcher,
          telegram: TelegramFetcher
      ):
          ...

      async def fetch_all_sentiment(
          self,
          symbol: str
      ) -> dict:
          """
          Fetch sentiment from all sources for a symbol.

          Returns:
              {
                  "lunarcrush": {...},
                  "bluesky_posts": [...],
                  "telegram_posts": [...],
                  "aggregated_score": int (0-100)
              }
          """
  ```

- [ ] **Implement aggregated score calculation**
  - [ ] Weight Galaxy Score as primary (60%)
  - [ ] Weight social volume as secondary (40%)
  - [ ] Normalize to 0-100 scale
  - [ ] Document scoring methodology

### Phase 5: Database Storage

- [ ] **Implement SentimentLog creation**
  ```python
  async def save_sentiment_log(
      session: AsyncSession,
      asset_id: str,
      source: str,
      data: dict
  ) -> SentimentLog:
      """
      Create a SentimentLog record in the database.

      Args:
          asset_id: Foreign key to Asset
          source: "lunarcrush", "bluesky", or "telegram"
          data: Source-specific data dict
      """
  ```

- [ ] **Map source data to SentimentLog fields**
  | Source | Database Field | Source Field |
  |--------|----------------|--------------|
  | LunarCrush | galaxyScore | galaxy_score |
  | LunarCrush | altRank | alt_rank |
  | LunarCrush | socialVolume | social_volume |
  | Bluesky | rawText | concatenated posts |
  | Telegram | rawText | concatenated messages |
  | All | sentimentScore | aggregated_score |

- [ ] **Handle batch inserts for efficiency**
  - [ ] Collect all sentiment logs before insert
  - [ ] Use bulk insert for 30 assets
  - [ ] Commit once at end of cycle

### Phase 6: Scheduler Integration

- [ ] **Integrate with existing scheduler**
  - [ ] Add sentiment job to `apps/bot/services/scheduler.py`
  - [ ] Run after Kraken ingestion completes
  - [ ] Or run in parallel if independent

- [ ] **Configure scheduler job**
  ```python
  scheduler.add_job(
      ingest_sentiment_data,
      CronTrigger(minute="0,15,30,45"),
      id="sentiment_ingest",
      name="Sentiment Data Ingestion",
      replace_existing=True
  )
  ```

- [ ] **Implement main sentiment ingestion job**
  ```python
  async def ingest_sentiment_data():
      """
      Main job function for sentiment ingestion.
      Fetches sentiment for all active assets and saves to DB.
      """
      start_time = datetime.utcnow()
      logger.info(f"Starting sentiment ingestion at {start_time}")

      assets = await get_active_assets()

      for asset in assets:
          sentiment = await sentiment_service.fetch_all_sentiment(asset.symbol)
          await save_sentiment_log(session, asset.id, "aggregated", sentiment)

      logger.info(f"Sentiment ingestion completed. Processed {len(assets)} assets.")
  ```

- [ ] **Handle source failures gracefully**
  - [ ] If LunarCrush fails, continue with social scrapers
  - [ ] If all sources fail, log warning but don't crash
  - [ ] Store partial data when available

### Phase 7: Error Handling & Retry Logic

- [ ] **Implement retry decorator for API calls**
  ```python
  @retry(
      stop=stop_after_attempt(3),
      wait=wait_exponential(multiplier=1, min=2, max=10),
      retry=retry_if_exception_type((httpx.TimeoutException, httpx.HTTPStatusError))
  )
  async def fetch_with_retry(...):
      ...
  ```

- [ ] **Handle API quota exhaustion**
  - [ ] LunarCrush free tier: ~300 calls/day
  - [ ] 30 assets * 96 cycles/day = 2,880 calls (over limit!)
  - [ ] **Solution:** Fetch only top 10 assets per cycle, rotate

- [ ] **Implement rate limiting strategy**
  ```python
  class RateLimitedClient:
      def __init__(self, calls_per_day: int = 300):
          self.daily_limit = calls_per_day
          self.calls_today = 0
          self.last_reset = datetime.utcnow().date()

      async def check_quota(self) -> bool:
          """Check if we can make another API call."""
          ...
  ```

- [ ] **Log rate limit status**
  - [ ] Log remaining quota at start of each cycle
  - [ ] Warn when below 20% remaining
  - [ ] Skip LunarCrush if quota exhausted

### Phase 8: Testing & Validation

- [ ] **Create mock data generators**
  - [ ] `apps/bot/tests/fixtures/sentiment_data.py`
  - [ ] Realistic Galaxy Scores (30-70 typical, 0-20 extreme fear)
  - [ ] Sample social media posts with crypto keywords

- [ ] **Create unit tests**
  - [ ] Test symbol conversion
  - [ ] Test score aggregation logic
  - [ ] Test database model creation

- [ ] **Create integration tests**
  - [ ] Test LunarCrush API with real call (use VCR/cassettes)
  - [ ] Test database upsert flow
  - [ ] Test scheduler integration

---

## Dev Notes

### Architecture Context

**Service Location:**
- `apps/bot/services/lunarcrush.py` - LunarCrush API client
- `apps/bot/services/socials/bluesky.py` - Bluesky scraper
- `apps/bot/services/socials/telegram.py` - Telegram scraper
- `apps/bot/services/sentiment.py` - Aggregation service

**Data Flow:**
```
LunarCrush API ─┐
                ├─> SentimentService.aggregate() ─> save_sentiment_log() ─> PostgreSQL
Bluesky API ────┤                                                              │
                │                                                        SentimentLog
Telegram API ───┘
```

### Technical Specifications

**LunarCrush API v4:**
- Base URL: `https://lunarcrush.com/api4/public`
- Auth: Bearer token in header
- Rate Limit: ~300 calls/day (free tier)
- Endpoint: `/coins/{symbol}/meta`

**LunarCrush Response Structure:**
```json
{
  "data": {
    "symbol": "SOL",
    "name": "Solana",
    "galaxy_score": 67,
    "alt_rank": 12,
    "social_volume": 15234,
    "social_score": 72,
    "market_dominance": 2.1,
    "sentiment": {
      "bullish": 0.65,
      "bearish": 0.35
    }
  }
}
```

**Galaxy Score Interpretation (per PRD FR4):**
| Score Range | Interpretation | Action |
|-------------|----------------|--------|
| 0-20 | Extreme Fear | BUY signal potential |
| 21-40 | Fear | Monitor closely |
| 41-60 | Neutral | No action |
| 61-80 | Greed | Caution |
| 81-100 | Extreme Greed | SELL signal potential |

**Bluesky AT Protocol:**
```python
from atproto import Client

client = Client()
# Public posts don't require auth
posts = client.get_author_feed(handle="crypto.bsky.social", limit=10)
```

### API Quota Strategy

**Problem:** LunarCrush free tier (300 calls/day) vs. 30 assets * 96 cycles = 2,880 calls/day

**Solutions:**

1. **Rotation Strategy:**
   - Divide 30 assets into 3 groups of 10
   - Rotate which group is fetched each cycle
   - Each asset updated every 45 minutes instead of 15

2. **Priority Strategy:**
   - Always fetch top 10 by market cap
   - Fetch remaining 20 only 4 times per day
   - Focus resources on high-value assets

3. **Upgrade Path:**
   - LunarCrush Pro: 10,000 calls/day (~$100/month)
   - Consider for production deployment

**Recommended:** Use rotation strategy for MVP, upgrade for production.

### Mock Implementation for Development

**MockLunarCrushClient:**
```python
import random

class MockLunarCrushClient:
    async def get_coin_metrics(self, symbol: str) -> dict:
        # Generate realistic random scores
        return {
            "galaxy_score": random.randint(30, 75),
            "alt_rank": random.randint(1, 100),
            "social_volume": random.randint(1000, 50000),
            "social_score": random.randint(40, 80),
            "bullish_sentiment": round(random.uniform(0.3, 0.7), 2),
            "bearish_sentiment": round(random.uniform(0.3, 0.7), 2)
        }
```

### Environment Variables Required

```
# LunarCrush
LUNARCRUSH_API_KEY=your_api_key_here

# Bluesky (optional - for authenticated access)
BLUESKY_HANDLE=yourhandle.bsky.social
BLUESKY_PASSWORD=your_app_password

# Telegram (optional - for Telethon)
TELEGRAM_API_ID=your_api_id
TELEGRAM_API_HASH=your_api_hash
TELEGRAM_PHONE=+1234567890
```

### Sentiment Score Aggregation Formula

```python
def calculate_aggregated_score(
    galaxy_score: int,
    social_volume: int,
    avg_social_volume: int
) -> int:
    """
    Calculate aggregated sentiment score.

    Formula:
    - 60% weight on Galaxy Score (direct sentiment)
    - 40% weight on normalized Social Volume (activity level)

    Social volume is normalized against 30-day average.
    """
    volume_normalized = min(100, (social_volume / avg_social_volume) * 50)

    aggregated = (galaxy_score * 0.6) + (volume_normalized * 0.4)

    return int(min(100, max(0, aggregated)))
```

### Dependencies & Prerequisites

- **Story 1.1:** Monorepo structure and Python environment
- **Story 1.2:** Database schema with SentimentLog model
- **Story 1.3:** Scheduler already configured (share scheduler instance)

### Downstream Dependencies

- **Epic 2 (Sentiment Agent):** Reads SentimentLog for fear score analysis
- **Epic 4 (Dashboard):** Displays sentiment trends and scores

---

## Testing Strategy

### Unit Tests

- [ ] `test_lunarcrush_client.py`
  - Test symbol conversion (SOLUSD -> sol)
  - Test response parsing
  - Test mock client generates valid data

- [ ] `test_aggregation.py`
  - Test score aggregation formula
  - Test boundary conditions (0, 100)
  - Test with missing data sources

- [ ] `test_sentiment_log_creation.py`
  - Test SentimentLog model instantiation
  - Test all fields map correctly

### Integration Tests

- [ ] `test_lunarcrush_api.py` (with VCR cassettes)
  - Record actual API response
  - Replay for consistent testing
  - Verify response structure

- [ ] `test_database_storage.py`
  - Create sentiment log
  - Query by asset and time range
  - Verify foreign key relationship

### Manual Testing Scenarios

1. **LunarCrush Live Test:**
   - Set API key in `.env`
   - Run `python -m services.lunarcrush test`
   - Verify Galaxy Score returned for SOL

2. **Mock Mode Test:**
   - Unset `LUNARCRUSH_API_KEY`
   - Run sentiment ingestion
   - Verify mock data stored in DB

3. **Full Cycle Test:**
   - Start scheduler
   - Wait for 15-minute mark
   - Verify SentimentLog entries for all 30 assets

4. **Quota Exhaustion Test:**
   - Mock quota at 0
   - Run ingestion
   - Verify graceful skip with warning log

### Acceptance Criteria Validation

- [x] AC1: LunarCrush client fetches Galaxy Score successfully
- [x] AC2: Bluesky/Telegram scrapers implemented (stubbed OK for MVP)
- [x] AC3: SentimentLog entries created with proper asset linkage

---

## Technical Considerations

### Security
- API keys stored in environment variables only (per PRD NFR2)
- No credentials logged in output
- Telegram auth tokens require extra care (session hijacking risk)

### Performance
- Batch sentiment fetches to minimize API calls
- Use async/await for parallel source fetching
- Cache Galaxy Scores if rate limited

### Reliability
- Graceful degradation when sources unavailable
- Continue with partial data rather than failing entirely
- Log warnings for monitoring

### Monitoring
- Log API call counts and remaining quota
- Log source success/failure rates
- Alert when approaching quota limits

### Cost Considerations
- LunarCrush free tier: 300 calls/day (adequate for MVP with rotation)
- LunarCrush Pro: ~$100/month for 10,000 calls/day
- Bluesky: Free (public API)
- Telegram: Free (but auth complexity)

### Edge Cases
- Handle coins not listed on LunarCrush
- Handle empty social media results
- Handle API maintenance windows
- Handle timezone differences in post timestamps
