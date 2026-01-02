"""
Dynamic Opportunity Scanner for ContrarianAI.

Story 5.8: Replaces fixed trading universe with dynamic discovery.
Story 5.11: Trend-Confirmed Pullback Trading

REVISED STRATEGY:
- Primary: Scan for uptrend pullback opportunities (buy dips in uptrends)
- Secondary: Extreme contrarian plays (fear < 25, RSI < 30)
- Fetch Fear & Greed index to pass to scoring engine

Scan Strategy (API-efficient):
1. Phase 1: Bulk ticker fetch (1 API call) for all ~613 USD pairs
2. Filter: Remove pairs with < $1M 24h volume (~550 eliminated)
3. Phase 2: Fetch OHLCV for top ~50 candidates by volume (~50 API calls)
4. Score: Calculate trend-confirmed opportunity score for each
5. Select: Top 5-10 assets by score, prioritizing TREND_PULLBACK over CONTRARIAN_EXTREME

Total API calls: ~51 (1 ticker + 50 OHLCV)
Target scan time: < 30 seconds
Schedule: Hourly at minute 10
"""

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from config import get_config
from services.kraken import get_kraken_client, KrakenClient
from services.contrarian_score import (
    ScoreBreakdown,
    calculate_contrarian_score,
    rank_opportunities,
    get_score_summary,
)

logger = logging.getLogger("opportunity_scanner")


@dataclass
class ScanResult:
    """Result of opportunity scan cycle."""

    timestamp: datetime
    total_pairs_scanned: int
    pairs_after_volume_filter: int
    pairs_scored: int
    opportunities_found: int
    top_opportunities: List[ScoreBreakdown]
    scan_duration_seconds: float
    errors: List[str]

    # NEW: Trend statistics
    uptrends_found: int = 0
    downtrends_found: int = 0
    sideways_found: int = 0
    trend_pullbacks: int = 0
    contrarian_extremes: int = 0

    # Fear & Greed context
    fear_greed_index: Optional[int] = None


class OpportunityScanner:
    """
    Scans Kraken for trend-confirmed trading opportunities.

    STRATEGY SHIFT (Story 5.11):
    - Primary: Find uptrend pullbacks (buy dips in confirmed uptrends)
    - Secondary: Extreme contrarian (only at Fear < 25, RSI < 30)

    Designed for API efficiency:
    - Single bulk ticker call for initial filtering
    - Selective OHLCV calls only for candidates
    - Respects rate limits with delays
    """

    def __init__(self):
        self.config = get_config().scanner
        self.kraken_client: Optional[KrakenClient] = None
        self._last_scan_result: Optional[ScanResult] = None
        self._dynamic_universe: List[str] = []
        self._current_fear_greed: Optional[int] = None

    async def initialize(self) -> None:
        """Initialize the scanner and Kraken client."""
        self.kraken_client = get_kraken_client()
        await self.kraken_client.initialize()

    async def close(self) -> None:
        """Close connections."""
        if self.kraken_client:
            await self.kraken_client.close()

    def get_dynamic_universe(self) -> List[str]:
        """
        Get current dynamic trading universe.

        Returns list of symbols (database format, e.g., "BTCUSD")
        that passed the latest scan.
        """
        return self._dynamic_universe.copy()

    def get_last_scan_result(self) -> Optional[ScanResult]:
        """Get the most recent scan result."""
        return self._last_scan_result

    async def _fetch_fear_greed_index(self) -> Optional[int]:
        """
        Fetch current Fear & Greed index.

        Uses cached sentiment data from database if available,
        or fetches from Alternative.me API.
        """
        try:
            # Try to get from database first (more reliable)
            from database.session import get_async_session
            from sqlalchemy import text

            async with get_async_session() as session:
                result = await session.execute(text("""
                    SELECT score FROM sentiment_scores
                    WHERE score_type = 'fear_greed'
                    ORDER BY recorded_at DESC
                    LIMIT 1
                """))
                row = result.fetchone()
                if row:
                    self._current_fear_greed = int(row[0])
                    return self._current_fear_greed

            # Fallback: fetch from Alternative.me
            import aiohttp
            async with aiohttp.ClientSession() as http_session:
                async with http_session.get(
                    "https://api.alternative.me/fng/?limit=1",
                    timeout=aiohttp.ClientTimeout(total=5)
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        if data.get("data"):
                            self._current_fear_greed = int(data["data"][0]["value"])
                            return self._current_fear_greed

        except Exception as e:
            logger.warning(f"[Scanner] Failed to fetch Fear & Greed index: {e}")

        return None

    async def run_scan(self) -> ScanResult:
        """
        Execute full opportunity scan cycle.

        Returns:
            ScanResult with scan statistics and top opportunities
        """
        start_time = datetime.now(timezone.utc)
        errors: List[str] = []

        logger.info(f"\n{'='*60}")
        logger.info(f"[Scanner] Starting TREND-CONFIRMED scan at {start_time.isoformat()}")
        logger.info(f"[Scanner] Strategy: Uptrend Pullbacks (primary) + Extreme Contrarian (secondary)")
        logger.info(f"{'='*60}")

        if not self.config.enabled:
            logger.info("[Scanner] Scanner disabled via configuration")
            return ScanResult(
                timestamp=start_time,
                total_pairs_scanned=0,
                pairs_after_volume_filter=0,
                pairs_scored=0,
                opportunities_found=0,
                top_opportunities=[],
                scan_duration_seconds=0,
                errors=["Scanner disabled"]
            )

        await self.initialize()

        # Fetch Fear & Greed index for scoring
        fear_greed = await self._fetch_fear_greed_index()
        if fear_greed is not None:
            logger.info(f"[Scanner] Fear & Greed Index: {fear_greed}")
        else:
            logger.warning("[Scanner] Fear & Greed index unavailable")

        # Phase 1: Bulk ticker fetch
        logger.info("[Scanner] Phase 1: Fetching all tickers...")
        try:
            tickers = await self.kraken_client.fetch_all_tickers()
        except Exception as e:
            error_msg = f"Failed to fetch tickers: {e}"
            logger.error(f"[Scanner] {error_msg}")
            errors.append(error_msg)
            return self._create_error_result(start_time, errors)

        total_pairs = len(tickers)
        logger.info(f"[Scanner] Found {total_pairs} USD pairs")

        # Phase 2: Volume filter
        logger.info(f"[Scanner] Phase 2: Filtering by volume >= ${self.config.min_volume_usd:,.0f}...")
        volume_filtered = self._filter_by_volume(tickers)
        pairs_after_filter = len(volume_filtered)
        logger.info(f"[Scanner] {pairs_after_filter} pairs passed volume filter")

        # Limit OHLCV fetches to top 50 by volume to control API usage
        max_ohlcv_fetches = 50
        candidates = sorted(
            volume_filtered.items(),
            key=lambda x: x[1].get('quoteVolume', 0) or 0,
            reverse=True
        )[:max_ohlcv_fetches]

        logger.info(f"[Scanner] Selected top {len(candidates)} candidates for trend analysis")

        # Phase 3: Fetch OHLCV and score each candidate
        logger.info("[Scanner] Phase 3: Analyzing trends and scoring...")
        scores: List[ScoreBreakdown] = []

        # Track trend statistics
        trend_stats = {"UPTREND": 0, "DOWNTREND": 0, "SIDEWAYS": 0}
        entry_stats = {"TREND_PULLBACK": 0, "CONTRARIAN_EXTREME": 0, "NO_OPPORTUNITY": 0}

        for i, (symbol, ticker_data) in enumerate(candidates):
            try:
                # Fetch OHLCV (4h candles, 50 candles = ~8 days)
                candles = await self.kraken_client.fetch_ohlcv(
                    symbol,
                    timeframe='4h',
                    limit=50
                )

                # Convert candle data to format expected by scoring module
                candle_dicts = self._convert_candles_for_scoring(candles)

                # Calculate score with trend analysis
                score = calculate_contrarian_score(
                    symbol,
                    candle_dicts,
                    ticker_data,
                    fear_greed_index=fear_greed
                )
                scores.append(score)

                # Track statistics
                trend_stats[score.trend_direction] = trend_stats.get(score.trend_direction, 0) + 1
                entry_stats[score.entry_type] = entry_stats.get(score.entry_type, 0) + 1

                # Log opportunities
                if score.total_score >= self.config.min_score:
                    logger.info(f"[Scanner] {get_score_summary(score)}")

                # Rate limiting delay
                await asyncio.sleep(0.5)  # 500ms between calls

                # Progress logging every 10 pairs
                if (i + 1) % 10 == 0:
                    logger.info(f"[Scanner] Analyzed {i + 1}/{len(candidates)} candidates...")

            except Exception as e:
                error_msg = f"Error scoring {symbol}: {e}"
                logger.warning(f"[Scanner] {error_msg}")
                errors.append(error_msg)

        # Phase 4: Rank and select top opportunities
        logger.info("[Scanner] Phase 4: Ranking opportunities by trend quality...")
        top_opportunities = rank_opportunities(
            scores,
            min_score=self.config.min_score,
            max_results=self.config.universe_size
        )

        # Update dynamic universe (convert to database symbol format)
        self._dynamic_universe = [
            self._convert_to_db_symbol(opp.symbol)
            for opp in top_opportunities
        ]

        # Calculate duration
        end_time = datetime.now(timezone.utc)
        duration = (end_time - start_time).total_seconds()

        # Create result with trend statistics
        result = ScanResult(
            timestamp=start_time,
            total_pairs_scanned=total_pairs,
            pairs_after_volume_filter=pairs_after_filter,
            pairs_scored=len(scores),
            opportunities_found=len(top_opportunities),
            top_opportunities=top_opportunities,
            scan_duration_seconds=duration,
            errors=errors,
            uptrends_found=trend_stats.get("UPTREND", 0),
            downtrends_found=trend_stats.get("DOWNTREND", 0),
            sideways_found=trend_stats.get("SIDEWAYS", 0),
            trend_pullbacks=entry_stats.get("TREND_PULLBACK", 0),
            contrarian_extremes=entry_stats.get("CONTRARIAN_EXTREME", 0),
            fear_greed_index=fear_greed
        )

        self._last_scan_result = result

        # Log summary
        logger.info(f"\n[Scanner] ═══════════════════════════════════════════════════════")
        logger.info(f"[Scanner] SCAN COMPLETE - TREND ANALYSIS SUMMARY")
        logger.info(f"[Scanner] ═══════════════════════════════════════════════════════")
        logger.info(f"[Scanner] Total pairs scanned: {total_pairs}")
        logger.info(f"[Scanner] After volume filter: {pairs_after_filter}")
        logger.info(f"[Scanner] Pairs analyzed: {len(scores)}")
        logger.info(f"[Scanner] ───────────────────────────────────────────────────────")
        logger.info(f"[Scanner] MARKET STRUCTURE:")
        logger.info(f"[Scanner]   ▲ Uptrends:  {trend_stats.get('UPTREND', 0)}")
        logger.info(f"[Scanner]   ▼ Downtrends: {trend_stats.get('DOWNTREND', 0)}")
        logger.info(f"[Scanner]   ─ Sideways:  {trend_stats.get('SIDEWAYS', 0)}")
        logger.info(f"[Scanner] ───────────────────────────────────────────────────────")
        logger.info(f"[Scanner] OPPORTUNITIES FOUND:")
        logger.info(f"[Scanner]   📈 Trend Pullbacks:     {entry_stats.get('TREND_PULLBACK', 0)}")
        logger.info(f"[Scanner]   💎 Contrarian Extremes: {entry_stats.get('CONTRARIAN_EXTREME', 0)}")
        logger.info(f"[Scanner] ───────────────────────────────────────────────────────")
        logger.info(f"[Scanner] Fear & Greed: {fear_greed if fear_greed else 'N/A'}")
        logger.info(f"[Scanner] Duration: {duration:.1f}s")

        if top_opportunities:
            logger.info(f"\n[Scanner] TOP OPPORTUNITIES (prioritized by trend quality):")
            for i, opp in enumerate(top_opportunities, 1):
                type_icon = "📈" if opp.entry_type == "TREND_PULLBACK" else "💎"
                logger.info(
                    f"[Scanner]   {i}. {type_icon} {opp.symbol}: "
                    f"Score {opp.total_score:.0f} | "
                    f"{opp.trend_direction} | "
                    f"RSI {opp.rsi_value:.1f if opp.rsi_value else 'N/A'} | "
                    f"Vol ${opp.volume_24h_usd/1e6:.1f}M"
                )
                logger.info(f"[Scanner]      {opp.reasoning}")
        else:
            logger.info(f"\n[Scanner] No opportunities found meeting threshold (min score: {self.config.min_score})")
            if trend_stats.get("UPTREND", 0) == 0:
                logger.info("[Scanner] Reason: No uptrends detected - market may be in downtrend/sideways phase")
            elif fear_greed and fear_greed > 75:
                logger.info(f"[Scanner] Reason: Extreme greed ({fear_greed}) - wait for pullback")

        logger.info(f"\n[Scanner] Dynamic Universe: {self._dynamic_universe}")
        logger.info(f"{'='*60}\n")

        return result

    def _filter_by_volume(
        self,
        tickers: Dict[str, Dict[str, Any]]
    ) -> Dict[str, Dict[str, Any]]:
        """Filter tickers by minimum volume threshold."""
        return {
            symbol: data
            for symbol, data in tickers.items()
            if (data.get('quoteVolume') or 0) >= self.config.min_volume_usd
        }

    def _convert_to_db_symbol(self, ccxt_symbol: str) -> str:
        """
        Convert ccxt symbol format to database format.

        e.g., "BTC/USD" -> "BTCUSD", "XBT/USD" -> "BTCUSD"
        """
        # Remove slash
        symbol = ccxt_symbol.replace('/', '')
        # Handle Kraken XBT -> BTC
        if symbol.startswith('XBT'):
            symbol = 'BTC' + symbol[3:]
        return symbol

    def _convert_candles_for_scoring(
        self,
        candles: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Convert candles from Kraken client format to scoring module format.

        Kraken client returns dicts with timestamp, open, high, low, close, volume
        as Decimal objects. Scoring module expects float values.
        """
        result = []
        for candle in candles:
            result.append({
                "timestamp": candle.get("timestamp"),
                "open": float(candle.get("open", 0)),
                "high": float(candle.get("high", 0)),
                "low": float(candle.get("low", 0)),
                "close": float(candle.get("close", 0)),
                "volume": float(candle.get("volume", 0)),
            })
        return result

    def _create_error_result(
        self,
        start_time: datetime,
        errors: List[str]
    ) -> ScanResult:
        """Create error result when scan fails early."""
        return ScanResult(
            timestamp=start_time,
            total_pairs_scanned=0,
            pairs_after_volume_filter=0,
            pairs_scored=0,
            opportunities_found=0,
            top_opportunities=[],
            scan_duration_seconds=0,
            errors=errors
        )


# Global scanner instance
_scanner: Optional[OpportunityScanner] = None


def get_opportunity_scanner() -> OpportunityScanner:
    """Get or create the global scanner instance."""
    global _scanner
    if _scanner is None:
        _scanner = OpportunityScanner()
    return _scanner


async def run_opportunity_scan() -> ScanResult:
    """
    Run opportunity scan (scheduler entry point).

    Returns:
        ScanResult with scan statistics
    """
    scanner = get_opportunity_scanner()
    return await scanner.run_scan()


def get_dynamic_trading_universe() -> List[str]:
    """
    Get current dynamic trading universe.

    Used by council cycle to get active assets.
    Falls back to static configuration if scanner disabled or no results.

    Returns:
        List of tradeable asset symbols in database format
    """
    scanner = get_opportunity_scanner()
    universe = scanner.get_dynamic_universe()

    if not universe:
        # Fallback to static configuration (Story 5.2)
        from services.asset_universe import get_full_asset_universe
        logger.info("[Scanner] No dynamic universe, falling back to static config")
        return get_full_asset_universe()

    return universe
