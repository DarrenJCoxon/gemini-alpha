# Contrarian AI Trading Platform

AI-powered cryptocurrency trading platform with contrarian sentiment analysis.

## Project Structure

```
contrarian-ai/
├── apps/
│   ├── web/                    # Next.js 15 Dashboard (Vercel)
│   │   ├── src/app/            # App Router
│   │   ├── src/components/     # Shadcn UI Components
│   │   └── src/lib/            # Utility functions
│   └── bot/                    # Python Trading Engine (Railway)
│       ├── core/               # LangGraph Definitions
│       ├── services/           # External API Services
│       ├── models/             # SQLModel Definitions
│       ├── database.py         # Database connection
│       └── main.py             # FastAPI Entry Point
├── packages/
│   ├── database/               # Shared Prisma Schema
│   │   ├── prisma/schema.prisma
│   │   └── index.ts            # Generated Client exports
│   └── types/                  # Shared TypeScript Interfaces
├── turbo.json                  # Turborepo Config
├── package.json                # Root (pnpm workspaces)
├── docker-compose.yml          # Local DB for dev
└── .github/workflows/ci.yml    # GitHub Actions CI
```

## Prerequisites

- Node.js 20.x or higher
- pnpm 10.x or higher
- Python 3.11 or higher
- Docker (for local PostgreSQL)

## Local Development Setup

### 1. Clone and Install Dependencies

```bash
# Clone the repository
git clone <repository-url>
cd contrarian-ai

# Install Node.js dependencies
pnpm install

# Generate Prisma client
pnpm db:generate
```

### 2. Set Up Environment Variables

```bash
# Copy example environment file
cp .env.example .env

# Edit .env with your configuration
# For local development, the default values should work with docker-compose
```

### 3. Start PostgreSQL with Docker

```bash
# Start the database
docker-compose up -d

# Verify it's running
docker-compose ps
```

### 4. Push Database Schema

```bash
# Push Prisma schema to database
pnpm db:push
```

### 5. Start Development Servers

```bash
# Start all apps (Next.js + FastAPI)
pnpm dev

# Or start individually:
# Next.js (web): http://localhost:3000
pnpm --filter @contrarian-ai/web dev

# FastAPI (bot): http://localhost:8000
# First, set up Python environment:
cd apps/bot
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

## Available Scripts

### Root Level

| Command | Description |
|---------|-------------|
| `pnpm dev` | Start all apps in development mode |
| `pnpm build` | Build all apps |
| `pnpm lint` | Run ESLint across all packages |
| `pnpm test` | Run tests across all packages |
| `pnpm db:generate` | Generate Prisma client |
| `pnpm db:push` | Push schema to database |
| `pnpm db:studio` | Open Prisma Studio |

### App-Specific

| Command | Description |
|---------|-------------|
| `pnpm --filter @contrarian-ai/web dev` | Start Next.js dev server |
| `pnpm --filter @contrarian-ai/web build` | Build Next.js app |
| `pnpm --filter @contrarian-ai/web test` | Run Next.js tests |

## Database Management

### Prisma Studio

```bash
pnpm db:studio
```

Opens a visual database browser at http://localhost:5555

### Schema Changes

1. Edit `packages/database/prisma/schema.prisma`
2. Run `pnpm db:generate` to update the client
3. Run `pnpm db:push` to apply changes to the database

## Python Bot Setup

```bash
cd apps/bot

# Create virtual environment
python -m venv .venv

# Activate virtual environment
source .venv/bin/activate  # macOS/Linux
# .venv\Scripts\activate   # Windows

# Install dependencies
pip install -r requirements.txt

# Run the bot
uvicorn main:app --reload --port 8000

# Access OpenAPI docs
# http://localhost:8000/docs
```

## Docker

### Start PostgreSQL

```bash
docker-compose up -d
```

### Stop PostgreSQL

```bash
docker-compose down
```

### Reset Database (warning: deletes all data)

```bash
docker-compose down -v
docker-compose up -d
pnpm db:push
```

## Troubleshooting

### Port Already in Use

If port 3000 (Next.js) or 5432 (PostgreSQL) is already in use:

```bash
# Find process using port
lsof -i :3000
lsof -i :5432

# Kill the process
kill -9 <PID>
```

### Prisma Client Not Found

```bash
pnpm db:generate
```

### Database Connection Issues

1. Verify PostgreSQL is running: `docker-compose ps`
2. Check DATABASE_URL in .env matches docker-compose.yml credentials
3. Try restarting: `docker-compose down && docker-compose up -d`

### Python Virtual Environment Issues

```bash
# Remove and recreate virtual environment
rm -rf apps/bot/.venv
cd apps/bot
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Tech Stack

- **Frontend**: Next.js 15, React 19, TypeScript, Tailwind CSS, Shadcn UI
- **Backend**: Python 3.11, FastAPI, SQLModel
- **Database**: PostgreSQL 15, Prisma 6
- **Build**: Turborepo, pnpm workspaces
- **Deployment**: Vercel (web), Railway (bot)

## License

MIT
