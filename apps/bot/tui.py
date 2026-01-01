#!/usr/bin/env python3
"""
ContrarianAI Terminal Dashboard
A lightweight TUI for monitoring and testing the trading bot.

Usage: python tui.py
"""

import asyncio
import os
import sys
from datetime import datetime, timedelta
from typing import Optional

# Add parent to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from rich.console import Console, Group
from rich.table import Table
from rich.panel import Panel
from rich.layout import Layout
from rich.live import Live
from rich.text import Text
from rich.prompt import Prompt, Confirm
from rich.align import Align
from rich import box

console = Console()

# Database connection
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://contrarian:contrarian_dev@localhost:5433/contrarian_ai")

# Try to import database client
try:
    import asyncpg
    HAS_DB = True
except ImportError:
    HAS_DB = False
    console.print("[yellow]asyncpg not installed - some features disabled[/yellow]")


class TradingDashboard:
    """Simple TUI Dashboard for ContrarianAI"""

    def __init__(self):
        self.db_pool: Optional[asyncpg.Pool] = None
        self.running = True

    async def connect_db(self):
        """Connect to database"""
        if not HAS_DB:
            return False
        try:
            self.db_pool = await asyncpg.create_pool(DATABASE_URL, min_size=1, max_size=5)
            return True
        except Exception as e:
            console.print(f"[red]Database connection failed: {e}[/red]")
            return False

    async def close_db(self):
        """Close database connection"""
        if self.db_pool:
            await self.db_pool.close()

    async def get_system_status(self) -> dict:
        """Get system configuration status"""
        if not self.db_pool:
            return {"status": "NO_DB", "tradingEnabled": False}

        try:
            async with self.db_pool.acquire() as conn:
                row = await conn.fetchrow(
                    'SELECT * FROM system_config ORDER BY "updatedAt" DESC LIMIT 1'
                )
                if row:
                    return dict(row)
                return {"status": "NOT_INITIALIZED", "tradingEnabled": False}
        except Exception as e:
            console.print(f"[red]DB Error: {e}[/red]")
            return {"status": "ERROR", "tradingEnabled": False}

    async def get_recent_sessions(self, limit: int = 10) -> list:
        """Get recent council sessions"""
        if not self.db_pool:
            return []

        try:
            async with self.db_pool.acquire() as conn:
                rows = await conn.fetch("""
                    SELECT cs.*, a.symbol
                    FROM "CouncilSession" cs
                    LEFT JOIN "Asset" a ON cs."assetId" = a.id
                    ORDER BY cs.timestamp DESC
                    LIMIT $1
                """, limit)
                return [dict(r) for r in rows]
        except Exception as e:
            console.print(f"[red]Error fetching sessions: {e}[/red]")
            return []

    async def get_open_trades(self) -> list:
        """Get open trades"""
        if not self.db_pool:
            return []

        try:
            async with self.db_pool.acquire() as conn:
                rows = await conn.fetch("""
                    SELECT t.*, a.symbol, a."lastPrice"
                    FROM "Trade" t
                    LEFT JOIN "Asset" a ON t."assetId" = a.id
                    WHERE t.status = 'OPEN'
                    ORDER BY t."entryTime" DESC
                """)
                return [dict(r) for r in rows]
        except Exception:
            return []

    async def get_assets(self) -> list:
        """Get all active assets"""
        if not self.db_pool:
            return []

        try:
            async with self.db_pool.acquire() as conn:
                rows = await conn.fetch("""
                    SELECT * FROM "Asset"
                    WHERE "isActive" = true
                    ORDER BY symbol
                """)
                return [dict(r) for r in rows]
        except Exception:
            return []

    async def get_market_movers(self) -> dict:
        """Get biggest gainers and losers from recent price data"""
        if not self.db_pool:
            return {"gainers": [], "losers": []}

        try:
            async with self.db_pool.acquire() as conn:
                # Get price changes over last 24h for each asset
                rows = await conn.fetch("""
                    WITH recent_prices AS (
                        SELECT
                            a.symbol,
                            a."lastPrice" as current_price,
                            (SELECT c.close FROM "Candle" c
                             WHERE c."assetId" = a.id
                             AND c.timestamp < NOW() - INTERVAL '24 hours'
                             ORDER BY c.timestamp DESC LIMIT 1) as price_24h_ago,
                            (SELECT c.close FROM "Candle" c
                             WHERE c."assetId" = a.id
                             AND c.timestamp < NOW() - INTERVAL '1 hour'
                             ORDER BY c.timestamp DESC LIMIT 1) as price_1h_ago
                        FROM "Asset" a
                        WHERE a."isActive" = true AND a."lastPrice" IS NOT NULL
                    )
                    SELECT
                        symbol,
                        current_price,
                        price_24h_ago,
                        price_1h_ago,
                        CASE WHEN price_24h_ago > 0
                            THEN ((current_price - price_24h_ago) / price_24h_ago * 100)
                            ELSE 0 END as change_24h,
                        CASE WHEN price_1h_ago > 0
                            THEN ((current_price - price_1h_ago) / price_1h_ago * 100)
                            ELSE 0 END as change_1h
                    FROM recent_prices
                    WHERE price_24h_ago IS NOT NULL
                    ORDER BY change_24h DESC
                """)

                all_movers = [dict(r) for r in rows]

                # Top 3 gainers and losers
                gainers = [m for m in all_movers if m["change_24h"] and float(m["change_24h"]) > 0][:3]
                losers = [m for m in reversed(all_movers) if m["change_24h"] and float(m["change_24h"]) < 0][:3]

                # Calculate market average
                changes = [float(m["change_24h"]) for m in all_movers if m["change_24h"]]
                avg_change = sum(changes) / len(changes) if changes else 0

                return {
                    "gainers": gainers,
                    "losers": losers,
                    "avg_change_24h": avg_change,
                    "total_assets": len(all_movers),
                }
        except Exception as e:
            console.print(f"[red]Movers error: {e}[/red]")
            return {"gainers": [], "losers": [], "avg_change_24h": 0}

    async def get_sentiment_summary(self) -> dict:
        """Get aggregated sentiment summary from recent data"""
        if not self.db_pool:
            return {}

        try:
            async with self.db_pool.acquire() as conn:
                # Get sentiment stats from last hour
                one_hour_ago = datetime.now() - timedelta(hours=1)

                # Get average fear score and counts
                stats = await conn.fetchrow("""
                    SELECT
                        AVG("sentimentScore") as avg_score,
                        COUNT(*) as total_entries,
                        COUNT(DISTINCT "assetId") as assets_covered
                    FROM "SentimentLog"
                    WHERE timestamp > $1
                """, one_hour_ago)

                # Get breakdown by source (from rawText which contains source info)
                sources = await conn.fetch("""
                    SELECT
                        source,
                        COUNT(*) as count,
                        AVG("sentimentScore") as avg_score
                    FROM "SentimentLog"
                    WHERE timestamp > $1
                    GROUP BY source
                """, one_hour_ago)

                # Get most recent Fear & Greed from rawText
                recent_fg = await conn.fetchrow("""
                    SELECT "rawText", "sentimentScore", timestamp
                    FROM "SentimentLog"
                    WHERE "rawText" LIKE '%Fear & Greed%' OR "rawText" LIKE '%FearGreed%'
                    ORDER BY timestamp DESC
                    LIMIT 1
                """)

                return {
                    "avg_score": float(stats["avg_score"]) if stats and stats["avg_score"] else 50,
                    "total_entries": stats["total_entries"] if stats else 0,
                    "assets_covered": stats["assets_covered"] if stats else 0,
                    "sources": [dict(s) for s in sources] if sources else [],
                    "fear_greed": recent_fg,
                }
        except Exception as e:
            console.print(f"[red]Sentiment error: {e}[/red]")
            return {}

    def create_header(self) -> Panel:
        """Create header panel"""
        sandbox_mode = os.getenv("KRAKEN_SANDBOX_MODE", "true").lower() == "true"

        header = Text()
        header.append("◆ ", style="cyan")
        header.append("ContrarianAI", style="bold cyan")
        header.append(" │ ", style="dim")
        if sandbox_mode:
            header.append("PAPER TRADING", style="yellow bold")
        else:
            header.append("LIVE TRADING", style="red bold")
        header.append(" │ ", style="dim")
        header.append(datetime.now().strftime("%Y-%m-%d %H:%M:%S"), style="white")

        return Panel(Align.center(header), box=box.DOUBLE, style="cyan")

    def create_status_panel(self, status: dict) -> Panel:
        """Create system status panel"""
        status_val = status.get("status", "UNKNOWN")
        trading = status.get("tradingEnabled", False)

        status_icon = "●" if status_val == "ACTIVE" else "○"
        status_style = "green" if status_val == "ACTIVE" else "yellow" if status_val == "PAUSED" else "red" if status_val == "EMERGENCY_STOP" else "dim"

        content = Text()
        content.append(f"{status_icon} ", style=status_style)
        content.append(f"{status_val}", style=status_style + " bold")
        content.append(" │ ", style="dim")
        content.append("ON" if trading else "OFF", style="green bold" if trading else "red")

        if status.get("initialBalance"):
            content.append(f"\n${float(status['initialBalance']):,.0f}", style="cyan")
            content.append(" initial", style="dim")
        if status.get("maxDrawdownPct"):
            content.append(f" │ {float(status['maxDrawdownPct'])*100:.0f}%", style="dim")
            content.append(" max DD", style="dim")

        return Panel(content, title="Status", box=box.ROUNDED)

    def create_sessions_table(self, sessions: list) -> Panel:
        """Create council sessions table (narrow version)"""
        table = Table(box=box.SIMPLE_HEAD, expand=True, show_edge=False)
        table.add_column("Time", style="dim", width=11)
        table.add_column("Asset", style="cyan", width=9)
        table.add_column("Call", width=6)
        table.add_column("Fear", justify="right", width=4)
        table.add_column("Tech", width=7)
        table.add_column("Conf", justify="right", width=5)

        for s in sessions[:15]:
            timestamp = s.get("timestamp", datetime.now())
            time_str = timestamp.strftime("%H:%M") if isinstance(timestamp, datetime) else str(timestamp)[:5]

            decision = s.get("finalDecision", "?")
            dec_style = "green bold" if decision == "BUY" else "red bold" if decision == "SELL" else "dim"

            fear = s.get("sentimentScore")
            fear_str = str(fear) if fear is not None else "-"
            fear_style = "green" if fear and fear < 30 else "red" if fear and fear > 70 else "white"

            signal = s.get("technicalSignal", "-")
            signal_short = "BULL" if signal == "BULLISH" else "BEAR" if signal == "BEARISH" else "NEUT"
            signal_style = "green" if signal == "BULLISH" else "red" if signal == "BEARISH" else "dim"

            conf = s.get("visionConfidence")
            conf_str = f"{conf}%" if conf is not None else "-"

            table.add_row(
                time_str,
                s.get("symbol", "?")[:8].replace("USD", ""),
                Text(decision[:4] if decision else "?", style=dec_style),
                Text(fear_str, style=fear_style),
                Text(signal_short, style=signal_style),
                conf_str
            )

        if not sessions:
            table.add_row("-", "-", "-", "-", "-", "-")

        return Panel(table, title=f"Sessions ({len(sessions)})", box=box.ROUNDED)

    def create_sessions_panel(self, sessions: list) -> Panel:
        """Create full-width council sessions panel"""
        table = Table(box=box.SIMPLE_HEAD, expand=True, show_edge=False)
        table.add_column("Time", style="dim", width=8)
        table.add_column("Asset", style="cyan", width=8)
        table.add_column("Decision", width=6)
        table.add_column("Fear", justify="center", width=5)
        table.add_column("Technical", width=8)
        table.add_column("Vision", justify="center", width=6)
        table.add_column("Reasoning", style="dim", ratio=1)

        for s in sessions[:12]:
            timestamp = s.get("timestamp", datetime.now())
            time_str = timestamp.strftime("%H:%M") if isinstance(timestamp, datetime) else str(timestamp)[:5]

            decision = s.get("finalDecision", "?")
            dec_style = "green bold" if decision == "BUY" else "red bold" if decision == "SELL" else "yellow"

            fear = s.get("sentimentScore")
            fear_str = str(fear) if fear is not None else "-"
            fear_style = "green" if fear and fear < 30 else "red" if fear and fear > 70 else "white"

            signal = s.get("technicalSignal", "-")
            signal_style = "green" if signal == "BULLISH" else "red" if signal == "BEARISH" else "dim"

            conf = s.get("visionConfidence")
            conf_str = f"{conf}%" if conf is not None else "-"

            reasoning = s.get("reasoning", "")[:60] + "..." if s.get("reasoning") else "-"

            table.add_row(
                time_str,
                s.get("symbol", "?")[:7].replace("USD", ""),
                Text(decision[:4] if decision else "?", style=dec_style),
                Text(fear_str, style=fear_style),
                Text(signal[:7] if signal else "-", style=signal_style),
                conf_str,
                reasoning,
            )

        if not sessions:
            table.add_row("-", "-", "-", "-", "-", "-", "No council sessions yet")

        return Panel(table, title=f"Council Decisions ({len(sessions)})", box=box.ROUNDED)

    def create_trades_table(self, trades: list) -> Panel:
        """Create open trades table"""
        content = Text()

        if not trades:
            content.append("No open positions", style="dim")
        else:
            total_pnl = 0
            for t in trades:
                entry = float(t.get("entryPrice", 0))
                current = float(t.get("lastPrice", entry))
                size = float(t.get("size", 0))
                pnl_pct = ((current - entry) / entry * 100) if entry > 0 else 0
                pnl_usd = (current - entry) * size
                total_pnl += pnl_usd

                pnl_style = "green" if pnl_pct >= 0 else "red"
                symbol = t.get("symbol", "?").replace("USD", "")

                content.append(f"{symbol:<6}", style="cyan")
                content.append(f"${current:>9,.2f} ", style="dim")
                content.append(f"{pnl_pct:+6.2f}%", style=pnl_style)
                content.append(f" (${pnl_usd:+,.0f})\n", style=pnl_style)

            content.append(f"\nTotal P&L: ", style="bold")
            pnl_style = "green bold" if total_pnl >= 0 else "red bold"
            content.append(f"${total_pnl:+,.2f}", style=pnl_style)

        return Panel(content, title=f"Trades ({len(trades)})", box=box.ROUNDED)

    def create_assets_panel(self, assets: list) -> Panel:
        """Create assets overview panel - compact grid"""
        content = Text()

        # Show assets in a compact 2-column format
        sorted_assets = sorted(assets, key=lambda x: x.get("symbol", ""))[:30]

        for i, a in enumerate(sorted_assets):
            symbol = a.get("symbol", "?").replace("USD", "")[:6]
            price = a.get("lastPrice")
            price_str = f"${float(price):>7,.2f}" if price else "     -"

            content.append(f"{symbol:<6}", style="cyan")
            content.append(f"{price_str}", style="dim")

            # New line every 2 assets, or add spacing
            if i % 2 == 1:
                content.append("\n")
            else:
                content.append("  │  ", style="dim")

        if not assets:
            content.append("No assets", style="dim")

        return Panel(content, title=f"Assets ({len(assets)})", box=box.ROUNDED)

    def create_movers_panel(self, movers: dict) -> Panel:
        """Create market movers panel showing gainers/losers"""
        content = Text()

        # Top Gainers
        content.append("▲ ", style="green bold")
        gainers = movers.get("gainers", [])
        if gainers:
            for i, g in enumerate(gainers[:3]):
                symbol = g.get("symbol", "?").replace("USD", "")[:5]
                change = float(g.get("change_24h", 0))
                content.append(f"{symbol}", style="cyan")
                content.append(f" {change:+.1f}%", style="green")
                if i < 2:
                    content.append(" │ ", style="dim")
        else:
            content.append("No data", style="dim")

        content.append("\n")

        # Top Losers
        content.append("▼ ", style="red bold")
        losers = movers.get("losers", [])
        if losers:
            for i, l in enumerate(losers[:3]):
                symbol = l.get("symbol", "?").replace("USD", "")[:5]
                change = float(l.get("change_24h", 0))
                content.append(f"{symbol}", style="cyan")
                content.append(f" {change:+.1f}%", style="red")
                if i < 2:
                    content.append(" │ ", style="dim")
        else:
            content.append("No data", style="dim")

        # Market average
        avg = movers.get("avg_change_24h", 0)
        total = movers.get("total_assets", 0)
        avg_style = "green" if avg > 0 else "red" if avg < 0 else "dim"
        content.append(f"\n\nMarket Avg: ", style="dim")
        content.append(f"{avg:+.2f}%", style=avg_style)
        content.append(f" │ {total} assets", style="dim")

        return Panel(content, title="24h Movers", box=box.ROUNDED)

    def create_sentiment_panel(self, sentiment: dict) -> Panel:
        """Create sentiment summary panel"""
        content = Text()

        avg_score = sentiment.get("avg_score", 50)

        # Determine sentiment and style
        if avg_score < 20:
            label, color, zone = "EXTREME FEAR", "green bold", "BUY"
        elif avg_score < 40:
            label, color, zone = "FEAR", "green", "caution"
        elif avg_score < 60:
            label, color, zone = "NEUTRAL", "yellow", "wait"
        elif avg_score < 80:
            label, color, zone = "GREED", "red", "caution"
        else:
            label, color, zone = "EXTREME GREED", "red bold", "SELL"

        # Score display with bar
        content.append(f"{avg_score:.0f}", style=color)
        content.append(f" {label}\n", style=color)

        # Visual bar
        bar_pos = int(avg_score / 5)  # 0-20 position
        bar = "─" * bar_pos + "●" + "─" * (20 - bar_pos)
        content.append(f"[{bar}]\n", style=color)

        # Zone indicator
        if zone in ["BUY", "SELL"]:
            content.append(f"Contrarian: ", style="dim")
            content.append(f"{zone} ZONE", style=color)
        else:
            content.append(f"Signal: {zone}", style="dim")

        # Source breakdown
        sources = sentiment.get("sources", [])
        if sources:
            content.append("\n\n")
            for src in sources[:4]:
                src_name = src.get("source", "?")[:8]
                src_count = src.get("count", 0)
                content.append(f"{src_name}: ", style="dim")
                content.append(f"{src_count} ", style="white")

        # Data count
        total = sentiment.get("total_entries", 0)
        assets_count = sentiment.get("assets_covered", 0)
        content.append(f"\n\n{total} entries │ {assets_count} assets (1h)", style="dim")

        return Panel(content, title="Sentiment", box=box.ROUNDED)

    def create_help_panel(self) -> Text:
        """Create help bar"""
        help_text = Text()
        help_text.append(" r", style="cyan bold")
        help_text.append(" refresh ", style="dim")
        help_text.append("│", style="dim")
        help_text.append(" c", style="cyan bold")
        help_text.append(" council ", style="dim")
        help_text.append("│", style="dim")
        help_text.append(" t", style="cyan bold")
        help_text.append(" test ", style="dim")
        help_text.append("│", style="dim")
        help_text.append(" p", style="cyan bold")
        help_text.append(" pause ", style="dim")
        help_text.append("│", style="dim")
        help_text.append(" q", style="cyan bold")
        help_text.append(" quit", style="dim")
        return help_text

    def create_layout(self) -> Layout:
        """Create the full-screen layout structure"""
        layout = Layout()

        # Main structure: header, body, footer
        layout.split_column(
            Layout(name="header", size=3),
            Layout(name="body"),
            Layout(name="footer", size=3),
        )

        # Body: grid on top, sessions full-width at bottom
        layout["body"].split_column(
            Layout(name="grid", ratio=2),
            Layout(name="sessions", ratio=1),
        )

        # Grid splits into two rows
        layout["grid"].split_column(
            Layout(name="top_row"),
            Layout(name="bottom_row"),
        )

        # Top row: Status | Sentiment | Trades
        layout["top_row"].split_row(
            Layout(name="status", ratio=1),
            Layout(name="sentiment", ratio=1),
            Layout(name="trades", ratio=1),
        )

        # Bottom row: Movers | Assets
        layout["bottom_row"].split_row(
            Layout(name="movers", ratio=1),
            Layout(name="assets", ratio=1),
        )

        return layout

    async def display_dashboard(self):
        """Display the main dashboard using full-screen Layout"""
        console.clear()

        # Fetch all data
        status = await self.get_system_status()
        sessions = await self.get_recent_sessions()
        trades = await self.get_open_trades()
        assets = await self.get_assets()
        sentiment = await self.get_sentiment_summary()
        movers = await self.get_market_movers()

        # Create layout
        layout = self.create_layout()

        # Populate layout sections
        layout["header"].update(self.create_header())
        layout["status"].update(self.create_status_panel(status))
        layout["sentiment"].update(self.create_sentiment_panel(sentiment))
        layout["trades"].update(self.create_trades_table(trades))
        layout["movers"].update(self.create_movers_panel(movers))
        layout["assets"].update(self.create_assets_panel(assets))
        layout["sessions"].update(self.create_sessions_panel(sessions))
        layout["footer"].update(
            Panel(Align.center(self.create_help_panel()), box=box.ROUNDED, style="dim")
        )

        # Print the full-screen layout
        console.print(layout)

    async def run_test_session(self):
        """Trigger a test council session via API"""
        import httpx

        bot_url = f"http://localhost:{os.getenv('BOT_PORT', '8000')}"

        console.print("\n[cyan]Running test council session...[/cyan]")

        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.get(f"{bot_url}/api/council/test")

                if response.status_code == 200:
                    data = response.json()
                    decision = data.get("final_decision", {})

                    console.print(f"\n[green]Test session complete![/green]")
                    console.print(f"Decision: [bold]{decision.get('decision', 'N/A')}[/bold]")
                    console.print(f"Confidence: {decision.get('confidence', 'N/A')}%")
                    console.print(f"Reasoning: {decision.get('reasoning', 'N/A')[:100]}...")
                else:
                    console.print(f"[red]Error: {response.status_code}[/red]")
                    console.print(response.text[:200])
        except httpx.ConnectError:
            console.print("[red]Cannot connect to bot. Is it running? (python main.py)[/red]")
        except Exception as e:
            console.print(f"[red]Error: {e}[/red]")

        input("\nPress Enter to continue...")

    async def toggle_trading(self):
        """Toggle trading enabled/disabled"""
        if not self.db_pool:
            console.print("[red]No database connection[/red]")
            return

        status = await self.get_system_status()
        current = status.get("tradingEnabled", False)

        action = "disable" if current else "enable"
        if Confirm.ask(f"Are you sure you want to [bold]{action}[/bold] trading?"):
            try:
                async with self.db_pool.acquire() as conn:
                    await conn.execute(
                        'UPDATE system_config SET "tradingEnabled" = $1, "updatedAt" = NOW()',
                        not current
                    )
                console.print(f"[green]Trading {'enabled' if not current else 'disabled'}[/green]")
            except Exception as e:
                console.print(f"[red]Error: {e}[/red]")

        await asyncio.sleep(1)

    async def main_loop(self):
        """Main interactive loop"""
        # Connect to database
        db_connected = await self.connect_db()
        if not db_connected:
            console.print("[yellow]Running in limited mode (no database)[/yellow]")

        try:
            while self.running:
                await self.display_dashboard()

                # Wait for input with timeout
                console.print("\n[dim]Enter command (or wait 30s for refresh):[/dim] ", end="")

                try:
                    # Use asyncio to handle input with timeout
                    import sys
                    import select

                    # Check if input available within 30 seconds
                    if sys.stdin in select.select([sys.stdin], [], [], 30)[0]:
                        cmd = sys.stdin.readline().strip().lower()
                    else:
                        cmd = "r"  # Auto-refresh

                    if cmd == "q":
                        self.running = False
                    elif cmd == "r":
                        continue  # Refresh
                    elif cmd == "t":
                        await self.run_test_session()
                    elif cmd == "p":
                        await self.toggle_trading()
                    elif cmd == "c":
                        console.print("[yellow]Council cycle runs automatically every 15 minutes[/yellow]")
                        await asyncio.sleep(2)

                except KeyboardInterrupt:
                    self.running = False

        finally:
            await self.close_db()
            console.print("\n[cyan]Goodbye![/cyan]")


async def main():
    """Entry point"""
    # Check for required dependency
    try:
        import httpx
    except ImportError:
        console.print("[yellow]Installing httpx for API calls...[/yellow]")
        os.system("pip install httpx")

    dashboard = TradingDashboard()
    await dashboard.main_loop()


if __name__ == "__main__":
    # Install asyncpg if needed
    try:
        import asyncpg
    except ImportError:
        console.print("[yellow]Installing asyncpg...[/yellow]")
        os.system("pip install asyncpg")
        import asyncpg

    asyncio.run(main())
