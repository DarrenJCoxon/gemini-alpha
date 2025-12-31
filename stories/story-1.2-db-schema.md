# Story 1.2: Database Schema & Client Generation

**Status:** Approved
**Epic:** 1 - Foundation & Data Pipeline
**Priority:** Critical (Blocking)

---

## Story

**As a** System Architect,
**I want** to define the Prisma schema for Assets, Candles, and SentimentLogs,
**so that** the Python bot and Next.js frontend share a single source of truth.

---

## Acceptance Criteria

1. `schema.prisma` defined with models: `Asset`, `Candle`, `SentimentLog`, `CouncilSession`, `Trade`.
2. `pnpm db:push` successfully creates tables in local Postgres.
3. Python `SQLModel` classes created in `apps/bot` that mirror the Prisma schema.
4. Seeding script created to populate the Top 30 Assets (Symbol, ID) into the DB.

---

## Tasks / Subtasks

### Phase 1: Prisma Schema Definition

- [ ] **Create `Asset` model**
  - [ ] Add `id` field (String, cuid, @id)
  - [ ] Add `symbol` field (String, unique) - e.g., "SOLUSD", "DOTUSD"
  - [ ] Add `name` field (String, optional) - e.g., "Solana", "Polkadot"
  - [ ] Add `isActive` field (Boolean, default: true)
  - [ ] Add `lastPrice` field (Decimal, optional)
  - [ ] Add `lastUpdated` field (DateTime, optional)
  - [ ] Add `createdAt` field (DateTime, default: now())
  - [ ] Add relations to `Candle`, `SentimentLog`, `CouncilSession`, `Trade`

- [ ] **Create `Candle` model**
  - [ ] Add `id` field (String, cuid, @id)
  - [ ] Add `assetId` field (String, foreign key to Asset)
  - [ ] Add `timestamp` field (DateTime) - candle open time
  - [ ] Add `timeframe` field (String, default: "15m")
  - [ ] Add `open` field (Decimal)
  - [ ] Add `high` field (Decimal)
  - [ ] Add `low` field (Decimal)
  - [ ] Add `close` field (Decimal)
  - [ ] Add `volume` field (Decimal)
  - [ ] Add compound unique constraint on `[assetId, timestamp, timeframe]`
  - [ ] Add compound index on `[assetId, timestamp]` for fast lookup

- [ ] **Create `SentimentLog` model**
  - [ ] Add `id` field (String, cuid, @id)
  - [ ] Add `assetId` field (String, foreign key to Asset)
  - [ ] Add `timestamp` field (DateTime)
  - [ ] Add `source` field (String) - e.g., "lunarcrush", "telegram", "bluesky"
  - [ ] Add `galaxyScore` field (Int, optional) - LunarCrush metric (0-100)
  - [ ] Add `altRank` field (Int, optional) - LunarCrush ranking
  - [ ] Add `socialVolume` field (Int, optional) - mention count
  - [ ] Add `rawText` field (String, optional) - scraped content sample
  - [ ] Add `sentimentScore` field (Int, optional) - normalized score (0-100)
  - [ ] Add `createdAt` field (DateTime, default: now())
  - [ ] Add index on `[assetId, timestamp]`

- [ ] **Create `CouncilSession` model** (Critical for UI)
  - [ ] Add `id` field (String, cuid, @id)
  - [ ] Add `assetId` field (String, foreign key to Asset)
  - [ ] Add `timestamp` field (DateTime) - session start time
  - [ ] Add `sentimentScore` field (Int) - Fear Score (0-100)
  - [ ] Add `technicalSignal` field (String) - "BUY", "SELL", "NEUTRAL"
  - [ ] Add `technicalDetails` field (Json, optional) - RSI, SMA values
  - [ ] Add `visionAnalysis` field (String, optional) - pattern description
  - [ ] Add `visionConfidence` field (Decimal, optional) - 0.0-1.0
  - [ ] Add `finalDecision` field (Enum: BUY, HOLD, SELL)
  - [ ] Add `reasoningLog` field (String) - full AI synthesis explanation
  - [ ] Add `executedTradeId` field (String, optional) - link to resulting trade
  - [ ] Add `createdAt` field (DateTime, default: now())
  - [ ] Add index on `[assetId, timestamp]`

- [ ] **Create `Trade` model**
  - [ ] Add `id` field (String, cuid, @id)
  - [ ] Add `assetId` field (String, foreign key to Asset)
  - [ ] Add `councilSessionId` field (String, optional, foreign key)
  - [ ] Add `status` field (Enum: PENDING, OPEN, CLOSED, CANCELLED)
  - [ ] Add `side` field (String, default: "BUY") - Long-only system
  - [ ] Add `entryPrice` field (Decimal)
  - [ ] Add `size` field (Decimal) - position size in base currency
  - [ ] Add `entryTime` field (DateTime)
  - [ ] Add `stopLossPrice` field (Decimal) - dynamic, updated by bot
  - [ ] Add `takeProfitPrice` field (Decimal, optional)
  - [ ] Add `exitPrice` field (Decimal, optional)
  - [ ] Add `exitTime` field (DateTime, optional)
  - [ ] Add `pnl` field (Decimal, optional) - profit/loss in quote currency
  - [ ] Add `pnlPercent` field (Decimal, optional) - percentage P&L
  - [ ] Add `exitReason` field (String, optional) - "STOP_LOSS", "TAKE_PROFIT", "MANUAL"
  - [ ] Add `krakenOrderId` field (String, optional) - external reference
  - [ ] Add `createdAt` field (DateTime, default: now())
  - [ ] Add `updatedAt` field (DateTime, @updatedAt)

- [ ] **Create Enums**
  - [ ] Create `Decision` enum: BUY, HOLD, SELL
  - [ ] Create `TradeStatus` enum: PENDING, OPEN, CLOSED, CANCELLED

### Phase 2: Migration & Generation

- [ ] **Push schema to local database**
  - [ ] Ensure Docker PostgreSQL is running: `docker-compose up -d`
  - [ ] Run `pnpm db:push` from root
  - [ ] Verify tables created via `pnpm db:studio`
  - [ ] Capture any errors and resolve

- [ ] **Generate Prisma Client**
  - [ ] Run `pnpm db:generate`
  - [ ] Verify client generated in `packages/database/generated/client`
  - [ ] Test import in `apps/web`: `import { PrismaClient } from '@contrarian-ai/database'`

### Phase 3: Python SQLModel Mirroring

- [ ] **Create Python models file**
  - [ ] Create `apps/bot/models/base.py` with SQLModel base configuration
  - [ ] Create `apps/bot/models/asset.py` with Asset model
  - [ ] Create `apps/bot/models/candle.py` with Candle model
  - [ ] Create `apps/bot/models/sentiment.py` with SentimentLog model
  - [ ] Create `apps/bot/models/council.py` with CouncilSession model
  - [ ] Create `apps/bot/models/trade.py` with Trade model
  - [ ] Create `apps/bot/models/__init__.py` exporting all models

- [ ] **Implement Asset SQLModel**
  ```python
  class Asset(SQLModel, table=True):
      __tablename__ = "Asset"
      id: str = Field(primary_key=True)
      symbol: str = Field(unique=True, index=True)
      name: Optional[str] = None
      is_active: bool = Field(default=True, sa_column_kwargs={"name": "isActive"})
      last_price: Optional[Decimal] = Field(sa_column_kwargs={"name": "lastPrice"})
      last_updated: Optional[datetime] = Field(sa_column_kwargs={"name": "lastUpdated"})
      created_at: datetime = Field(default_factory=datetime.utcnow, sa_column_kwargs={"name": "createdAt"})
  ```

- [ ] **Implement Candle SQLModel**
  - [ ] Match all Prisma fields with snake_case to camelCase mapping
  - [ ] Add `sa_column_kwargs` for proper column name mapping

- [ ] **Implement SentimentLog SQLModel**
  - [ ] Match all Prisma fields
  - [ ] Handle optional fields properly with `Optional[T]`

- [ ] **Implement CouncilSession SQLModel**
  - [ ] Match all Prisma fields
  - [ ] Create Python enum for Decision type
  - [ ] Handle JSON field for technicalDetails

- [ ] **Implement Trade SQLModel**
  - [ ] Match all Prisma fields
  - [ ] Create Python enum for TradeStatus

- [ ] **Configure database connection**
  - [ ] Update `apps/bot/database.py` with SQLModel engine setup
  - [ ] Add async session factory
  - [ ] Test basic CRUD operations

### Phase 4: Seeding Script

- [ ] **Create seed data file**
  - [ ] Create `packages/database/prisma/seed.ts`
  - [ ] Define Top 30 Kraken trading pairs (per PRD FR1)

- [ ] **Implement seeding logic**
  ```typescript
  const TOP_30_ASSETS = [
    { symbol: "BTCUSD", name: "Bitcoin" },
    { symbol: "ETHUSD", name: "Ethereum" },
    { symbol: "SOLUSD", name: "Solana" },
    { symbol: "DOTUSD", name: "Polkadot" },
    { symbol: "ADAUSD", name: "Cardano" },
    { symbol: "AVAXUSD", name: "Avalanche" },
    { symbol: "LINKUSD", name: "Chainlink" },
    { symbol: "MATICUSD", name: "Polygon" },
    { symbol: "ATOMUSD", name: "Cosmos" },
    { symbol: "UNIUSD", name: "Uniswap" },
    { symbol: "XLMUSD", name: "Stellar" },
    { symbol: "ALGOUSD", name: "Algorand" },
    { symbol: "NEARUSD", name: "NEAR Protocol" },
    { symbol: "FILUSD", name: "Filecoin" },
    { symbol: "APTUSD", name: "Aptos" },
    { symbol: "ARBUSD", name: "Arbitrum" },
    { symbol: "OPUSD", name: "Optimism" },
    { symbol: "INJUSD", name: "Injective" },
    { symbol: "SUIUSD", name: "Sui" },
    { symbol: "TIAUSD", name: "Celestia" },
    { symbol: "IMXUSD", name: "Immutable X" },
    { symbol: "RNDRUSD", name: "Render" },
    { symbol: "GRTUSD", name: "The Graph" },
    { symbol: "SANDUSD", name: "The Sandbox" },
    { symbol: "MANAUSD", name: "Decentraland" },
    { symbol: "AABORUSD", name: "Aave" },
    { symbol: "MKRUSD", name: "Maker" },
    { symbol: "SNXUSD", name: "Synthetix" },
    { symbol: "COMPUSD", name: "Compound" },
    { symbol: "LDOUSD", name: "Lido DAO" }
  ];
  ```

- [ ] **Configure seed script in Prisma**
  - [ ] Add `"prisma": { "seed": "ts-node prisma/seed.ts" }` to `package.json`
  - [ ] Install `ts-node` as dev dependency
  - [ ] Run `npx prisma db seed`
  - [ ] Verify 30 assets created via Prisma Studio

- [ ] **Create Python seed verification**
  - [ ] Create `apps/bot/scripts/verify_seed.py`
  - [ ] Query all assets and print count
  - [ ] Ensure Python can read seeded data

---

## Dev Notes

### Architecture Context

**Data Models (per `docs/core/architecture.md` Section 4):**

The Prisma schema is the **single source of truth**. Python SQLModel classes must mirror it exactly, with proper column name mapping for camelCase (Prisma) to snake_case (Python) conventions.

**Key Relationships:**
```
Asset 1---* Candle          (One asset has many candles)
Asset 1---* SentimentLog    (One asset has many sentiment logs)
Asset 1---* CouncilSession  (One asset has many council sessions)
Asset 1---* Trade           (One asset has many trades)
CouncilSession 1---0..1 Trade  (Session may result in a trade)
```

### Technical Specifications

**Prisma Schema Location:**
- `packages/database/prisma/schema.prisma`

**Complete Schema Definition:**
```prisma
generator client {
  provider = "prisma-client-js"
  output   = "../generated/client"
}

datasource db {
  provider = "postgresql"
  url      = env("DATABASE_URL")
}

enum Decision {
  BUY
  HOLD
  SELL
}

enum TradeStatus {
  PENDING
  OPEN
  CLOSED
  CANCELLED
}

model Asset {
  id           String   @id @default(cuid())
  symbol       String   @unique
  name         String?
  isActive     Boolean  @default(true)
  lastPrice    Decimal? @db.Decimal(18, 8)
  lastUpdated  DateTime?
  createdAt    DateTime @default(now())

  candles          Candle[]
  sentimentLogs    SentimentLog[]
  councilSessions  CouncilSession[]
  trades           Trade[]
}

model Candle {
  id        String   @id @default(cuid())
  assetId   String
  timestamp DateTime
  timeframe String   @default("15m")
  open      Decimal  @db.Decimal(18, 8)
  high      Decimal  @db.Decimal(18, 8)
  low       Decimal  @db.Decimal(18, 8)
  close     Decimal  @db.Decimal(18, 8)
  volume    Decimal  @db.Decimal(24, 8)

  asset Asset @relation(fields: [assetId], references: [id])

  @@unique([assetId, timestamp, timeframe])
  @@index([assetId, timestamp])
}

model SentimentLog {
  id             String   @id @default(cuid())
  assetId        String
  timestamp      DateTime
  source         String
  galaxyScore    Int?
  altRank        Int?
  socialVolume   Int?
  rawText        String?  @db.Text
  sentimentScore Int?
  createdAt      DateTime @default(now())

  asset Asset @relation(fields: [assetId], references: [id])

  @@index([assetId, timestamp])
}

model CouncilSession {
  id               String   @id @default(cuid())
  assetId          String
  timestamp        DateTime
  sentimentScore   Int
  technicalSignal  String
  technicalDetails Json?
  visionAnalysis   String?  @db.Text
  visionConfidence Decimal? @db.Decimal(3, 2)
  finalDecision    Decision
  reasoningLog     String   @db.Text
  executedTradeId  String?
  createdAt        DateTime @default(now())

  asset Asset  @relation(fields: [assetId], references: [id])
  trade Trade? @relation(fields: [executedTradeId], references: [id])

  @@index([assetId, timestamp])
}

model Trade {
  id               String      @id @default(cuid())
  assetId          String
  councilSessionId String?
  status           TradeStatus @default(PENDING)
  side             String      @default("BUY")
  entryPrice       Decimal     @db.Decimal(18, 8)
  size             Decimal     @db.Decimal(18, 8)
  entryTime        DateTime
  stopLossPrice    Decimal     @db.Decimal(18, 8)
  takeProfitPrice  Decimal?    @db.Decimal(18, 8)
  exitPrice        Decimal?    @db.Decimal(18, 8)
  exitTime         DateTime?
  pnl              Decimal?    @db.Decimal(18, 8)
  pnlPercent       Decimal?    @db.Decimal(8, 4)
  exitReason       String?
  krakenOrderId    String?
  createdAt        DateTime    @default(now())
  updatedAt        DateTime    @updatedAt

  asset           Asset            @relation(fields: [assetId], references: [id])
  councilSessions CouncilSession[]
}
```

### Python SQLModel Configuration

**Database Connection (`apps/bot/database.py`):**
```python
from sqlmodel import SQLModel, create_engine, Session
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
import os

DATABASE_URL = os.getenv("DATABASE_URL", "").replace(
    "postgresql://", "postgresql+asyncpg://"
)

async_engine = create_async_engine(DATABASE_URL, echo=True)

async def get_session() -> AsyncSession:
    async_session = sessionmaker(
        async_engine, class_=AsyncSession, expire_on_commit=False
    )
    async with async_session() as session:
        yield session
```

### Important Considerations

**Decimal Precision:**
- Price fields use `Decimal(18, 8)` for high precision (8 decimal places)
- Volume fields use `Decimal(24, 8)` for larger values
- P&L percentage uses `Decimal(8, 4)` for 4 decimal places

**Indexing Strategy (per Architecture Doc):**
- Compound index on `Candle[assetId, timestamp]` for fast OHLCV queries
- Index on `SentimentLog[assetId, timestamp]` for sentiment retrieval
- Index on `CouncilSession[assetId, timestamp]` for council history

**Column Naming:**
- Prisma uses camelCase (JavaScript convention)
- Python uses snake_case (PEP 8)
- Use `sa_column_kwargs={"name": "columnName"}` in SQLModel for mapping

### Dependencies & Prerequisites

- **Story 1.1:** Must be completed (Turborepo, Prisma, Docker)

### Downstream Dependencies

- **Story 1.3:** Uses Candle model for OHLCV data storage
- **Story 1.4:** Uses SentimentLog model for sentiment storage
- **Epic 2:** Uses CouncilSession model for agent deliberation
- **Epic 3:** Uses Trade model for order execution
- **Epic 4:** Dashboard reads all models for visualization

---

## Testing Strategy

### Unit Tests
- [ ] Prisma Client can instantiate and connect
- [ ] SQLModel classes can instantiate with valid data
- [ ] Enum types serialize/deserialize correctly

### Integration Tests
- [ ] Create Asset via Prisma, read via SQLModel
- [ ] Create Candle with foreign key constraint satisfied
- [ ] Unique constraint on Candle prevents duplicates
- [ ] Seed script populates exactly 30 assets

### Manual Testing Scenarios
1. Run `pnpm db:push` - verify no errors
2. Run `pnpm db:studio` - verify all 5 tables visible
3. Run seed script - verify 30 assets in Asset table
4. Run Python verification script - confirm Python reads 30 assets

### Acceptance Criteria Validation
- [x] AC1: All 5 models defined in schema.prisma
- [x] AC2: `pnpm db:push` creates tables successfully
- [x] AC3: Python SQLModel classes mirror Prisma exactly
- [x] AC4: Seed script populates 30 assets

---

## Technical Considerations

### Security
- No sensitive data in seed script
- Database credentials remain in environment variables

### Performance
- Compound indexes critical for query performance on large datasets
- Consider partitioning Candle table by date in future

### Scalability
- Schema designed to support millions of candles (15-min intervals)
- CouncilSession grows at max 4 per hour per asset

### Data Integrity
- Unique constraint on Candle prevents duplicate ingestion
- Foreign key constraints ensure referential integrity
- Cascade deletes should be avoided (audit trail important)

### Edge Cases
- Handle Decimal conversion between JavaScript and Python
- Handle timezone-aware DateTime fields (always store UTC)
- Handle optional fields gracefully in both languages
