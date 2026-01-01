# ContrarianAI Trading Bot - Development Guide

## Quick Start

### Start the Bot Server
```bash
cd apps/bot
source .venv/bin/activate
uvicorn main:app --host 0.0.0.0 --port 8000
```

### Start the TUI Dashboard
```bash
cd apps/bot
source .venv/bin/activate
python tui.py
```

### Start PostgreSQL (if not running)
```bash
docker-compose up -d
```

## Project Structure

```
apps/bot/           # Python trading engine
├── core/           # LangGraph state machine (graph.py, state.py)
├── nodes/          # AI Agents (sentiment.py, technical.py, vision.py, master.py)
├── services/       # External APIs (kraken.py, fear_greed.py, telegram.py, etc.)
├── main.py         # FastAPI application (run with uvicorn)
├── tui.py          # Rich terminal dashboard
└── config.py       # Configuration management

packages/database/  # Prisma schema
apps/web/           # Next.js dashboard (optional)
```

## Key Commands

| Task | Command |
|------|---------|
| Start bot | `uvicorn main:app --host 0.0.0.0 --port 8000` |
| Start TUI | `python tui.py` |
| Run tests | `pytest tests/ -v` |
| DB studio | `pnpm db:studio` |
| DB push | `pnpm db:push` |
| Health check | `curl http://localhost:8000/health` |

## Architecture

### Council of AI Agents (LangGraph)
```
Sentiment Agent → Technical Agent → Vision Agent → Master Node → Decision
```

- **Sentiment Agent**: Fear & Greed Index, Telegram, LunarCrush
- **Technical Agent**: RSI, moving averages, volume analysis
- **Vision Agent**: Chart pattern recognition via Gemini Vision
- **Master Node**: Synthesizes inputs, applies contrarian logic

### Contrarian Strategy
- **BUY** when Fear & Greed < 25 (extreme fear)
- **SELL** when Fear & Greed > 75 (extreme greed)
- Always requires multi-factor confirmation

## Environment Variables

Required in `.env`:
```bash
DATABASE_URL          # PostgreSQL connection
KRAKEN_API_KEY        # Kraken exchange
KRAKEN_API_SECRET
KRAKEN_SANDBOX_MODE   # "true" for paper trading
GOOGLE_AI_API_KEY     # Gemini for AI agents
```

Optional:
```bash
TELEGRAM_API_ID       # Social sentiment
TELEGRAM_API_HASH
CRYPTOPANIC_API_KEY   # News sentiment
LUNARCRUSH_API_KEY    # Social metrics
```

## Code Patterns

### Database Access
Use asyncpg for direct queries or Prisma client:
```python
async with db_pool.acquire() as conn:
    rows = await conn.fetch("SELECT * FROM ...")
```

### Adding New Agents/Nodes
1. Create node function in `nodes/`
2. Add to graph in `core/graph.py`
3. Update `GraphState` in `core/state.py` if new fields needed

### API Endpoints
FastAPI routes in `main.py`:
- `GET /health` - Health check
- `GET /api/council/test` - Test council session
- `GET /api/status` - System status

## Testing

```bash
# Run all tests
pytest tests/ -v

# Run specific test
pytest tests/test_graph.py -v

# With coverage
pytest tests/ --cov=. --cov-report=html
```

## Safety Rules

1. **NEVER** set `KRAKEN_SANDBOX_MODE=false` without explicit confirmation
2. **NEVER** commit `.env` file (only `.env.example`)
3. **ALWAYS** test with paper trading first
4. **ALWAYS** check max drawdown settings before live trading

## Current Epic

**Epic 5: Profitability Optimization**
- Story 5.1: Market Regime Filter (CRITICAL)
- Story 5.2: Asset Universe Reduction
- Story 5.3: Multi-Factor Confirmation
- Story 5.4: Scale In/Out Positions
- Story 5.5: Risk Parameter Optimization
- Story 5.6: On-Chain Data Integration
- Story 5.7: Enhanced Technical Indicators
