"""
Kraken API client wrapper for order execution.

Story 3.1: Kraken Order Execution Service

This module extends the base Kraken client with trading capabilities:
- Market buy/sell order execution
- Balance checking
- Connection testing with authentication
- Sandbox mode support (no real trades in testing)
"""

import logging
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Optional

import ccxt.async_support as ccxt

from config import get_config
from .exceptions import (
    InsufficientFundsError,
    RateLimitError,
    OrderRejectedError,
    ConnectionError as ExecConnectionError,
    InvalidSymbolError,
)
from .kraken import KrakenClient, SYMBOL_MAP

# Configure logging
logger = logging.getLogger("kraken_execution")


class KrakenExecutionClient:
    """
    Kraken client wrapper for order execution.

    Extends base trading functionality with:
    - Authenticated API access for private endpoints
    - Market order execution (buy/sell)
    - Balance queries
    - Sandbox mode for testing

    Usage:
        client = KrakenExecutionClient()
        await client.initialize()

        # Check connection
        if await client.test_connection():
            # Get balance
            usd_balance = await client.get_balance("USD")

            # Execute trade (sandbox mode = logged only)
            if not client.is_sandbox:
                order = await client.create_market_buy_order("SOL/USD", 10.0)
    """

    def __init__(self) -> None:
        """Initialize the execution client."""
        self.config = get_config().kraken
        self.exchange: Optional[ccxt.kraken] = None
        self._initialized = False
        self._sandbox_mode = self.config.sandbox_mode

    @property
    def is_sandbox(self) -> bool:
        """Check if running in sandbox mode."""
        return self._sandbox_mode

    async def initialize(self) -> None:
        """
        Initialize the exchange connection with trading credentials.

        Raises:
            ValueError: If credentials are missing in non-sandbox mode
        """
        if self._initialized:
            return

        # Validate credentials in production mode
        if not self._sandbox_mode:
            self.config.validate_trading_credentials()

        exchange_config: dict[str, Any] = {
            'enableRateLimit': self.config.enable_rate_limit,
            'rateLimit': self.config.rate_limit_ms,
            'options': {
                'defaultType': 'spot',
                'adjustForTimeDifference': True,
            }
        }

        # Add API credentials
        if self.config.api_key and self.config.api_secret:
            exchange_config['apiKey'] = self.config.api_key
            exchange_config['secret'] = self.config.api_secret

        self.exchange = ccxt.kraken(exchange_config)
        self._initialized = True

        mode = "SANDBOX" if self._sandbox_mode else "LIVE"
        logger.info(f"Kraken execution client initialized in {mode} mode")

    async def close(self) -> None:
        """Close the exchange connection."""
        if self.exchange:
            await self.exchange.close()
            self._initialized = False
            logger.info("Kraken execution client closed")

    async def test_connection(self) -> bool:
        """
        Test connection to Kraken exchange with authentication.

        Returns:
            True if connection is successful and authenticated
        """
        try:
            await self.initialize()
            if self.exchange is None:
                return False

            # In sandbox mode, just check public endpoint
            if self._sandbox_mode:
                status = await self.exchange.fetch_status()
                if status and status.get('status') == 'ok':
                    logger.info("Kraken connection test successful (sandbox mode)")
                    return True
                return False

            # In live mode, verify authentication by fetching balance
            balance = await self.exchange.fetch_balance()
            if balance is not None:
                logger.info("Kraken connection test successful (authenticated)")
                return True

            return False

        except ccxt.AuthenticationError as e:
            logger.error(f"Kraken authentication failed: {e}")
            return False
        except Exception as e:
            logger.error(f"Kraken connection test failed: {e}")
            return False

    async def get_balance(self, currency: str = "USD") -> Decimal:
        """
        Get available balance for a currency.

        Args:
            currency: Currency code (e.g., "USD", "SOL")

        Returns:
            Available balance as Decimal

        Note:
            In sandbox mode, returns a mock balance of $10,000 USD
            or 100 units for other currencies.
        """
        await self.initialize()

        # Return mock balance in sandbox mode
        if self._sandbox_mode:
            mock_balance = Decimal("10000.00") if currency == "USD" else Decimal("100.0")
            logger.debug(f"[SANDBOX] Mock balance for {currency}: {mock_balance}")
            return mock_balance

        if self.exchange is None:
            raise RuntimeError("Exchange not initialized")

        try:
            balance = await self.exchange.fetch_balance()

            # Handle Kraken's XBT notation for BTC
            lookup_currency = "XBT" if currency == "BTC" else currency

            if lookup_currency in balance:
                free_balance = balance[lookup_currency].get('free', 0)
                return Decimal(str(free_balance))

            return Decimal("0.0")

        except ccxt.AuthenticationError as e:
            logger.error(f"Authentication error fetching balance: {e}")
            raise ExecConnectionError(f"Authentication failed: {e}")
        except Exception as e:
            logger.error(f"Error fetching balance for {currency}: {e}")
            raise

    async def get_current_price(self, symbol: str) -> Decimal:
        """
        Get the current market price for a symbol.

        Args:
            symbol: Trading pair in ccxt format (e.g., "SOL/USD")

        Returns:
            Current price as Decimal
        """
        await self.initialize()

        if self.exchange is None:
            raise RuntimeError("Exchange not initialized")

        try:
            ticker = await self.exchange.fetch_ticker(symbol)
            return Decimal(str(ticker['last']))

        except ccxt.BadSymbol as e:
            raise InvalidSymbolError(f"Invalid symbol: {symbol}", symbol=symbol)
        except Exception as e:
            logger.error(f"Error fetching price for {symbol}: {e}")
            raise

    async def create_market_buy_order(
        self,
        symbol: str,
        quantity: float,
    ) -> dict[str, Any]:
        """
        Create a market buy order.

        Args:
            symbol: Trading pair in ccxt format (e.g., "SOL/USD")
            quantity: Amount of base currency to buy

        Returns:
            Order response dict with id, price, amount, timestamp

        Raises:
            InsufficientFundsError: If balance is too low
            RateLimitError: If rate limit exceeded
            OrderRejectedError: If order is rejected
        """
        await self.initialize()

        if self.exchange is None:
            raise RuntimeError("Exchange not initialized")

        # In sandbox mode, return mock order
        if self._sandbox_mode:
            current_price = await self.get_current_price(symbol)
            mock_order = {
                'id': f'sandbox_buy_{datetime.now(timezone.utc).timestamp()}',
                'symbol': symbol,
                'type': 'market',
                'side': 'buy',
                'amount': quantity,
                'price': float(current_price),
                'cost': float(current_price * Decimal(str(quantity))),
                'timestamp': int(datetime.now(timezone.utc).timestamp() * 1000),
                'datetime': datetime.now(timezone.utc).isoformat(),
                'status': 'closed',
                'filled': quantity,
                'remaining': 0,
                'average': float(current_price),
            }
            logger.info(
                f"[SANDBOX] Would execute BUY {quantity} {symbol} @ "
                f"${current_price:.4f} (cost: ${mock_order['cost']:.2f})"
            )
            return mock_order

        try:
            order = await self.exchange.create_market_buy_order(symbol, quantity)
            logger.info(
                f"BUY order executed: {quantity} {symbol} @ "
                f"${order.get('average', order.get('price', 'N/A'))}"
            )
            return order

        except ccxt.InsufficientFunds as e:
            logger.error(f"Insufficient funds for buy order: {e}")
            raise InsufficientFundsError(
                f"Insufficient funds to buy {quantity} {symbol}",
                currency="USD",
            )
        except ccxt.RateLimitExceeded as e:
            logger.warning(f"Rate limit exceeded: {e}")
            raise RateLimitError("Rate limit exceeded, please retry")
        except ccxt.BadSymbol as e:
            raise InvalidSymbolError(f"Invalid symbol: {symbol}", symbol=symbol)
        except ccxt.ExchangeError as e:
            logger.error(f"Order rejected: {e}")
            raise OrderRejectedError(
                f"Buy order rejected: {e}",
                rejection_reason=str(e),
            )

    async def create_market_sell_order(
        self,
        symbol: str,
        quantity: float,
    ) -> dict[str, Any]:
        """
        Create a market sell order.

        Args:
            symbol: Trading pair in ccxt format (e.g., "SOL/USD")
            quantity: Amount of base currency to sell

        Returns:
            Order response dict with id, price, amount, timestamp

        Raises:
            InsufficientFundsError: If balance is too low
            RateLimitError: If rate limit exceeded
            OrderRejectedError: If order is rejected
        """
        await self.initialize()

        if self.exchange is None:
            raise RuntimeError("Exchange not initialized")

        # In sandbox mode, return mock order
        if self._sandbox_mode:
            current_price = await self.get_current_price(symbol)
            mock_order = {
                'id': f'sandbox_sell_{datetime.now(timezone.utc).timestamp()}',
                'symbol': symbol,
                'type': 'market',
                'side': 'sell',
                'amount': quantity,
                'price': float(current_price),
                'cost': float(current_price * Decimal(str(quantity))),
                'timestamp': int(datetime.now(timezone.utc).timestamp() * 1000),
                'datetime': datetime.now(timezone.utc).isoformat(),
                'status': 'closed',
                'filled': quantity,
                'remaining': 0,
                'average': float(current_price),
            }
            logger.info(
                f"[SANDBOX] Would execute SELL {quantity} {symbol} @ "
                f"${current_price:.4f} (proceeds: ${mock_order['cost']:.2f})"
            )
            return mock_order

        try:
            order = await self.exchange.create_market_sell_order(symbol, quantity)
            logger.info(
                f"SELL order executed: {quantity} {symbol} @ "
                f"${order.get('average', order.get('price', 'N/A'))}"
            )
            return order

        except ccxt.InsufficientFunds as e:
            logger.error(f"Insufficient funds for sell order: {e}")
            # Extract base currency from symbol
            base_currency = symbol.split('/')[0] if '/' in symbol else symbol[:3]
            raise InsufficientFundsError(
                f"Insufficient {base_currency} to sell {quantity}",
                currency=base_currency,
            )
        except ccxt.RateLimitExceeded as e:
            logger.warning(f"Rate limit exceeded: {e}")
            raise RateLimitError("Rate limit exceeded, please retry")
        except ccxt.BadSymbol as e:
            raise InvalidSymbolError(f"Invalid symbol: {symbol}", symbol=symbol)
        except ccxt.ExchangeError as e:
            logger.error(f"Order rejected: {e}")
            raise OrderRejectedError(
                f"Sell order rejected: {e}",
                rejection_reason=str(e),
            )

    @staticmethod
    def convert_symbol_to_kraken(db_symbol: str) -> str:
        """
        Convert database symbol format to Kraken ccxt format.

        Args:
            db_symbol: Symbol from database (e.g., "BTCUSD", "SOLUSD")

        Returns:
            ccxt-compatible symbol (e.g., "XBT/USD", "SOL/USD")
        """
        return KrakenClient.convert_symbol_to_kraken(db_symbol)

    @staticmethod
    def convert_symbol_from_kraken(kraken_symbol: str) -> str:
        """
        Convert Kraken ccxt symbol to database format.

        Args:
            kraken_symbol: ccxt symbol (e.g., "XBT/USD", "SOL/USD")

        Returns:
            Database symbol format (e.g., "BTCUSD", "SOLUSD")
        """
        return KrakenClient.convert_symbol_from_kraken(kraken_symbol)


# Global execution client instance
_execution_client: Optional[KrakenExecutionClient] = None


def get_kraken_execution_client() -> KrakenExecutionClient:
    """Get or create the global Kraken execution client instance."""
    global _execution_client
    if _execution_client is None:
        _execution_client = KrakenExecutionClient()
    return _execution_client


async def close_kraken_execution_client() -> None:
    """Close the global Kraken execution client connection."""
    global _execution_client
    if _execution_client is not None:
        await _execution_client.close()
        _execution_client = None
