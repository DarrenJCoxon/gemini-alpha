### **File 1: `docs/stories/story-1.1.monorepo-setup.md`**

```markdown
# Story 1.1: Monorepo & Infrastructure Setup

**Status:** Draft

## Story
**As a** Developer,
**I want** to set up a Turborepo with Next.js (Web) and Python (Bot) packages,
**so that** I have a unified codebase with shared types and a synchronized build process.

## Acceptance Criteria
1.  Turborepo initialized with `apps/web` (Next.js 15) and `apps/bot` (Python/FastAPI).
2.  `packages/database` created with Prisma 7 initialized (PostgreSQL).
3.  Docker Compose file created to run local Postgres and Redis (if needed) for dev.
4.  GitHub Actions workflow created for linting/type-checking on PR.
5.  Railway project initialized (verified via CLI or placeholder config).

## Tasks / Subtasks
- [ ] Initialize Turborepo
    - [ ] Run `npx create-turbo@latest` using pnpm
    - [ ] Configure `turbo.json` pipeline
- [ ] Setup Frontend App (`apps/web`)
    - [ ] Initialize Next.js 15 app
    - [ ] Install Shadcn UI and Tailwind CSS
- [ ] Setup Backend App (`apps/bot`)
    - [ ] Create Python 3.11 virtual environment structure
    - [ ] Install FastAPI and Uvicorn
    - [ ] Configure `pyproject.toml` or `requirements.txt`
- [ ] Setup Database Package (`packages/database`)
    - [ ] Initialize Prisma 7
    - [ ] Export Prisma Client for usage in `apps/web`
- [ ] Docker Environment
    - [ ] Create `docker-compose.yml` for PostgreSQL 15
    - [ ] Verify local connection from both apps
- [ ] CI/CD Skeleton
    - [ ] Create `.github/workflows/ci.yml`

## Dev Notes
- **Stack:** Turborepo, pnpm, Next.js 15, Python 3.11, FastAPI.
- **Reference:** See `docs/architecture.md` Section 5 (Repository Structure).
- **Python in Monorepo:** Ensure the Python app is treated as a distinct workspace if possible, or managed via a root-level script.
- **Prisma:** We are using Prisma 7. Ensure `previewFeatures` are configured if needed for serverless drivers.
```

---

### **File 2: `docs/stories/story-1.2.db-schema.md`**

```markdown
# Story 1.2: Database Schema & Client Generation

**Status:** Draft

## Story
**As a** System Architect,
**I want** to define the Prisma schema for Assets, Candles, and SentimentLogs,
**so that** the Python bot and Next.js frontend share a single source of truth.

## Acceptance Criteria
1.  `schema.prisma` defined with models: `Asset`, `Candle`, `SentimentLog`, `CouncilSession`, `Trade`.
2.  `pnpm db:push` successfully creates tables in local Postgres.
3.  Python `SQLModel` classes created in `apps/bot` that mirror the Prisma schema.
4.  Seeding script created to populate the Top 30 Assets (Symbol, ID) into the DB.

## Tasks / Subtasks
- [ ] Define Prisma Schema
    - [ ] Create `Asset` model (symbol, isActive)
    - [ ] Create `Candle` model (timestamp, open, high, low, close, volume)
    - [ ] Create `SentimentLog` model
    - [ ] Create `CouncilSession` model
    - [ ] Create `Trade` model
- [ ] Migration & Generation
    - [ ] Run `pnpm db:push` to sync local DB
    - [ ] Generate Prisma Client
- [ ] Python SQLModel Mirroring
    - [ ] Create `apps/bot/models.py`
    - [ ] Define SQLModel classes matching Prisma schema exactly
- [ ] Seeding
    - [ ] Create `packages/database/seed.ts`
    - [ ] Populate list of Top 30 Kraken Assets (SOL/USD, DOT/USD, etc.)

## Dev Notes
- **Source of Truth:** Prisma is master. Python models must align manually or via a generation script if you prefer, but manual mirror is fine for now.
- **Indexes:** Ensure `Candle` has a compound index on `[assetId, timestamp]` for fast retrieval.
- **Reference:** See `docs/architecture.md` Section 4 (Data Models).
```

---

### **File 3: `docs/stories/story-1.3.kraken-ingest.md`**

```markdown
# Story 1.3: Kraken Data Ingestor (Python)

**Status:** Draft

## Story
**As a** Data Engineer,
**I want** to build a Python service that polls Kraken API every 15 minutes,
**so that** we have a continuous stream of OHLCV data for our target assets.

## Acceptance Criteria
1.  Python service uses `ccxt` or `httpx` to fetch OHLCV for the 30 active assets.
2.  Scheduler (e.g., `APScheduler`) triggers job exactly at 00, 15, 30, 45 minutes past the hour.
3.  Data is upserted into Supabase `Candle` table.
4.  Error handling: Retry logic implemented if Kraken API times out (3 retries).

## Tasks / Subtasks
- [ ] Kraken Client Setup
    - [ ] Install `ccxt` (Crypto library) or `httpx`
    - [ ] Configure `KRAKEN_API_KEY` (even if public endpoints don't need it, good practice)
- [ ] Database Connection (Python)
    - [ ] Setup `AsyncSession` with SQLModel connecting to Postgres
- [ ] Polling Logic
    - [ ] Create function `fetch_ohlcv(asset_pair)`
    - [ ] Implement loop for all active assets from DB
    - [ ] Implement `upsert` logic (do not duplicate candles)
- [ ] Scheduler Implementation
    - [ ] Install `APScheduler`
    - [ ] Configure CronTrigger for `*/15 * * * *`
    - [ ] Ensure main thread keeps running (Daemon mode)

## Dev Notes
- **Rate Limits:** Kraken Public API is generous, but ensure we don't hit limits by querying 30 assets instantly. Add a small `sleep(0.5)` between calls if needed.
- **Data Integrity:** Timestamps should be UTC.
```

---

### **File 4: `docs/stories/story-1.4.sentiment-ingest.md`**

```markdown
# Story 1.4: Sentiment Ingestor (LunarCrush/Socials)

**Status:** Draft

## Story
**As a** Quant,
**I want** to fetch social sentiment metrics every 15 minutes,
**so that** the Sentiment Agent has raw data to analyze.

## Acceptance Criteria
1.  Service fetches "Galaxy Score" or "AltRank" (or raw volume) from LunarCrush API.
2.  Service scrapes/fetches latest messages from configured Telegram/Bluesky sources (stubbed/mocked if API access pending).
3.  Data stored in `SentimentLog` table linked to the `Asset`.

## Tasks / Subtasks
- [ ] LunarCrush Integration
    - [ ] Obtain API Key (or use free tier endpoints/mock for dev)
    - [ ] Create `fetch_galaxy_score(symbol)`
- [ ] Bluesky/Telegram Scrapers
    - [ ] Create basic scraper module `apps/bot/services/socials.py`
    - [ ] Implement Bluesky public feed fetcher (using `atproto` lib if available or simple RSS/JSON)
    - [ ] Implement Telegram fetcher (Telethon or similar - *Note: Be careful with auth*)
- [ ] Database Storage
    - [ ] Map raw text/scores to `SentimentLog` model
    - [ ] Save to DB
- [ ] Integration with Scheduler
    - [ ] Add to the 15-minute loop alongside Kraken ingest

## Dev Notes
- **Mocking:** If API keys are not ready, build the structure and return random/mock data to prove the pipeline works.
- **Cost:** Be mindful of API quotas on LunarCrush.
```

---

**Next Steps:**
1.  Save these files.
2.  Start development with **Story 1.1**.
3.  When you are ready to code, summon the **Developer Agent**: `*agent dev`.

**Ready to start coding?**