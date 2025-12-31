# Product Requirements Document (PRD): ContrarianAI

**Version:** 1.0
**Date:** 2025-12-31
**Status:** Approved

## 1. Goals and Background Context

### 1.1 Goals
*   **Primary:** Create an automated trading system that outperforms Bitcoin's % ROI over a 3-month period.
*   **Risk:** Maintain a maximum portfolio drawdown of <20% using dynamic volatility-based risk management.
*   **Proof:** Successfully execute and log at least 50 automated trades to statistically validate the "Sentiment/Technical Divergence" thesis.
*   **Foundation:** Build a scalable architecture (LangGraph/Python/Supabase) capable of supporting multi-tenant SaaS expansion in V2.

### 1.2 Background Context
Retail crypto traders consistently underperform because they trade on emotion—panic-selling during "FUD" (Fear, Uncertainty, Doubt) and FOMO-buying tops. "ContrarianAI" is an automated investment system designed to exploit this behavior. It uses a "Council of AI Agents" powered by **Gemini 3** to synthesize Sentiment (Text), Technicals (Data), and Chart Patterns (Vision). The system executes "Long-Only" trades specifically when retail sentiment is at "Extreme Fear" but smart money/technicals show accumulation strength.

### 1.3 Change Log
| Date | Version | Description | Author |
| :--- | :--- | :--- | :--- |
| 2025-12-31 | 1.0 | Initial MVP Requirements | John (PM) |

## 2. Requirements

### 2.1 Functional Requirements (FR)

**Data Ingestion (The Senses)**
*   **FR1:** System must poll **Kraken API** every **15 minutes** to ingest OHLCV (Open, High, Low, Close, Volume) data for the target Top 30 Altcoins.
*   **FR2:** System must ingest aggregated sentiment data (via LunarCrush or similar) and scrape custom sources (Bluesky/Telegram) on the same 15-minute interval.
*   **FR3:** System must store all raw inputs in Supabase for historical backtesting and audit logs.

**The "Council" Logic (The Brain)**
*   **FR4:** **Sentiment Agent:** Must process text data and output a normalized "Fear Score" (0-100).
*   **FR5:** **Technical Agent:** Must calculate indicators (RSI, SMA 50/200, Volume Delta) to identify support/resistance zones.
*   **FR6:** **Vision Agent:** Must analyze generated chart images to identify visual bullish reversal patterns (e.g., "Wyckoff Spring", "Double Bottom").
*   **FR7:** **Master Node:** Must synthesize outputs and generate a BUY signal **ONLY** when:
    *   Sentiment Score < 20 (Extreme Fear)
    *   Technical Agent confirms Support/Uptrend
    *   Vision Agent confirms Validity (rejects "scam wicks")

**Execution & Risk (The Hands)**
*   **FR8:** System must execute "Market Buy" orders on Kraken via API when a signal is confirmed.
*   **FR9:** **Dynamic Stop Loss:** Upon entry, calculate ATR (Average True Range) and place Stop Loss at `Entry - (2 * ATR)`.
*   **FR10:** **Trailing Stop:** Monitor price every 15m; if price increases by [X]%, move Stop Loss to Breakeven, then trail price to lock in profits.

### 2.2 Non-Functional Requirements (NFR)
*   **NFR1 (Reliability):** The 15-minute polling loop must be robust; if a cycle is missed, an alert must be logged.
*   **NFR2 (Security):** API Keys (Kraken, LunarCrush) must be stored in environment variables/Secrets management, NEVER in the database or code.
*   **NFR3 (Latency):** "Council" decision process must complete within 2 minutes of the candle close to ensure timely entry.
*   **NFR4 (Compliance):** System must adhere to Kraken's API rate limits to avoid IP bans.

## 3. User Interface Design Goals

**3.1 Overall UX Vision**
A "Mission Control" aesthetic. Dark mode, high data density, designed for trust and transparency. The user needs to see *why* the bot is making decisions, not just *what* decisions it made.

**3.2 Core Screens**
*   **Dashboard (Home):**
    *   **"The Council Chamber":** A chat-like feed showing the live deliberation between agents (e.g., "Sentiment Agent: Panic detected on X... Technical Agent: But support holds at $1.20...").
    *   **Active Positions:** Card view of current trades with live P&L and dynamic Stop Loss visualization.
*   **Market Scanner:** A heatmap of the Top 30 coins sorted by "Divergence Score" (Gap between Sentiment and Technicals).
*   **Settings:** API Key management and Risk parameter configuration (e.g., Max Drawdown limit).

**3.3 Branding**
*   **Theme:** "Institutional Dark." Deep blacks/greys with neon accents (Green for Profit, Red for Loss/Risk).
*   **Typography:** Monospace fonts for data/logs (e.g., JetBrains Mono), clean Sans-Serif for UI.

## 4. Technical Assumptions

*   **Repository:** Monorepo (TurboRepo or Nx).
*   **Frontend:** Next.js 15 (App Router), Tailwind CSS, Shadcn UI, Recharts (for charts).
*   **Backend:** Python 3.11+, FastAPI.
*   **Agent Framework:** **LangGraph** (for stateful multi-agent orchestration).
*   **Database:** Supabase (PostgreSQL).
*   **AI Engine:** Google Gemini 3 (via Vertex AI SDK).
*   **Infrastructure:** Vercel (Frontend), Railway/DigitalOcean (Backend Worker).

## 5. Epic List

### Epic 1: Foundation & Data Pipeline
**Goal:** Establish the monorepo, backend infrastructure, and live 15-minute data ingestion for Price and Sentiment.
*   Set up Monorepo (Next.js + Python).
*   Configure Supabase Schema (`assets`, `candles`, `sentiment_logs`).
*   Implement Kraken API Client (Read-Only).
*   Implement Sentiment Ingestors (LunarCrush + Custom Scrapers).
*   Create Scheduler (15-min heartbeat) to populate DB.

### Epic 2: The "AI Council" Engine
**Goal:** Implement the LangGraph multi-agent reasoning system to generate "Paper Trading" signals.
*   Implement **Sentiment Agent** (Text Analysis -> Score).
*   Implement **Technical Agent** (Pandas/TA-Lib -> Indicators).
*   Implement **Vision Agent** (Matplotlib Chart Gen -> Gemini Vision -> Analysis).
*   Implement **Master Node** (Synthesis & Decision Logic).
*   Build "Signal Logger" to record decisions without executing trades.

### Epic 3: Execution & Risk Management
**Goal:** Enable real trading with robust risk controls (Stops/Exits).
*   Implement Kraken Order Execution (Buy/Sell).
*   Implement Dynamic Stop Loss (ATR Calculation).
*   Implement Trailing Stop Logic (Position Management).
*   Build "Safety Switch" (Global Kill Switch if drawdown > 20%).

### Epic 4: Mission Control Dashboard
**Goal:** Build the UI to visualize the bot's operations and performance.
*   Setup Next.js + Shadcn UI.
*   Build "Council Chamber" Feed component.
*   Build "Active Positions" & P&L Dashboard.
*   Integrate Auth (Supabase) for secure access.