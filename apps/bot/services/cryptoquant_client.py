"""
CryptoQuant API client for on-chain data (Story 5.6).

This module provides async API access to CryptoQuant for:
- Exchange inflow/outflow data
- Whale transaction tracking
- Perpetual funding rates
- Stablecoin reserves

API Documentation: https://cryptoquant.com/docs
"""

import httpx
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, List, Optional
from decimal import Decimal
import logging

from config import get_config

logger = logging.getLogger(__name__)


class CryptoQuantClient:
    """
    Async client for CryptoQuant on-chain data API.

    Provides methods for fetching:
    - Exchange flows (inflow/outflow/netflow)
    - Whale transactions (large wallet movements)
    - Funding rates (perpetual futures)
    - Stablecoin reserves (buying power indicator)
    """

    BASE_URL = "https://api.cryptoquant.com/v1"

    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize the CryptoQuant client.

        Args:
            api_key: Optional API key override. If not provided,
                     uses CRYPTOQUANT_API_KEY from environment.
        """
        config = get_config()
        self.api_key = api_key or config.onchain.cryptoquant_api_key

        if not self.api_key:
            raise ValueError("CRYPTOQUANT_API_KEY not configured")

        self.client = httpx.AsyncClient(
            headers={"Authorization": f"Bearer {self.api_key}"},
            timeout=30.0
        )

    async def get_exchange_flow(
        self,
        asset: str,
        window: str = "day",
        limit: int = 7
    ) -> List[Dict[str, Any]]:
        """
        Get exchange inflow/outflow data.

        Args:
            asset: "btc" or "eth"
            window: "hour", "day"
            limit: Number of data points

        Returns:
            List of flow data points with:
            - timestamp: datetime
            - inflow: Decimal
            - outflow: Decimal
            - netflow: Decimal
            - reserve: Decimal
        """
        try:
            response = await self.client.get(
                f"{self.BASE_URL}/{asset}/exchange-flows/reserve",
                params={
                    "window": window,
                    "limit": limit
                }
            )
            response.raise_for_status()
            data = response.json()

            results = []
            for d in data.get("result", {}).get("data", []):
                try:
                    results.append({
                        "timestamp": self._parse_datetime(d.get("date")),
                        "inflow": Decimal(str(d.get("inflow", 0))),
                        "outflow": Decimal(str(d.get("outflow", 0))),
                        "netflow": Decimal(str(d.get("netflow", 0))),
                        "reserve": Decimal(str(d.get("reserve", 0)))
                    })
                except (ValueError, TypeError) as e:
                    logger.warning(f"Skipping malformed flow data: {e}")
                    continue

            return results

        except httpx.HTTPStatusError as e:
            logger.error(f"CryptoQuant exchange flow HTTP error: {e}")
            return []
        except Exception as e:
            logger.error(f"CryptoQuant exchange flow error: {e}")
            return []

    async def get_whale_transactions(
        self,
        asset: str,
        min_value_usd: int = 1000000,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Get large wallet transactions.

        Args:
            asset: "btc" or "eth"
            min_value_usd: Minimum transaction value
            limit: Number of transactions

        Returns:
            List of whale transactions with:
            - timestamp: datetime
            - value_usd: Decimal
            - from_type: str (exchange, whale, etc.)
            - to_type: str
        """
        try:
            response = await self.client.get(
                f"{self.BASE_URL}/{asset}/market-data/whale-transactions",
                params={
                    "min_value": min_value_usd,
                    "limit": limit
                }
            )
            response.raise_for_status()
            data = response.json()

            results = []
            for tx in data.get("result", {}).get("data", []):
                try:
                    results.append({
                        "timestamp": self._parse_datetime(tx.get("date")),
                        "value_usd": Decimal(str(tx.get("value_usd", 0))),
                        "from_type": tx.get("from_type", "unknown"),
                        "to_type": tx.get("to_type", "unknown")
                    })
                except (ValueError, TypeError) as e:
                    logger.warning(f"Skipping malformed whale transaction: {e}")
                    continue

            return results

        except httpx.HTTPStatusError as e:
            logger.error(f"CryptoQuant whale transactions HTTP error: {e}")
            return []
        except Exception as e:
            logger.error(f"CryptoQuant whale transactions error: {e}")
            return []

    async def get_funding_rates(
        self,
        asset: str,
        exchange: str = "all",
        limit: int = 24
    ) -> List[Dict[str, Any]]:
        """
        Get perpetual futures funding rates.

        Args:
            asset: "btc" or "eth"
            exchange: "binance", "bybit", "all"
            limit: Number of funding rate snapshots

        Returns:
            List of funding rate data with:
            - timestamp: datetime
            - exchange: str
            - funding_rate: Decimal
            - open_interest: Decimal
        """
        try:
            response = await self.client.get(
                f"{self.BASE_URL}/{asset}/market-data/funding-rates",
                params={
                    "exchange": exchange,
                    "limit": limit
                }
            )
            response.raise_for_status()
            data = response.json()

            results = []
            for d in data.get("result", {}).get("data", []):
                try:
                    results.append({
                        "timestamp": self._parse_datetime(d.get("date")),
                        "exchange": d.get("exchange", "aggregate"),
                        "funding_rate": Decimal(str(d.get("funding_rate", 0))),
                        "open_interest": Decimal(str(d.get("open_interest", 0)))
                    })
                except (ValueError, TypeError) as e:
                    logger.warning(f"Skipping malformed funding rate: {e}")
                    continue

            return results

        except httpx.HTTPStatusError as e:
            logger.error(f"CryptoQuant funding rates HTTP error: {e}")
            return []
        except Exception as e:
            logger.error(f"CryptoQuant funding rates error: {e}")
            return []

    async def get_stablecoin_reserves(
        self,
        limit: int = 7
    ) -> List[Dict[str, Any]]:
        """
        Get stablecoin reserves on exchanges.

        Returns:
            List of stablecoin reserve data with:
            - timestamp: datetime
            - usdt_reserve: Decimal
            - usdc_reserve: Decimal
            - total_reserve: Decimal
        """
        try:
            response = await self.client.get(
                f"{self.BASE_URL}/stablecoin/exchange-reserve",
                params={"limit": limit}
            )
            response.raise_for_status()
            data = response.json()

            results = []
            for d in data.get("result", {}).get("data", []):
                try:
                    results.append({
                        "timestamp": self._parse_datetime(d.get("date")),
                        "usdt_reserve": Decimal(str(d.get("usdt", 0))),
                        "usdc_reserve": Decimal(str(d.get("usdc", 0))),
                        "total_reserve": Decimal(str(d.get("total", 0)))
                    })
                except (ValueError, TypeError) as e:
                    logger.warning(f"Skipping malformed stablecoin reserve: {e}")
                    continue

            return results

        except httpx.HTTPStatusError as e:
            logger.error(f"CryptoQuant stablecoin reserves HTTP error: {e}")
            return []
        except Exception as e:
            logger.error(f"CryptoQuant stablecoin reserves error: {e}")
            return []

    def _parse_datetime(self, date_str: Optional[str]) -> datetime:
        """
        Parse a datetime string from the API.

        Args:
            date_str: ISO format datetime string

        Returns:
            Parsed datetime object
        """
        if not date_str:
            return datetime.now(timezone.utc).replace(tzinfo=None)

        try:
            # Try ISO format first
            return datetime.fromisoformat(date_str.replace("Z", "+00:00"))
        except ValueError:
            try:
                # Try parsing as timestamp
                return datetime.fromtimestamp(float(date_str) / 1000, tz=timezone.utc).replace(tzinfo=None)
            except (ValueError, TypeError):
                logger.warning(f"Could not parse datetime: {date_str}")
                return datetime.now(timezone.utc).replace(tzinfo=None)

    async def close(self) -> None:
        """Close the HTTP client."""
        await self.client.aclose()

    async def __aenter__(self) -> "CryptoQuantClient":
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Async context manager exit."""
        await self.close()


# Global client instance (lazy initialization)
_client: Optional[CryptoQuantClient] = None


def get_cryptoquant_client() -> CryptoQuantClient:
    """
    Get or create the global CryptoQuant client instance.

    Returns:
        CryptoQuantClient instance

    Raises:
        ValueError: If API key is not configured
    """
    global _client
    if _client is None:
        _client = CryptoQuantClient()
    return _client


async def close_cryptoquant_client() -> None:
    """Close the global CryptoQuant client if it exists."""
    global _client
    if _client is not None:
        await _client.close()
        _client = None
