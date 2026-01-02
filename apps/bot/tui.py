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

    async def get_onchain_data(self) -> dict:
        """Get latest on-chain metrics from database"""
        # Check if on-chain is enabled
        from config import get_config
        config = get_config()
        if not config.onchain.enabled:
            return {"available": False, "disabled": True}

        if not self.db_pool:
            return {"available": False}

        try:
            async with self.db_pool.acquire() as conn:
                one_day_ago = datetime.now() - timedelta(hours=24)

                # Get latest exchange flow
                flow = await conn.fetchrow("""
                    SELECT "netFlowUsd", "assetSymbol", timestamp
                    FROM "ExchangeFlow"
                    WHERE timestamp > $1
                    ORDER BY timestamp DESC LIMIT 1
                """, one_day_ago)

                # Get whale activity summary
                whale = await conn.fetchrow("""
                    SELECT
                        SUM("whaleBuyVolume") as buy_vol,
                        SUM("whaleSellVolume") as sell_vol,
                        SUM("largeTxCount") as tx_count
                    FROM "WhaleActivity"
                    WHERE timestamp > $1
                """, one_day_ago)

                # Get latest funding rate
                funding = await conn.fetchrow("""
                    SELECT "fundingRate", "assetSymbol", timestamp
                    FROM "FundingRate"
                    WHERE timestamp > $1
                    ORDER BY timestamp DESC LIMIT 1
                """, one_day_ago)

                # Get stablecoin reserves
                stablecoin = await conn.fetchrow("""
                    SELECT "totalReservesUsd", "change7dPct", timestamp
                    FROM "StablecoinReserves"
                    ORDER BY timestamp DESC LIMIT 1
                """)

                # Calculate signals
                flow_signal = "NEUTRAL"
                flow_value = 0
                if flow and flow["netFlowUsd"]:
                    flow_value = float(flow["netFlowUsd"])
                    if flow_value < -1000000:
                        flow_signal = "ACCUM"
                    elif flow_value > 1000000:
                        flow_signal = "DISTRIB"

                whale_signal = "NEUTRAL"
                whale_ratio = 1.0
                if whale and whale["buy_vol"] and whale["sell_vol"]:
                    buy = float(whale["buy_vol"])
                    sell = float(whale["sell_vol"])
                    if sell > 0:
                        whale_ratio = buy / sell
                        if whale_ratio > 1.2:
                            whale_signal = "BUYING"
                        elif whale_ratio < 0.8:
                            whale_signal = "SELLING"

                funding_signal = "NEUTRAL"
                funding_rate = 0
                if funding and funding["fundingRate"]:
                    funding_rate = float(funding["fundingRate"]) * 100
                    if funding_rate < -0.05:
                        funding_signal = "SHORT SQ"
                    elif funding_rate > 0.05:
                        funding_signal = "LONG SQ"

                stable_signal = "NEUTRAL"
                stable_change = 0
                if stablecoin and stablecoin["change7dPct"]:
                    stable_change = float(stablecoin["change7dPct"])
                    if stable_change > 5:
                        stable_signal = "DRY PWD"
                    elif stable_change < -5:
                        stable_signal = "LOW"

                # Count bullish factors
                bullish = sum([
                    flow_signal == "ACCUM",
                    whale_signal == "BUYING",
                    funding_signal == "SHORT SQ",
                    stable_signal == "DRY PWD"
                ])

                return {
                    "available": True,
                    "flow_signal": flow_signal,
                    "flow_value": flow_value,
                    "whale_signal": whale_signal,
                    "whale_ratio": whale_ratio,
                    "funding_signal": funding_signal,
                    "funding_rate": funding_rate,
                    "stable_signal": stable_signal,
                    "stable_change": stable_change,
                    "bullish_count": bullish,
                    "overall": "BULLISH" if bullish >= 3 else "BEARISH" if bullish <= 1 else "NEUTRAL"
                }
        except Exception:
            return {"available": False}

    async def get_technical_indicators(self) -> dict:
        """Get latest technical analysis from most recent session"""
        if not self.db_pool:
            return {"available": False}

        try:
            async with self.db_pool.acquire() as conn:
                # Get most recent session with technical data
                session = await conn.fetchrow("""
                    SELECT
                        "technicalSignal",
                        "technicalStrength",
                        "sentimentScore"
                    FROM "CouncilSession"
                    ORDER BY timestamp DESC LIMIT 1
                """)

                # Get latest candle data for an asset to calculate indicators
                candle = await conn.fetchrow("""
                    SELECT a.symbol, a."lastPrice",
                        (SELECT close FROM "Candle" c WHERE c."assetId" = a.id ORDER BY timestamp DESC LIMIT 1) as close
                    FROM "Asset" a
                    WHERE a."isActive" = true AND a.symbol = 'BTCUSD'
                    LIMIT 1
                """)

                # Default values
                result = {
                    "available": True,
                    "macd_signal": "NEUTRAL",
                    "macd_hist": 0,
                    "bb_signal": "NEUTRAL",
                    "bb_percent": 0.5,
                    "bb_squeeze": False,
                    "obv_signal": "NEUTRAL",
                    "obv_change": 0,
                    "adx_value": 25,
                    "adx_safe": True,
                    "vwap_signal": "NEUTRAL",
                    "vwap_dist": 0,
                    "rsi": 50,
                    "overall": session["technicalSignal"] if session else "NEUTRAL",
                    "strength": session["technicalStrength"] if session and session["technicalStrength"] else 50
                }

                # If we have extended technical data in session, use it
                # For now, use placeholder data that will be populated when technical_indicators runs
                if session:
                    signal = session.get("technicalSignal", "NEUTRAL")
                    if signal == "BULLISH":
                        result["macd_signal"] = "BULLISH"
                        result["bb_signal"] = "OVERSOLD"
                        result["rsi"] = 35
                    elif signal == "BEARISH":
                        result["macd_signal"] = "BEARISH"
                        result["bb_signal"] = "OVERBOUGHT"
                        result["rsi"] = 65

                return result
        except Exception:
            return {"available": False}

    async def get_risk_status(self) -> dict:
        """Get current risk status from portfolio and config"""
        if not self.db_pool:
            return {"available": False}

        try:
            async with self.db_pool.acquire() as conn:
                # Get system config for limits
                config = await conn.fetchrow("""
                    SELECT "maxDrawdownPct", "initialBalance", "tradingEnabled"
                    FROM system_config
                    ORDER BY "updatedAt" DESC LIMIT 1
                """)

                # Get latest portfolio snapshot for drawdown
                snapshot = await conn.fetchrow("""
                    SELECT "portfolioValue", "peakValue", "drawdownPct"
                    FROM "PortfolioSnapshot"
                    ORDER BY timestamp DESC LIMIT 1
                """)

                # Get open trades for position concentration
                trades = await conn.fetch("""
                    SELECT t."entryPrice", t.size, a."lastPrice"
                    FROM "Trade" t
                    JOIN "Asset" a ON t."assetId" = a.id
                    WHERE t.status = 'OPEN'
                """)

                # Get today's P&L
                today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
                daily_pnl = await conn.fetchrow("""
                    SELECT COALESCE(SUM(pnl), 0) as total_pnl
                    FROM "Trade"
                    WHERE "exitTime" > $1
                """, today_start)

                # Calculate metrics
                max_dd = float(config["maxDrawdownPct"]) * 100 if config and config["maxDrawdownPct"] else 15
                initial_bal = float(config["initialBalance"]) if config and config["initialBalance"] else 10000
                trading_on = config["tradingEnabled"] if config else False

                current_dd = float(snapshot["drawdownPct"]) if snapshot and snapshot["drawdownPct"] else 0
                portfolio_val = float(snapshot["portfolioValue"]) if snapshot and snapshot["portfolioValue"] else initial_bal

                # Position concentration
                largest_pos = 0
                if trades and portfolio_val > 0:
                    for t in trades:
                        price = float(t["lastPrice"]) if t["lastPrice"] else float(t["entryPrice"])
                        size = float(t["size"]) if t["size"] else 0
                        pos_val = price * size
                        pos_pct = (pos_val / portfolio_val) * 100
                        if pos_pct > largest_pos:
                            largest_pos = pos_pct

                # Daily P&L
                daily_pnl_val = float(daily_pnl["total_pnl"]) if daily_pnl and daily_pnl["total_pnl"] else 0
                daily_pnl_pct = (daily_pnl_val / initial_bal) * 100 if initial_bal > 0 else 0

                # Calculate utilizations (as percentage of limit used)
                dd_util = (current_dd / max_dd) * 100 if max_dd > 0 else 0
                pos_util = (largest_pos / 10) * 100  # 10% limit
                daily_util = (abs(daily_pnl_pct) / 5) * 100  # 5% limit
                corr_util = 30  # Placeholder - would need correlation calculation

                # Determine risk level
                max_util = max(dd_util, pos_util, daily_util)
                if max_util >= 100:
                    risk_level = "CRITICAL"
                elif max_util >= 80:
                    risk_level = "HIGH"
                elif max_util >= 50:
                    risk_level = "MODERATE"
                else:
                    risk_level = "LOW"

                return {
                    "available": True,
                    "risk_level": risk_level,
                    "drawdown_pct": current_dd,
                    "drawdown_limit": max_dd,
                    "drawdown_util": min(dd_util, 100),
                    "daily_pnl_pct": daily_pnl_pct,
                    "daily_limit": 5,
                    "daily_util": min(daily_util, 100),
                    "position_pct": largest_pos,
                    "position_limit": 10,
                    "position_util": min(pos_util, 100),
                    "corr_pct": 18,  # Placeholder
                    "corr_limit": 30,
                    "corr_util": min(corr_util, 100),
                    "trading_enabled": trading_on,
                    "alerts": 0
                }
        except Exception:
            return {"available": False}

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

    def create_onchain_panel(self, data: dict) -> Panel:
        """Create on-chain signals panel"""
        content = Text()

        if data.get("disabled"):
            content.append("On-chain disabled\n", style="dim")
            content.append("Set ONCHAIN_ENABLED=true\n", style="dim italic")
            content.append("Requires paid API", style="dim italic")
            return Panel(content, title="On-Chain", box=box.ROUNDED)

        if not data.get("available"):
            content.append("No on-chain data\n", style="dim")
            content.append("Configure API keys in .env", style="dim italic")
            return Panel(content, title="On-Chain", box=box.ROUNDED)

        # Exchange Flow
        flow_sig = data.get("flow_signal", "NEUTRAL")
        flow_val = data.get("flow_value", 0)
        flow_style = "green" if flow_sig == "ACCUM" else "red" if flow_sig == "DISTRIB" else "dim"
        flow_icon = "▼" if flow_sig == "ACCUM" else "▲" if flow_sig == "DISTRIB" else "●"
        content.append(f"Exchange  {flow_icon} ", style=flow_style)
        content.append(f"{flow_sig:<8}", style=flow_style + " bold")
        flow_str = f"${flow_val/1000000:+.1f}M" if abs(flow_val) >= 1000000 else f"${flow_val/1000:+.0f}K"
        content.append(f"{flow_str:>8}\n", style="dim")

        # Whale Activity
        whale_sig = data.get("whale_signal", "NEUTRAL")
        whale_ratio = data.get("whale_ratio", 1.0)
        whale_style = "green" if whale_sig == "BUYING" else "red" if whale_sig == "SELLING" else "dim"
        whale_icon = "◆" if whale_sig == "BUYING" else "◇" if whale_sig == "SELLING" else "●"
        content.append(f"Whales    {whale_icon} ", style=whale_style)
        content.append(f"{whale_sig:<8}", style=whale_style + " bold")
        content.append(f"({whale_ratio:.1f}:1)\n", style="dim")

        # Funding Rate
        fund_sig = data.get("funding_signal", "NEUTRAL")
        fund_rate = data.get("funding_rate", 0)
        fund_style = "green" if fund_sig == "SHORT SQ" else "red" if fund_sig == "LONG SQ" else "dim"
        content.append(f"Funding   ● ", style=fund_style)
        content.append(f"{fund_sig:<8}", style=fund_style + " bold")
        content.append(f"{fund_rate:+.3f}%\n", style="dim")

        # Stablecoin
        stable_sig = data.get("stable_signal", "NEUTRAL")
        stable_chg = data.get("stable_change", 0)
        stable_style = "green" if stable_sig == "DRY PWD" else "red" if stable_sig == "LOW" else "dim"
        stable_icon = "▲" if stable_chg > 0 else "▼" if stable_chg < 0 else "●"
        content.append(f"Stables   {stable_icon} ", style=stable_style)
        content.append(f"{stable_sig:<8}", style=stable_style + " bold")
        content.append(f"{stable_chg:+.1f}%\n", style="dim")

        # Overall signal
        content.append("─" * 28 + "\n", style="dim")
        overall = data.get("overall", "NEUTRAL")
        bullish = data.get("bullish_count", 0)
        overall_style = "green bold" if overall == "BULLISH" else "red bold" if overall == "BEARISH" else "yellow"
        content.append(f"Signal: ", style="dim")
        content.append(f"{overall}", style=overall_style)
        content.append(f"  ({bullish}/4)", style="dim")

        return Panel(content, title="On-Chain", box=box.ROUNDED)

    def create_technical_panel(self, data: dict) -> Panel:
        """Create technical indicators panel"""
        content = Text()

        if not data.get("available"):
            content.append("No technical data\n", style="dim")
            content.append("Run council session first", style="dim italic")
            return Panel(content, title="Technical", box=box.ROUNDED)

        # MACD
        macd_sig = data.get("macd_signal", "NEUTRAL")
        macd_hist = data.get("macd_hist", 0)
        macd_style = "green" if macd_sig == "BULLISH" else "red" if macd_sig == "BEARISH" else "dim"
        macd_icon = "▲" if macd_sig == "BULLISH" else "▼" if macd_sig == "BEARISH" else "●"
        content.append(f"MACD  {macd_icon} ", style=macd_style)
        macd_label = "Bull Cross" if macd_sig == "BULLISH" else "Bear Cross" if macd_sig == "BEARISH" else "Neutral"
        content.append(f"{macd_label:<11}", style=macd_style)
        content.append(f"{macd_hist:+.2f}\n", style="dim")

        # Bollinger Bands
        bb_sig = data.get("bb_signal", "NEUTRAL")
        bb_pct = data.get("bb_percent", 0.5)
        bb_squeeze = data.get("bb_squeeze", False)
        bb_style = "green" if bb_sig == "OVERSOLD" else "red" if bb_sig == "OVERBOUGHT" else "dim"
        bb_icon = "●"
        content.append(f"BB    {bb_icon} ", style=bb_style)
        bb_label = "Lower Band" if bb_sig == "OVERSOLD" else "Upper Band" if bb_sig == "OVERBOUGHT" else "Mid Band"
        content.append(f"{bb_label:<11}", style=bb_style)
        content.append(f"%B:{bb_pct:.2f}", style="dim")
        if bb_squeeze:
            content.append(" SQ", style="yellow bold")
        content.append("\n")

        # OBV
        obv_sig = data.get("obv_signal", "NEUTRAL")
        obv_chg = data.get("obv_change", 0)
        obv_style = "green" if obv_sig == "ACCUM" else "red" if obv_sig == "DISTRIB" else "dim"
        obv_icon = "▲" if obv_chg > 0 else "▼" if obv_chg < 0 else "●"
        content.append(f"OBV   {obv_icon} ", style=obv_style)
        obv_label = "Accumulate" if obv_sig == "ACCUM" else "Distribute" if obv_sig == "DISTRIB" else "Neutral"
        content.append(f"{obv_label:<11}", style=obv_style)
        content.append(f"{obv_chg:+.1f}%\n", style="dim")

        # ADX
        adx_val = data.get("adx_value", 25)
        adx_safe = data.get("adx_safe", True)
        adx_style = "green" if adx_safe else "red"
        adx_icon = "✓" if adx_safe else "✗"
        content.append(f"ADX   {adx_icon} ", style=adx_style)
        content.append(f"{adx_val:.1f}", style=adx_style + " bold")
        adx_label = " (Safe)" if adx_safe else " (Avoid)"
        content.append(f"{adx_label}\n", style=adx_style)

        # RSI with bar
        rsi = data.get("rsi", 50)
        rsi_style = "green" if rsi < 30 else "red" if rsi > 70 else "yellow"
        rsi_label = "OVERSOLD" if rsi < 30 else "OVERBOUGHT" if rsi > 70 else ""
        bar_len = 10
        filled = int(rsi / 10)
        bar = "█" * filled + "░" * (bar_len - filled)
        content.append(f"RSI   ", style="dim")
        content.append(f"{rsi:.0f}", style=rsi_style + " bold")
        content.append(f"  {bar}", style=rsi_style)
        if rsi_label:
            content.append(f" {rsi_label}", style=rsi_style)

        return Panel(content, title="Technical", box=box.ROUNDED)

    def create_risk_panel(self, data: dict) -> Panel:
        """Create risk status panel"""
        content = Text()

        if not data.get("available"):
            content.append("No risk data\n", style="dim")
            content.append("Configure risk settings", style="dim italic")
            return Panel(content, title="Risk", box=box.ROUNDED)

        # Risk level header
        risk_level = data.get("risk_level", "LOW")
        level_style = {
            "LOW": "green bold",
            "MODERATE": "yellow bold",
            "HIGH": "red bold",
            "CRITICAL": "red bold reverse"
        }.get(risk_level, "dim")
        content.append("      ● ", style=level_style)
        content.append(f"{risk_level} RISK\n", style=level_style)
        content.append("─" * 28 + "\n", style="dim")

        def make_bar(util: float, label: str, current: float, limit: float) -> None:
            bar_len = 10
            filled = int(util / 10)
            bar = "█" * filled + "░" * (bar_len - filled)
            bar_style = "green" if util < 50 else "yellow" if util < 80 else "red"
            content.append(f"{label:<8}", style="dim")
            content.append(f"{current:.1f}/{limit:.0f}%", style="white")
            content.append(f" {bar}", style=bar_style)
            content.append(f" {util:.0f}%\n", style=bar_style)

        # Drawdown
        make_bar(
            data.get("drawdown_util", 0),
            "Drawdown",
            data.get("drawdown_pct", 0),
            data.get("drawdown_limit", 15)
        )

        # Daily P&L
        make_bar(
            data.get("daily_util", 0),
            "Daily",
            abs(data.get("daily_pnl_pct", 0)),
            data.get("daily_limit", 5)
        )

        # Position concentration
        make_bar(
            data.get("position_util", 0),
            "Position",
            data.get("position_pct", 0),
            data.get("position_limit", 10)
        )

        # Correlation
        make_bar(
            data.get("corr_util", 0),
            "Correl.",
            data.get("corr_pct", 0),
            data.get("corr_limit", 30)
        )

        # Footer
        content.append("─" * 28 + "\n", style="dim")
        trading = data.get("trading_enabled", False)
        alerts = data.get("alerts", 0)
        content.append("Trading: ", style="dim")
        content.append("ON " if trading else "OFF", style="green bold" if trading else "red")
        content.append(f"         Alerts: ", style="dim")
        alert_style = "red bold" if alerts > 0 else "dim"
        content.append(f"{alerts}", style=alert_style)

        return Panel(content, title="Risk", box=box.ROUNDED)

    def create_help_panel(self) -> Text:
        """Create help bar"""
        help_text = Text()
        help_text.append(" r", style="cyan bold")
        help_text.append(" refresh ", style="dim")
        help_text.append("│", style="dim")
        help_text.append(" t", style="cyan bold")
        help_text.append(" test ", style="dim")
        help_text.append("│", style="dim")
        help_text.append(" p", style="cyan bold")
        help_text.append(" pause ", style="dim")
        help_text.append("│", style="dim")
        help_text.append(" q", style="cyan bold")
        help_text.append(" quit ", style="dim")
        help_text.append("│", style="dim")
        help_text.append(" auto-refresh 30s", style="dim italic")
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

        # Body: grid on top, metrics row, sessions full-width at bottom
        layout["body"].split_column(
            Layout(name="grid", ratio=2),
            Layout(name="metrics", ratio=1),
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

        # Metrics row: On-Chain | Technical | Risk
        layout["metrics"].split_row(
            Layout(name="onchain", ratio=1),
            Layout(name="technical", ratio=1),
            Layout(name="risk", ratio=1),
        )

        return layout

    async def display_dashboard(self):
        """Display the main dashboard using full-screen Layout"""
        # Clear screen and move cursor to top-left
        print("\033[2J\033[H", end="", flush=True)

        # Fetch all data (existing + new metrics)
        status = await self.get_system_status()
        sessions = await self.get_recent_sessions()
        trades = await self.get_open_trades()
        assets = await self.get_assets()
        sentiment = await self.get_sentiment_summary()
        movers = await self.get_market_movers()
        onchain = await self.get_onchain_data()
        technical = await self.get_technical_indicators()
        risk = await self.get_risk_status()

        # Create layout
        layout = self.create_layout()

        # Populate layout sections
        layout["header"].update(self.create_header())
        layout["status"].update(self.create_status_panel(status))
        layout["sentiment"].update(self.create_sentiment_panel(sentiment))
        layout["trades"].update(self.create_trades_table(trades))
        layout["movers"].update(self.create_movers_panel(movers))
        layout["assets"].update(self.create_assets_panel(assets))

        # New metrics row
        layout["onchain"].update(self.create_onchain_panel(onchain))
        layout["technical"].update(self.create_technical_panel(technical))
        layout["risk"].update(self.create_risk_panel(risk))

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
