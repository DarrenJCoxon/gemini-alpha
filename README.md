# ContrarianAI Trading Bot

An AI-powered cryptocurrency trading bot that uses **contrarian sentiment analysis** - buying when others are fearful and selling when others are greedy.

Built with a **Council of AI Agents** architecture using LangGraph, where multiple specialized AI agents analyze different aspects of the market and a Master Node synthesizes their insights into trading decisions.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         Council of AI Agents                                │
├──────────────────┬──────────────────┬──────────────────┬───────────────────┤
│  Sentiment Agent │  Technical Agent │   Vision Agent   │    Master Node    │
│                  │                  │                  │                   │
│  "People are     │  "RSI is         │  "I see a        │  "Everyone is     │
│   scared"        │   oversold"      │   double bottom" │   scared...       │
│                  │                  │                  │   → BUY"          │
└──────────────────┴──────────────────┴──────────────────┴───────────────────┘
```

## Features

- **Contrarian Trading Philosophy**: Buy on extreme fear, sell on extreme greed
- **Multi-Agent AI Council**: 4 specialized agents analyze markets from different angles
- **Real-time Sentiment**: Fear & Greed Index, Telegram channels, LunarCrush social data
- **Technical Analysis**: RSI, moving averages, volume analysis
- **Chart Vision**: AI visually analyzes candlestick charts for patterns
- **Paper Trading Mode**: Test strategies without risking real money
- **Terminal Dashboard (TUI)**: Beautiful Rich-powered terminal interface
- **Kraken Integration**: Execute trades on Kraken exchange

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              Data Sources                                   │
├─────────────────┬─────────────────┬─────────────────┬──────────────────────┤
│  Kraken API     │  Telegram       │  LunarCrush     │  Fear & Greed Index  │
│  (OHLCV Data)   │  (Social Posts) │  (Social Stats) │  (Market Sentiment)  │
└────────┬────────┴────────┬────────┴────────┬────────┴──────────┬───────────┘
         │                 │                 │                   │
         ▼                 ▼                 ▼                   ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         LangGraph State Machine                             │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐    │
│  │  Sentiment   │─▶│  Technical   │─▶│   Vision     │─▶│   Master     │    │
│  │    Agent     │  │    Agent     │  │    Agent     │  │    Node      │    │
│  └──────────────┘  └──────────────┘  └──────────────┘  └──────────────┘    │
└─────────────────────────────────────────────────────────────────────────────┘
                                        │
                                        ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                           Trading Decision                                  │
│                     BUY  │  SELL  │  HOLD                                   │
└─────────────────────────────────────────────────────────────────────────────┘
                                        │
                                        ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         Kraken Execution                                    │
│                   (Paper Mode or Live Trading)                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Prerequisites

- **Python 3.11+**
- **Node.js 20+** and **pnpm 10+**
- **Docker** (for PostgreSQL)
- **API Keys** (see Configuration section)

## Quick Start

### 1. Clone and Install

```bash
git clone <repository-url>
cd contrarian-ai

# Install Node.js dependencies
pnpm install

# Set up Python environment
cd apps/bot
python3 -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cd ../..
```

### 2. Configure Environment

```bash
# Copy the example environment file
cp .env.example .env

# Edit .env with your API keys (see Configuration section below)
```

### 3. Start Database

```bash
# Start PostgreSQL with Docker
docker-compose up -d

# Generate Prisma client and push schema
pnpm db:generate
pnpm db:push
```

### 4. Run the Bot

```bash
cd apps/bot
source .venv/bin/activate

# Start the bot server
python main.py

# In another terminal, run the TUI dashboard
python tui.py
```

## Configuration

Copy `.env.example` to `.env` and configure the following:

### Required API Keys

| Service | Purpose | Get Key From |
|---------|---------|--------------|
| **Kraken** | Price data & trading | [kraken.com/u/security/api](https://www.kraken.com/u/security/api) |
| **Google AI (Gemini)** | AI agents (LLM) | [aistudio.google.com/app/apikey](https://aistudio.google.com/app/apikey) |

### Optional API Keys (Enhanced Sentiment)

| Service | Purpose | Get Key From |
|---------|---------|--------------|
| **Telegram** | Social sentiment scraping | [my.telegram.org/apps](https://my.telegram.org/apps) |
| **LunarCrush** | Social metrics & galaxy scores | [lunarcrush.com/developers](https://lunarcrush.com/developers) |
| **CryptoPanic** | News sentiment | [cryptopanic.com/developers/api](https://cryptopanic.com/developers/api/) |

### Environment Variables

```bash
# Database (works with docker-compose defaults)
DATABASE_URL="postgresql://contrarian:contrarian_dev@localhost:5432/contrarian_ai"

# Kraken API
KRAKEN_API_KEY="your-api-key"
KRAKEN_API_SECRET="your-api-secret"
KRAKEN_SANDBOX_MODE="true"  # IMPORTANT: Keep true for testing!

# Google Gemini AI (required for AI agents)
GOOGLE_AI_API_KEY="your-gemini-api-key"
GEMINI_MODEL="gemini-1.5-flash"

# Telegram (optional - for social sentiment)
TELEGRAM_API_ID="your-api-id"
TELEGRAM_API_HASH="your-api-hash"
TELEGRAM_PHONE="+1234567890"

# LunarCrush (optional)
LUNARCRUSH_API_KEY="your-key"

# Bot settings
BOT_PORT=8000
```

### Telegram First-Time Setup

If using Telegram sentiment scraping, you need to authenticate once:

```bash
cd apps/bot
source .venv/bin/activate
python -m services.socials.telegram_auth
```

This creates a session file that persists your authentication.

## Running the Bot

### Terminal Dashboard (TUI)

The beautiful terminal interface for monitoring:

```bash
cd apps/bot
python tui.py
```

**Keyboard Commands:**
- `r` - Refresh display
- `t` - Run test council session
- `p` - Pause/unpause trading
- `c` - Info about council cycle
- `q` - Quit

### Bot Server

The FastAPI backend that runs the trading logic:

```bash
cd apps/bot
python main.py
```

**API Endpoints:**
- `GET /health` - Health check
- `GET /api/council/test` - Run a test council session
- `GET /api/status` - Get system status
- `GET /docs` - OpenAPI documentation

### Web Dashboard (Optional)

```bash
# From project root
pnpm --filter @contrarian-ai/web dev
```

Access at http://localhost:3000

## Project Structure

```
contrarian-ai/
├── apps/
│   ├── bot/                    # Python Trading Engine
│   │   ├── core/               # LangGraph state machine
│   │   │   ├── graph.py        # Graph definition
│   │   │   └── state.py        # State types
│   │   ├── nodes/              # AI Agent implementations
│   │   │   ├── sentiment.py    # Sentiment Agent
│   │   │   ├── technical.py    # Technical Agent
│   │   │   ├── vision.py       # Vision Agent
│   │   │   └── master.py       # Master Node
│   │   ├── services/           # External integrations
│   │   │   ├── kraken.py       # Kraken API client
│   │   │   ├── fear_greed.py   # Fear & Greed Index
│   │   │   ├── lunarcrush.py   # LunarCrush API
│   │   │   └── socials/        # Telegram scraping
│   │   ├── main.py             # FastAPI entry point
│   │   ├── tui.py              # Terminal dashboard
│   │   └── config.py           # Configuration
│   └── web/                    # Next.js Dashboard
├── packages/
│   └── database/               # Shared Prisma schema
├── docker-compose.yml          # Local PostgreSQL
└── .env.example                # Environment template
```

## How the AI Council Works

### 1. Sentiment Agent
Analyzes market mood from multiple sources:
- Fear & Greed Index (0-100 scale)
- Telegram channel mentions
- LunarCrush social metrics

**Contrarian Logic:** Fear score < 25 = BUY opportunity, > 75 = SELL opportunity

### 2. Technical Agent
Calculates technical indicators:
- RSI (Relative Strength Index)
- 50/200 period moving averages
- Volume analysis

**Output:** BULLISH / BEARISH / NEUTRAL signal with strength score

### 3. Vision Agent
Uses Gemini's vision capabilities to analyze chart images:
- Pattern recognition (head & shoulders, double bottoms, etc.)
- Support/resistance levels
- "Scam wick" detection

### 4. Master Node
Synthesizes all agent inputs:
1. **Pre-validation**: Checks for extreme conditions
2. **LLM Synthesis**: Weighs all factors with contrarian bias
3. **Safety Override**: Blocks dangerous trades

**Output:** Final BUY / SELL / HOLD decision with reasoning

## Safety Features

- **Paper Trading Mode**: Default mode logs trades without executing
- **Sandbox Mode**: Kraken sandbox for testing
- **Max Drawdown Protection**: Stops trading if losses exceed threshold
- **ATR-Based Stop Losses**: Dynamic risk management
- **Emergency Stop**: Manual kill switch

## Development

### Running Tests

```bash
cd apps/bot
pytest tests/ -v
```

### Database Management

```bash
# Open Prisma Studio (visual database browser)
pnpm db:studio

# Reset database
docker-compose down -v
docker-compose up -d
pnpm db:push
```

### Adding New Assets

Assets are managed in the database. Use Prisma Studio or the API to add new trading pairs.

## Troubleshooting

### Bot won't start
1. Check PostgreSQL is running: `docker-compose ps`
2. Verify `.env` file exists with correct values
3. Ensure virtual environment is activated

### Telegram authentication fails
1. Verify API ID and hash are correct
2. Run `python -m services.socials.telegram_auth` interactively
3. Check phone number format includes country code

### No sentiment data
1. Check API keys are configured
2. Fear & Greed Index works without API key
3. Telegram requires authentication (see above)

### TUI shows "NO_DB"
1. Start PostgreSQL: `docker-compose up -d`
2. Check DATABASE_URL in `.env`
3. Run `pnpm db:push` to create tables

## Tech Stack

| Component | Technology |
|-----------|------------|
| AI Orchestration | LangGraph |
| LLM | Google Gemini 1.5 |
| Backend | Python, FastAPI |
| Database | PostgreSQL, Prisma |
| TUI | Rich |
| Exchange | Kraken API |
| Frontend | Next.js 15, React 19 |

## License

MIT

## Disclaimer

This software is for educational purposes only. Cryptocurrency trading involves substantial risk of loss. Never trade with money you cannot afford to lose. The authors are not responsible for any financial losses incurred through the use of this software.

**Always start with `KRAKEN_SANDBOX_MODE="true"` and thoroughly test before considering live trading.**
