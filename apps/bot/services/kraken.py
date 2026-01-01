"""
Kraken API client for fetching OHLCV data.

This module provides functionality to:
- Connect to Kraken exchange via ccxt
- Fetch OHLCV candle data for active assets
- Handle symbol conversion (e.g., BTC -> XBT)
- Implement retry logic with exponential backoff
- Implement circuit breaker pattern for resilience

Based on Story 1.3: Kraken Data Ingestor requirements.
"""

import asyncio
import logging
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Optional

import ccxt.async_support as ccxt
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    before_sleep_log,
    RetryError,
)

from config import get_config

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
)
logger = logging.getLogger("kraken_ingestor")


# Kraken symbol mapping - Kraken uses XBT for Bitcoin
# Maps our database symbol format to ccxt/Kraken format
SYMBOL_MAP: dict[str, str] = {
    "BTCUSD": "XBT/USD",
    "ETHUSD": "ETH/USD",
    "SOLUSD": "SOL/USD",
    "ADAUSD": "ADA/USD",
    "DOTUSD": "DOT/USD",
    "AVAXUSD": "AVAX/USD",
    "MATICUSD": "MATIC/USD",
    "LINKUSD": "LINK/USD",
    "UNIUSD": "UNI/USD",
    "AAVEUSD": "AAVE/USD",
    "ATOMUSD": "ATOM/USD",
    "LTCUSD": "LTC/USD",
    "XLMUSD": "XLM/USD",
    "ALGOUSD": "ALGO/USD",
    "XTZUSD": "XTZ/USD",
    "EOSUSD": "EOS/USD",
    "XMRUSD": "XMR/USD",
    "TRXUSD": "TRX/USD",
    "FILUSD": "FIL/USD",
    "ICPUSD": "ICP/USD",
    "SANDUSD": "SAND/USD",
    "MANAUSD": "MANA/USD",
    "AXSUSD": "AXS/USD",
    "APEUSD": "APE/USD",
    "NEARUSD": "NEAR/USD",
    "FTMUSD": "FTM/USD",
    "GRTUSD": "GRT/USD",
    "ENSUSD": "ENS/USD",
    "LDOUSD": "LDO/USD",
    "OPUSD": "OP/USD",
}


class CircuitBreaker:
    """
    Circuit breaker pattern implementation for API resilience.

    After consecutive failures, the circuit opens and blocks requests
    for a cooldown period before attempting recovery.
    """

    def __init__(
        self,
        failure_threshold: int = 5,
        cooldown_seconds: int = 300,  # 5 minutes
    ) -> None:
        self.failure_threshold = failure_threshold
        self.cooldown_seconds = cooldown_seconds
        self.consecutive_failures = 0
        self.last_failure_time: Optional[datetime] = None
        self.is_open = False

    def record_success(self) -> None:
        """Record a successful call, resetting the failure count."""
        self.consecutive_failures = 0
        self.is_open = False

    def record_failure(self) -> None:
        """Record a failed call, potentially opening the circuit."""
        self.consecutive_failures += 1
        self.last_failure_time = datetime.now(timezone.utc)

        if self.consecutive_failures >= self.failure_threshold:
            self.is_open = True
            logger.critical(
                f"Circuit breaker OPEN after {self.consecutive_failures} consecutive failures. "
                f"Cooling down for {self.cooldown_seconds} seconds."
            )

    def can_proceed(self) -> bool:
        """Check if a request can proceed through the circuit."""
        if not self.is_open:
            return True

        # Check if cooldown period has passed
        if self.last_failure_time is None:
            return True

        elapsed = (datetime.now(timezone.utc) - self.last_failure_time).total_seconds()
        if elapsed >= self.cooldown_seconds:
            logger.info("Circuit breaker cooldown complete, attempting recovery...")
            self.is_open = False
            self.consecutive_failures = 0
            return True

        logger.warning(
            f"Circuit breaker is OPEN. {self.cooldown_seconds - elapsed:.0f} seconds remaining."
        )
        return False


class KrakenClient:
    """
    Async client for Kraken exchange using ccxt.

    Provides methods to fetch OHLCV data with proper rate limiting,
    retry logic, and error handling.
    """

    def __init__(self) -> None:
        self.config = get_config().kraken
        self.exchange: Optional[ccxt.kraken] = None
        self.circuit_breaker = CircuitBreaker()
        self._initialized = False

    async def initialize(self) -> None:
        """Initialize the exchange connection."""
        if self._initialized:
            return

        exchange_config: dict[str, Any] = {
            'enableRateLimit': self.config.enable_rate_limit,
            'rateLimit': self.config.rate_limit_ms,
            'options': {
                'adjustForTimeDifference': True,
            }
        }

        # Add API credentials if available (not required for public endpoints)
        if self.config.api_key and self.config.api_secret:
            exchange_config['apiKey'] = self.config.api_key
            exchange_config['secret'] = self.config.api_secret

        self.exchange = ccxt.kraken(exchange_config)
        self._initialized = True
        logger.info("Kraken exchange client initialized")

    async def close(self) -> None:
        """Close the exchange connection."""
        if self.exchange:
            await self.exchange.close()
            self._initialized = False
            logger.info("Kraken exchange client closed")

    async def test_connection(self) -> bool:
        """
        Test connection to Kraken exchange.

        Returns:
            True if connection is successful, False otherwise.
        """
        try:
            await self.initialize()
            if self.exchange is None:
                return False

            status = await self.exchange.fetch_status()
            if status and status.get('status') == 'ok':
                logger.info("Kraken connection test successful")
                return True

            logger.warning(f"Kraken status: {status}")
            return False
        except Exception as e:
            logger.error(f"Kraken connection test failed: {e}")
            return False

    @staticmethod
    def convert_symbol_to_kraken(db_symbol: str) -> str:
        """
        Convert database symbol format to Kraken ccxt format.

        Args:
            db_symbol: Symbol from database (e.g., "BTCUSD", "SOLUSD")

        Returns:
            ccxt-compatible symbol (e.g., "XBT/USD", "SOL/USD")

        Raises:
            ValueError: If symbol is not in the known mapping
        """
        # First check exact mapping
        if db_symbol in SYMBOL_MAP:
            return SYMBOL_MAP[db_symbol]

        # Try to construct from pattern (XXXUSD -> XXX/USD)
        if db_symbol.endswith("USD") and len(db_symbol) >= 6:
            base = db_symbol[:-3]
            # Handle BTC -> XBT conversion
            if base == "BTC":
                base = "XBT"
            return f"{base}/USD"

        raise ValueError(f"Unknown symbol format: {db_symbol}")

    @staticmethod
    def convert_symbol_from_kraken(kraken_symbol: str) -> str:
        """
        Convert Kraken ccxt symbol to database format.

        Args:
            kraken_symbol: ccxt symbol (e.g., "XBT/USD", "SOL/USD")

        Returns:
            Database symbol format (e.g., "BTCUSD", "SOLUSD")
        """
        # Remove the slash and convert XBT back to BTC
        parts = kraken_symbol.split("/")
        if len(parts) != 2:
            raise ValueError(f"Invalid Kraken symbol format: {kraken_symbol}")

        base = parts[0]
        quote = parts[1]

        # Convert XBT back to BTC
        if base == "XBT":
            base = "BTC"

        return f"{base}{quote}"

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((ccxt.NetworkError, ccxt.RequestTimeout)),
        before_sleep=before_sleep_log(logger, logging.WARNING),
    )
    async def fetch_ohlcv(
        self,
        symbol: str,
        timeframe: str = "15m",
        limit: int = 1,
    ) -> list[dict[str, Any]]:
        """
        Fetch OHLCV data from Kraken for a single symbol.

        Args:
            symbol: Trading pair in ccxt format (e.g., "SOL/USD")
            timeframe: Candle interval (default: "15m")
            limit: Number of candles to fetch (default: 1 = latest)

        Returns:
            List of OHLCV dicts with keys: timestamp, open, high, low, close, volume

        Raises:
            ccxt.NetworkError: On network issues (will be retried)
            ccxt.RequestTimeout: On timeout (will be retried)
            ccxt.BadSymbol: If symbol is invalid
        """
        await self.initialize()
        if self.exchange is None:
            raise RuntimeError("Exchange not initialized")

        # Check circuit breaker
        if not self.circuit_breaker.can_proceed():
            raise RuntimeError("Circuit breaker is open, skipping request")

        try:
            # Fetch OHLCV data
            ohlcv_data = await self.exchange.fetch_ohlcv(
                symbol,
                timeframe=timeframe,
                limit=limit,
            )

            self.circuit_breaker.record_success()

            # Convert to dict format
            result = []
            for ohlcv in ohlcv_data:
                # Use naive datetime for Prisma compatibility (data is always UTC)
                ts = datetime.fromtimestamp(ohlcv[0] / 1000, tz=timezone.utc).replace(tzinfo=None)
                result.append({
                    "timestamp": ts,
                    "open": Decimal(str(ohlcv[1])),
                    "high": Decimal(str(ohlcv[2])),
                    "low": Decimal(str(ohlcv[3])),
                    "close": Decimal(str(ohlcv[4])),
                    "volume": Decimal(str(ohlcv[5])),
                    "timeframe": timeframe,
                })

            return result

        except ccxt.BadSymbol as e:
            # Don't retry on invalid symbol - it won't work
            logger.error(f"Invalid symbol {symbol}: {e}")
            raise

        except ccxt.RateLimitExceeded:
            # Back off for 60 seconds on rate limit
            logger.warning(f"Rate limit exceeded for {symbol}, backing off 60 seconds")
            self.circuit_breaker.record_failure()
            await asyncio.sleep(60)
            raise ccxt.NetworkError("Rate limit exceeded, please retry")

        except Exception as e:
            self.circuit_breaker.record_failure()
            raise

    async def fetch_ohlcv_for_asset(
        self,
        db_symbol: str,
        timeframe: str = "15m",
        limit: int = 1,
    ) -> list[dict[str, Any]]:
        """
        Fetch OHLCV data using database symbol format.

        Args:
            db_symbol: Database symbol (e.g., "BTCUSD", "SOLUSD")
            timeframe: Candle interval
            limit: Number of candles

        Returns:
            List of OHLCV dicts
        """
        kraken_symbol = self.convert_symbol_to_kraken(db_symbol)
        return await self.fetch_ohlcv(kraken_symbol, timeframe, limit)

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((ccxt.NetworkError, ccxt.RequestTimeout)),
        before_sleep=before_sleep_log(logger, logging.WARNING),
    )
    async def fetch_daily_ohlcv(
        self,
        symbol: str,
        limit: int = 250
    ) -> list[dict[str, Any]]:
        """
        Fetch daily OHLCV for market regime analysis.

        Story 5.1: Used to calculate 200 DMA and detect Golden/Death crosses.

        Args:
            symbol: Trading pair in ccxt format (e.g., "SOL/USD")
            limit: Number of daily candles to fetch (default: 250 for 200 DMA + buffer)

        Returns:
            List of daily OHLCV dicts with keys: timestamp, open, high, low, close, volume

        Raises:
            ccxt.NetworkError: On network issues (will be retried)
            ccxt.RequestTimeout: On timeout (will be retried)
            ccxt.BadSymbol: If symbol is invalid
        """
        await self.initialize()
        if self.exchange is None:
            raise RuntimeError("Exchange not initialized")

        # Check circuit breaker
        if not self.circuit_breaker.can_proceed():
            raise RuntimeError("Circuit breaker is open, skipping request")

        try:
            # Fetch daily OHLCV data
            ohlcv_data = await self.exchange.fetch_ohlcv(
                symbol,
                timeframe='1d',
                limit=limit,
            )

            self.circuit_breaker.record_success()

            # Convert to dict format - use float for pandas TA compatibility
            result = []
            for ohlcv in ohlcv_data:
                # Use naive datetime for consistency
                ts = datetime.fromtimestamp(ohlcv[0] / 1000, tz=timezone.utc).replace(tzinfo=None)
                result.append({
                    "timestamp": ts,
                    "open": float(ohlcv[1]),
                    "high": float(ohlcv[2]),
                    "low": float(ohlcv[3]),
                    "close": float(ohlcv[4]),
                    "volume": float(ohlcv[5]),
                    "timeframe": "1d",
                })

            logger.info(f"Fetched {len(result)} daily candles for {symbol}")
            return result

        except ccxt.BadSymbol as e:
            logger.error(f"Invalid symbol {symbol}: {e}")
            raise

        except ccxt.RateLimitExceeded:
            logger.warning(f"Rate limit exceeded for {symbol}, backing off 60 seconds")
            self.circuit_breaker.record_failure()
            await asyncio.sleep(60)
            raise ccxt.NetworkError("Rate limit exceeded, please retry")

        except Exception as e:
            self.circuit_breaker.record_failure()
            raise

    async def fetch_daily_ohlcv_for_asset(
        self,
        db_symbol: str,
        limit: int = 250
    ) -> list[dict[str, Any]]:
        """
        Fetch daily OHLCV using database symbol format.

        Story 5.1: Convenience method for regime detection.

        Args:
            db_symbol: Database symbol (e.g., "BTCUSD", "SOLUSD")
            limit: Number of daily candles (default: 250 for 200 DMA)

        Returns:
            List of daily OHLCV dicts
        """
        kraken_symbol = self.convert_symbol_to_kraken(db_symbol)
        return await self.fetch_daily_ohlcv(kraken_symbol, limit)

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((ccxt.NetworkError, ccxt.RequestTimeout)),
        before_sleep=before_sleep_log(logger, logging.WARNING),
    )
    async def fetch_all_tickers(self) -> dict[str, dict[str, Any]]:
        """
        Fetch ticker data for ALL trading pairs in a single API call.

        Story 5.8: Efficient bulk fetch for opportunity scanner.

        Returns:
            Dict mapping symbol to ticker data:
            {
                "BTC/USD": {
                    "symbol": "BTC/USD",
                    "last": 42000.0,
                    "high": 43000.0,
                    "low": 41000.0,
                    "baseVolume": 1234.5,
                    "quoteVolume": 52000000.0,  # 24h volume in USD
                    "change": -2.5,  # % change
                    ...
                },
                ...
            }

        Raises:
            ccxt.NetworkError: On network issues (will be retried)
            ccxt.RequestTimeout: On timeout (will be retried)
        """
        await self.initialize()
        if self.exchange is None:
            raise RuntimeError("Exchange not initialized")

        if not self.circuit_breaker.can_proceed():
            raise RuntimeError("Circuit breaker is open, skipping request")

        try:
            tickers = await self.exchange.fetch_tickers()
            self.circuit_breaker.record_success()

            # Filter to USD pairs only
            usd_tickers = {
                k: v for k, v in tickers.items()
                if k.endswith('/USD')
            }

            logger.info(f"Fetched {len(usd_tickers)} USD tickers from Kraken")
            return usd_tickers

        except Exception as e:
            self.circuit_breaker.record_failure()
            raise

    async def get_usd_pair_count(self) -> int:
        """Get count of available USD trading pairs."""
        await self.initialize()
        if self.exchange is None:
            return 0

        await self.exchange.load_markets()
        usd_pairs = [s for s in self.exchange.symbols if s.endswith('/USD')]
        return len(usd_pairs)


# Global client instance
_kraken_client: Optional[KrakenClient] = None


def get_kraken_client() -> KrakenClient:
    """Get or create the global Kraken client instance."""
    global _kraken_client
    if _kraken_client is None:
        _kraken_client = KrakenClient()
    return _kraken_client


async def close_kraken_client() -> None:
    """Close the global Kraken client connection."""
    global _kraken_client
    if _kraken_client is not None:
        await _kraken_client.close()
        _kraken_client = None
