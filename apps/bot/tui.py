#!/usr/bin/env python3
"""
Gemini Alpha Terminal Dashboard
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
    """Simple TUI Dashboard for Gemini Alpha"""

    def __init__(self):
        self.db_pool: Optional[asyncpg.Pool] = None
        self.running = True
        self.sessions_expanded = False  # Toggle for expanded reasoning view

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
        """Get tracked assets from dynamic universe with real prices"""
        try:
            from services.opportunity_scanner import get_opportunity_scanner
            from services.kraken import get_kraken_client

            # Get dynamic universe (assets we're actually tracking)
            scanner = get_opportunity_scanner()
            universe = scanner.get_dynamic_universe()

            # Fallback to top 10 liquid assets if no scanner results yet
            if not universe:
                universe = [
                    "BTCUSD", "ETHUSD", "SOLUSD", "XRPUSD", "ADAUSD",
                    "AVAXUSD", "DOGEUSD", "LINKUSD", "DOTUSD", "MATICUSD"
                ]

            # Fetch all tickers in one call (efficient)
            kraken = get_kraken_client()
            await kraken.initialize()
            all_tickers = await kraken.fetch_all_tickers()

            assets = []
            for symbol in universe:  # Show all tracked assets (up to 10 from scanner)
                # Convert to Kraken format (BTCUSD -> BTC/USD)
                kraken_symbol = symbol[:-3] + "/" + symbol[-3:]
                ticker = all_tickers.get(kraken_symbol)
                if ticker:
                    assets.append({
                        "symbol": symbol,
                        "lastPrice": ticker.get("last", 0),
                        "change_24h": ticker.get("percentage", 0),
                        "volume_24h": ticker.get("quoteVolume", 0),
                    })
                else:
                    assets.append({"symbol": symbol, "lastPrice": None})

            return assets
        except Exception:
            return []

    async def get_market_movers(self) -> dict:
        """Get biggest gainers and losers from tracked universe"""
        try:
            from services.opportunity_scanner import get_opportunity_scanner
            from services.kraken import get_kraken_client

            # Get dynamic universe
            scanner = get_opportunity_scanner()
            universe = scanner.get_dynamic_universe()

            # Fallback to top 10 liquid assets if no scanner results yet
            if not universe:
                universe = [
                    "BTCUSD", "ETHUSD", "SOLUSD", "XRPUSD", "ADAUSD",
                    "AVAXUSD", "DOGEUSD", "LINKUSD", "DOTUSD", "MATICUSD"
                ]

            # Fetch all tickers in one call (efficient)
            kraken = get_kraken_client()
            await kraken.initialize()
            all_tickers = await kraken.fetch_all_tickers()

            all_movers = []
            for symbol in universe:  # Check all tracked assets
                kraken_symbol = symbol[:-3] + "/" + symbol[-3:]
                ticker = all_tickers.get(kraken_symbol)
                if ticker and ticker.get("percentage") is not None:
                    all_movers.append({
                        "symbol": symbol,
                        "current_price": ticker.get("last", 0),
                        "change_24h": ticker.get("percentage", 0),
                        "volume": ticker.get("quoteVolume", 0),
                    })

            # Sort by 24h change
            all_movers.sort(key=lambda x: x.get("change_24h", 0), reverse=True)

            # Top gainers and losers
            gainers = [m for m in all_movers if m.get("change_24h", 0) > 0][:3]
            losers = [m for m in reversed(all_movers) if m.get("change_24h", 0) < 0][:3]

            # Calculate average
            changes = [m.get("change_24h", 0) for m in all_movers]
            avg_change = sum(changes) / len(changes) if changes else 0

            return {
                "gainers": gainers,
                "losers": losers,
                "avg_change_24h": avg_change,
                "total_assets": len(all_movers),
            }
        except Exception as e:
            return {"gainers": [], "losers": [], "avg_change_24h": 0, "error": str(e)}

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

    async def get_scanner_results(self) -> dict:
        """Get latest opportunity scanner results"""
        try:
            from services.opportunity_scanner import get_opportunity_scanner

            scanner = get_opportunity_scanner()
            result = scanner.get_last_scan_result()

            if not result:
                return {"available": False, "no_scan": True}

            # Get top opportunities
            opportunities = []
            for opp in result.top_opportunities[:5]:
                opportunities.append({
                    "symbol": opp.symbol.replace("/", "").replace("USD", ""),
                    "score": opp.total_score,
                    "entry_type": opp.entry_type,
                    "trend": opp.trend_direction,
                    "rsi": opp.rsi_value,
                    "reasoning": opp.reasoning[:50] if opp.reasoning else "",
                })

            return {
                "available": True,
                "timestamp": result.timestamp,
                "total_scanned": result.total_pairs_scanned,
                "volume_filtered": result.pairs_after_volume_filter,
                "pairs_scored": result.pairs_scored,
                "opportunities_found": result.opportunities_found,
                "uptrends": result.uptrends_found,
                "downtrends": result.downtrends_found,
                "sideways": result.sideways_found,
                "trend_pullbacks": result.trend_pullbacks,
                "contrarian_extremes": result.contrarian_extremes,
                "fear_greed": result.fear_greed_index,
                "duration": result.scan_duration_seconds,
                "opportunities": opportunities,
                "universe": scanner.get_dynamic_universe()[:5],
            }
        except Exception as e:
            return {"available": False, "error": str(e)}

    async def get_technical_indicators(self) -> dict:
        """Get real technical indicators for BTC, ETH, SOL as market reference"""
        try:
            from services.kraken import get_kraken_client
            from services.technical_indicators import analyze_all_indicators

            kraken = get_kraken_client()
            await kraken.initialize()

            # Reference assets for market overview
            assets = ["BTC/USD", "ETH/USD", "SOL/USD"]
            result = {"available": True, "assets": {}}

            for symbol in assets:
                try:
                    # Fetch 4h candles (50 candles = ~8 days of data)
                    candles = await kraken.fetch_ohlcv(symbol, timeframe='4h', limit=50)

                    if not candles or len(candles) < 30:
                        result["assets"][symbol] = {"error": "Insufficient data"}
                        continue

                    # Convert to format expected by technical_indicators
                    candle_dicts = []
                    for c in candles:
                        candle_dicts.append({
                            "timestamp": c.get("timestamp"),
                            "open": float(c.get("open", 0)),
                            "high": float(c.get("high", 0)),
                            "low": float(c.get("low", 0)),
                            "close": float(c.get("close", 0)),
                            "volume": float(c.get("volume", 0)),
                        })

                    # Calculate comprehensive technical analysis
                    analysis = analyze_all_indicators(candle_dicts)

                    # Get current price
                    current_price = candle_dicts[-1]["close"]

                    # Store results
                    result["assets"][symbol] = {
                        "price": current_price,
                        "rsi": analysis.rsi,
                        "adx": analysis.adx.value,
                        "macd_signal": analysis.macd.signal.value,
                        "macd_hist": analysis.macd.auxiliary_values.get("histogram", 0),
                        "bb_percent": analysis.bollinger.value,
                        "bb_squeeze": analysis.bollinger.auxiliary_values.get("is_squeeze", False),
                        "overall": analysis.overall_signal.value,
                        "bullish_count": analysis.bullish_count,
                        "bearish_count": analysis.bearish_count,
                        "safe_for_contrarian": analysis.safe_for_contrarian,
                        "sma_50": analysis.sma_50,
                        "sma_200": analysis.sma_200,
                    }
                except Exception as e:
                    result["assets"][symbol] = {"error": str(e)[:30]}

            return result
        except Exception as e:
            return {"available": False, "error": str(e)}

    async def get_risk_status(self) -> dict:
        """Get real portfolio risk status from Kraken and database"""
        try:
            # Get open positions from database
            open_positions = 0
            total_invested = 0
            unrealized_pnl = 0
            trading_enabled = False
            today_pnl = 0

            if self.db_pool:
                async with self.db_pool.acquire() as conn:
                    trades = await conn.fetch("""
                        SELECT t."entryPrice", t.size, t.side, a."lastPrice", a.symbol
                        FROM "Trade" t
                        JOIN "Asset" a ON t."assetId" = a.id
                        WHERE t.status = 'OPEN'
                    """)

                    for t in trades:
                        open_positions += 1
                        entry = float(t["entryPrice"]) if t["entryPrice"] else 0
                        size = float(t["size"]) if t["size"] else 0
                        current = float(t["lastPrice"]) if t["lastPrice"] else entry
                        cost = entry * size
                        total_invested += cost
                        if t["side"] == "BUY":
                            unrealized_pnl += (current - entry) * size
                        else:
                            unrealized_pnl += (entry - current) * size

                    # Get today's realized P&L
                    today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
                    daily = await conn.fetchrow("""
                        SELECT COALESCE(SUM(pnl), 0) as pnl
                        FROM "Trade"
                        WHERE "exitTime" > $1
                    """, today_start)
                    today_pnl = float(daily["pnl"]) if daily and daily["pnl"] else 0

                    # Get trading enabled status from system_config
                    config_row = await conn.fetchrow("""
                        SELECT "tradingEnabled" FROM system_config
                        ORDER BY "updatedAt" DESC LIMIT 1
                    """)
                    if config_row:
                        trading_enabled = bool(config_row["tradingEnabled"])

            # Get Fear & Greed index from API
            fear_greed = None
            try:
                from services.fear_greed import fetch_fear_greed_index
                fg_data = await fetch_fear_greed_index()
                if fg_data:
                    fear_greed = fg_data.value
            except Exception:
                pass  # Fear & Greed unavailable

            # Get scanner status
            from services.opportunity_scanner import get_opportunity_scanner
            scanner = get_opportunity_scanner()
            last_scan = scanner.get_last_scan_result()
            scan_age_mins = None
            if last_scan:
                age = datetime.now(last_scan.timestamp.tzinfo) - last_scan.timestamp
                scan_age_mins = int(age.total_seconds() / 60)

            return {
                "available": True,
                "trading_enabled": trading_enabled,
                "open_positions": open_positions,
                "total_invested": total_invested,
                "unrealized_pnl": unrealized_pnl,
                "today_pnl": today_pnl,
                "fear_greed": fear_greed,
                "scan_age_mins": scan_age_mins,
                "universe_size": len(scanner.get_dynamic_universe()),
            }
        except Exception as e:
            return {"available": False, "error": str(e)}

    def create_header(self) -> Panel:
        """Create header panel"""
        sandbox_mode = os.getenv("KRAKEN_SANDBOX_MODE", "true").lower() == "true"

        header = Text()
        header.append("◆ ", style="cyan")
        header.append("Gemini Alpha", style="bold cyan")
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

    def create_sessions_panel(self, sessions: list, expanded: bool = False) -> Panel:
        """Create full-width council sessions panel"""
        table = Table(box=box.SIMPLE_HEAD, expand=True, show_edge=False)
        table.add_column("Time", style="dim", width=8)
        table.add_column("Asset", style="cyan", width=8)
        table.add_column("Decision", width=6)
        table.add_column("Fear", justify="center", width=5)
        table.add_column("Technical", width=8)
        table.add_column("Vision", justify="center", width=6)
        table.add_column("Reasoning", style="dim", ratio=1, overflow="fold" if expanded else "ellipsis")

        # Show fewer rows if expanded to make room for full text per row
        max_rows = 4 if expanded else 12

        for s in sessions[:max_rows]:
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

            reasoning_text = s.get("reasoningLog") or s.get("reasoning") or ""
            # Show full text if expanded, otherwise truncate
            if expanded:
                reasoning = reasoning_text if reasoning_text else "-"
            else:
                reasoning = reasoning_text[:80] + "..." if len(reasoning_text) > 80 else reasoning_text or "-"

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

        title = f"Council Decisions ({len(sessions)})"
        if expanded:
            title += " [EXPANDED - press 'd' to collapse]"
        else:
            title += " [press 'd' for full text]"

        return Panel(table, title=title, box=box.ROUNDED)

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
        """Create tracked assets panel with prices and 24h change"""
        content = Text()

        if not assets:
            content.append("No tracked assets\n", style="dim")
            content.append("Scanner runs hourly at :10", style="dim italic")
            return Panel(content, title="Tracked Assets", box=box.ROUNDED)

        # Header
        content.append("Asset    Price       24h\n", style="bold dim")
        content.append("─" * 28 + "\n", style="dim")

        for a in assets[:10]:
            symbol = a.get("symbol", "?").replace("USD", "")[:6]
            price = a.get("lastPrice")
            change = a.get("change_24h", 0)

            # Format price based on magnitude
            if price:
                if price >= 1000:
                    price_str = f"${float(price):>8,.0f}"
                elif price >= 1:
                    price_str = f"${float(price):>8,.2f}"
                else:
                    price_str = f"${float(price):>8,.4f}"
            else:
                price_str = "       -"

            # Change styling
            if change and change > 0:
                change_style = "green"
                change_str = f"+{change:.1f}%"
            elif change and change < 0:
                change_style = "red"
                change_str = f"{change:.1f}%"
            else:
                change_style = "dim"
                change_str = "0.0%"

            content.append(f"{symbol:<6} ", style="cyan bold")
            content.append(f"{price_str} ", style="white")
            content.append(f"{change_str:>6}\n", style=change_style)

        return Panel(content, title=f"Tracked Assets ({len(assets)})", box=box.ROUNDED)

    def create_movers_panel(self, movers: dict) -> Panel:
        """Create market movers panel showing gainers/losers with prices"""
        content = Text()

        # Top Gainers section
        content.append("▲ TOP GAINERS\n", style="green bold")
        gainers = movers.get("gainers", [])
        if gainers:
            for g in gainers[:3]:
                symbol = g.get("symbol", "?").replace("USD", "")[:5]
                change = float(g.get("change_24h", 0))
                price = g.get("current_price", 0)
                # Format price
                if price >= 1000:
                    price_str = f"${price:,.0f}"
                elif price >= 1:
                    price_str = f"${price:.2f}"
                else:
                    price_str = f"${price:.4f}"
                content.append(f"  {symbol:<5} ", style="cyan bold")
                content.append(f"{price_str:<10} ", style="white")
                content.append(f"{change:+.1f}%\n", style="green bold")
        else:
            content.append("  No gainers\n", style="dim")

        content.append("\n")

        # Top Losers section
        content.append("▼ TOP LOSERS\n", style="red bold")
        losers = movers.get("losers", [])
        if losers:
            for l in losers[:3]:
                symbol = l.get("symbol", "?").replace("USD", "")[:5]
                change = float(l.get("change_24h", 0))
                price = l.get("current_price", 0)
                if price >= 1000:
                    price_str = f"${price:,.0f}"
                elif price >= 1:
                    price_str = f"${price:.2f}"
                else:
                    price_str = f"${price:.4f}"
                content.append(f"  {symbol:<5} ", style="cyan bold")
                content.append(f"{price_str:<10} ", style="white")
                content.append(f"{change:+.1f}%\n", style="red bold")
        else:
            content.append("  No losers\n", style="dim")

        # Market average
        content.append("\n")
        avg = movers.get("avg_change_24h", 0)
        total = movers.get("total_assets", 0)
        avg_style = "green bold" if avg > 0 else "red bold" if avg < 0 else "dim"
        content.append("Avg: ", style="dim")
        content.append(f"{avg:+.2f}%", style=avg_style)
        content.append(f" ({total} tracked)", style="dim")

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
        """Create technical indicators panel for BTC, ETH, SOL"""
        content = Text()

        if not data.get("available"):
            content.append("Loading market data...\n", style="dim")
            if data.get("error"):
                content.append(f"{data['error'][:40]}", style="red dim italic")
            return Panel(content, title="Market Technical", box=box.ROUNDED)

        assets = data.get("assets", {})
        if not assets:
            content.append("No market data available", style="dim")
            return Panel(content, title="Market Technical", box=box.ROUNDED)

        # Header row
        content.append("Asset   RSI   ADX   Signal      MACD\n", style="bold dim")
        content.append("─" * 38 + "\n", style="dim")

        for symbol, info in assets.items():
            # Get short name (BTC, ETH, SOL)
            short = symbol.replace("/USD", "")

            if info.get("error"):
                content.append(f"{short:<7} ", style="cyan")
                content.append(f"Error: {info['error'][:20]}\n", style="red dim")
                continue

            # RSI
            rsi = info.get("rsi", 50)
            rsi_style = "green bold" if rsi < 35 else "red bold" if rsi > 65 else "white"

            # ADX
            adx = info.get("adx", 25)
            adx_style = "green" if adx < 25 else "yellow" if adx < 40 else "red"

            # Overall signal
            overall = info.get("overall", "NEUTRAL")
            if "BULLISH" in overall:
                sig_style = "green bold"
                sig_icon = "▲"
            elif "BEARISH" in overall:
                sig_style = "red bold"
                sig_icon = "▼"
            else:
                sig_style = "dim"
                sig_icon = "●"

            # MACD
            macd_sig = info.get("macd_signal", "NEUTRAL")
            macd_hist = info.get("macd_hist", 0)
            macd_icon = "+" if macd_hist > 0 else "-" if macd_hist < 0 else "○"
            macd_style = "green" if "BULLISH" in macd_sig else "red" if "BEARISH" in macd_sig else "dim"

            # Build row
            content.append(f"{short:<7} ", style="cyan bold")
            content.append(f"{rsi:>4.0f}  ", style=rsi_style)
            content.append(f"{adx:>4.0f}  ", style=adx_style)
            content.append(f"{sig_icon} ", style=sig_style)
            # Shorten signal name
            sig_short = overall.replace("STRONG_", "S_")[:8]
            content.append(f"{sig_short:<8} ", style=sig_style)
            content.append(f"{macd_icon}\n", style=macd_style)

        # Summary line
        content.append("─" * 38 + "\n", style="dim")
        bullish_count = sum(1 for a in assets.values() if "BULLISH" in a.get("overall", ""))
        bearish_count = sum(1 for a in assets.values() if "BEARISH" in a.get("overall", ""))
        content.append("Market: ", style="dim")
        if bullish_count > bearish_count:
            content.append("BULLISH ", style="green bold")
        elif bearish_count > bullish_count:
            content.append("BEARISH ", style="red bold")
        else:
            content.append("MIXED ", style="yellow")
        content.append(f"({bullish_count}▲ {bearish_count}▼)", style="dim")

        return Panel(content, title="Market Technical", box=box.ROUNDED)

    def create_risk_panel(self, data: dict) -> Panel:
        """Create portfolio status panel with real data"""
        content = Text()

        if not data.get("available"):
            content.append("Loading...\n", style="dim")
            if data.get("error"):
                content.append(f"{data['error'][:30]}", style="red dim")
            return Panel(content, title="Portfolio", box=box.ROUNDED)

        # Trading status
        trading_on = data.get("trading_enabled", False)
        status_style = "green bold" if trading_on else "yellow bold"
        status_text = "LIVE" if trading_on else "PAUSED"
        content.append("Trading: ", style="dim")
        content.append(f"{status_text}\n", style=status_style)
        content.append("─" * 28 + "\n", style="dim")

        # Open positions
        positions = data.get("open_positions", 0)
        invested = data.get("total_invested", 0)
        content.append("Positions: ", style="dim")
        content.append(f"{positions}", style="cyan bold")
        if invested > 0:
            content.append(f"  (${invested:,.0f})\n", style="dim")
        else:
            content.append("\n")

        # Unrealized P&L
        unrealized = data.get("unrealized_pnl", 0)
        pnl_style = "green bold" if unrealized >= 0 else "red bold"
        content.append("Unrealized: ", style="dim")
        content.append(f"${unrealized:+,.2f}\n", style=pnl_style)

        # Today's P&L
        today = data.get("today_pnl", 0)
        today_style = "green" if today >= 0 else "red"
        content.append("Today P&L:  ", style="dim")
        content.append(f"${today:+,.2f}\n", style=today_style)

        content.append("─" * 28 + "\n", style="dim")

        # Fear & Greed
        fg = data.get("fear_greed")
        if fg is not None:
            if fg < 25:
                fg_style = "green bold"
                fg_label = "Extreme Fear"
            elif fg < 45:
                fg_style = "green"
                fg_label = "Fear"
            elif fg < 55:
                fg_style = "yellow"
                fg_label = "Neutral"
            elif fg < 75:
                fg_style = "red"
                fg_label = "Greed"
            else:
                fg_style = "red bold"
                fg_label = "Extreme Greed"
            content.append("Fear/Greed: ", style="dim")
            content.append(f"{fg}", style=fg_style)
            content.append(f" ({fg_label})\n", style=fg_style)
        else:
            content.append("Fear/Greed: ", style="dim")
            content.append("-\n", style="dim")

        # Scanner status
        scan_age = data.get("scan_age_mins")
        universe = data.get("universe_size", 0)
        content.append("Scanner:    ", style="dim")
        if scan_age is not None:
            age_style = "green" if scan_age < 70 else "yellow" if scan_age < 120 else "red"
            content.append(f"{scan_age}m ago", style=age_style)
            content.append(f" ({universe} assets)\n", style="dim")
        else:
            content.append("Not run yet\n", style="yellow")

        return Panel(content, title="Portfolio", box=box.ROUNDED)

    def create_scanner_panel(self, data: dict) -> Panel:
        """Create opportunity scanner panel showing trend analysis"""
        content = Text()

        if data.get("no_scan"):
            content.append("No scan yet\n", style="dim")
            content.append("Scanner runs hourly at :10", style="dim italic")
            return Panel(content, title="Scanner", box=box.ROUNDED)

        if not data.get("available"):
            content.append("Scanner unavailable\n", style="dim")
            if data.get("error"):
                content.append(f"{data['error'][:30]}", style="dim italic")
            return Panel(content, title="Scanner", box=box.ROUNDED)

        # Market structure summary
        uptrends = data.get("uptrends", 0)
        downtrends = data.get("downtrends", 0)
        sideways = data.get("sideways", 0)
        total = uptrends + downtrends + sideways

        content.append("MARKET STRUCTURE\n", style="bold")
        content.append(f"  Uptrends:   ", style="dim")
        content.append(f"{uptrends:>3}", style="green bold")
        up_pct = uptrends*100//total if total else 0
        content.append(f"  ({up_pct}%)\n", style="dim")
        content.append(f"  Downtrends: ", style="dim")
        content.append(f"{downtrends:>3}", style="red bold")
        down_pct = downtrends*100//total if total else 0
        content.append(f"  ({down_pct}%)\n", style="dim")
        content.append(f"  Sideways:   ", style="dim")
        content.append(f"{sideways:>3}", style="yellow bold")
        side_pct = sideways*100//total if total else 0
        content.append(f"  ({side_pct}%)\n", style="dim")

        content.append("-" * 26 + "\n", style="dim")

        # Opportunities found
        pullbacks = data.get("trend_pullbacks", 0)
        extremes = data.get("contrarian_extremes", 0)
        content.append("OPPORTUNITIES\n", style="bold")
        content.append(f"  Trend Pullbacks:  ", style="dim")
        content.append(f"{pullbacks}\n", style="green bold" if pullbacks else "dim")
        content.append(f"  Contrarian Ext:   ", style="dim")
        content.append(f"{extremes}\n", style="cyan bold" if extremes else "dim")

        # Fear & Greed
        fg = data.get("fear_greed")
        if fg is not None:
            fg_style = "green" if fg < 30 else "red" if fg > 70 else "yellow"
            content.append(f"  Fear & Greed:     ", style="dim")
            content.append(f"{fg}\n", style=fg_style + " bold")

        content.append("-" * 26 + "\n", style="dim")

        # Top opportunities
        opportunities = data.get("opportunities", [])
        if opportunities:
            content.append("TOP PICKS\n", style="bold")
            for opp in opportunities[:4]:
                icon = "+" if opp["entry_type"] == "TREND_PULLBACK" else "*"
                trend_icon = "^" if opp["trend"] == "UPTREND" else "v" if opp["trend"] == "DOWNTREND" else "-"
                trend_style = "green" if opp["trend"] == "UPTREND" else "red" if opp["trend"] == "DOWNTREND" else "dim"

                content.append(f"  {icon} ", style="dim")
                content.append(f"{opp['symbol']:<6}", style="cyan")
                content.append(f" {opp['score']:>3.0f}", style="white bold")
                content.append(f" {trend_icon}", style=trend_style)
                if opp.get("rsi"):
                    rsi_style = "green" if 40 <= opp["rsi"] <= 55 else "yellow" if opp["rsi"] < 30 else "dim"
                    content.append(f" R:{opp['rsi']:.0f}", style=rsi_style)
                content.append("\n")
        else:
            content.append("No opportunities\n", style="dim")
            if uptrends == 0:
                content.append("  (No uptrends)\n", style="dim italic")

        # Scan info
        content.append("-" * 26 + "\n", style="dim")
        scanned = data.get("total_scanned", 0)
        scored = data.get("pairs_scored", 0)
        duration = data.get("duration", 0)
        content.append(f"{scanned} scanned, {scored} scored ({duration:.0f}s)", style="dim")

        return Panel(content, title="Scanner (5.11)", box=box.ROUNDED)

    def create_help_panel(self) -> Text:
        """Create help bar"""
        help_text = Text()
        help_text.append(" r", style="cyan bold")
        help_text.append(" refresh ", style="dim")
        help_text.append("│", style="dim")
        help_text.append(" d", style="cyan bold")
        help_text.append(" details ", style="dim")
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

    def create_layout(self, sessions_expanded: bool = False) -> Layout:
        """Create the full-screen layout structure"""
        layout = Layout()

        # Main structure: header, body, footer
        layout.split_column(
            Layout(name="header", size=3),
            Layout(name="body"),
            Layout(name="footer", size=3),
        )

        # Body: grid on top, metrics row, sessions full-width at bottom
        # When sessions expanded, give it more vertical space
        if sessions_expanded:
            layout["body"].split_column(
                Layout(name="grid", ratio=1),
                Layout(name="metrics", size=8),  # Fixed small size
                Layout(name="sessions", ratio=3),  # Much larger for expanded text
            )
        else:
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

        # Metrics row: Scanner | Technical | Risk
        layout["metrics"].split_row(
            Layout(name="scanner", ratio=1),
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
        technical = await self.get_technical_indicators()
        risk = await self.get_risk_status()
        scanner = await self.get_scanner_results()

        # Create layout (pass expanded state to adjust panel sizes)
        layout = self.create_layout(sessions_expanded=self.sessions_expanded)

        # Populate layout sections
        layout["header"].update(self.create_header())
        layout["status"].update(self.create_status_panel(status))
        layout["sentiment"].update(self.create_sentiment_panel(sentiment))
        layout["trades"].update(self.create_trades_table(trades))
        layout["movers"].update(self.create_movers_panel(movers))
        layout["assets"].update(self.create_assets_panel(assets))

        # Metrics row
        layout["scanner"].update(self.create_scanner_panel(scanner))
        layout["technical"].update(self.create_technical_panel(technical))
        layout["risk"].update(self.create_risk_panel(risk))

        layout["sessions"].update(self.create_sessions_panel(sessions, expanded=self.sessions_expanded))
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
                    elif cmd == "d":
                        self.sessions_expanded = not self.sessions_expanded
                        state = "expanded" if self.sessions_expanded else "collapsed"
                        console.print(f"[cyan]Council decisions view: {state}[/cyan]")
                        await asyncio.sleep(1)

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
